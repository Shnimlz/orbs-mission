"""
Validation module for cross-platform file, folder, and executable names.
Enforces the minimum common denominator between Linux and Windows.
"""

import re
from pathlib import PurePath, Path

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
    Validates a file or directory name component against Windows/Linux restrictions.
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
    Validates executable name. If it lacks .exe extension, returns adjusted name if approved or requested.
    Raises ValueError if invalid.
    """
    validate_name(exe_name, item_type="Executable name")

    if not exe_name.lower().endswith(".exe"):
        exe_name = f"{exe_name}.exe"
        # Re-validate adjusted name
        validate_name(exe_name, item_type="Executable name")

    return exe_name


def validate_relative_path(path_str: str) -> Path:
    """
    Validates that a relative path does not escape parent directory via '..' traversal.
    """
    if not path_str or not path_str.strip():
        raise ValueError("Path cannot be empty.")

    p = Path(path_str)
    if p.is_absolute():
        raise ValueError(f"Custom layout path must be relative, got absolute: '{path_str}'")

    parts = p.parts
    if ".." in parts:
        raise ValueError(f"Path traversal ('..') is strictly prohibited in '{path_str}'")

    return p
