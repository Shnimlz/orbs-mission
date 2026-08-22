"""
Tests for SystemDoctor diagnostics module.
"""

import sys
from pathlib import Path
import pytest
from unittest.mock import patch

from src.doctor import SystemDoctor, SystemHealthReport


def test_doctor_check_system_linux(tmp_path: Path):
    with patch("sys.platform", "linux"), \
         patch("platform.system", return_value="Linux"), \
         patch("platform.release", return_value="6.6.0-arch"), \
         patch("platform.machine", return_value="x86_64"), \
         patch("src.doctor.SystemDoctor.get_linux_distro", return_value="Arch Linux"), \
         patch("src.template.TemplateManager.find_extractor", return_value=("7z", "/usr/bin/7z")), \
         patch("shutil.which") as mock_which:
        
        mock_which.side_effect = lambda cmd: "/usr/bin/" + cmd if cmd in ("wine", "winetricks") else None

        rar_file = Path("Win64.rar")
        if not rar_file.is_file():
            rar_file = Path("templates/Win64.rar")

        report = SystemDoctor.check_system(template_path=rar_file)

        assert isinstance(report, SystemHealthReport)
        assert "Linux" in report.os_name
        assert "Arch Linux" in report.os_name
        assert not report.has_errors

        names = {item.name: item for item in report.items}
        assert names["Entorno Python"].status == "OK"
        assert names["Extractor RAR"].status == "OK"
        assert names["Wine Runner"].status == "OK"
        assert names["Winetricks"].status == "OK"


def test_doctor_check_system_windows(tmp_path: Path):
    with patch("sys.platform", "win32"), \
         patch("platform.system", return_value="Windows"), \
         patch("platform.release", return_value="10"), \
         patch("platform.machine", return_value="AMD64"), \
         patch("src.template.TemplateManager.find_extractor", return_value=("7z", r"C:\Program Files\7-Zip\7z.exe")):

        rar_file = Path("Win64.rar")
        if not rar_file.is_file():
            rar_file = Path("templates/Win64.rar")

        report = SystemDoctor.check_system(template_path=rar_file)

        assert report.os_name == "Windows"
        names = {item.name: item for item in report.items}
        assert names["Entorno de Ejecución"].status == "OK"
        assert "Windows Nativo" in names["Entorno de Ejecución"].details


def test_doctor_print_report(capsys):
    rar_file = Path("Win64.rar")
    if not rar_file.is_file():
        rar_file = Path("templates/Win64.rar")

    SystemDoctor.print_diagnostic_report(template_path=rar_file)
    captured = capsys.readouterr().out
    assert "Diagnóstico del Sistema y Requisitos" in captured
    assert "Sistema Operativo:" in captured
    assert "Versión de Python:" in captured


def test_doctor_quick_status_line():
    status = SystemDoctor.get_quick_status_line(Path("Win64.rar"))
    assert "SO:" in status
    assert "Python:" in status
