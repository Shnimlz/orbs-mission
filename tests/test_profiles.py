"""
Tests for Profile schema validation, JSON loading, discovery, and semantics.
"""

import json
from pathlib import Path
import pytest

from src.profiles import Profile, ProfileManager, SchemaValidationError, validate_profile_schema


def test_valid_profile_schema():
    valid_data = {
        "displayName": "Test Game",
        "folderName": "TestGame",
        "executableName": "TestGame.exe",
        "layout": "steam",
        "platformHints": {"arch": "win64"},
        "additionalDirectories": ["Saved/Config"],
        "companionFiles": [
            {"source": "metadata/game.conf", "relativeDestination": "steamapps/metadata/game.conf"}
        ]
    }
    validate_profile_schema(valid_data)
    profile = Profile.from_dict(valid_data, default_name="test-game")
    assert profile.name == "test-game"
    assert profile.display_name == "Test Game"
    assert profile.executable_name == "TestGame.exe"
    assert profile.layout == "steam"
    assert profile.relative_game_path == ""
    assert len(profile.additional_directories) == 1
    assert len(profile.companion_files) == 1


def test_steam_profile_with_relative_game_path_rejected():
    data = {
        "displayName": "Steam Game",
        "folderName": "SteamGame",
        "executableName": "SteamGame.exe",
        "layout": "steam",
        "relativeGamePath": "steamapps/common/SteamGame"
    }
    with pytest.raises(SchemaValidationError, match="forbidden when layout is 'steam'"):
        validate_profile_schema(data)


def test_steam_profile_without_relative_game_path_accepted():
    data = {
        "displayName": "Steam Game",
        "folderName": "SteamGame",
        "executableName": "SteamGame.exe",
        "layout": "steam"
    }
    validate_profile_schema(data)
    prof = Profile.from_dict(data, default_name="steam-game")
    assert prof.layout == "steam"
    assert prof.relative_game_path == ""


def test_direct_profile_with_relative_game_path_rejected():
    data = {
        "displayName": "Direct Game",
        "folderName": "DirectGame",
        "executableName": "DirectGame.exe",
        "layout": "direct",
        "relativeGamePath": "DirectGame"
    }
    with pytest.raises(SchemaValidationError, match="forbidden when layout is 'direct'"):
        validate_profile_schema(data)


def test_custom_profile_requires_relative_game_path():
    data_missing = {
        "displayName": "Custom Game",
        "folderName": "CustomGame",
        "executableName": "CustomGame.exe",
        "layout": "custom"
    }
    with pytest.raises(SchemaValidationError, match="requires 'relativeGamePath'"):
        validate_profile_schema(data_missing)

    data_valid = {
        "displayName": "Custom Game",
        "folderName": "CustomGame",
        "executableName": "CustomGame.exe",
        "layout": "custom",
        "relativeGamePath": "MyGame/Binaries/Win64"
    }
    validate_profile_schema(data_valid)
    prof = Profile.from_dict(data_valid, default_name="custom-game")
    assert prof.relative_game_path == "MyGame/Binaries/Win64"


def test_unknown_layout_rejection():
    data = {
        "displayName": "Unknown Game",
        "folderName": "UnknownGame",
        "executableName": "UnknownGame.exe",
        "layout": "epic_games"
    }
    with pytest.raises(SchemaValidationError, match="Invalid layout 'epic_games'"):
        validate_profile_schema(data)


def test_malformed_profile_rejection():
    # Missing required field
    with pytest.raises(SchemaValidationError, match="Missing or invalid required field"):
        validate_profile_schema({"displayName": "Incomplete"})

    # Invalid folderName characters
    with pytest.raises(SchemaValidationError, match="invalid characters"):
        validate_profile_schema({
            "displayName": "Invalid",
            "folderName": "Bad/Name",
            "executableName": "Game.exe",
            "layout": "direct"
        })

    # Traversal in companionFiles
    with pytest.raises(SchemaValidationError, match="Path traversal"):
        validate_profile_schema({
            "displayName": "Invalid",
            "folderName": "Game",
            "executableName": "Game.exe",
            "layout": "direct",
            "companionFiles": [
                {"source": "../escaped.conf", "relativeDestination": "config.conf"}
            ]
        })


def test_profile_manager_discovery_and_load(tmp_path: Path):
    profiles_dir = tmp_path / "profiles"
    profiles_dir.mkdir()

    prof1_data = {
        "displayName": "Game One",
        "folderName": "GameOne",
        "executableName": "GameOne.exe",
        "layout": "direct"
    }
    (profiles_dir / "game-one.json").write_text(json.dumps(prof1_data), encoding="utf-8")

    prof2_data = {
        "displayName": "Game Two",
        "folderName": "GameTwo",
        "executableName": "GameTwo.exe",
        "layout": "steam"
    }
    (profiles_dir / "game-two.json").write_text(json.dumps(prof2_data), encoding="utf-8")

    discovered = ProfileManager.list_profiles(profiles_dir)
    assert len(discovered) == 2
    names = [p.name for p in discovered]
    assert "game-one" in names
    assert "game-two" in names

    loaded = ProfileManager.load_profile("game-one", profiles_dir)
    assert loaded.display_name == "Game One"
