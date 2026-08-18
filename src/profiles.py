"""
Profile and Recipe management module.
Defines application profile structures, JSON loading, schema validation, and discovery.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Tuple, Dict, Any

from src.validators import (
    validate_name,
    validate_executable_name,
    validate_relative_path,
)

VALID_LAYOUTS = {"direct", "steam", "custom"}


class SchemaValidationError(ValueError):
    """Raised when profile JSON structure fails schema constraints."""
    pass


@dataclass(frozen=True)
class CompanionFileSpec:
    """Specification of an auxiliary companion resource."""
    source: str                 # Relative path within profile_assets_root
    relative_destination: str   # Relative destination path in target output layout


@dataclass(frozen=True)
class Profile:
    """Immutable application profile defining how a game/app structure is prepared."""
    name: str                                                   # Unique identifier (e.g. "example-game")
    display_name: str                                           # Friendly display name
    folder_name: str                                            # Root game folder name
    executable_name: str                                        # Target executable (.exe)
    layout: str                                                 # "direct" | "steam" | "custom"
    relative_game_path: str = ""                                # Used exclusively when layout="custom"
    platform_hints: Dict[str, str] = field(default_factory=dict)# Platform metadata (wine prefix, etc.)
    additional_directories: Tuple[str, ...] = ()                # Subdirectories to ensure
    companion_files: Tuple[CompanionFileSpec, ...] = ()         # Companion file specifications

    @classmethod
    def from_dict(cls, data: Dict[str, Any], default_name: str = "") -> "Profile":
        """Constructs and validates a Profile from a dictionary."""
        validate_profile_schema(data)

        name = data.get("name", default_name)
        if not name:
            name = default_name

        companion_specs = []
        for cf in data.get("companionFiles", []):
            companion_specs.append(
                CompanionFileSpec(
                    source=cf["source"],
                    relative_destination=cf["relativeDestination"]
                )
            )

        additional_dirs = tuple(data.get("additionalDirectories", []))

        return cls(
            name=name,
            display_name=data.get("displayName", name),
            folder_name=data["folderName"],
            executable_name=validate_executable_name(data["executableName"]),
            layout=data["layout"].lower(),
            relative_game_path=data.get("relativeGamePath", ""),
            platform_hints=dict(data.get("platformHints", {})),
            additional_directories=additional_dirs,
            companion_files=tuple(companion_specs),
        )


def validate_profile_schema(data: Dict[str, Any]) -> None:
    """
    Validates profile JSON schema against strict structural and security rules.
    Raises SchemaValidationError on failure.
    """
    if not isinstance(data, dict):
        raise SchemaValidationError("Profile root must be a JSON object.")

    # Required fields
    required_fields = ["displayName", "folderName", "executableName", "layout"]
    for req in required_fields:
        val = data.get(req)
        if val is None or not isinstance(val, str) or not val.strip():
            raise SchemaValidationError(f"Missing or invalid required field '{req}' in profile.")

    # Validate layout whitelist
    layout = data["layout"].lower()
    if layout not in VALID_LAYOUTS:
        raise SchemaValidationError(
            f"Invalid layout '{data['layout']}'. Must be one of: {sorted(list(VALID_LAYOUTS))}"
        )

    # Validate folder and executable names
    try:
        validate_name(data["folderName"], item_type="Profile folderName")
    except ValueError as e:
        raise SchemaValidationError(str(e))

    try:
        validate_executable_name(data["executableName"])
    except ValueError as e:
        raise SchemaValidationError(str(e))

    # relativeGamePath semantics: legal ONLY for custom layout
    rel_game_path = data.get("relativeGamePath")
    if rel_game_path is not None and str(rel_game_path).strip():
        if layout in ("direct", "steam"):
            raise SchemaValidationError(
                f"Field 'relativeGamePath' is forbidden when layout is '{layout}'. "
                "It is valid exclusively for layout='custom'."
            )
        try:
            validate_relative_path(rel_game_path, item_type="relativeGamePath")
        except ValueError as e:
            raise SchemaValidationError(str(e))
    elif layout == "custom":
        raise SchemaValidationError("Layout 'custom' requires 'relativeGamePath' to be defined.")

    # Validate additionalDirectories
    add_dirs = data.get("additionalDirectories", [])
    if not isinstance(add_dirs, list):
        raise SchemaValidationError("'additionalDirectories' must be a list of relative paths.")
    for d in add_dirs:
        if not isinstance(d, str) or not d.strip():
            raise SchemaValidationError(f"Invalid directory entry in additionalDirectories: {d}")
        try:
            validate_relative_path(d, item_type="additionalDirectories entry")
        except ValueError as e:
            raise SchemaValidationError(str(e))

    # Validate companionFiles
    comp_files = data.get("companionFiles", [])
    if not isinstance(comp_files, list):
        raise SchemaValidationError("'companionFiles' must be a list of objects.")
    for idx, cf in enumerate(comp_files):
        if not isinstance(cf, dict):
            raise SchemaValidationError(f"companionFiles[{idx}] must be a JSON object.")
        if "source" not in cf or not isinstance(cf["source"], str) or not cf["source"].strip():
            raise SchemaValidationError(f"companionFiles[{idx}] missing 'source' path.")
        if "relativeDestination" not in cf or not isinstance(cf["relativeDestination"], str) or not cf["relativeDestination"].strip():
            raise SchemaValidationError(f"companionFiles[{idx}] missing 'relativeDestination' path.")
        try:
            validate_relative_path(cf["source"], item_type=f"companionFiles[{idx}].source")
            validate_relative_path(cf["relativeDestination"], item_type=f"companionFiles[{idx}].relativeDestination")
        except ValueError as e:
            raise SchemaValidationError(str(e))

    # Validate platformHints
    if "platformHints" in data and not isinstance(data["platformHints"], dict):
        raise SchemaValidationError("'platformHints' must be a JSON object mapping.")


class ProfileManager:
    """Handles discovering and loading profiles from disk."""

    @staticmethod
    def load_profile(path_or_name: str | Path, profiles_dir: Path = Path("profiles")) -> Profile:
        """Loads a profile by file path or by profile name in profiles_dir."""
        p = Path(path_or_name)
        if not p.is_file():
            # Try within profiles_dir
            candidate = profiles_dir / f"{path_or_name}.json"
            if candidate.is_file():
                p = candidate
            else:
                candidate_direct = profiles_dir / path_or_name
                if candidate_direct.is_file():
                    p = candidate_direct
                else:
                    raise FileNotFoundError(f"Profile not found: '{path_or_name}' (checked '{p}' and '{candidate}')")

        with open(p, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                raise SchemaValidationError(f"Malformed JSON in profile '{p}': {e}")

        stem_name = p.stem
        return Profile.from_dict(data, default_name=stem_name)

    @staticmethod
    def list_profiles(profiles_dir: Path = Path("profiles")) -> List[Profile]:
        """Discovers and loads all valid profile JSON files in profiles_dir."""
        if not profiles_dir.is_dir():
            return []

        profiles = []
        for file_path in sorted(profiles_dir.glob("*.json")):
            try:
                prof = ProfileManager.load_profile(file_path, profiles_dir)
                profiles.append(prof)
            except Exception:
                # Malformed profiles are skipped during simple list or handled explicitly
                pass
        return profiles
