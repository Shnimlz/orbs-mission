"""
Tests for directory layout resolution module.
"""

from pathlib import Path
import pytest

from src.layouts import DirectLayout, SteamLayout, CustomLayout


def test_direct_layout(tmp_path: Path):
    layout = DirectLayout("Shift At Midnight Demo")
    dest = layout.resolve_destination(tmp_path)
    assert dest == (tmp_path / "Shift At Midnight Demo").resolve()


def test_steam_layout_default(tmp_path: Path):
    layout = SteamLayout("Example Game")
    dest = layout.resolve_destination(tmp_path)
    assert dest == (tmp_path / "steamapps" / "common" / "Example Game").resolve()


def test_steam_layout_explicit_library(tmp_path: Path):
    steam_lib = tmp_path / "CustomSteamLibrary"
    layout = SteamLayout("Example Game", steam_library=steam_lib)
    dest = layout.resolve_destination(tmp_path)
    assert dest == (steam_lib / "steamapps" / "common" / "Example Game").resolve()


def test_custom_layout(tmp_path: Path):
    layout = CustomLayout("steamapps/common/My Game/Binaries/Win64")
    dest = layout.resolve_destination(tmp_path)
    expected = (tmp_path / "steamapps/common/My Game/Binaries/Win64").resolve()
    assert dest == expected


def test_custom_layout_path_traversal_escape(tmp_path: Path):
    with pytest.raises(ValueError, match="Path traversal"):
        CustomLayout("steamapps/../../escaped")
