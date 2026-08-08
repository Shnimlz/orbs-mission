#!/usr/bin/env python3
"""
Win64 Template Builder
Cross-platform CLI tool to generate custom folder structures from an immutable Win64 template.
"""

import sys
import platform
import shutil
import time
from pathlib import Path

from src.cli import (
    parse_args,
    run_interactive_prompts,
    print_banner,
    clear_screen,
    animate_text,
    Spinner,
    CYAN,
    GREEN,
    YELLOW,
    RED,
    BOLD,
    DIM,
    RESET,
)
from src.config import BuildConfig
from src.template import TemplateManager
from src.validators import validate_executable_name, validate_name
from src.layouts import DirectLayout, SteamLayout, CustomLayout
from src.filesystem import FilesystemBuilder, CollisionMode


def run_inspect(template_path: Path) -> int:
    try:
        print_banner(animated=True)
        with Spinner("Inspeccionando archivo de plantilla Win64.rar") as sp:
            time.sleep(0.3)
            manager = TemplateManager(template_path)
            info = manager.inspect()

        print(f"{CYAN}╭────────────────────────────────────────────────────────╮{RESET}")
        print(f"{CYAN}│{RESET} {BOLD}Plantilla:{RESET} {info['archive_path']:<44} {CYAN}│{RESET}")
        print(f"{CYAN}╰────────────────────────────────────────────────────────╯{RESET}")

        print(f"\n{BOLD}Root:{RESET}\n  {CYAN}{info['root']}/{RESET}")
        print(f"\n{BOLD}Directorios / Idiomas:{RESET}")
        for lang in info["languages"]:
            print(f"  {DIM}├──{RESET} {lang}/")

        print(f"\n{BOLD}Archivos detectados:{RESET}")
        for dll in info["dlls"]:
            print(f"  {DIM}├──{RESET} {GREEN}{dll}{RESET}")
        for exe in info["executables"]:
            print(f"  {DIM}├──{RESET} {CYAN}{exe}{RESET}")
        for other in info["other_files"]:
            print(f"  {DIM}├──{RESET} {other}")

        print(f"\n{BOLD}Candidatos a ejecutable raíz:{RESET}")
        for exe in info["executables"]:
            print(f"  {CYAN}➜{RESET} {BOLD}{exe}{RESET}")

        print(f"\n{BOLD}Estado:{RESET}\n  {GREEN}✓ Plantilla válida e inmutable{RESET}\n")
        return 0
    except Exception as e:
        print(f"\n{RED}Status:{RESET}\n  {RED}✗ Inspección fallida: {e}{RESET}\n", file=sys.stderr)
        return 1


def run_clean(target_dir: Path) -> int:
    print_banner(animated=False)
    print(f"Limpiando artefactos de win64-builder en {CYAN}{target_dir.resolve()}{RESET}...")
    with Spinner("Buscando artefactos temporales") as sp:
        time.sleep(0.2)
        removed = FilesystemBuilder.clean_owned_artifacts(target_dir)

    if removed:
        for r in removed:
            print(f"  {GREEN}✓{RESET} Removido: {r}")
    else:
        print(f"  {DIM}No se encontraron artefactos temporales.{RESET}")
    print()
    return 0


def main() -> int:
    args = parse_args()

    if args.command == "inspect":
        return run_inspect(args.template)
    elif args.command == "clean":
        return run_clean(args.dir)

    # Initialize configuration
    config = BuildConfig(
        template_path=args.template,
        folder_name=args.folder or "",
        exe_name=args.exe or "",
        layout_type=args.layout or "",
        output_dir=args.output,
        steam_library=args.steam_library,
        custom_path=args.custom_path or "",
        collision_mode=args.collision,
        dry_run=args.dry_run,
        verbose=args.verbose,
    )

    # Validate template existence
    if not config.template_path.is_file():
        print(f"{RED}Error: Archivo de plantilla no encontrado: {config.template_path}{RESET}", file=sys.stderr)
        return 1

    template_mgr = TemplateManager(config.template_path)

    try:
        with Spinner("Validando plantilla base"):
            inspection = template_mgr.inspect()
    except Exception as e:
        print(f"{RED}Error inspeccionando la plantilla: {e}{RESET}", file=sys.stderr)
        return 1

    candidates = inspection["executables"]
    if not candidates:
        print(f"{RED}Error: No se encontraron ejecutables .exe en el raíz del template.{RESET}", file=sys.stderr)
        return 1

    # Select candidate executable
    source_exe_name = candidates[0]

    # Run interactive prompts if missing parameters and stdin is a TTY
    if sys.stdin.isatty() and not (config.folder_name and config.exe_name and config.layout_type):
        config = run_interactive_prompts(config, candidate_exe=source_exe_name)

    if not config.folder_name or not config.exe_name or not config.layout_type:
        print(f"{RED}Error: Faltan argumentos requeridos. Ejecute de forma interactiva o pase --folder, --exe, --layout.{RESET}", file=sys.stderr)
        return 1

    # Validate names
    try:
        validate_name(config.folder_name, item_type="Folder name")
        config.exe_name = validate_executable_name(config.exe_name)
    except ValueError as e:
        print(f"{RED}Error de validación: {e}{RESET}", file=sys.stderr)
        return 1

    # Resolve layout
    if config.layout_type == "direct":
        layout = DirectLayout(config.folder_name)
    elif config.layout_type == "steam":
        game_name = config.folder_name
        layout = SteamLayout(game_name, steam_library=config.steam_library)
    elif config.layout_type == "custom":
        if not config.custom_path:
            print(f"{RED}Error: El layout custom requiere --custom-path.{RESET}", file=sys.stderr)
            return 1
        layout = CustomLayout(config.custom_path)
    else:
        print(f"{RED}Error: Tipo de layout desconocido '{config.layout_type}'.{RESET}", file=sys.stderr)
        return 1

    target_destination = layout.resolve_destination(config.output_dir)

    # Collision mode enum conversion
    col_mode = CollisionMode(config.collision_mode)

    # Preview summary box with clear screen if interactive
    if sys.stdin.isatty() and not config.dry_run:
        clear_screen()
        print_banner(animated=False)

    print("\n" + f"{CYAN}╭─────────────────── Resumen de Configuración ───────────────────╮{RESET}")
    print(f"{CYAN}│{RESET} {BOLD}Carpeta:{RESET}    {config.folder_name:<50} {CYAN}│{RESET}")
    print(f"{CYAN}│{RESET} {BOLD}Ejecutable:{RESET} {config.exe_name:<50} {CYAN}│{RESET}")
    print(f"{CYAN}│{RESET} {BOLD}Salida:{RESET}     {str(target_destination):<50} {CYAN}│{RESET}")
    print(f"{CYAN}╰────────────────────────────────────────────────────────────────╯{RESET}")

    # Confirm if interactive TTY
    if sys.stdin.isatty() and not config.dry_run:
        confirm = input(f"\n¿Crear esta estructura? [{GREEN}Y{RESET}/n] ").strip().lower()
        if confirm and confirm not in ("y", "yes", "s", "sí"):
            print(f"\n{YELLOW}Operación cancelada por el usuario.{RESET}")
            return 0

    if config.dry_run:
        animate_text(f"\n{BOLD}Previsualización de creación (Dry-Run):{RESET}\n", delay=0.01)
        print(f"{CYAN}{target_destination}/{RESET}")
        print(f"├── {DIM}en-US/{RESET}")
        print(f"├── {DIM}es-MX/{RESET}")
        print(f"│   └── {DIM}wordpad.exe.mui{RESET}")
        print(f"├── {GREEN}{config.exe_name}{RESET}")
        print(f"└── {CYAN}WordpadFilter.dll{RESET}")
        print(f"\n{YELLOW}Modo Dry-Run: No se modificaron archivos.{RESET}\n")
        return 0

    # Real Build Execution with Animations
    if config.verbose:
        print(f"{DIM}[platform] {platform.system()} ({platform.machine()}){RESET}")

    print()
    # Prepare staging directory as sibling
    staging_dir, build_id = FilesystemBuilder.prepare_staging_directory(target_destination)

    try:
        # Step 1: Extract template
        with Spinner("Extrayendo plantilla base") as sp:
            temp_extract_root = staging_dir / ".extract_tmp"
            template_mgr.extract_to(temp_extract_root)
            sp.stop(f"Plantilla extraída ({config.template_path.name})")

        # Step 2: Organize files into staging
        with Spinner("Organizando archivos en staging") as sp:
            template_root_dir = temp_extract_root / inspection["root"]
            for item in template_root_dir.iterdir():
                target_item = staging_dir / item.name
                shutil.move(str(item), str(target_item))
            shutil.rmtree(temp_extract_root, ignore_errors=True)
            sp.stop("Archivos copiados en el staging")

        # Step 3: Configure executable
        with Spinner(f"Renombrando ejecutable a {config.exe_name}") as sp:
            extracted_source_exe = staging_dir / source_exe_name
            target_exe_path = staging_dir / config.exe_name

            if extracted_source_exe.exists():
                if extracted_source_exe != target_exe_path:
                    extracted_source_exe.rename(target_exe_path)
            else:
                raise FileNotFoundError(f"Ejecutable origen '{source_exe_name}' no fue encontrado tras la extracción.")
            sp.stop(f"Ejecutable configurado: {config.exe_name}")

        # Step 4: Atomic Commit
        with Spinner("Confirmando estructura final en destino") as sp:
            final_dest = FilesystemBuilder.commit_staging(
                staging_path=staging_dir,
                destination_dir=target_destination,
                mode=col_mode,
                dry_run=False
            )
            sp.stop("Estructura confirmada exitosamente")

        print("\n" + f"{GREEN}================================================================{RESET}")
        print(f" {GREEN}✓ Operación completada con éxito!{RESET}")
        print(f" {BOLD}Resultado:{RESET} {CYAN}{final_dest}/{RESET}")
        print(f"{GREEN}================================================================{RESET}\n")
        return 0

    except Exception as e:
        print(f"\n{RED}✗ Falló el proceso de construcción: {e}{RESET}", file=sys.stderr)
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
