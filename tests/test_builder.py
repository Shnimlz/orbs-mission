"""
Integration and transactional tests for FilesystemBuilder and build process.
"""

from pathlib import Path
import pytest

from src.filesystem import FilesystemBuilder, CollisionMode, OWNERSHIP_MARKER_FILENAME, TMP_BUILD_PREFIX
from src.template import TemplateManager


def test_sibling_staging_directory(tmp_path: Path):
    dest_dir = tmp_path / "output" / "My Game"
    staging_path, build_id = FilesystemBuilder.prepare_staging_directory(dest_dir)

    assert staging_path.parent == dest_dir.parent
    assert staging_path.name.startswith(TMP_BUILD_PREFIX)
    assert (staging_path / OWNERSHIP_MARKER_FILENAME).exists()


def test_commit_staging_new_destination(tmp_path: Path):
    dest_dir = tmp_path / "output" / "My Game"
    staging_path, _ = FilesystemBuilder.prepare_staging_directory(dest_dir)

    # Add dummy payload file inside staging
    (staging_path / "test.txt").write_text("hello")

    final_dest = FilesystemBuilder.commit_staging(staging_path, dest_dir, mode=CollisionMode.CANCEL)

    assert final_dest.exists()
    assert (final_dest / "test.txt").read_text() == "hello"
    assert not staging_path.exists()


def test_commit_staging_replace_with_rollback(tmp_path: Path):
    dest_dir = tmp_path / "output" / "My Game"
    dest_dir.mkdir(parents=True)
    (dest_dir / "old.txt").write_text("old version")

    staging_path, _ = FilesystemBuilder.prepare_staging_directory(dest_dir)
    (staging_path / "new.txt").write_text("new version")

    final_dest = FilesystemBuilder.commit_staging(staging_path, dest_dir, mode=CollisionMode.REPLACE)

    assert final_dest.exists()
    assert (final_dest / "new.txt").read_text() == "new version"
    assert not (final_dest / "old.txt").exists()


def test_collision_incremental(tmp_path: Path):
    dest_dir = tmp_path / "output" / "My Game"
    dest_dir.mkdir(parents=True)

    res2 = FilesystemBuilder.resolve_collision(dest_dir, CollisionMode.INCREMENTAL)
    assert res2.name == "My Game (2)"

    res2.mkdir()
    res3 = FilesystemBuilder.resolve_collision(dest_dir, CollisionMode.INCREMENTAL)
    assert res3.name == "My Game (3)"


def test_clean_owned_artifacts(tmp_path: Path):
    dest_dir = tmp_path / "output" / "My Game"
    staging_path, _ = FilesystemBuilder.prepare_staging_directory(dest_dir)

    # Create dummy unowned directory
    unowned = tmp_path / "output" / ".win64-builder-tmp-unowned"
    unowned.mkdir()

    removed = FilesystemBuilder.clean_owned_artifacts(tmp_path)

    assert staging_path in removed
    assert not staging_path.exists()
    # Unowned directory without ownership marker should NOT be deleted
    assert unowned.exists()


def test_full_build_execution(tmp_path: Path):
    rar_file = Path("Win64.rar")
    if not rar_file.is_file():
        pytest.skip("Win64.rar not found in current directory")

    mgr = TemplateManager(rar_file)
    inspection = mgr.inspect()

    output_dir = tmp_path / "output"
    target_dest = output_dir / "Shift At Midnight Demo"

    staging_dir, _ = FilesystemBuilder.prepare_staging_directory(target_dest)

    # Extract template into staging
    temp_extract = staging_dir / ".extract_tmp"
    mgr.extract_to(temp_extract)

    root_extracted = temp_extract / inspection["root"]
    import shutil
    for item in root_extracted.iterdir():
        shutil.move(str(item), str(staging_dir / item.name))

    shutil.rmtree(temp_extract)

    # Rename executable
    source_exe = staging_dir / "Rouge-Win64-Shipping.exe"
    target_exe = staging_dir / "Shift At Midnight.exe"

    assert source_exe.exists()
    source_exe.rename(target_exe)

    final_dest = FilesystemBuilder.commit_staging(staging_dir, target_dest)

    assert final_dest.exists()
    assert (final_dest / "Shift At Midnight.exe").exists()
    assert (final_dest / "WordpadFilter.dll").exists()
    assert (final_dest / "es-MX" / "wordpad.exe.mui").exists()
    assert (final_dest / "en-US").is_dir()


def test_discover_existing_folders(tmp_path: Path):
    output_dir = tmp_path / "output"
    output_dir.mkdir()

    # Create direct folder
    direct_game = output_dir / "DirectGame"
    direct_game.mkdir()
    (direct_game / "DirectGame.exe").write_text("dummy")

    # Create steam folder
    steam_game = output_dir / "steamapps" / "common" / "SteamGame"
    steam_game.mkdir(parents=True)
    (steam_game / "SteamGame.exe").write_text("dummy")

    # Discovered folders
    folders = FilesystemBuilder.discover_existing_folders(output_dir)
    assert len(folders) == 2

    names = {f.name: f for f in folders}
    assert "DirectGame" in names
    assert names["DirectGame"].layout == "direct"
    assert "DirectGame.exe" in names["DirectGame"].executables

    assert "SteamGame" in names
    assert names["SteamGame"].layout == "steam"
    assert "SteamGame.exe" in names["SteamGame"].executables


def test_rename_executable_in_folder(tmp_path: Path):
    game_dir = tmp_path / "ExistingGame"
    game_dir.mkdir()

    # 1. Rename when candidate exe is present
    source_exe = game_dir / "Rouge-Win64-Shipping.exe"
    source_exe.write_text("bin")

    success, final_path, msg = FilesystemBuilder.rename_executable_in_folder(
        game_dir,
        target_exe_name="NewGame.exe",
        source_exe_name="Rouge-Win64-Shipping.exe"
    )
    assert success is True
    assert final_path.name == "NewGame.exe"
    assert final_path.exists()
    assert not source_exe.exists()

    # 2. Idempotent call when target exe already exists
    success2, final_path2, msg2 = FilesystemBuilder.rename_executable_in_folder(
        game_dir,
        target_exe_name="NewGame.exe"
    )
    assert success2 is True
    assert "ya está presente" in msg2

    # 3. Rename without source_exe hint (detects root exe)
    success3, final_path3, msg3 = FilesystemBuilder.rename_executable_in_folder(
        game_dir,
        target_exe_name="ThirdName.exe"
    )
    assert success3 is True
    assert final_path3.name == "ThirdName.exe"
    assert final_path3.exists()

    # 4. Folder without any executables
    empty_dir = tmp_path / "EmptyGame"
    empty_dir.mkdir()
    success4, final_path4, msg4 = FilesystemBuilder.rename_executable_in_folder(
        empty_dir,
        target_exe_name="Never.exe"
    )
    assert success4 is False
    assert "No se encontró ningún archivo" in msg4

