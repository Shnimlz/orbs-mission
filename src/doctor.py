"""
System Diagnostics and Environment Health Check Module.
Inspects operating system (Linux distros, Windows, macOS), Python runtime,
RAR extractors (7z, unrar), Wine/Winetricks on Linux, and template file availability.
"""

import os
import sys
import platform
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict

# ANSI styling
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"


@dataclass
class DiagnosticItem:
    name: str
    status: str  # "OK" | "WARN" | "ERROR"
    details: str
    hint: Optional[str] = None


@dataclass
class SystemHealthReport:
    os_name: str
    os_details: str
    python_version: str
    items: List[DiagnosticItem] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(item.status == "ERROR" for item in self.items)

    @property
    def has_warnings(self) -> bool:
        return any(item.status == "WARN" for item in self.items)


class SystemDoctor:
    """Performs comprehensive environment inspections and dependency checks."""

    @staticmethod
    def get_linux_distro() -> str:
        """Reads Linux distribution name from /etc/os-release if available."""
        if not sys.platform.startswith("linux"):
            return ""
        os_release = Path("/etc/os-release")
        if os_release.is_file():
            try:
                content = os_release.read_text(encoding="utf-8")
                for line in content.splitlines():
                    if line.startswith("PRETTY_NAME="):
                        return line.split("=", 1)[1].strip('"\'')
                    if line.startswith("NAME=") and "PRETTY_NAME" not in content:
                        return line.split("=", 1)[1].strip('"\'')
            except Exception:
                pass
        return "Linux Generic"

    @staticmethod
    def check_system(template_path: Path = Path("Win64.rar")) -> SystemHealthReport:
        """Runs all diagnostics and returns a SystemHealthReport."""
        is_windows = sys.platform == "win32" or platform.system() == "Windows"
        is_linux = sys.platform.startswith("linux") or platform.system() == "Linux"
        is_mac = sys.platform == "darwin" or platform.system() == "Darwin"

        # 1. OS Details
        if is_windows:
            os_name = "Windows"
            os_details = f"Windows {platform.release()} ({platform.machine()})"
        elif is_linux:
            distro = SystemDoctor.get_linux_distro()
            os_name = f"Linux ({distro})"
            os_details = f"{distro} | Kernel {platform.release()} ({platform.machine()})"
        elif is_mac:
            os_name = "macOS"
            os_details = f"macOS {platform.mac_ver()[0]} ({platform.machine()})"
        else:
            os_name = platform.system()
            os_details = f"{platform.system()} {platform.release()}"

        report = SystemHealthReport(
            os_name=os_name,
            os_details=os_details,
            python_version=platform.python_version()
        )

        # 2. Python Version Check (>= 3.11)
        py_major, py_minor = sys.version_info[:2]
        if py_major >= 3 and py_minor >= 11:
            report.items.append(DiagnosticItem(
                name="Entorno Python",
                status="OK",
                details=f"Python {platform.python_version()} (Compatible >= 3.11)"
            ))
        else:
            report.items.append(DiagnosticItem(
                name="Entorno Python",
                status="ERROR",
                details=f"Python {platform.python_version()} (Requiere Python >= 3.11)",
                hint="Por favor actualice Python a la versión 3.11 o superior."
            ))

        # 3. RAR Extractor Check
        from src.template import TemplateManager
        try:
            tool_name, tool_path = TemplateManager.find_extractor()
            report.items.append(DiagnosticItem(
                name="Extractor RAR",
                status="OK",
                details=f"{tool_name} encontrado en '{tool_path}'"
            ))
        except Exception:
            hint = "Instala 7-Zip: sudo pacman -S 7zip (Arch) | sudo apt install 7zip (Ubuntu) | https://www.7-zip.org (Windows)"
            report.items.append(DiagnosticItem(
                name="Extractor RAR",
                status="ERROR",
                details="No se encontró 7z, 7zz ni unrar en el sistema",
                hint=hint
            ))

        # 4. Wine / Winetricks / Windows Native Check
        if is_windows:
            report.items.append(DiagnosticItem(
                name="Entorno de Ejecución",
                status="OK",
                details="Windows Nativo (Ejecución directa de binarios .exe habilitada)"
            ))
        elif is_linux or is_mac:
            wine_path = shutil.which("wine")
            if wine_path:
                wine_ver = "Instalado"
                report.items.append(DiagnosticItem(
                    name="Wine Runner",
                    status="OK",
                    details=f"Wine detectado en '{wine_path}'"
                ))
            else:
                hint_distro = (
                    "Arch/CachyOS: sudo pacman -S wine winetricks wine-gecko wine-mono\n"
                    "  Ubuntu/Debian: sudo apt install wine winetricks\n"
                    "  Fedora: sudo dnf install wine"
                )
                report.items.append(DiagnosticItem(
                    name="Wine Runner",
                    status="WARN",
                    details="Wine no está instalado en el sistema (no podrás ejecutar los .exe directamente en Linux)",
                    hint=hint_distro
                ))

            # Winetricks check
            winetricks_path = shutil.which("winetricks")
            if winetricks_path:
                report.items.append(DiagnosticItem(
                    name="Winetricks",
                    status="OK",
                    details=f"Winetricks detectado en '{winetricks_path}'"
                ))
            else:
                report.items.append(DiagnosticItem(
                    name="Winetricks",
                    status="WARN",
                    details="Winetricks no instalado (recomendado para configurar runtime/fuentes)",
                    hint="Instala winetricks para instalar dependencias de juegos fácilmente."
                ))

        # 5. Template file check
        resolved_template = template_path
        if not resolved_template.is_file():
            alt_template = Path("templates") / template_path.name
            if alt_template.is_file():
                resolved_template = alt_template

        if resolved_template.is_file():
            try:
                mgr = TemplateManager(resolved_template)
                info = mgr.inspect()
                report.items.append(DiagnosticItem(
                    name="Plantilla Base",
                    status="OK",
                    details=f"'{resolved_template}' válida ({len(info['executables'])} exe, {len(info['dlls'])} dlls, {len(info['languages'])} idiomas)"
                ))
            except Exception as e:
                report.items.append(DiagnosticItem(
                    name="Plantilla Base",
                    status="ERROR",
                    details=f"'{resolved_template}' está dañada o no es válida: {e}",
                    hint="Verifica que el archivo Win64.rar no esté corrupto."
                ))
        else:
            report.items.append(DiagnosticItem(
                name="Plantilla Base",
                status="ERROR",
                details=f"No se encontró el archivo de plantilla '{template_path}' ni en 'templates/'",
                hint="Asegúrate de colocar 'Win64.rar' en la raíz del proyecto o en 'templates/'."
            ))

        return report

    @staticmethod
    def get_quick_status_line(template_path: Path = Path("Win64.rar")) -> str:
        """Returns a compact, single-line status badge for the menu header."""
        is_windows = sys.platform == "win32" or platform.system() == "Windows"
        os_label = "Windows" if is_windows else (SystemDoctor.get_linux_distro() or "Linux")

        from src.template import TemplateManager
        has_7z = False
        try:
            TemplateManager.find_extractor()
            has_7z = True
        except Exception:
            pass

        has_wine = True if is_windows else (shutil.which("wine") is not None)

        z7_status = f"{GREEN}7z: OK{RESET}" if has_7z else f"{RED}7z: Falta{RESET}"
        wine_status = f"{GREEN}Wine: OK{RESET}" if has_wine else f"{YELLOW}Wine: No{RESET}"

        return f"  {DIM}󰌽 SO:{RESET} {CYAN}{os_label}{RESET}  {DIM}•  󰌠 Python:{RESET} {GREEN}{platform.python_version()}{RESET}  {DIM}•  📦 7z:{RESET} {z7_status}  {DIM}•  🍷 Wine:{RESET} {wine_status}"

    @staticmethod
    def print_diagnostic_report(template_path: Path = Path("Win64.rar"), animated: bool = True) -> None:
        """Renders styled ANSI diagnostic report to the terminal with animation."""
        report = SystemDoctor.check_system(template_path)

        print(f"\n{CYAN}╭────────────────────────────────────────────────────────╮{RESET}")
        print(f"{CYAN}│{RESET} {BOLD}Diagnóstico del Sistema y Requisitos{RESET}                   {CYAN}│{RESET}")
        print(f"{CYAN}╰────────────────────────────────────────────────────────╯{RESET}")

        print(f"\n{BOLD}Sistema Operativo:{RESET} {CYAN}{report.os_details}{RESET}")
        print(f"{BOLD}Versión de Python:{RESET} {GREEN}{report.python_version}{RESET}\n")

        print(f"{BOLD}Resultados del Diagnóstico:{RESET}")
        for item in report.items:
            if item.status == "OK":
                badge = f"{GREEN}[✓ OK]{RESET}"
            elif item.status == "WARN":
                badge = f"{YELLOW}[⚠ AVISO]{RESET}"
            else:
                badge = f"{RED}[✗ ERROR]{RESET}"

            print(f"  {badge} {BOLD}{item.name}:{RESET} {item.details}")
            if item.hint:
                for hint_line in item.hint.splitlines():
                    print(f"       {DIM}➜ {hint_line}{RESET}")
            if animated and sys.stdout.isatty():
                import time
                time.sleep(0.04)

        print()
        if report.has_errors:
            print(f"{RED}⚠ Se encontraron errores que impedirán la extracción o construcción.{RESET}\n")
        elif report.has_warnings:
            print(f"{YELLOW}✓ El sistema está listo para construir. Se encontraron sugerencias opcionales.{RESET}\n")
        else:
            print(f"{GREEN}✓ ¡Excelente! Todas las dependencias y herramientas están listas y configuradas.{RESET}\n")

