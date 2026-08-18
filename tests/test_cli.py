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
