"""
Layout builders module.
Calculates target destination paths for Direct, Steam-style, and Custom layout presets
without performing filesystem side effects.
"""

from pathlib import Path
from typing import Optional

from src.validators import validate_name, validate_relative_path


class BaseLayout:
    """Base interface for directory layout resolution."""

    def resolve_destination(self, base_output_dir: Path) -> Path:
        """Calculates the primary directory destination path."""
        raise NotImplementedError()

    def resolve_companion_destination(self, base_output_dir: Path, relative_destination: str) -> Path:
        """Calculates destination path for companion files under this layout."""
        raise NotImplementedError()


class DirectLayout(BaseLayout):
    """
    Direct Layout:
    Primary tree: [base_output_dir] / [folder_name]
    Companion paths: resolved relative to primary folder root or base_output_dir.
    """

    def __init__(self, folder_name: str):
        validate_name(folder_name, item_type="Folder name")
        self.folder_name = folder_name

    def resolve_destination(self, base_output_dir: Path) -> Path:
        return (base_output_dir / self.folder_name).resolve()

    def resolve_companion_destination(self, base_output_dir: Path, relative_destination: str) -> Path:
        rel_p = validate_relative_path(relative_destination, item_type="Companion relativeDestination")
        primary = self.resolve_destination(base_output_dir)
        return (primary / rel_p).resolve()


class SteamLayout(BaseLayout):
    """
    Steam Layout:
    By default (Steam-style): [base_output_dir] / steamapps / common / [game_name]
    When steam_library is provided: [steam_library] / steamapps / common / [game_name]
    Companion paths: resolved relative to the active Steam root (output_dir or steam_library).
    """

    def __init__(self, game_name: str, steam_library: Optional[Path] = None):
        validate_name(game_name, item_type="Game name")
        self.game_name = game_name
        self.steam_library = steam_library.resolve() if steam_library else None

    @property
    def root_directory(self) -> Optional[Path]:
        return self.steam_library

    def resolve_destination(self, base_output_dir: Path) -> Path:
        root_dir = self.steam_library if self.steam_library else base_output_dir.resolve()
        return (root_dir / "steamapps" / "common" / self.game_name).resolve()

    def resolve_companion_destination(self, base_output_dir: Path, relative_destination: str) -> Path:
        rel_p = validate_relative_path(relative_destination, item_type="Companion relativeDestination")
        root_dir = self.steam_library if self.steam_library else base_output_dir.resolve()
        return (root_dir / rel_p).resolve()


class CustomLayout(BaseLayout):
    """
    Custom Layout:
    Primary tree: [base_output_dir] / [relative_game_path]
    Companion paths: resolved relative to [base_output_dir] / [relative_destination]
    """

    def __init__(self, relative_path_str: str):
        self.rel_path = validate_relative_path(relative_path_str, item_type="Custom layout path")

    def resolve_destination(self, base_output_dir: Path) -> Path:
        dest = (base_output_dir / self.rel_path).resolve()
        return dest

    def resolve_companion_destination(self, base_output_dir: Path, relative_destination: str) -> Path:
        rel_p = validate_relative_path(relative_destination, item_type="Companion relativeDestination")
        return (base_output_dir / rel_p).resolve()
