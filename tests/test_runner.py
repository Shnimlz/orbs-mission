"""
Tests for WineRunner execution module.
"""

from pathlib import Path
import pytest
from unittest.mock import patch, MagicMock

from src.runner import WineRunner


def test_wine_availability():
    with patch("shutil.which", return_value="/usr/bin/wine"):
        assert WineRunner.is_wine_available() is True

    with patch("shutil.which", return_value=None):
        assert WineRunner.is_wine_available() is False


def test_wine_run_missing_wine():
    with patch("shutil.which", return_value=None):
        with pytest.raises(RuntimeError) as exc:
            WineRunner.run(Path("dummy.exe"))
        assert "Wine no está instalado" in str(exc.value)


def test_wine_run_missing_executable(tmp_path: Path):
    with patch("shutil.which", return_value="/usr/bin/wine"):
        with pytest.raises(FileNotFoundError) as exc:
            WineRunner.run(tmp_path / "non_existent.exe")
        assert "Ejecutable no encontrado" in str(exc.value)


def test_wine_run_success(tmp_path: Path):
    exe = tmp_path / "game.exe"
    exe.write_text("dummy exe")

    mock_result = MagicMock(returncode=0)

    with patch("shutil.which", return_value="/usr/bin/wine"), \
         patch("subprocess.run", return_value=mock_result) as mock_sub:
        code = WineRunner.run(exe, wine_args=["--debug"], wine_prefix=str(tmp_path / "prefix"))
        assert code == 0
        mock_sub.assert_called_once()
        args, kwargs = mock_sub.call_args
        assert args[0] == ["wine", str(exe.resolve()), "--debug"]
        assert kwargs["cwd"] == exe.parent
        assert kwargs["env"]["WINEPREFIX"] == str((tmp_path / "prefix").resolve())


def test_windows_native_run_success(tmp_path: Path):
    exe = tmp_path / "win_game.exe"
    exe.write_text("dummy exe")

    mock_result = MagicMock(returncode=0)

    with patch("sys.platform", "win32"), \
         patch("platform.system", return_value="Windows"), \
         patch("subprocess.run", return_value=mock_result) as mock_sub:
        assert WineRunner.is_wine_available() is True
        code = WineRunner.run(exe, wine_args=["-fullscreen"])
        assert code == 0
        mock_sub.assert_called_once()
        args, kwargs = mock_sub.call_args
        assert args[0] == [str(exe.resolve()), "-fullscreen"]
        assert kwargs["cwd"] == exe.parent

