"""
BuildPlan and BuildArtifact module.
Defines declarative multi-artifact planning, destination resolution, boundary checks,
overlap detection, and embedded vs independent companion classification.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Tuple, List, Union

from src.profiles import Profile, CompanionFileSpec
from src.layouts import DirectLayout, SteamLayout, CustomLayout, BaseLayout
from src.validators import validate_asset_source_path


@dataclass(frozen=True)
class EmbeddedFile:
    """An auxiliary companion resource residing inside a DirectoryArtifact root."""
    source_path: Path           # Validated absolute source path inside profile_assets_root
    relative_destination: str   # Relative path inside the DirectoryArtifact root


@dataclass(frozen=True)
class BaseArtifact:
    """Base dataclass for any transactional build artifact."""
    destination: Path


@dataclass(frozen=True)
class DirectoryArtifact(BaseArtifact):
    """
    Directory tree artifact populated from template archive,
    with executable renaming, subdirectory creation, and embedded companion resources.
    """
    source_template: Optional[Path] = None
    executable_rename: Optional[Tuple[str, str]] = None  # (source_exe, target_exe)
    subdirectories: Tuple[str, ...] = ()
    embedded_files: Tuple[EmbeddedFile, ...] = ()


@dataclass(frozen=True)
class FileArtifact(BaseArtifact):
    """
    Independent top-level file artifact.
    Invariant: exactly one validated source path inside profile_assets_root.
    """
    source_path: Path


BuildArtifact = Union[DirectoryArtifact, FileArtifact]


@dataclass(frozen=True)
class BuildPlan:
    """Declarative plan describing all artifacts to be staged, committed, and verified."""
    profile_name: str
    output_root: Path
    artifacts: Tuple[BuildArtifact, ...]
    allow_external_destination: bool = False


class PlanBuilder:
    """Constructs, resolves, and validates a complete BuildPlan."""

    @staticmethod
    def create_plan(
        profile: Profile,
        output_root: Path,
        template_path: Optional[Path] = None,
        source_exe_name: Optional[str] = None,
        profile_assets_root: Path = Path("profiles/assets"),
        steam_library: Optional[Path] = None,
        allow_external_destination: bool = False
    ) -> BuildPlan:
        """
        Creates and validates a complete BuildPlan from a Profile and build parameters.
        """
        output_root_resolved = output_root.resolve()

        # 1. Resolve Layout
        layout_obj: BaseLayout
        if profile.layout == "direct":
            layout_obj = DirectLayout(profile.folder_name)
        elif profile.layout == "steam":
            layout_obj = SteamLayout(profile.folder_name, steam_library=steam_library)
        elif profile.layout == "custom":
            layout_obj = CustomLayout(profile.relative_game_path)
        else:
            raise ValueError(f"Unknown profile layout '{profile.layout}'")

        # 2. Resolve primary directory destination
        primary_dest = layout_obj.resolve_destination(output_root_resolved)

        # 3. Check primary destination boundary
        try:
            primary_dest.relative_to(output_root_resolved)
        except ValueError:
            if not allow_external_destination:
                raise PermissionError(
                    f"External destination denied by default: '{primary_dest}'. "
                    f"Use --allow-external-destination to enable writing outside '{output_root_resolved}'."
                )

        # 4. Resolve companion files into embedded vs independent
        embedded_files: List[EmbeddedFile] = []
        independent_files: List[FileArtifact] = []

        for spec in profile.companion_files:
            # Validate source file containment inside profile_assets_root
            validated_source = validate_asset_source_path(spec.source, profile_assets_root)

            # Resolve companion destination
            comp_dest = layout_obj.resolve_companion_destination(output_root_resolved, spec.relative_destination)

            # Check companion destination boundary
            try:
                comp_dest.relative_to(output_root_resolved)
            except ValueError:
                if not allow_external_destination:
                    raise PermissionError(
                        f"External destination denied by default: '{comp_dest}'. "
                        f"Use --allow-external-destination to enable writing outside '{output_root_resolved}'."
                    )

            # Classify: is it inside primary_dest or an independent destination?
            try:
                rel_inside = comp_dest.relative_to(primary_dest)
                # Inside primary directory -> EmbeddedFile
                embedded_files.append(
                    EmbeddedFile(
                        source_path=validated_source,
                        relative_destination=str(rel_inside)
                    )
                )
            except ValueError:
                # Outside primary directory -> Independent FileArtifact
                independent_files.append(
                    FileArtifact(
                        destination=comp_dest,
                        source_path=validated_source
                    )
                )

        # 5. Build DirectoryArtifact
        exe_rename = None
        if source_exe_name:
            exe_rename = (source_exe_name, profile.executable_name)

        dir_artifact = DirectoryArtifact(
            destination=primary_dest,
            source_template=template_path.resolve() if template_path else None,
            executable_rename=exe_rename,
            subdirectories=tuple(profile.additional_directories),
            embedded_files=tuple(embedded_files)
        )

        all_artifacts: Tuple[BuildArtifact, ...] = (dir_artifact, *independent_files)

        # 6. Validate independent artifact destinations (uniqueness & no overlap)
        destinations = [a.destination.resolve() for a in all_artifacts]

        # Duplicate check
        if len(destinations) != len(set(destinations)):
            duplicates = [d for d in destinations if destinations.count(d) > 1]
            raise ValueError(f"Duplicate independent artifact destination detected: {duplicates[0]}")

        # Overlapping check (parent-child conflict between top-level independent artifacts)
        for i, dest_a in enumerate(destinations):
            for j, dest_b in enumerate(destinations):
                if i != j:
                    if dest_a in dest_b.parents:
                        raise ValueError(
                            f"Overlapping independent artifact destinations detected: "
                            f"'{dest_b}' is nested inside '{dest_a}'."
                        )

        return BuildPlan(
            profile_name=profile.name,
            output_root=output_root_resolved,
            artifacts=all_artifacts,
            allow_external_destination=allow_external_destination
        )
