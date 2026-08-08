"""
Layout builders module.
Calculates target destination paths for Direct, Steam-style, and Custom layout presets.
"""

from pathlib import Path
from typing import Optional
from src.validators import validate_name, validate_relative_path


class BaseLayout:
    """Base interface for directory layout resolution."""

    def resolve_destination(self, base_output_dir: Path) -> Path:
        raise NotImplementedError()


class DirectLayout(BaseLayout):
    """
    Direct Layout:
    Creates structure in [base_output_dir] / [folder_name]
    """

    def __init__(self, folder_name: str):
        validate_name(folder_name, item_type="Folder name")
        self.folder_name = folder_name

    def resolve_destination(self, base_output_dir: Path) -> Path:
        return (base_output_dir / self.folder_name).resolve()


class SteamLayout(BaseLayout):
    """
    Steam Layout:
    By default (Steam-style): [base_output_dir] / steamapps / common / [game_name]
    When steam_library is provided: [steam_library] / steamapps / common / [game_name]
    """

    def __init__(self, game_name: str, steam_library: Optional[Path] = None):
        validate_name(game_name, item_type="Game name")
        self.game_name = game_name
        self.steam_library = steam_library.resolve() if steam_library else None

    def resolve_destination(self, base_output_dir: Path) -> Path:
        root_dir = self.steam_library if self.steam_library else base_output_dir
        return (root_dir / "steamapps" / "common" / self.game_name).resolve()


class CustomLayout(BaseLayout):
    """
    Custom Layout:
    Creates structure in [base_output_dir] / [relative_path]
    """

    def __init__(self, relative_path_str: str):
        self.rel_path = validate_relative_path(relative_path_str)

    def resolve_destination(self, base_output_dir: Path) -> Path:
        dest = (base_output_dir / self.rel_path).resolve()
        # Verify destination stays inside base_output_dir or child
        base_resolved = base_output_dir.resolve()
        try:
            dest.relative_to(base_resolved)
        except ValueError:
            raise ValueError(f"Custom layout target '{dest}' escapes base directory '{base_resolved}'")
        return dest
