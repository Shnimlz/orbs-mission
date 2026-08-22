"""
Command-line interface module.
Provides interactive console prompts with ANSI styling, colors, screen clearing,
typewriter text animations, box borders, and argparse command parsing using standard library only.
"""

import argparse
import os
import sys
import time
import platform
import threading
from pathlib import Path
from typing import Optional, List

from src.plan import BuildPlan, DirectoryArtifact, FileArtifact
from src.profiles import Profile, ProfileManager

# Windows Console initialization: enable VT100 ANSI escapes and UTF-8 output
if sys.platform == "win32":
    os.system("")  # Enables ANSI VT100 escape sequence processing in Windows cmd/conhost
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ANSI Style Definitions
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"

# Modern Neon Gradient Palette
CYAN = "\033[38;5;51m"
PURPLE = "\033[38;5;141m"
PINK = "\033[38;5;213m"
BLUE = "\033[38;5;39m"
GREEN = "\033[38;5;48m"
YELLOW = "\033[38;5;221m"
AMBER = "\033[38;5;215m"
RED = "\033[38;5;203m"
MAGENTA = "\033[38;5;207m"
WHITE = "\033[97m"
MUTED = "\033[38;5;244m"
DARK_GRAY = "\033[38;5;238m"
BG_SEL = "\033[48;5;236m"
BG_BADGE = "\033[48;5;235m"


def clear_screen():
    """Clears the terminal screen cleanly using ANSI escape sequences or cls on Windows."""
    if sys.stdout.isatty():
        if sys.platform == "win32":
            os.system("cls")
        else:
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
    """Renders styled modern ASCII banner header with purple/cyan gradient."""
    if animated and sys.stdout.isatty():
        clear_screen()

    banner_lines = [
        f"{PURPLE}  ██╗    ██╗██╗███╗   ██╗ ██████╗ ██╗  ██╗{RESET}",
        f"{PINK}  ██║    ██║██║████╗  ██║██╔════╝ ██║  ██║{RESET}",
        f"{BLUE}  ██║ █╗ ██║██║██╔██╗ ██║███████╗ ███████║{RESET}",
        f"{CYAN}  ██║███╗██║██║██║╚██╗██║██╔═══██╗╚════██║{RESET}",
        f"{CYAN}  ╚███╔███╔╝██║██║ ╚████║╚██████╔╝     ██║{RESET}",
        f"{MUTED}   ╚══╝╚══╝ ╚═╝╚═╝  ╚═══╝ ╚═════╝      ╚═╝{RESET}",
    ]

    for line in banner_lines:
        print(line)
        if animated and sys.stdout.isatty():
            time.sleep(0.012)

    print(f"{PURPLE}  ╭───────────────────────────────────────────────────────────────╮{RESET}")
    print(f"{PURPLE}  │{RESET}  {BOLD}{WHITE}✦ WIN64 TEMPLATE BUILDER{RESET}                      {DIM}{CYAN}v1.4.0-alpha{RESET} {PURPLE}│{RESET}")
    print(f"{PURPLE}  │{RESET}  {DIM}Cross-Platform Profile Recipe & Multi-Artifact Generator    {PURPLE}│{RESET}")
    print(f"{PURPLE}  ╰───────────────────────────────────────────────────────────────╯{RESET}\n")


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
        description="Cross-Platform Win64 Template Builder & Profile Recipe Manager"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Subcommand: inspect
    inspect_parser = subparsers.add_parser("inspect", help="Inspect template RAR structure without modifying anything")
    inspect_parser.add_argument("--template", type=Path, default=Path("Win64.rar"), help="Path to template Win64.rar")

    # Subcommand: clean
    clean_parser = subparsers.add_parser("clean", help="Clean win64-builder temporary artifacts and cache")
    clean_parser.add_argument("--dir", type=Path, default=Path("."), help="Directory to search for temporary artifacts")

    # Subcommand: profile
    profile_parser = subparsers.add_parser("profile", help="Manage and inspect application profiles")
    profile_subparsers = profile_parser.add_subparsers(dest="profile_action", help="Profile actions")

    profile_list_parser = profile_subparsers.add_parser("list", help="List available application profiles")
    profile_list_parser.add_argument("--dir", type=Path, default=Path("profiles"), help="Profiles directory")

    profile_inspect_parser = profile_subparsers.add_parser("inspect", help="Inspect a specific profile")
    profile_inspect_parser.add_argument("profile_name", type=str, help="Name or path of profile to inspect")
    profile_inspect_parser.add_argument("--dir", type=Path, default=Path("profiles"), help="Profiles directory")

    # Subcommand: doctor
    doctor_parser = subparsers.add_parser("doctor", help="Run comprehensive system and dependency health check")
    doctor_parser.add_argument("--template", type=Path, default=Path("Win64.rar"), help="Path to template Win64.rar")

    # Main builder options
    parser.add_argument("--profile", type=str, help="Application profile name or JSON file path")
    parser.add_argument("--template", type=Path, default=Path("Win64.rar"), help="Path to template Win64.rar")
    parser.add_argument("--folder", type=str, help="Main root folder name")
    parser.add_argument("--exe", type=str, help="Target executable name")
    parser.add_argument("--layout", choices=["direct", "steam", "custom"], help="Layout preset: direct, steam, custom")
    parser.add_argument("--output", type=Path, default=Path("./output"), help="Base output directory")
    parser.add_argument("--steam-library", type=Path, help="Explicit Steam library directory (for steam layout)")
    parser.add_argument("--custom-path", type=str, help="Custom relative path (for custom layout)")
    parser.add_argument("--collision", choices=["cancel", "replace", "incremental"], default="cancel", help="Existing directory handling")
    parser.add_argument("--assets-root", type=Path, default=Path("profiles/assets"), help="Assets root directory for companion files")
    parser.add_argument("--allow-external-destination", action="store_true", help="Allow writing artifacts outside base output directory")
    parser.add_argument("--list-folders", action="store_true", help="List existing game folders found in the output directory")
    parser.add_argument("--doctor", action="store_true", help="Run system and dependency diagnostics")
    parser.add_argument("--wine", "--run", action="store_true", dest="run_wine", help="Execute the target executable with Wine after build/rename")
    parser.add_argument("--dry-run", action="store_true", help="Simulate build without modifying filesystem")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging output")

    return parser.parse_args(args)


def read_raw_key() -> str:
    """
    Reads a single keypress or key sequence from standard input in raw mode.
    Returns: 'up', 'down', 'left', 'right', 'enter', 'escape', 'backspace', 'tab', 'space',
    or the character string (e.g. '1', 'a', etc.).
    """
    if not sys.stdin.isatty():
        line = sys.stdin.readline()
        return line.strip()

    if sys.platform == "win32":
        import msvcrt
        try:
            ch = msvcrt.getwch()
            if ch in ("\x00", "\xe0"):
                ch2 = msvcrt.getwch()
                key_map = {
                    "H": "up",
                    "P": "down",
                    "K": "left",
                    "M": "right",
                    "G": "home",
                    "O": "end",
                    "S": "delete",
                }
                return key_map.get(ch2, "")
            if ch in ("\r", "\n"):
                return "enter"
            if ch == "\x1b":
                return "escape"
            if ch == "\x08":
                return "backspace"
            if ch == "\t":
                return "tab"
            if ch == " ":
                return "space"
            if ch == "\x03":
                raise KeyboardInterrupt
            return ch
        except Exception:
            return ""
    else:
        import select
        try:
            import termios
            import tty

            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(fd)
                raw_bytes = os.read(fd, 32)
                if not raw_bytes:
                    return ""
                # If a single escape byte was read, give a tiny window for subsequent arrow sequence bytes
                if raw_bytes == b"\x1b":
                    r, _, _ = select.select([fd], [], [], 0.05)
                    if r:
                        raw_bytes += os.read(fd, 31)

                # Match arrow sequences
                if raw_bytes in (b"\x1b[A", b"\x1bOA", b"\x1b[1;2A", b"\x1b[1;5A"):
                    return "up"
                elif raw_bytes in (b"\x1b[B", b"\x1bOB", b"\x1b[1;2B", b"\x1b[1;5B"):
                    return "down"
                elif raw_bytes in (b"\x1b[C", b"\x1bOC", b"\x1b[1;2C", b"\x1b[1;5C"):
                    return "right"
                elif raw_bytes in (b"\x1b[D", b"\x1bOD", b"\x1b[1;2D", b"\x1b[1;5D"):
                    return "left"
                elif raw_bytes in (b"\r", b"\n", b"\r\n"):
                    return "enter"
                elif raw_bytes == b"\x1b":
                    return "escape"
                elif raw_bytes in (b"\x7f", b"\x08"):
                    return "backspace"
                elif raw_bytes == b"\t":
                    return "tab"
                elif raw_bytes == b" ":
                    return "space"
                elif raw_bytes == b"\x03":
                    raise KeyboardInterrupt
                elif raw_bytes == b"\x04":
                    raise EOFError
                try:
                    return raw_bytes.decode("utf-8", errors="ignore")
                except Exception:
                    return ""
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        except Exception:
            try:
                line = sys.stdin.readline()
                return line.strip()
            except Exception:
                return ""


class MenuItem:
    """Represents a selectable item within an interactive menu."""

    def __init__(self, key: str, label: str, detail: str = "", is_back: bool = False):
        self.key = key
        self.label = label
        self.detail = detail
        self.is_back = is_back


def interactive_menu_selection(
    items: List[MenuItem],
    title_box: Optional[str] = None,
    subtitle: Optional[str] = None,
    default_index: int = 0,
    back_key: str = "0",
    footer_hint: Optional[str] = None,
) -> str:
    """
    Renders an interactive menu navigated via Arrow Keys (Up/Down/Left/Right), Enter, Esc, or Direct Keys.
    - Up / Down: Navegar entre opciones
    - Right / Enter: Adelante (Seleccionar opción actual)
    - Left / Esc / q: Atrás (Volver / Salir) -> devuelve back_key
    - Tecla directa ('0', '1', '2'...): Selecciona directamente la opción
    """
    if not items:
        return back_key

    # Fallback if standard input/output is not an interactive terminal
    if not sys.stdin.isatty() or not sys.stdout.isatty():
        if title_box:
            print(f"  {CYAN}─── ◈ {title_box} ──────────────────────────────────────────{RESET}")
        if subtitle:
            print(f"  {subtitle}\n")
        for itm in items:
            detail_str = f" {MUTED}{itm.detail}{RESET}" if itm.detail else ""
            print(f"    [{itm.key}] {itm.label}{detail_str}")
        print()
        try:
            val = input(f"{CYAN}Selecciona una opción ❯ {RESET}").strip()
            return val if val else back_key
        except (EOFError, KeyboardInterrupt):
            print()
            return back_key

    selected_idx = max(0, min(default_index, len(items) - 1))
    item_key_map = {itm.key: idx for idx, itm in enumerate(items)}

    if subtitle:
        print(f"  {subtitle}\n")
    if title_box:
        print(f"  {CYAN}─── ◈ {title_box} ──────────────────────────────────────────{RESET}\n")

    default_footer = f"{MUTED}  [ ↑/↓ ] Navegar   [ Enter/→ ] Seleccionar   [ Esc/← ] Atrás   [ 0-{len(items)-1} ] Atajos{RESET}"
    footer = footer_hint if footer_hint is not None else default_footer

    def render_menu(current_idx: int, is_first: bool = False):
        lines = []
        for idx, itm in enumerate(items):
            is_selected = idx == current_idx
            detail_str = f" {MUTED}{itm.detail}{RESET}" if itm.detail else ""
            if is_selected:
                if itm.is_back:
                    lines.append(f"  {RED}{BOLD}➜{RESET} {BG_SEL}{RED}{BOLD} [ {itm.key} ] {RESET}{BG_SEL} {BOLD}{WHITE}{itm.label} {RESET}{detail_str}")
                else:
                    lines.append(f"  {CYAN}{BOLD}➜{RESET} {BG_SEL}{CYAN}{BOLD} [ {itm.key} ] {RESET}{BG_SEL} {BOLD}{WHITE}{itm.label} {RESET}{detail_str} {CYAN}✦{RESET}")
            else:
                if itm.is_back:
                    lines.append(f"     {DIM}[ {itm.key} ]  {itm.label}{detail_str}{RESET}")
                else:
                    lines.append(f"     {DIM}[ {itm.key} ]{RESET}  {itm.label}{detail_str}")
        lines.append("")
        lines.append(f"  {DARK_GRAY}────────────────────────────────────────────────────────────────{RESET}")
        lines.append(footer)

        if is_first:
            for l in lines:
                print(l)
        else:
            num_lines = len(lines)
            sys.stdout.write(f"\033[{num_lines}A\r")
            for l in lines:
                sys.stdout.write(f"\033[2K{l}\n")
            sys.stdout.flush()

    # Hide cursor during menu navigation for fluid appearance
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    try:
        render_menu(selected_idx, is_first=True)

        while True:
            key = read_raw_key()

            if key in ("up", "w", "W", "k", "K"):
                selected_idx = (selected_idx - 1) % len(items)
                render_menu(selected_idx)
            elif key in ("down", "s", "S", "j", "J"):
                selected_idx = (selected_idx + 1) % len(items)
                render_menu(selected_idx)
            elif key in ("enter", "right", "space", "d", "D", "l", "L", " "):
                # Forward / Select
                return items[selected_idx].key
            elif key in ("left", "a", "A", "h", "H", "escape", "backspace", "q", "Q"):
                # Back / Atrás
                return back_key
            elif key in item_key_map:
                # Direct key shortcut
                return key
    except KeyboardInterrupt:
        return back_key
    finally:
        # Restore terminal cursor
        sys.stdout.write("\033[?25h\n")
        sys.stdout.flush()


def display_main_menu(status_line: str, animated: bool = True) -> str:
    """Renders the top-level interactive application menu with arrow navigation and shortcuts."""
    print_banner(animated=animated)

    menu_items = [
        MenuItem("1", "🚀 Crear nueva estructura / Aplicar perfil"),
        MenuItem("2", "📁 Ver carpetas ya hechas", "(explorar, renombrar exe, ejecutar)"),
        MenuItem("3", "📋 Ver plantillas y perfiles disponibles"),
        MenuItem("4", "🩺 Diagnóstico del sistema y dependencias", "(Linux / Windows)"),
        MenuItem("5", "🧹 Limpiar artefactos temporales"),
        MenuItem("0", "🚪 Salir", is_back=True),
    ]

    return interactive_menu_selection(
        items=menu_items,
        title_box="MENÚ PRINCIPAL",
        subtitle=status_line,
        default_index=0,
        back_key="0",
    )


def run_select_profile_prompt(profiles_dir: Path = Path("profiles")) -> Optional[Profile]:
    """Displays available profiles with arrow navigation and allows user to pick one or choose manual/back."""
    profiles = ProfileManager.list_profiles(profiles_dir)
    if not profiles:
        print(f"\n  {DIM}(No se encontraron perfiles en {profiles_dir}){RESET}\n")
        return None

    items = []
    for idx, p in enumerate(profiles, 1):
        items.append(
            MenuItem(
                key=str(idx),
                label=f"{p.display_name} ({p.name})",
                detail=f"- Layout: {p.layout}, Exe: {p.executable_name}",
            )
        )
    items.append(MenuItem("0", "⚙️  Configuración personalizada (manual)", is_back=True))

    choice = interactive_menu_selection(
        items=items,
        title_box="SELECCIONAR PERFIL DE JUEGO",
        subtitle="Elige un perfil preconfigurado o selecciona manual.",
        default_index=0,
        back_key="0",
        footer_hint=f"{MUTED}  [ ↑/↓ ] Navegar   [ Enter/→ ] Seleccionar   [ Esc/← ] Volver / Manual   [ 0-{len(profiles)} ] Atajos{RESET}",
    )

    if choice == "0" or not choice or not choice.isdigit():
        return None

    idx = int(choice) - 1
    if 0 <= idx < len(profiles):
        return profiles[idx]
    return None


def run_manage_existing_folders_menu(output_dir: Path, source_exe_name: Optional[str] = None) -> None:
    """Sub-menu to explore, execute, or rename executables in existing game folders with arrow navigation."""
    from src.filesystem import FilesystemBuilder
    from src.runner import WineRunner
    from src.validators import validate_executable_name

    while True:
        folders = FilesystemBuilder.discover_existing_folders(output_dir)
        print_banner(animated=True)

        if not folders:
            print(f"  {CYAN}─── ◈ CARPETAS YA CREADAS ({output_dir}) ──────────────────────────{RESET}\n")
            print(f"  {DIM}(No hay carpetas generadas en {output_dir}){RESET}\n")
            input(f"  {MUTED}Presiona Enter para volver...{RESET}")
            return

        folder_items = []
        for idx, fld in enumerate(folders, 1):
            exe_str = f"[{fld.executables[0]}]" if fld.executables else "[sin .exe]"
            folder_items.append(
                MenuItem(
                    key=str(idx),
                    label=fld.name,
                    detail=f"[{fld.layout}] {exe_str}",
                )
            )
        folder_items.append(MenuItem("0", "↩️  Volver al menú principal", is_back=True))

        choice = interactive_menu_selection(
            items=folder_items,
            title_box=f"CARPETAS YA CREADAS ({output_dir})",
            subtitle="Selecciona una carpeta para ejecutarla o renombrar su ejecutable.",
            default_index=0,
            back_key="0",
            footer_hint=f"{MUTED}  [ ↑/↓ ] Navegar   [ Enter/→ ] Abrir carpeta   [ Esc/← ] Volver   [ 0-{len(folders)} ] Atajos{RESET}",
        )

        if choice == "0" or not choice or not choice.isdigit():
            return

        idx = int(choice) - 1
        if not (0 <= idx < len(folders)):
            continue

        chosen_folder = folders[idx]

        # Action sub-menu for selected folder
        action_items = [
            MenuItem("1", "▶️   Ejecutar aplicación", f"({chosen_folder.executables[0] if chosen_folder.executables else 'sin exe'})"),
            MenuItem("2", "✏️   Renombrar ejecutable .exe"),
            MenuItem("0", "↩️   Volver a la lista de carpetas", is_back=True),
        ]

        sub_choice = interactive_menu_selection(
            items=action_items,
            title_box="ACCIONES DE CARPETA",
            subtitle=f"Carpeta: {chosen_folder.name} ({chosen_folder.path})",
            default_index=0,
            back_key="0",
            footer_hint=f"{MUTED}  [ ↑/↓ ] Navegar   [ Enter/→ ] Confirmar   [ Esc/← ] Volver atrás{RESET}",
        )

        if sub_choice == "1":
            if chosen_folder.executables:
                target_exe_path = chosen_folder.path / chosen_folder.executables[0]
                WineRunner.run(target_exe_path)
            else:
                print(f"\n  {RED}✗ No se encontró ningún .exe en esta carpeta.{RESET}")
            input(f"\n{MUTED}Presiona Enter para continuar...{RESET}")

        elif sub_choice == "2":
            curr_exe = chosen_folder.executables[0] if chosen_folder.executables else "NuevoNombre.exe"
            print(f"\n{BOLD}Nombre actual:{RESET} {CYAN}{curr_exe}{RESET}")
            new_exe_raw = input(f"{CYAN}Nuevo nombre del .exe ❯ {RESET}").strip()
            if new_exe_raw:
                try:
                    new_exe_clean = validate_executable_name(new_exe_raw)
                    renamed, final_p, msg = FilesystemBuilder.rename_executable_in_folder(
                        chosen_folder.path,
                        target_exe_name=new_exe_clean,
                        source_exe_name=source_exe_name,
                    )
                    if renamed:
                        print(f"\n  {GREEN}✓{RESET} {msg}")
                    else:
                        print(f"\n  {YELLOW}⚠{RESET} {msg}")
                except ValueError as e:
                    print(f"\n  {RED}⚠ {e}{RESET}")
            input(f"\n{MUTED}Presiona Enter para continuar...{RESET}")


def display_existing_folders(folders: List) -> None:
    """Renders a formatted list of discovered game folders."""
    print(f"\n{BOLD}Carpetas existentes detectadas:{RESET}\n")
    if not folders:
        print(f"  {DIM}(No se encontraron carpetas previas en el directorio de salida){RESET}\n")
        return

    for idx, folder in enumerate(folders, 1):
        exe_str = f" {CYAN}[exe: {', '.join(folder.executables)}]{RESET}" if folder.executables else f" {DIM}[sin exe detectado]{RESET}"
        layout_badge = f"{YELLOW}[{folder.layout}]{RESET}"
        print(f"  {CYAN}[{idx}]{RESET} {BOLD}{folder.name:<25}{RESET} {layout_badge} {DIM}{folder.path}{RESET}{exe_str}")
    print()


def prompt_wine_execution(executable_path: Path) -> bool:
    """Prompts user asking if they want to execute the configured application."""
    is_windows = sys.platform == "win32" or platform.system() == "Windows"
    title = "¿Deseas ejecutar la aplicación ahora?" if is_windows else "¿Deseas ejecutarlo ahora con Wine?"
    cmd_hint = f"{executable_path.name}" if is_windows else f"wine {executable_path.name}"

    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print(f"\n  {CYAN}─── ◈ {title} ──────────────────────────────────────────{RESET}")
        print(f"  {cmd_hint}\n")
        try:
            choice = input(f"{CYAN}❯ [{GREEN}s{RESET}/{RED}N{RESET}]: {RESET}").strip().lower()
            return choice in ("s", "si", "sí", "y", "yes")
        except (EOFError, KeyboardInterrupt):
            print()
            return False

    items = [
        MenuItem("1", "🚀 Sí, ejecutar aplicación", cmd_hint),
        MenuItem("2", "↩️  No, volver al menú", is_back=True),
    ]

    choice = interactive_menu_selection(
        items=items,
        title_box=title,
        subtitle=f"Comando a ejecutar: {cmd_hint}",
        default_index=0,
        back_key="2",
        footer_hint=f"{MUTED}  [ ↑/↓ ] Navegar   [ Enter/→ ] Confirmar   [ Esc/← ] Cancelar{RESET}",
    )
    return choice == "1"


def display_build_plan(plan: BuildPlan) -> None:
    """Renders a comprehensive multi-artifact dry-run plan."""
    print(f"\n{BOLD}Profile:{RESET}")
    print(f"  {CYAN}{plan.profile_name}{RESET}\n")

    print(f"{BOLD}Build plan:{RESET}\n")

    operations = []

    for art in plan.artifacts:
        if isinstance(art, DirectoryArtifact):
            print(f"{BOLD}[Directory]{RESET}")
            print(f"{CYAN}{art.destination}/{RESET}")
            operations.append("CREATE directory tree")
            if art.source_template:
                print(f"  {DIM}├── [Template Extract]{RESET} {art.source_template.name}")
                operations.append("EXTRACT template archive")
            if art.executable_rename:
                src_exe, target_exe = art.executable_rename
                print(f"  {DIM}├── [Executable]{RESET} {GREEN}{target_exe}{RESET} {DIM}(from {src_exe}){RESET}")
                operations.append("RENAME template executable")
            for sub in art.subdirectories:
                print(f"  {DIM}├── [Subdirectory]{RESET} {sub}/")
                operations.append("ENSURE subdirectory structure")
            for emb in art.embedded_files:
                print(f"  {DIM}└── [Embedded Companion]{RESET} {emb.relative_destination} {DIM}(from {emb.source_path}){RESET}")
                operations.append("COPY embedded companion file")
            print()
        elif isinstance(art, FileArtifact):
            print(f"{BOLD}[File]{RESET}")
            print(f"{CYAN}{art.destination}{RESET} {DIM}(from {art.source_path}){RESET}")
            operations.append("COPY independent companion file")
            print()

    print(f"{BOLD}Operations:{RESET}")
    # Deduplicate operations order-preservingly
    seen_ops = set()
    for op in operations:
        if op not in seen_ops:
            print(f"  {CYAN}•{RESET} {op}")
            seen_ops.add(op)

    print(f"\n{YELLOW}No filesystem changes will be made.{RESET}\n")


def prompt_external_destinations(external_destinations: List[Path]) -> bool:
    """Prompts user for explicit confirmation when external destinations are requested."""
    print(f"\n{YELLOW}External destinations requested:{RESET}\n")
    for idx, p in enumerate(external_destinations, 1):
        print(f"  {idx}. {CYAN}{p}{RESET}")
    print(f"\n{DIM}These paths are outside the configured output root.{RESET}\n")

    if sys.stdin.isatty():
        choice = input(f"Continue? [{GREEN}y{RESET}/{RED}N{RESET}] ").strip().lower()
        return choice in ("y", "yes", "s", "sí")
    else:
        # In non-interactive mode, returning True requires --allow-external-destination was set
        return True


def run_interactive_prompts(config, candidate_exe: Optional[str] = None):
    """Runs interactive prompts with rich ANSI animations."""
    from src.validators import validate_name, validate_executable_name, validate_relative_path
    from src.filesystem import FilesystemBuilder

    print_banner(animated=True)
    animate_text(f"{BOLD}Plantilla detectada:{RESET} {CYAN}{config.template_path.resolve()}{RESET}\n", delay=0.008)

    # Discover existing folders in output directory
    existing_folders = FilesystemBuilder.discover_existing_folders(config.output_dir)

    # Prompt Folder Name
    if not config.folder_name:
        animate_text(f"{BOLD}1. Nombre de la carpeta principal:{RESET}", delay=0.008)
        if existing_folders:
            print(f"  {DIM}Carpetas existentes encontradas en {config.output_dir}:{RESET}")
            for idx, fld in enumerate(existing_folders, 1):
                exe_hint = f" {DIM}(exe: {fld.executables[0]}){RESET}" if fld.executables else ""
                print(f"    {CYAN}[{idx}]{RESET} {BOLD}{fld.name}{RESET} {DIM}[{fld.layout}]{RESET}{exe_hint}")
            print(f"  {DIM}Ingresa el número de una carpeta existente o escribe un nuevo nombre.{RESET}")

        while True:
            val = input(f"{CYAN}❯ {RESET}").strip()
            if not val:
                continue

            # Check if user picked an existing folder by index
            if existing_folders and val.isdigit():
                idx_choice = int(val)
                if 1 <= idx_choice <= len(existing_folders):
                    chosen = existing_folders[idx_choice - 1]
                    config.folder_name = chosen.name
                    if not config.layout_type:
                        config.layout_type = chosen.layout
                    if chosen.executables:
                        candidate_exe = chosen.executables[0]
                    break
                else:
                    print(f"  {RED}⚠ Opción fuera de rango (1-{len(existing_folders)}).{RESET}")
                    continue

            try:
                validate_name(val, item_type="Folder name")
                config.folder_name = val
                # If typed name matches an existing folder, inherit layout / candidate exe
                for fld in existing_folders:
                    if fld.name.lower() == val.lower():
                        if not config.layout_type:
                            config.layout_type = fld.layout
                        if fld.executables:
                            candidate_exe = fld.executables[0]
                        break
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

    # Prompt Layout Type (if not already deduced from existing folder)
    if not config.layout_type:
        layout_items = [
            MenuItem("1", "📁 Carpeta directa", "(Output / FolderName)"),
            MenuItem("2", "🚂 Estructura Steam", "(Output / steamapps / common / FolderName)"),
            MenuItem("3", "🛠️  Ruta personalizada", "(Custom layout)"),
        ]
        choice = interactive_menu_selection(
            items=layout_items,
            title_box="TIPO DE ESTRUCTURA",
            subtitle="Selecciona cómo se organizará la estructura de directorios.",
            default_index=0,
            back_key="1",
        )
        if choice == "2":
            config.layout_type = "steam"
        elif choice == "3":
            config.layout_type = "custom"
        else:
            config.layout_type = "direct"

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

    # Prompt Output Directory if default and wasn't changed
    if str(config.output_dir) == "./output":
        animate_text(f"\n{BOLD}Directorio de salida:{RESET} {DIM}(default: {config.output_dir}){RESET}", delay=0.008)
        user_out = input(f"{CYAN}❯ {RESET}").strip()
        if user_out:
            config.output_dir = Path(user_out)

    return config

