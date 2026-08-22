"""
Tests for CLI argument parsing, subcommands, profile inspection, and dry-run output formatting.
"""

import json
import sys
from pathlib import Path
import pytest
from src.cli import parse_args, display_build_plan
from src.plan import BuildPlan, DirectoryArtifact, FileArtifact, EmbeddedFile
from main import run_profile_list, run_profile_inspect, run_clean, run_inspect, main


def test_cli_parse_main_args():
    args = parse_args([
        "--folder", "TestGame",
        "--exe", "TestGame.exe",
        "--layout", "steam",
        "--output", "./out",
        "--collision", "replace",
        "--allow-external-destination",
        "--dry-run",
        "--verbose"
    ])
    assert args.command is None
    assert args.folder == "TestGame"
    assert args.exe == "TestGame.exe"
    assert args.layout == "steam"
    assert str(args.output) == "out"
    assert args.collision == "replace"
    assert args.allow_external_destination is True
    assert args.dry_run is True
    assert args.verbose is True


def test_cli_parse_subcommands():
    # inspect
    args_inspect = parse_args(["inspect", "--template", "custom.rar"])
    assert args_inspect.command == "inspect"
    assert str(args_inspect.template) == "custom.rar"

    # clean
    args_clean = parse_args(["clean", "--dir", "./tmp"])
    assert args_clean.command == "clean"
    assert str(args_clean.dir) == "tmp"

    # profile list
    args_plist = parse_args(["profile", "list", "--dir", "./my_profiles"])
    assert args_plist.command == "profile"
    assert args_plist.profile_action == "list"
    assert str(args_plist.dir) == "my_profiles"

    # profile inspect
    args_pinspect = parse_args(["profile", "inspect", "my-game", "--dir", "./my_profiles"])
    assert args_pinspect.command == "profile"
    assert args_pinspect.profile_action == "inspect"
    assert args_pinspect.profile_name == "my-game"


def test_display_build_plan_output(capsys, tmp_path: Path):
    out_root = tmp_path / "output"
    src_emb = tmp_path / "settings.ini"
    src_emb.write_text("volume=100")
    src_file = tmp_path / "manifest.acf"
    src_file.write_text("manifest")

    dir_art = DirectoryArtifact(
        destination=out_root / "steamapps" / "common" / "Game",
        source_template=Path("Win64.rar"),
        executable_rename=("Source.exe", "Game.exe"),
        subdirectories=("Saved/Config",),
        embedded_files=(
            EmbeddedFile(source_path=src_emb, relative_destination="settings.ini"),
        )
    )

    file_art = FileArtifact(
        destination=out_root / "steamapps" / "metadata" / "manifest.acf",
        source_path=src_file
    )

    plan = BuildPlan(
        profile_name="SampleGame",
        output_root=out_root,
        artifacts=(dir_art, file_art)
    )

    display_build_plan(plan)
    captured = capsys.readouterr().out

    assert "Profile:" in captured
    assert "SampleGame" in captured
    assert "[Directory]" in captured
    assert "[File]" in captured
    assert "CREATE directory tree" in captured
    assert "EXTRACT template archive" in captured
    assert "RENAME template executable" in captured
    assert "COPY embedded companion file" in captured
    assert "COPY independent companion file" in captured
    assert "No filesystem changes will be made." in captured


def test_cli_profile_list_and_inspect_execution(capsys, tmp_path: Path):
    p_dir = tmp_path / "profiles"
    p_dir.mkdir()

    p_data = {
        "displayName": "Cli Game",
        "folderName": "CliGame",
        "executableName": "CliGame.exe",
        "layout": "steam",
        "additionalDirectories": ["Binaries"],
        "companionFiles": [
            {"source": "conf.ini", "relativeDestination": "steamapps/metadata/conf.ini"}
        ]
    }
    (p_dir / "cli-game.json").write_text(json.dumps(p_data), encoding="utf-8")

    # Run list
    code_list = run_profile_list(p_dir)
    assert code_list == 0
    cap_list = capsys.readouterr().out
    assert "cli-game" in cap_list

    # Run inspect
    code_inspect = run_profile_inspect("cli-game", p_dir)
    assert code_inspect == 0
    cap_inspect = capsys.readouterr().out
    assert "Cli Game" in cap_inspect
    assert "cli-game" in cap_inspect
    assert "Folder:" in cap_inspect
    assert "CliGame" in cap_inspect
    assert "Executable:" in cap_inspect
    assert "CliGame.exe" in cap_inspect
    assert "Layout:" in cap_inspect
    assert "steam" in cap_inspect
    assert "1 companion file(s)" in cap_inspect


def test_cli_clean_execution(capsys, tmp_path: Path):
    code = run_clean(tmp_path)
    assert code == 0
    cap = capsys.readouterr().out
    assert "Limpiando artefactos" in cap


def test_cli_inspect_template_execution(capsys):
    rar_file = Path("Win64.rar")
    if not rar_file.is_file():
        rar_file = Path("templates/Win64.rar")
    if not rar_file.is_file():
        pytest.skip("Win64.rar not found")

    code = run_inspect(rar_file)
    assert code == 0
    cap = capsys.readouterr().out
    assert "Plantilla:" in cap
    assert "Root:" in cap
    assert "Win64" in cap


def test_main_cli_dry_run_with_profile(monkeypatch, capsys, tmp_path: Path):
    rar_file = Path("Win64.rar")
    if not rar_file.is_file():
        rar_file = Path("templates/Win64.rar")
    if not rar_file.is_file():
        pytest.skip("Win64.rar not found")

    p_dir = tmp_path / "profiles"
    p_dir.mkdir()
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "meta.conf").write_text("info=1")

    p_data = {
        "displayName": "EndToEnd Game",
        "folderName": "E2EGame",
        "executableName": "E2EGame.exe",
        "layout": "steam",
        "companionFiles": [
            {"source": "meta.conf", "relativeDestination": "steamapps/metadata/meta.conf"}
        ]
    }
    p_file = p_dir / "e2e-game.json"
    p_file.write_text(json.dumps(p_data), encoding="utf-8")

    out_dir = tmp_path / "output"

    monkeypatch.setattr(
        sys, "argv",
        ["main.py", "--profile", str(p_file), "--output", str(out_dir), "--template", str(rar_file), "--assets-root", str(assets_dir), "--dry-run"]
    )

    exit_code = main()
    assert exit_code == 0
    cap = capsys.readouterr().out
    assert "Build plan:" in cap
    assert "E2EGame" in cap


def test_main_cli_execution_with_profile(monkeypatch, capsys, tmp_path: Path):
    rar_file = Path("Win64.rar")
    if not rar_file.is_file():
        rar_file = Path("templates/Win64.rar")
    if not rar_file.is_file():
        pytest.skip("Win64.rar not found")

    p_dir = tmp_path / "profiles"
    p_dir.mkdir()
    assets_dir = tmp_path / "assets"
    assets_dir.mkdir()
    (assets_dir / "meta.conf").write_text("info=1")

    p_data = {
        "displayName": "Real Game",
        "folderName": "RealGame",
        "executableName": "RealGame.exe",
        "layout": "steam",
        "companionFiles": [
            {"source": "meta.conf", "relativeDestination": "steamapps/metadata/meta.conf"}
        ]
    }
    p_file = p_dir / "real-game.json"
    p_file.write_text(json.dumps(p_data), encoding="utf-8")

    out_dir = tmp_path / "output"

    monkeypatch.setattr(
        sys, "argv",
        ["main.py", "--profile", str(p_file), "--output", str(out_dir), "--template", str(rar_file), "--assets-root", str(assets_dir)]
    )

    exit_code = main()
    assert exit_code == 0
    cap = capsys.readouterr().out
    assert "Operación completada con éxito" in cap

    assert (out_dir / "steamapps" / "common" / "RealGame" / "RealGame.exe").exists()
    assert (out_dir / "steamapps" / "metadata" / "meta.conf").exists()


def test_main_cli_list_folders(monkeypatch, capsys, tmp_path: Path):
    out_dir = tmp_path / "output"
    game_dir = out_dir / "steamapps" / "common" / "ExistingGame"
    game_dir.mkdir(parents=True)
    (game_dir / "Existing.exe").write_text("dummy")

    monkeypatch.setattr(
        sys, "argv",
        ["main.py", "--list-folders", "--output", str(out_dir)]
    )

    exit_code = main()
    assert exit_code == 0
    cap = capsys.readouterr().out
    assert "Carpetas existentes detectadas:" in cap
    assert "ExistingGame" in cap
    assert "Existing.exe" in cap


def test_main_cli_existing_folder_renames_exe(monkeypatch, capsys, tmp_path: Path):
    rar_file = Path("Win64.rar")
    if not rar_file.is_file():
        rar_file = Path("templates/Win64.rar")
    if not rar_file.is_file():
        pytest.skip("Win64.rar not found")

    out_dir = tmp_path / "output"
    game_dir = out_dir / "steamapps" / "common" / "PreExistingGame"
    game_dir.mkdir(parents=True)
    (game_dir / "OldName.exe").write_text("dummy binary")

    monkeypatch.setattr(
        sys, "argv",
        [
            "main.py",
            "--folder", "PreExistingGame",
            "--exe", "RenamedGame.exe",
            "--layout", "steam",
            "--output", str(out_dir),
            "--template", str(rar_file)
        ]
    )

    exit_code = main()
    assert exit_code == 0
    cap = capsys.readouterr().out
    assert "Carpeta existente detectada" in cap or "Operación completada con éxito" in cap

    # Verify that the exe was renamed in place without failing
    assert (game_dir / "RenamedGame.exe").exists()
    assert not (game_dir / "OldName.exe").exists()


def test_main_cli_with_wine_flag(monkeypatch, capsys, tmp_path: Path):
    from unittest.mock import patch
    rar_file = Path("Win64.rar")
    if not rar_file.is_file():
        rar_file = Path("templates/Win64.rar")
    if not rar_file.is_file():
        pytest.skip("Win64.rar not found")

    out_dir = tmp_path / "output"

    monkeypatch.setattr(
        sys, "argv",
        [
            "main.py",
            "--folder", "WineGame",
            "--exe", "WineGame.exe",
            "--layout", "direct",
            "--output", str(out_dir),
            "--template", str(rar_file),
            "--wine"
        ]
    )

    with patch("src.runner.WineRunner.run", return_value=0) as mock_wine:
        exit_code = main()
        assert exit_code == 0
        mock_wine.assert_called_once()


def test_interactive_prompt_selection_existing_folder(monkeypatch, tmp_path: Path):
    from src.config import BuildConfig
    from src.cli import run_interactive_prompts

    out_dir = tmp_path / "output"
    g_dir = out_dir / "steamapps" / "common" / "SelectMe"
    g_dir.mkdir(parents=True)
    (g_dir / "SelectMe.exe").write_text("bin")

    config = BuildConfig(
        output_dir=out_dir,
        template_path=Path("Win64.rar")
    )

    # User enters "1" to pick the existing folder, then presses Enter for exe default
    user_inputs = iter(["1", ""])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(user_inputs))

    updated_config = run_interactive_prompts(config, candidate_exe="SelectMe.exe")
    assert updated_config.folder_name == "SelectMe"
    assert updated_config.layout_type == "steam"
    assert updated_config.exe_name == "SelectMe.exe"


def test_main_cli_doctor_command(monkeypatch, capsys):
    rar_file = Path("Win64.rar")
    if not rar_file.is_file():
        rar_file = Path("templates/Win64.rar")

    monkeypatch.setattr(
        sys, "argv",
        ["main.py", "doctor", "--template", str(rar_file)]
    )

    exit_code = main()
    assert exit_code == 0
    cap = capsys.readouterr().out
    assert "Diagnóstico del Sistema y Requisitos" in cap


def test_main_menu_exit(monkeypatch):
    from main import run_interactive_menu

    # User chooses "0" (Exit) immediately
    monkeypatch.setattr("builtins.input", lambda prompt="": "0")
    exit_code = run_interactive_menu()
    assert exit_code == 0


def test_select_profile_prompt(monkeypatch, tmp_path: Path):
    from src.cli import run_select_profile_prompt

    p_dir = tmp_path / "profiles"
    p_dir.mkdir()
    p_data = {
        "displayName": "Tokon Fighting",
        "folderName": "MTFS",
        "executableName": "Game.exe",
        "layout": "steam"
    }
    (p_dir / "tokon.json").write_text(json.dumps(p_data), encoding="utf-8")

    # Select profile 1
    monkeypatch.setattr("builtins.input", lambda prompt="": "1")
    prof = run_select_profile_prompt(p_dir)
    assert prof is not None
    assert prof.folder_name == "MTFS"
    assert prof.executable_name == "Game.exe"


def test_interactive_menu_selection_non_tty(monkeypatch):
    from src.cli import MenuItem, interactive_menu_selection

    items = [
        MenuItem("1", "Option One"),
        MenuItem("2", "Option Two"),
        MenuItem("0", "Exit", is_back=True),
    ]

    monkeypatch.setattr("builtins.input", lambda prompt="": "2")
    res = interactive_menu_selection(items, title_box="TEST MENU", default_index=0)
    assert res == "2"


def test_interactive_menu_selection_keyboard_navigation(monkeypatch):
    from unittest.mock import MagicMock
    from src.cli import MenuItem, interactive_menu_selection
    import src.cli as cli_mod

    items = [
        MenuItem("1", "Option One"),
        MenuItem("2", "Option Two"),
        MenuItem("0", "Exit", is_back=True),
    ]

    # Simulate TTY
    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    # Test 1: Move down then enter -> Option 2
    keys_down_enter = iter(["down", "enter"])
    monkeypatch.setattr(cli_mod, "read_raw_key", lambda: next(keys_down_enter))
    res1 = interactive_menu_selection(items, default_index=0)
    assert res1 == "2"

    # Test 2: Move left / back -> back_key ("0")
    keys_left = iter(["left"])
    monkeypatch.setattr(cli_mod, "read_raw_key", lambda: next(keys_left))
    res2 = interactive_menu_selection(items, default_index=0)
    assert res2 == "0"

    # Test 3: Escape -> back_key ("0")
    keys_esc = iter(["escape"])
    monkeypatch.setattr(cli_mod, "read_raw_key", lambda: next(keys_esc))
    res3 = interactive_menu_selection(items, default_index=0)
    assert res3 == "0"

    # Test 4: Right arrow (Forward / Select) on first item -> Option 1
    keys_right = iter(["right"])
    monkeypatch.setattr(cli_mod, "read_raw_key", lambda: next(keys_right))
    res4 = interactive_menu_selection(items, default_index=0)
    assert res4 == "1"

    # Test 5: Direct number shortcut "2" -> Option 2
    keys_direct = iter(["2"])
    monkeypatch.setattr(cli_mod, "read_raw_key", lambda: next(keys_direct))
    res5 = interactive_menu_selection(items, default_index=0)
    assert res5 == "2"


def test_read_raw_key_sequences(monkeypatch):
    import os
    import termios
    import tty
    from src.cli import read_raw_key

    monkeypatch.setattr(sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(sys.stdin, "fileno", lambda: 0)
    monkeypatch.setattr(termios, "tcgetattr", lambda fd: [])
    monkeypatch.setattr(termios, "tcsetattr", lambda fd, when, attr: None)
    monkeypatch.setattr(tty, "setraw", lambda fd: None)

    # Test UP arrow
    monkeypatch.setattr(os, "read", lambda fd, n: b"\x1b[A")
    assert read_raw_key() == "up"

    # Test DOWN arrow
    monkeypatch.setattr(os, "read", lambda fd, n: b"\x1b[B")
    assert read_raw_key() == "down"

    # Test RIGHT arrow
    monkeypatch.setattr(os, "read", lambda fd, n: b"\x1b[C")
    assert read_raw_key() == "right"

    # Test LEFT arrow
    monkeypatch.setattr(os, "read", lambda fd, n: b"\x1b[D")
    assert read_raw_key() == "left"

    # Test Enter
    monkeypatch.setattr(os, "read", lambda fd, n: b"\r")
    assert read_raw_key() == "enter"

    # Test Direct key
    monkeypatch.setattr(os, "read", lambda fd, n: b"1")
    assert read_raw_key() == "1"




