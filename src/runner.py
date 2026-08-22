"""
Wine execution runner module.
Provides safe execution of Windows .exe binaries using Wine,
configuring working directory, optional Wine prefixes, and helpful error diagnostics.
"""

import sys
import platform
import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, List


class WineRunner:
    """Handles running Windows executables natively on Windows, or through Wine on Linux/POSIX."""

    @staticmethod
    def is_wine_available() -> bool:
        """
        Checks if the runner is available.
        On Windows, returns True as .exe binaries run natively.
        On Linux/POSIX, checks if 'wine' is available in system PATH.
        """
        if sys.platform == "win32" or platform.system() == "Windows":
            return True
        return shutil.which("wine") is not None

    @staticmethod
    def run(
        executable_path: Path,
        wine_args: Optional[List[str]] = None,
        wine_prefix: Optional[str] = None
    ) -> int:
        """
        Executes a Windows executable (.exe).
        On Windows, runs the binary natively.
        On POSIX/Linux, runs with Wine.
        Sets working directory (cwd) to the directory containing the executable.
        Returns the process return code.
        """
        is_windows = sys.platform == "win32" or platform.system() == "Windows"

        if not is_windows and not WineRunner.is_wine_available():
            raise RuntimeError(
                "Wine no está instalado en el sistema o no se encuentra en el PATH.\n"
                "Para instalar Wine:\n"
                "  - Arch / CachyOS / Manjaro: sudo pacman -S wine winetricks\n"
                "  - Ubuntu / Debian: sudo apt install wine\n"
                "  - Fedora: sudo dnf install wine"
            )

        exe_resolved = executable_path.resolve()
        if not exe_resolved.is_file():
            raise FileNotFoundError(f"Ejecutable no encontrado en la ruta: {exe_resolved}")

        if is_windows:
            cmd = [str(exe_resolved)]
        else:
            cmd = ["wine", str(exe_resolved)]

        if wine_args:
            cmd.extend(wine_args)

        env = None
        if not is_windows and wine_prefix:
            env = os.environ.copy()
            env["WINEPREFIX"] = str(Path(wine_prefix).expanduser().resolve())

        # Execute within the executable's directory
        result = subprocess.run(cmd, cwd=exe_resolved.parent, env=env)
        return result.returncode

