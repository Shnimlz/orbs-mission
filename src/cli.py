"""
Command-line interface module.
Provides interactive console prompts with ANSI styling, colors, screen clearing,
typewriter text animations, box borders, and argparse command parsing using standard library only.
"""

import argparse
import sys
import time
import threading
from pathlib import Path
from typing import Optional

# ANSI Style Definitions
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

# Colors
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
RED = "\033[91m"
WHITE = "\033[97m"


def clear_screen():
    """Clears the terminal screen cleanly using ANSI escape sequences."""
    if sys.stdout.isatty():
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()


def animate_text(text: str, delay: float = 0.012, end: str = "\n"):
    """Prints text with a typewriter effect if connected to an interactive TTY."""
    if sys.stdout.isatty():
        for char in text:
            sys.stdout.write(char)
            sys.stdout.flush()
            time.sleep(delay)
        sys.stdout.write(end)
        sys.stdout.flush()
    else:
        print(text, end=end)


def print_banner(animated: bool = True):
    """Renders styled ASCII banner header with optional fade/typewriter animation."""
    if animated and sys.stdout.isatty():
        clear_screen()

    banner_lines = [
        f"{MAGENTA}    __      __.__          ________   _____  {RESET}",
        f"{MAGENTA}   /  \\    /  \\__| ____   /  _____/  /  |  | {RESET}",
        f"{CYAN}   \\   \\/\\/   /  |/    \\ /   \\  ___ /   |  |_{RESET}",
        f"{CYAN}    \\        /|  |   |  \\\\    \\_\\  /    ^   /{RESET}",
        f"{BLUE}     \\__/\\  / |__|___|  / \\______  /\\____|_| {RESET}",
        f"{BLUE}          \\/          \\/         \\/          {RESET}",
    ]

    for line in banner_lines:
        print(line)
        if animated and sys.stdout.isatty():
            time.sleep(0.03)

    print("\n" + f"{CYAN}╭────────────────────────────────────────────────────────╮{RESET}")
    print(f"{CYAN}│{RESET} {BOLD}{WHITE}   Win64 Template Builder{RESET} {DIM}(Cross-Platform CLI){RESET}          {CYAN}│{RESET}")
    print(f"{CYAN}╰────────────────────────────────────────────────────────╯{RESET}\n")


class Spinner:
    """Animated CLI spinner using standard library threading."""

    SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, message: str = "Procesando"):
        self.message = message
        self._stop_event = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def _spin(self):
        idx = 0
        while not self._stop_event.is_set():
            frame = self.SPINNER_FRAMES[idx % len(self.SPINNER_FRAMES)]
            sys.stdout.write(f"\r  {CYAN}{frame}{RESET} {self.message}...")
            sys.stdout.flush()
            idx += 1
            time.sleep(0.07)

    def start(self):
        if sys.stdout.isatty():
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()
        else:
            print(f"  ... {self.message}")

    def stop(self, success_message: Optional[str] = None):
        if self._thread and self._thread.is_alive():
            self._stop_event.set()
            self._thread.join()
        if sys.stdout.isatty():
            sys.stdout.write("\r\033[K")  # Clear line
            if success_message:
                print(f"  {GREEN}✓{RESET} {success_message}")
            sys.stdout.flush()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self.stop()
        else:
            self.stop()
            print(f"  {RED}✗ Error:{RESET} {exc_val}")


def parse_args(args: Optional[list] = None) -> argparse.Namespace:
    """Parses command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="win64-builder",
        description="Cross-Platform Win64 Template Builder CLI"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Subcommand: inspect
    inspect_parser = subparsers.add_parser("inspect", help="Inspect template RAR structure without modifying anything")
    inspect_parser.add_argument("--template", type=Path, default=Path("Win64.rar"), help="Path to template Win64.rar")

    # Subcommand: clean
    clean_parser = subparsers.add_parser("clean", help="Clean win64-builder temporary artifacts and cache")
    clean_parser.add_argument("--dir", type=Path, default=Path("."), help="Directory to search for temporary artifacts")

    # Main builder options
    parser.add_argument("--template", type=Path, default=Path("Win64.rar"), help="Path to template Win64.rar")
    parser.add_argument("--folder", type=str, help="Main root folder name")
    parser.add_argument("--exe", type=str, help="Target executable name")
    parser.add_argument("--layout", choices=["direct", "steam", "custom"], help="Layout preset: direct, steam, custom")
    parser.add_argument("--output", type=Path, default=Path("./output"), help="Base output directory")
    parser.add_argument("--steam-library", type=Path, help="Explicit Steam library directory (for steam layout)")
    parser.add_argument("--custom-path", type=str, help="Custom relative path (for custom layout)")
    parser.add_argument("--collision", choices=["cancel", "replace", "incremental"], default="cancel", help="Existing directory handling")
    parser.add_argument("--dry-run", action="store_true", help="Simulate build without modifying filesystem")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging output")

    return parser.parse_args(args)


def run_interactive_prompts(config, candidate_exe: Optional[str] = None):
    """
    Runs interactive prompts with rich ANSI animations, typewriter text, and inputs.
    """
    from src.validators import validate_name, validate_executable_name, validate_relative_path

    print_banner(animated=True)

    animate_text(f"{BOLD}Plantilla detectada:{RESET} {CYAN}{config.template_path.resolve()}{RESET}\n", delay=0.008)

    # Prompt Folder Name
    if not config.folder_name:
        animate_text(f"{BOLD}1. Nombre de la carpeta principal:{RESET}", delay=0.008)
        while True:
            val = input(f"{CYAN}❯ {RESET}").strip()
            try:
                validate_name(val, item_type="Folder name")
                config.folder_name = val
                break
            except ValueError as e:
                print(f"  {RED}⚠ {e}{RESET}")

    # Prompt Executable Name
    if not config.exe_name:
        default_hint = f" {DIM}(default: {candidate_exe}){RESET}" if candidate_exe else ""
        animate_text(f"\n{BOLD}2. Nombre del ejecutable:{RESET}{default_hint}", delay=0.008)
        while True:
            val = input(f"{CYAN}❯ {RESET}").strip()
            if not val and candidate_exe:
                val = candidate_exe
            try:
                config.exe_name = validate_executable_name(val)
                break
            except ValueError as e:
                print(f"  {RED}⚠ {e}{RESET}")

    # Prompt Layout Type
    if not config.layout_type:
        animate_text(f"\n{BOLD}3. Tipo de estructura:{RESET}", delay=0.008)
        print(f"  {CYAN}[1]{RESET} Carpeta directa {DIM}(Output / FolderName){RESET}")
        print(f"  {CYAN}[2]{RESET} Estructura Steam {DIM}(Output / steamapps / common / FolderName){RESET}")
        print(f"  {CYAN}[3]{RESET} Ruta personalizada {DIM}(Custom layout){RESET}")
        while True:
            choice = input(f"\n{CYAN}❯ {RESET}").strip()
            if choice == "1":
                config.layout_type = "direct"
                break
            elif choice == "2":
                config.layout_type = "steam"
                break
            elif choice == "3":
                config.layout_type = "custom"
                break
            else:
                print(f"  {RED}⚠ Opción inválida. Seleccione 1, 2 o 3.{RESET}")

    # Additional prompts depending on layout
    if config.layout_type == "custom" and not config.custom_path:
        animate_text(f"\n{BOLD}Ruta relativa personalizada:{RESET} {DIM}(ej. steamapps/common/MyGame/Binaries/Win64){RESET}", delay=0.008)
        while True:
            val = input(f"{CYAN}❯ {RESET}").strip()
            try:
                validate_relative_path(val)
                config.custom_path = val
                break
            except ValueError as e:
                print(f"  {RED}⚠ {e}{RESET}")

    # Prompt Output Directory if default
    if str(config.output_dir) == "./output":
        animate_text(f"\n{BOLD}Directorio de salida:{RESET} {DIM}(default: {config.output_dir}){RESET}", delay=0.008)
        user_out = input(f"{CYAN}❯ {RESET}").strip()
        if user_out:
            config.output_dir = Path(user_out)

    return config
