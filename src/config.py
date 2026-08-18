"""
Configuration management module.
Defines data structures for build options, profile selection, and JSON config support.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class BuildConfig:
    template_path: Path = field(default_factory=lambda: Path("Win64.rar"))
    profile_name: Optional[str] = None
    profiles_dir: Path = field(default_factory=lambda: Path("profiles"))
    profile_assets_root: Path = field(default_factory=lambda: Path("profiles/assets"))
    folder_name: str = ""
    exe_name: str = ""
    layout_type: str = ""  # "direct", "steam", "custom"
    output_dir: Path = field(default_factory=lambda: Path("./output"))
    steam_library: Optional[Path] = None
    custom_path: str = ""
    collision_mode: str = "cancel"  # "cancel", "replace", "incremental"
    allow_external_destination: bool = False
    dry_run: bool = False
    verbose: bool = False

    @classmethod
    def from_json(cls, json_path: Path) -> "BuildConfig":
        """Loads configuration from a JSON file."""
        if not json_path.is_file():
            raise FileNotFoundError(f"Config file not found: {json_path}")

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return cls(
            template_path=Path(data.get("template", "Win64.rar")),
            profile_name=data.get("profile"),
            profiles_dir=Path(data.get("profilesDir", "profiles")),
            profile_assets_root=Path(data.get("profileAssetsRoot", "profiles/assets")),
            folder_name=data.get("folderName", ""),
            exe_name=data.get("exeName", ""),
            layout_type=data.get("layout", ""),
            output_dir=Path(data.get("output", "./output")),
            steam_library=Path(data["steamLibrary"]) if data.get("steamLibrary") else None,
            custom_path=data.get("customPath", ""),
            collision_mode=data.get("collisionMode", "cancel"),
            allow_external_destination=data.get("allowExternalDestination", False),
            dry_run=data.get("dryRun", False),
            verbose=data.get("verbose", False),
        )
