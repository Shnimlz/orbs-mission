"""
Tests for BuildPlan creation, multi-artifact planning, destination resolution,
boundary enforcement, and overlap detection.
"""

from pathlib import Path
import pytest

from src.profiles import Profile, CompanionFileSpec
from src.plan import PlanBuilder, DirectoryArtifact, FileArtifact, EmbeddedFile


@pytest.fixture
def sample_assets(tmp_path: Path) -> Path:
    assets_root = tmp_path / "assets"
    assets_root.mkdir()
    (assets_root / "config").mkdir()
    (assets_root / "config" / "game.ini").write_text("volume=100")
    (assets_root / "metadata").mkdir()
    (assets_root / "metadata" / "manifest.acf").write_text("dummy manifest")
    (assets_root / "metadata" / "extra.acf").write_text("extra manifest")
    return assets_root


def test_build_plan_generation_direct_with_embedded_files(tmp_path: Path, sample_assets: Path):
    profile = Profile(
        name="direct-game",
        display_name="Direct Game",
        folder_name="DirectGame",
        executable_name="DirectGame.exe",
        layout="direct",
        additional_directories=("Saved/Logs",),
        companion_files=(
            CompanionFileSpec(source="config/game.ini", relative_destination="Config/game.ini"),
        )
    )

    output_root = tmp_path / "output"
    plan = PlanBuilder.create_plan(
        profile=profile,
        output_root=output_root,
        source_exe_name="Rouge-Win64-Shipping.exe",
        profile_assets_root=sample_assets,
    )

    assert plan.profile_name == "direct-game"
    assert len(plan.artifacts) == 1
    dir_art = plan.artifacts[0]
    assert isinstance(dir_art, DirectoryArtifact)
    assert dir_art.destination == (output_root / "DirectGame").resolve()
    assert dir_art.subdirectories == ("Saved/Logs",)
    assert dir_art.executable_rename == ("Rouge-Win64-Shipping.exe", "DirectGame.exe")
    assert len(dir_art.embedded_files) == 1
    emb = dir_art.embedded_files[0]
    assert isinstance(emb, EmbeddedFile)
    assert emb.relative_destination == "Config/game.ini"


def test_build_plan_generation_steam_with_independent_file(tmp_path: Path, sample_assets: Path):
    profile = Profile(
        name="steam-game",
        display_name="Steam Game",
        folder_name="SteamGame",
        executable_name="SteamGame.exe",
        layout="steam",
        additional_directories=(),
        companion_files=(
            # Independent companion outside steamapps/common/SteamGame/
            CompanionFileSpec(source="metadata/manifest.acf", relative_destination="steamapps/metadata/manifest.acf"),
            # Embedded companion inside steamapps/common/SteamGame/
            CompanionFileSpec(source="config/game.ini", relative_destination="steamapps/common/SteamGame/game.ini"),
        )
    )

    output_root = tmp_path / "output"
    plan = PlanBuilder.create_plan(
        profile=profile,
        output_root=output_root,
        source_exe_name="Rouge-Win64-Shipping.exe",
        profile_assets_root=sample_assets,
    )

    assert len(plan.artifacts) == 2
    dir_art = [a for a in plan.artifacts if isinstance(a, DirectoryArtifact)][0]
    file_art = [a for a in plan.artifacts if isinstance(a, FileArtifact)][0]

    assert dir_art.destination == (output_root / "steamapps" / "common" / "SteamGame").resolve()
    assert len(dir_art.embedded_files) == 1
    assert dir_art.embedded_files[0].relative_destination == "game.ini"

    assert file_art.destination == (output_root / "steamapps" / "metadata" / "manifest.acf").resolve()


def test_external_destination_denied_by_default(tmp_path: Path, sample_assets: Path):
    profile = Profile(
        name="steam-game",
        display_name="Steam Game",
        folder_name="SteamGame",
        executable_name="SteamGame.exe",
        layout="steam",
    )

    output_root = tmp_path / "output"
    external_lib = tmp_path / "ExternalSteamLibrary"

    # Steam library outside output_root without opt-in
    with pytest.raises(PermissionError, match="External destination denied by default"):
        PlanBuilder.create_plan(
            profile=profile,
            output_root=output_root,
            steam_library=external_lib,
            allow_external_destination=False,
            profile_assets_root=sample_assets,
        )


def test_external_destination_allowed_with_opt_in(tmp_path: Path, sample_assets: Path):
    profile = Profile(
        name="steam-game",
        display_name="Steam Game",
        folder_name="SteamGame",
        executable_name="SteamGame.exe",
        layout="steam",
    )

    output_root = tmp_path / "output"
    external_lib = tmp_path / "ExternalSteamLibrary"

    plan = PlanBuilder.create_plan(
        profile=profile,
        output_root=output_root,
        steam_library=external_lib,
        allow_external_destination=True,
        profile_assets_root=sample_assets,
    )

    assert plan.allow_external_destination is True
    assert plan.artifacts[0].destination == (external_lib / "steamapps" / "common" / "SteamGame").resolve()


def test_overlapping_independent_destinations_rejected(tmp_path: Path, sample_assets: Path):
    # If custom layout creates overlapping independent top-level artifacts
    profile = Profile(
        name="overlap-game",
        display_name="Overlap Game",
        folder_name="OverlapGame",
        executable_name="OverlapGame.exe",
        layout="custom",
        relative_game_path="CustomTree/Game",
        companion_files=(
            # Relative to output_root: CustomTree (which is a parent of CustomTree/Game)
            CompanionFileSpec(source="config/game.ini", relative_destination="CustomTree"),
        )
    )

    output_root = tmp_path / "output"
    with pytest.raises(ValueError, match="Overlapping independent artifact destinations"):
        PlanBuilder.create_plan(
            profile=profile,
            output_root=output_root,
            profile_assets_root=sample_assets,
        )


def test_duplicate_independent_destinations_rejected(tmp_path: Path, sample_assets: Path):
    profile = Profile(
        name="dup-game",
        display_name="Dup Game",
        folder_name="DupGame",
        executable_name="DupGame.exe",
        layout="steam",
        companion_files=(
            CompanionFileSpec(source="metadata/manifest.acf", relative_destination="steamapps/metadata/manifest.acf"),
            CompanionFileSpec(source="metadata/extra.acf", relative_destination="steamapps/metadata/manifest.acf"),
        )
    )

    output_root = tmp_path / "output"
    with pytest.raises(ValueError, match="Duplicate independent artifact destination"):
        PlanBuilder.create_plan(
            profile=profile,
            output_root=output_root,
            profile_assets_root=sample_assets,
        )
