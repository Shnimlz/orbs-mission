"""
Tests for cross-platform validation module and asset source containment.
"""

from pathlib import Path
import pytest
from src.validators import (
    validate_name,
    validate_executable_name,
    validate_relative_path,
    validate_asset_source_path,
)


def test_valid_names():
    validate_name("Shift At Midnight Demo")
    validate_name("Example_Game-v1.0")
    validate_name("123-Game")


def test_invalid_characters():
    invalid_examples = [
        "Game<One>",
        "Game:One",
        'Game"One',
        "Game/One",
        "Game\\One",
        "Game|One",
        "Game?One",
        "Game*One",
    ]
    for ex in invalid_examples:
        with pytest.raises(ValueError, match="invalid characters"):
            validate_name(ex)


def test_trailing_dot_or_space():
    invalid_examples = ["Game ", "Game.", "Game. ", "Game  ."]
    for ex in invalid_examples:
        with pytest.raises(ValueError, match="cannot end with a space or dot"):
            validate_name(ex)


def test_windows_reserved_names_and_stems():
    reserved_examples = [
        "CON", "con", "Prn", "AUX", "NUL",
        "COM1", "com9", "LPT1", "lpt3",
        "CON.exe", "NUL.txt", "com1.foo", "aux.bin"
    ]
    for ex in reserved_examples:
        with pytest.raises(ValueError, match="reserved Windows device name stem"):
            validate_name(ex)


def test_validate_executable_name():
    assert validate_executable_name("Shift At Midnight.exe") == "Shift At Midnight.exe"
    assert validate_executable_name("ExampleGame") == "ExampleGame.exe"
    assert validate_executable_name("MyGame.EXE") == "MyGame.EXE"

    with pytest.raises(ValueError):
        validate_executable_name("CON.exe")

    with pytest.raises(ValueError):
        validate_executable_name("Game?.exe")


def test_validate_relative_path():
    p = validate_relative_path("steamapps/common/My Game")
    assert str(p) == "steamapps/common/My Game"

    with pytest.raises(ValueError, match="Path traversal"):
        validate_relative_path("steamapps/../../My Game")

    with pytest.raises(ValueError, match="Path traversal"):
        validate_relative_path("../outside")

    with pytest.raises(ValueError, match="must be relative"):
        validate_relative_path("/absolute/path")


def test_asset_source_containment(tmp_path: Path):
    assets_root = tmp_path / "assets"
    assets_root.mkdir()
    sample_file = assets_root / "config" / "test.conf"
    sample_file.parent.mkdir()
    sample_file.write_text("setting=1")

    # Valid relative source inside assets_root
    validated = validate_asset_source_path("config/test.conf", assets_root)
    assert validated == sample_file.resolve()

    # Traversal attempt
    with pytest.raises(ValueError, match="Path traversal"):
        validate_asset_source_path("config/../../escaped.conf", assets_root)

    # Absolute path attempt
    with pytest.raises(ValueError, match="must be relative"):
        validate_asset_source_path(str(sample_file), assets_root)

    # Missing file inside assets_root
    with pytest.raises(FileNotFoundError):
        validate_asset_source_path("config/nonexistent.conf", assets_root)
