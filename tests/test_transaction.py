"""
Tests for TransactionJournal, reverse-order rollback, backup preservation, and partial failure restoration.
"""

from pathlib import Path
import pytest
import shutil

from src.plan import BuildPlan, DirectoryArtifact, FileArtifact, EmbeddedFile
from src.transaction import (
    TransactionJournal,
    TransactionEntry,
    TransactionState,
    CollisionMode,
    OWNERSHIP_MARKER_FILENAME,
    TMP_BUILD_PREFIX,
)
from src.template import TemplateManager


def _find_test_template() -> Path:
    candidates = [Path("Win64.rar"), Path("templates/Win64.rar")]
    for c in candidates:
        if c.is_file():
            return c
    pytest.skip("Win64.rar not found")


def test_multi_artifact_stage_and_commit_success(tmp_path: Path):
    rar_file = _find_test_template()
    output_root = tmp_path / "output"
    game_dir = output_root / "steamapps" / "common" / "TestGame"
    meta_file = output_root / "steamapps" / "metadata" / "test.conf"

    companion_src = tmp_path / "src_test.conf"
    companion_src.write_text("config_key=123")

    embedded_src = tmp_path / "emb.ini"
    embedded_src.write_text("[Embedded]\nval=true")

    dir_art = DirectoryArtifact(
        destination=game_dir,
        source_template=rar_file,
        executable_rename=("Rouge-Win64-Shipping.exe", "TestGame.exe"),
        subdirectories=("Saved/Config",),
        embedded_files=(
            EmbeddedFile(source_path=embedded_src, relative_destination="Config/emb.ini"),
        )
    )

    file_art = FileArtifact(
        destination=meta_file,
        source_path=companion_src
    )

    plan = BuildPlan(
        profile_name="test-game",
        output_root=output_root,
        artifacts=(dir_art, file_art)
    )

    journal = TransactionJournal(output_root=output_root, collision_mode=CollisionMode.CANCEL)
    journal.populate_from_plan(plan)

    # 1. Stage
    journal.stage_all()
    assert len(journal.entries) == 2
    assert journal.entries[0].state == TransactionState.STAGED
    assert journal.entries[1].state == TransactionState.STAGED

    # Verify physical staging of embedded file inside directory staging
    staging_dir = journal.entries[0].staging_path
    assert (staging_dir / "Config" / "emb.ini").read_text() == "[Embedded]\nval=true"
    assert (staging_dir / "TestGame.exe").exists()
    assert (staging_dir / "Saved" / "Config").is_dir()

    # 2. Commit
    journal.commit_all()
    assert journal.entries[0].state == TransactionState.COMMITTED
    assert journal.entries[1].state == TransactionState.COMMITTED
    assert game_dir.exists()
    assert meta_file.exists()
    assert (game_dir / "TestGame.exe").exists()
    assert (game_dir / "Config" / "emb.ini").exists()
    assert meta_file.read_text() == "config_key=123"

    # 3. Finalize
    journal.finalize_all()
    assert journal.entries[0].state == TransactionState.FINALIZED
    assert journal.entries[1].state == TransactionState.FINALIZED


def test_multi_artifact_rollback_reverse_order_on_failure(tmp_path: Path):
    output_root = tmp_path / "output"
    dest1 = output_root / "Dir1"
    dest2 = output_root / "Dir2"
    dest3 = output_root / "Dir3"

    src_file = tmp_path / "file.txt"
    src_file.write_text("payload")

    art1 = FileArtifact(destination=dest1 / "f1.txt", source_path=src_file)
    art2 = FileArtifact(destination=dest2 / "f2.txt", source_path=src_file)
    art3 = FileArtifact(destination=dest3 / "f3.txt", source_path=src_file)

    plan = BuildPlan(
        profile_name="multi-rollback",
        output_root=output_root,
        artifacts=(art1, art2, art3)
    )

    journal = TransactionJournal(output_root=output_root, collision_mode=CollisionMode.CANCEL)
    journal.populate_from_plan(plan)

    journal.stage_all()

    # Simulate error on committing art3 by deleting its staging path
    journal.entries[2].staging_path.unlink()

    with pytest.raises(Exception):
        journal.commit_all()

    # Rollback must have reverted entry 0 and entry 1
    assert not (dest1 / "f1.txt").exists()
    assert not (dest2 / "f2.txt").exists()
    assert not (dest3 / "f3.txt").exists()
    assert journal.entries[0].state == TransactionState.ROLLED_BACK
    assert journal.entries[1].state == TransactionState.ROLLED_BACK
    assert journal.entries[2].state == TransactionState.ROLLED_BACK


def test_replaced_committed_artifact_restores_exact_previous_contents(tmp_path: Path):
    output_root = tmp_path / "output"
    dest1 = output_root / "TargetDir"
    dest1.mkdir(parents=True)
    (dest1 / "original.txt").write_text("original content")

    dest2 = output_root / "SecondFile.txt"

    src_new = tmp_path / "new_src"
    src_new.mkdir()
    (src_new / "new.txt").write_text("new content")

    src_file = tmp_path / "f.txt"
    src_file.write_text("second file")

    art1 = DirectoryArtifact(destination=dest1, source_template=None)
    art2 = FileArtifact(destination=dest2, source_path=src_file)

    plan = BuildPlan(profile_name="replace-rollback", output_root=output_root, artifacts=(art1, art2))

    journal = TransactionJournal(output_root=output_root, collision_mode=CollisionMode.REPLACE)
    journal.populate_from_plan(plan)

    # Manually populate staging for art1
    dest_parent = dest1.parent
    staging1 = dest_parent / f"{TMP_BUILD_PREFIX}TargetDir-test"
    staging1.mkdir()
    (staging1 / "new_placed.txt").write_text("replacement data")
    journal.entries[0].staging_path = staging1
    journal.entries[0].state = TransactionState.STAGED

    # Staging for art2
    staging2 = dest_parent / f"{TMP_BUILD_PREFIX}SecondFile-test"
    staging2.write_text("second data")
    journal.entries[1].staging_path = staging2
    journal.entries[1].state = TransactionState.STAGED

    # Delete staging2 so commit of art2 fails
    staging2.unlink()

    with pytest.raises(Exception):
        journal.commit_all()

    # Verify art1 replacement was fully rolled back and original contents restored
    assert dest1.exists()
    assert (dest1 / "original.txt").exists()
    assert (dest1 / "original.txt").read_text() == "original content"
    assert not (dest1 / "new_placed.txt").exists()
    assert journal.entries[0].state == TransactionState.ROLLED_BACK


def test_failure_preserves_lifecycle_state_and_error(tmp_path: Path):
    output_root = tmp_path / "output"
    dest = output_root / "ConflictDir"
    dest.mkdir(parents=True)
    (dest / "existing.txt").write_text("existing data")

    art = DirectoryArtifact(destination=dest)
    plan = BuildPlan(profile_name="fail-state", output_root=output_root, artifacts=(art,))

    journal = TransactionJournal(output_root=output_root, collision_mode=CollisionMode.CANCEL)
    journal.populate_from_plan(plan)

    staging = output_root / f"{TMP_BUILD_PREFIX}ConflictDir-st"
    staging.mkdir()
    journal.entries[0].staging_path = staging
    journal.entries[0].state = TransactionState.STAGED

    # Collision CANCEL will fail at commit
    with pytest.raises(FileExistsError):
        journal.commit_all()

    # Entry recorded error and rolled back
    assert journal.entries[0].error is not None
    assert isinstance(journal.entries[0].error, FileExistsError)
    assert journal.entries[0].state == TransactionState.ROLLED_BACK
    assert (dest / "existing.txt").read_text() == "existing data"


def test_failure_during_backed_up_restores_backup(tmp_path: Path):
    output_root = tmp_path / "output"
    dest = output_root / "MutateDir"
    dest.mkdir(parents=True)
    (dest / "prior.txt").write_text("prior data")

    art = DirectoryArtifact(destination=dest)
    plan = BuildPlan(profile_name="backed-up-fail", output_root=output_root, artifacts=(art,))

    journal = TransactionJournal(output_root=output_root, collision_mode=CollisionMode.REPLACE)
    journal.populate_from_plan(plan)

    staging = output_root / f"{TMP_BUILD_PREFIX}MutateDir-st"
    staging.mkdir()
    journal.entries[0].staging_path = staging
    journal.entries[0].state = TransactionState.STAGED

    # Simulate failure right after backup is made:
    backup_path = output_root / f".MutateDir.backup-test"
    dest.rename(backup_path)
    journal.entries[0].backup_path = backup_path
    journal.entries[0].state = TransactionState.BACKED_UP

    # Trigger rollback
    journal.rollback_all(failed_index=0)

    assert dest.exists()
    assert (dest / "prior.txt").read_text() == "prior data"
    assert not backup_path.exists()
    assert journal.entries[0].state == TransactionState.ROLLED_BACK


def test_backup_lifetime_preserved_throughout_commit_all(tmp_path: Path):
    output_root = tmp_path / "output"
    dest1 = output_root / "Dir1"
    dest1.mkdir(parents=True)
    (dest1 / "old1.txt").write_text("old1")

    dest2 = output_root / "Dir2"
    dest2.mkdir(parents=True)
    (dest2 / "old2.txt").write_text("old2")

    art1 = DirectoryArtifact(destination=dest1)
    art2 = DirectoryArtifact(destination=dest2)
    plan = BuildPlan(profile_name="backup-lifetime", output_root=output_root, artifacts=(art1, art2))

    journal = TransactionJournal(output_root=output_root, collision_mode=CollisionMode.REPLACE)
    journal.populate_from_plan(plan)

    # Setup staging
    s1 = output_root / f"{TMP_BUILD_PREFIX}Dir1-s1"
    s1.mkdir()
    (s1 / "new1.txt").write_text("new1")
    journal.entries[0].staging_path = s1
    journal.entries[0].state = TransactionState.STAGED

    s2 = output_root / f"{TMP_BUILD_PREFIX}Dir2-s2"
    s2.mkdir()
    (s2 / "new2.txt").write_text("new2")
    journal.entries[1].staging_path = s2
    journal.entries[1].state = TransactionState.STAGED

    # Commit all
    journal.commit_all()

    # Backups MUST exist during COMMIT ALL (before finalize)
    assert journal.entries[0].backup_path is not None
    assert journal.entries[0].backup_path.exists()
    assert journal.entries[1].backup_path is not None
    assert journal.entries[1].backup_path.exists()

    # Finalize
    journal.finalize_all()

    # Now backups are purged
    assert not journal.entries[0].backup_path.exists()
    assert not journal.entries[1].backup_path.exists()
    assert (dest1 / "new1.txt").read_text() == "new1"
    assert (dest2 / "new2.txt").read_text() == "new2"


def test_zero_partial_output_remaining_after_multi_destination_failure(tmp_path: Path):
    output_root = tmp_path / "output"
    dest1 = output_root / "SubdirA" / "GameDir"
    dest2 = output_root / "SubdirB" / "Config.json"
    dest3 = output_root / "SubdirC" / "Failing.txt"

    file_src = tmp_path / "source.txt"
    file_src.write_text("hello")

    art1 = DirectoryArtifact(destination=dest1)
    art2 = FileArtifact(destination=dest2, source_path=file_src)
    art3 = FileArtifact(destination=dest3, source_path=file_src)

    plan = BuildPlan(profile_name="zero-partial", output_root=output_root, artifacts=(art1, art2, art3))

    journal = TransactionJournal(output_root=output_root, collision_mode=CollisionMode.CANCEL)
    journal.populate_from_plan(plan)

    # Setup staging
    dest1.parent.mkdir(parents=True, exist_ok=True)
    dest2.parent.mkdir(parents=True, exist_ok=True)
    dest3.parent.mkdir(parents=True, exist_ok=True)

    s1 = dest1.parent / f"{TMP_BUILD_PREFIX}GameDir-s1"
    s1.mkdir()
    (s1 / "game.exe").write_text("binary")
    journal.entries[0].staging_path = s1
    journal.entries[0].state = TransactionState.STAGED

    s2 = dest2.parent / f"{TMP_BUILD_PREFIX}Config-s2"
    s2.write_text("{}")
    journal.entries[1].staging_path = s2
    journal.entries[1].state = TransactionState.STAGED

    # Entry 3 has no staging path -> causes commit failure at index 2
    journal.entries[2].staging_path = None
    journal.entries[2].state = TransactionState.PENDING

    with pytest.raises(Exception):
        journal.commit_all()

    # Zero partial output at destinations
    assert not dest1.exists()
    assert not dest2.exists()
    assert not dest3.exists()

    # Zero staging files left behind
    assert not s1.exists()
    assert not s2.exists()
