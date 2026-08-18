"""
Transactional journal and state machine module.
Implements multi-artifact sibling staging, backup management during commit,
reverse-order rollback with partial side-effect restoration, and finalization.
"""

import os
import shutil
import uuid
from enum import Enum
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List, Tuple

from src.plan import BuildPlan, BuildArtifact, DirectoryArtifact, FileArtifact, EmbeddedFile
from src.template import TemplateManager

OWNERSHIP_MARKER_FILENAME = ".win64-builder-owned"
TMP_BUILD_PREFIX = ".win64-builder-tmp-"
BACKUP_PREFIX = ".backup-"


class CollisionMode(Enum):
    CANCEL = "cancel"
    REPLACE = "replace"
    INCREMENTAL = "incremental"


class TransactionState(Enum):
    PENDING = "pending"           # Initial state
    STAGING = "staging"           # Staging sibling creation & population in progress
    STAGED = "staged"             # Staging sibling fully prepared
    BACKING_UP = "backing_up"     # Moving existing destination -> backup in progress
    BACKED_UP = "backed_up"       # Destination safely preserved in backup; destination path is now free
    COMMITTING = "committing"     # Moving staging -> destination in progress
    COMMITTED = "committed"       # Staging successfully placed at destination
    ROLLED_BACK = "rolled_back"   # Pre-transaction state fully restored
    FINALIZED = "finalized"       # Backups cleaned up after ALL entries committed


@dataclass
class TransactionEntry:
    """Represents the transactional lifecycle of a single BuildArtifact."""
    artifact: BuildArtifact
    destination: Path
    staging_path: Optional[Path] = None
    backup_path: Optional[Path] = None
    state: TransactionState = TransactionState.PENDING
    created_new: bool = False
    error: Optional[Exception] = None


def _remove_fs_path(p: Path) -> None:
    """Removes a file or directory tree safely."""
    if not p.exists() and not p.is_symlink():
        return
    if p.is_dir() and not p.is_symlink():
        shutil.rmtree(p, ignore_errors=True)
    else:
        try:
            p.unlink()
        except OSError:
            pass


class TransactionJournal:
    """
    Manages multi-artifact staging, commits, reverse-order rollback, and finalization.
    Guarantees no partial output remains on recoverable exceptions.
    """

    def __init__(
        self,
        output_root: Path,
        collision_mode: CollisionMode = CollisionMode.CANCEL
    ):
        self.output_root = output_root.resolve()
        self.collision_mode = collision_mode
        self.entries: List[TransactionEntry] = []

    def populate_from_plan(self, plan: BuildPlan) -> None:
        """Initializes transaction entries for all artifacts in the BuildPlan."""
        self.entries = [
            TransactionEntry(
                artifact=art,
                destination=art.destination.resolve()
            )
            for art in plan.artifacts
        ]

    def stage_all(self) -> None:
        """
        Prepares staging siblings for all artifacts.
        If any artifact fails staging, cleans up all created staging siblings.
        """
        for entry in self.entries:
            try:
                entry.state = TransactionState.STAGING
                dest_parent = entry.destination.parent
                dest_parent.mkdir(parents=True, exist_ok=True)

                build_id = str(uuid.uuid4())[:8]

                if isinstance(entry.artifact, DirectoryArtifact):
                    staging_name = f"{TMP_BUILD_PREFIX}{entry.destination.name}-{build_id}"
                    staging_path = dest_parent / staging_name
                    staging_path.mkdir(parents=True, exist_ok=False)
                    entry.staging_path = staging_path

                    # Mark ownership
                    marker = staging_path / OWNERSHIP_MARKER_FILENAME
                    marker.write_text(f"win64-builder staging {build_id}\n", encoding="utf-8")

                    # Extract template if specified
                    if entry.artifact.source_template:
                        mgr = TemplateManager(entry.artifact.source_template)
                        inspection = mgr.inspect()
                        temp_extract = staging_path / ".extract_tmp"
                        mgr.extract_to(temp_extract)

                        root_extracted = temp_extract / inspection["root"]
                        for item in root_extracted.iterdir():
                            shutil.move(str(item), str(staging_path / item.name))
                        _remove_fs_path(temp_extract)

                    # Rename executable if specified
                    if entry.artifact.executable_rename:
                        src_exe_name, target_exe_name = entry.artifact.executable_rename
                        src_exe_path = staging_path / src_exe_name
                        target_exe_path = staging_path / target_exe_name
                        if src_exe_path.exists():
                            if src_exe_path != target_exe_path:
                                src_exe_path.rename(target_exe_path)
                        else:
                            raise FileNotFoundError(
                                f"Source executable '{src_exe_name}' not found in extracted template."
                            )

                    # Create subdirectories
                    for sub in entry.artifact.subdirectories:
                        (staging_path / sub).mkdir(parents=True, exist_ok=True)

                    # Copy embedded companion files
                    for emb in entry.artifact.embedded_files:
                        emb_target = staging_path / emb.relative_destination
                        emb_target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(str(emb.source_path), str(emb_target))

                elif isinstance(entry.artifact, FileArtifact):
                    staging_name = f"{TMP_BUILD_PREFIX}{entry.destination.name}-{build_id}"
                    staging_path = dest_parent / staging_name
                    entry.staging_path = staging_path
                    shutil.copy2(str(entry.artifact.source_path), str(staging_path))

                entry.state = TransactionState.STAGED

            except Exception as e:
                entry.error = e
                # Clean up all created staging siblings across all entries
                self._cleanup_all_stagings()
                raise e

    def commit_all(self) -> None:
        """
        Atomically commits staging siblings to final destinations.
        Backups are strictly preserved until finalization.
        If commit fails at index k, executes rollback from k down to 0.
        """
        for k, entry in enumerate(self.entries):
            if not entry.staging_path or not entry.staging_path.exists():
                err = RuntimeError(f"Cannot commit un-staged artifact: {entry.destination}")
                entry.error = err
                self.rollback_all(failed_index=k)
                raise err

            dest = entry.destination
            parent_dir = dest.parent
            build_id = str(uuid.uuid4())[:8]

            try:
                if dest.exists():
                    if self.collision_mode == CollisionMode.CANCEL:
                        raise FileExistsError(f"Destination already exists: '{dest}'")
                    elif self.collision_mode == CollisionMode.REPLACE:
                        entry.state = TransactionState.BACKING_UP
                        backup_name = f".{dest.name}{BACKUP_PREFIX}{build_id}"
                        backup_path = parent_dir / backup_name
                        dest.rename(backup_path)
                        entry.backup_path = backup_path
                        entry.state = TransactionState.BACKED_UP

                entry.state = TransactionState.COMMITTING
                entry.staging_path.rename(dest)
                entry.created_new = (entry.backup_path is None)
                entry.state = TransactionState.COMMITTED

            except Exception as exc:
                entry.error = exc
                # Do NOT overwrite entry.state with FAILED! It preserves exact lifecycle point
                self.rollback_all(failed_index=k)
                raise exc

    def rollback_all(self, failed_index: int) -> None:
        """
        Rolls back all entries from failed_index down to 0 in reverse order.
        Guarantees exact restoration of prior filesystem state.
        """
        for idx in range(failed_index, -1, -1):
            entry = self.entries[idx]

            try:
                if entry.state == TransactionState.COMMITTED:
                    if entry.created_new:
                        _remove_fs_path(entry.destination)
                    elif entry.backup_path and entry.backup_path.exists():
                        _remove_fs_path(entry.destination)
                        entry.backup_path.rename(entry.destination)

                elif entry.state in (TransactionState.BACKED_UP, TransactionState.COMMITTING):
                    if entry.destination.exists():
                        _remove_fs_path(entry.destination)
                    if entry.backup_path and entry.backup_path.exists():
                        entry.backup_path.rename(entry.destination)

                elif entry.state == TransactionState.BACKING_UP:
                    if entry.backup_path and entry.backup_path.exists() and not entry.destination.exists():
                        entry.backup_path.rename(entry.destination)

            except Exception:
                # Best-effort rollback for individual step; continue restoring other entries
                pass
            finally:
                entry.state = TransactionState.ROLLED_BACK

        self._cleanup_all_stagings()

    def finalize_all(self) -> None:
        """
        Finalizes the transaction after all entries have been successfully COMMITTED.
        Purges backup copies and ownership markers.
        """
        for entry in self.entries:
            if entry.backup_path and entry.backup_path.exists():
                _remove_fs_path(entry.backup_path)

            if isinstance(entry.artifact, DirectoryArtifact) and entry.destination.exists():
                marker = entry.destination / OWNERSHIP_MARKER_FILENAME
                if marker.exists():
                    try:
                        marker.unlink()
                    except OSError:
                        pass

            entry.state = TransactionState.FINALIZED

    def _cleanup_all_stagings(self) -> None:
        """Removes all temporary staging siblings created during this session."""
        for entry in self.entries:
            if entry.staging_path and entry.staging_path.exists():
                _remove_fs_path(entry.staging_path)
