"""
Filesystem and transactional operations module.
Implements sibling staging, atomic replace with rollback, collision handling,
and ownership-based cleanup.
"""

import os
import shutil
import uuid
from pathlib import Path
from typing import Optional, List, Tuple
from enum import Enum


class CollisionMode(Enum):
    CANCEL = "cancel"
    REPLACE = "replace"
    INCREMENTAL = "incremental"


OWNERSHIP_MARKER_FILENAME = ".win64-builder-owned"
TMP_BUILD_PREFIX = ".win64-builder-tmp-"
CACHE_DIR_NAME = ".win64-builder-cache"


class FilesystemBuilder:
    """
    Handles transactional build and atomic placement into destination directory.
    """

    @staticmethod
    def resolve_collision(target_dir: Path, mode: CollisionMode) -> Path:
        """
        Determines the effective target path based on collision resolution mode.
        """
        if not target_dir.exists():
            return target_dir

        if mode == CollisionMode.CANCEL:
            raise FileExistsError(f"Destination directory already exists: {target_dir}")
        elif mode == CollisionMode.REPLACE:
            return target_dir
        elif mode == CollisionMode.INCREMENTAL:
            parent = target_dir.parent
            base_name = target_dir.name
            counter = 2
            while True:
                new_name = f"{base_name} ({counter})"
                new_path = parent / new_name
                if not new_path.exists():
                    return new_path
                counter += 1
        return target_dir

    @staticmethod
    def prepare_staging_directory(destination_dir: Path) -> Tuple[Path, str]:
        """
        Creates a sibling staging directory inside the parent directory of destination.
        Returns tuple of (staging_path, build_uuid).
        """
        parent_dir = destination_dir.parent
        parent_dir.mkdir(parents=True, exist_ok=True)

        build_id = str(uuid.uuid4())[:8]
        staging_name = f"{TMP_BUILD_PREFIX}{destination_dir.name}-{build_id}"
        staging_path = parent_dir / staging_name

        staging_path.mkdir(parents=True, exist_ok=False)

        # Mark ownership
        marker = staging_path / OWNERSHIP_MARKER_FILENAME
        marker.write_text(f"win64-builder staging {build_id}\n")

        return staging_path, build_id

    @staticmethod
    def commit_staging(
        staging_path: Path,
        destination_dir: Path,
        mode: CollisionMode = CollisionMode.CANCEL,
        dry_run: bool = False
    ) -> Path:
        """
        Atomically commits staging directory to final destination.
        Implements rollback if destination exists and mode is REPLACE.
        """
        effective_dest = FilesystemBuilder.resolve_collision(destination_dir, mode)
        parent_dir = effective_dest.parent

        if dry_run:
            return effective_dest

        backup_path: Optional[Path] = None
        build_id = str(uuid.uuid4())[:8]

        try:
            if effective_dest.exists() and mode == CollisionMode.REPLACE:
                backup_name = f".{effective_dest.name}.backup-{build_id}"
                backup_path = parent_dir / backup_name
                # Backup existing destination
                effective_dest.rename(backup_path)

            # Move staging to final destination
            staging_path.rename(effective_dest)

            # Cleanup ownership marker from final destination if desired, or keep it
            marker = effective_dest / OWNERSHIP_MARKER_FILENAME
            if marker.exists():
                try:
                    marker.unlink()
                except OSError:
                    pass

            # Successfully moved; clean up backup if created
            if backup_path and backup_path.exists():
                shutil.rmtree(backup_path, ignore_errors=True)

            return effective_dest

        except Exception as e:
            # Rollback: restore backup if available
            if backup_path and backup_path.exists() and not effective_dest.exists():
                try:
                    backup_path.rename(effective_dest)
                except Exception:
                    pass
            # Cleanup staging if failed
            if staging_path.exists():
                shutil.rmtree(staging_path, ignore_errors=True)
            raise e

    @staticmethod
    def clean_owned_artifacts(root_dir: Path) -> List[Path]:
        """
        Cleans exclusively artifacts created and tagged by win64-builder.
        """
        removed = []

        # Remove local cache dir if present
        cache_dir = root_dir / CACHE_DIR_NAME
        if cache_dir.exists():
            shutil.rmtree(cache_dir, ignore_errors=True)
            removed.append(cache_dir)

        # Search for temporary build directories prefixed with .win64-builder-tmp-
        for item in root_dir.glob(f"**/{TMP_BUILD_PREFIX}*"):
            if item.is_dir():
                marker = item / OWNERSHIP_MARKER_FILENAME
                if marker.exists():
                    shutil.rmtree(item, ignore_errors=True)
                    removed.append(item)

        return removed
