"""
Configuration management module.
Defines data structures for build options and optional builder.json config file support.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class BuildConfig:
    template_path: Path = field(default_factory=lambda: Path("templates/Win64.rar"))
    folder_name: str = ""
    exe_name: str = ""
    layout_type: str = "direct"  # "direct", "steam", "custom"
    output_dir: Path = field(default_factory=lambda: Path("./output"))
    steam_library: Optional[Path] = None
    custom_path: str = ""
    collision_mode: str = "cancel"  # "cancel", "replace", "incremental"
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
            template_path=Path(data.get("template", "templates/Win64.rar")),
            folder_name=data.get("folderName", ""),
            exe_name=data.get("exeName", ""),
            layout_type=data.get("layout", "direct"),
            output_dir=Path(data.get("output", "./output")),
            steam_library=Path(data["steamLibrary"]) if data.get("steamLibrary") else None,
            custom_path=data.get("customPath", ""),
            collision_mode=data.get("collisionMode", "cancel"),
            dry_run=data.get("dryRun", False),
            verbose=data.get("verbose", False),
        )
