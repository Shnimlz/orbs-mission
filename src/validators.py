"""
Validation module for cross-platform file, folder, executable names, and asset paths.
Enforces the minimum common denominator between Linux and Windows.
"""

import os
import re
from pathlib import PurePath, PurePosixPath, Path

# Reserved Windows device names
RESERVED_NAMES = {
    "CON", "PRN", "AUX", "NUL",
    "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
    "LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9"
}

# Forbidden characters in Windows files/directories
INVALID_CHARS_PATTERN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def validate_name(name: str, item_type: str = "Name") -> None:
    """
    Validates a single file or directory name component against Windows/Linux restrictions.
    Raises ValueError if invalid.
    """
    if not name or not name.strip():
        raise ValueError(f"{item_type} cannot be empty or whitespace only.")

    if INVALID_CHARS_PATTERN.search(name):
        raise ValueError(
            f"{item_type} '{name}' contains invalid characters. "
            f"Avoid characters: < > : \" / \\ | ? *"
        )

    if name.endswith(" ") or name.endswith("."):
        raise ValueError(
            f"{item_type} '{name}' cannot end with a space or dot."
        )

    # Check reserved device stem case-insensitively
    stem = PurePath(name).stem.upper()
    if stem in RESERVED_NAMES:
        raise ValueError(
            f"{item_type} '{name}' uses a reserved Windows device name stem ({stem})."
        )


def validate_executable_name(exe_name: str) -> str:
    """
    Validates executable name. If it lacks .exe extension, returns adjusted name.
    Raises ValueError if invalid.
    """
    validate_name(exe_name, item_type="Executable name")

    if not exe_name.lower().endswith(".exe"):
        exe_name = f"{exe_name}.exe"
        # Re-validate adjusted name
        validate_name(exe_name, item_type="Executable name")

    return exe_name


def validate_relative_path(path_str: str, item_type: str = "Relative path") -> Path:
    """
    Validates that a relative path does not escape parent directory via '..' traversal,
    is not absolute, and does not contain UNC or drive-qualified roots.
    """
    if not path_str or not path_str.strip():
        raise ValueError(f"{item_type} cannot be empty.")

    norm = path_str.replace("\\", "/")
    if norm.startswith("/") or ":" in path_str or norm.startswith("//"):
        raise ValueError(f"{item_type} must be relative, got absolute/qualified: '{path_str}'")

    p = Path(path_str)
    if p.is_absolute():
        raise ValueError(f"{item_type} must be relative, got absolute: '{path_str}'")

    parts = PurePosixPath(norm).parts
    if ".." in parts:
        raise ValueError(f"Path traversal ('..') is strictly prohibited in '{path_str}'")

    for part in parts:
        validate_name(part, item_type=f"{item_type} component")

    return Path(norm)


def validate_asset_source_path(source_str: str, profile_assets_root: Path) -> Path:
    """
    Validates that an asset source path is relative, does not escape profile_assets_root via '..',
    resolves inside profile_assets_root (including symlink resolution checks), and exists.
    """
    if not source_str or not source_str.strip():
        raise ValueError("Asset source path cannot be empty.")

    norm = source_str.replace("\\", "/")
    if norm.startswith("/") or ":" in source_str or norm.startswith("//"):
        raise ValueError(f"Asset source path must be relative: '{source_str}'")

    parts = PurePosixPath(norm).parts
    if ".." in parts:
        raise ValueError(f"Path traversal ('..') is strictly prohibited in asset source '{source_str}'")

    root_resolved = profile_assets_root.resolve()
    target_path = (root_resolved / norm).resolve()

    try:
        target_path.relative_to(root_resolved)
    except ValueError:
        raise ValueError(
            f"Asset source '{source_str}' escapes profile assets root '{root_resolved}'"
        )

    if not target_path.is_file():
        raise FileNotFoundError(
            f"Companion asset source not found: '{source_str}' (resolved to '{target_path}')"
        )

    return target_path
