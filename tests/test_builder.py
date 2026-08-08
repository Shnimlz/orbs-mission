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
