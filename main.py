#!/usr/bin/env python3
"""
Win64 Template Builder & Profile Recipe Manager
Cross-platform CLI tool to generate custom multi-artifact folder structures from immutable templates.
"""

import sys
import platform
import shutil
import time
from pathlib import Path
from typing import Optional

from src.cli import (
    parse_args,
    run_interactive_prompts,
    print_banner,
    clear_screen,
    animate_text,
    display_build_plan,
    display_existing_folders,
    display_main_menu,
    run_select_profile_prompt,
    run_manage_existing_folders_menu,
    prompt_wine_execution,
    prompt_external_destinations,
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
from src.profiles import Profile, ProfileManager, SchemaValidationError
from src.plan import PlanBuilder, DirectoryArtifact, FileArtifact
from src.filesystem import FilesystemBuilder
from src.transaction import CollisionMode
from src.runner import WineRunner
from src.doctor import SystemDoctor


def run_inspect(template_path: Path) -> int:
    try:
        print(f"\n{CYAN}╭────────────────────────────────────────────────────────╮{RESET}")
        print(f"{CYAN}│{RESET} {BOLD}📋 Inspección de Plantilla Base{RESET}                          {CYAN}│{RESET}")
        print(f"{CYAN}╰────────────────────────────────────────────────────────╯{RESET}\n")
        with Spinner("Inspeccionando archivo de plantilla Win64.rar") as sp:
            time.sleep(0.2)
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
        print(f"\n{RED}Error:{RESET} {e}\n", file=sys.stderr)
        return 1


def run_clean(target_dir: Path) -> int:
    print(f"\n{CYAN}╭────────────────────────────────────────────────────────╮{RESET}")
    print(f"{CYAN}│{RESET} {BOLD}🧹 Limpieza de Artefactos Temporales{RESET}                   {CYAN}│{RESET}")
    print(f"{CYAN}╰────────────────────────────────────────────────────────╯{RESET}\n")
    print(f"Limpiando artefactos de win64-builder en {CYAN}{target_dir.resolve()}{RESET}...")
    with Spinner("Buscando artefactos temporales") as sp:
        time.sleep(0.1)
        removed = FilesystemBuilder.clean_owned_artifacts(target_dir)

    if removed:
        for r in removed:
            print(f"  {GREEN}✓{RESET} Removido: {r}")
    else:
        print(f"  {DIM}No se encontraron artefactos temporales.{RESET}")
    print()
    return 0


def run_profile_list(profiles_dir: Path) -> int:
    profiles = ProfileManager.list_profiles(profiles_dir)
    print(f"\n{BOLD}Available profiles:{RESET}\n")
    if not profiles:
        print(f"  {DIM}(No profiles found in {profiles_dir}){RESET}\n")
        return 0

    for prof in profiles:
        print(f"  {CYAN}{prof.name}{RESET}")
    print()
    return 0


def run_profile_inspect(profile_name: str, profiles_dir: Path) -> int:
    try:
        prof = ProfileManager.load_profile(profile_name, profiles_dir)
    except Exception as e:
        print(f"{RED}Error loading profile '{profile_name}': {e}{RESET}", file=sys.stderr)
        return 1

    print(f"\n{BOLD}Profile:{RESET} {CYAN}{prof.display_name}{RESET} ({prof.name})\n")
    print(f"{BOLD}Folder:{RESET}\n  {prof.folder_name}\n")
    print(f"{BOLD}Executable:{RESET}\n  {prof.executable_name}\n")
    print(f"{BOLD}Layout:{RESET}\n  {prof.layout}\n")

    dir_count = 1 + len(prof.additional_directories)
    comp_count = len(prof.companion_files)
    print(f"{BOLD}Artifacts:{RESET}")
    print(f"  {dir_count} directory/subdirectories")
    print(f"  {comp_count} companion file(s)\n")

    if prof.additional_directories:
        print(f"{BOLD}Additional Directories:{RESET}")
        for d in prof.additional_directories:
            print(f"  {DIM}├──{RESET} {d}")
        print()

    if prof.companion_files:
        print(f"{BOLD}Companion Files:{RESET}")
        for cf in prof.companion_files:
            print(f"  {DIM}├──{RESET} {cf.source} -> {cf.relative_destination}")
        print()

    return 0


def run_doctor(template_path: Path = Path("Win64.rar")) -> int:
    """Runs system and dependency health checks."""
    SystemDoctor.print_diagnostic_report(template_path)
    return 0


def run_build_with_config(config: BuildConfig, profile_obj: Optional[Profile] = None) -> int:
    """Core logic to plan and execute a build or in-place rename from BuildConfig."""
    # Resolve template archive path (support both Win64.rar and templates/Win64.rar)
    if not config.template_path.is_file():
        alt_template = Path("templates") / config.template_path.name
        if alt_template.is_file():
            config.template_path = alt_template
        else:
            print(f"{RED}Error: Archivo de plantilla no encontrado: {config.template_path}{RESET}", file=sys.stderr)
            return 1

    template_mgr = TemplateManager(config.template_path)

    try:
        inspection = template_mgr.inspect()
    except Exception as e:
        print(f"{RED}Error inspeccionando la plantilla: {e}{RESET}", file=sys.stderr)
        return 1

    candidates = inspection["executables"]
    source_exe_name = candidates[0] if candidates else None

    # Load or construct Profile if not provided
    if profile_obj is None:
        if config.profile_name:
            try:
                profile_obj = ProfileManager.load_profile(config.profile_name, config.profiles_dir)
            except Exception as e:
                print(f"{RED}Error loading profile: {e}{RESET}", file=sys.stderr)
                return 1
        else:
            # Interactive prompts if required arguments are missing and interactive TTY
            if sys.stdin.isatty() and not (config.folder_name and config.exe_name and config.layout_type):
                config = run_interactive_prompts(config, candidate_exe=source_exe_name)

            if not config.folder_name or not config.exe_name or not config.layout_type:
                print(f"{RED}Error: Faltan argumentos requeridos. Pase --profile o --folder, --exe, --layout.{RESET}", file=sys.stderr)
                return 1

            try:
                profile_obj = Profile(
                    name=config.folder_name,
                    display_name=config.folder_name,
                    folder_name=config.folder_name,
                    executable_name=validate_executable_name(config.exe_name),
                    layout=config.layout_type,
                    relative_game_path=config.custom_path if config.layout_type == "custom" else "",
                    additional_directories=(),
                    companion_files=(),
                )
            except Exception as e:
                print(f"{RED}Error de validación: {e}{RESET}", file=sys.stderr)
                return 1

    # Generate BuildPlan
    try:
        plan = PlanBuilder.create_plan(
            profile=profile_obj,
            output_root=config.output_dir,
            template_path=config.template_path,
            source_exe_name=source_exe_name,
            profile_assets_root=config.profile_assets_root,
            steam_library=config.steam_library,
            allow_external_destination=config.allow_external_destination,
        )
    except PermissionError as e:
        print(f"{RED}Permission error: {e}{RESET}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"{RED}BuildPlan planning error: {e}{RESET}", file=sys.stderr)
        return 1

    # Primary destination directory
    primary_dir_artifact = next((art for art in plan.artifacts if isinstance(art, DirectoryArtifact)), None)
    primary_dest = primary_dir_artifact.destination.resolve() if primary_dir_artifact else None

    # Check for external destinations and prompt if interactive
    external_dests = []
    output_resolved = config.output_dir.resolve()
    for art in plan.artifacts:
        try:
            art.destination.resolve().relative_to(output_resolved)
        except ValueError:
            external_dests.append(art.destination.resolve())

    if external_dests and sys.stdin.isatty() and not config.dry_run:
        if not prompt_external_destinations(external_dests):
            print(f"\n{YELLOW}Operación cancelada por el usuario.{RESET}")
            return 0

    # Dry-Run mode
    if config.dry_run:
        display_build_plan(plan)
        return 0

    # Execute BuildPlan or Rename In-Place if folder already exists
    col_mode = CollisionMode(config.collision_mode)
    final_exe_path: Optional[Path] = None

    print()
    try:
        # If destination folder already exists and collision mode is default cancel:
        # Rename the executable in the existing directory instead of failing or rebuilding
        if primary_dest and primary_dest.is_dir() and col_mode == CollisionMode.CANCEL:
            target_exe = profile_obj.executable_name
            with Spinner(f"Carpeta existente detectada. Renombrando ejecutable a '{target_exe}'") as sp:
                time.sleep(0.1)
                renamed, final_exe_path, msg = FilesystemBuilder.rename_executable_in_folder(
                    primary_dest,
                    target_exe_name=target_exe,
                    source_exe_name=source_exe_name
                )
                sp.stop(msg)

            final_destinations = [primary_dest]
        else:
            with Spinner("Ejecutando plan de construcción transaccional") as sp:
                final_destinations = FilesystemBuilder.execute_plan(
                    plan=plan,
                    collision_mode=col_mode
                )
                sp.stop("Estructura confirmada exitosamente")

            if primary_dest:
                final_exe_path = primary_dest / profile_obj.executable_name

        print("\n" + f"{GREEN}================================================================{RESET}")
        print(f" {GREEN}✓ Operación completada con éxito!{RESET}")
        for dest in final_destinations:
            print(f" {BOLD}Destino:{RESET} {CYAN}{dest}{RESET}")
        if final_exe_path and final_exe_path.exists():
            print(f" {BOLD}Ejecutable:{RESET} {GREEN}{final_exe_path}{RESET}")
        print(f"{GREEN}================================================================{RESET}\n")

        # Wine / Native Execution Prompt or Flag
        should_run = config.run_wine
        if not should_run and sys.stdin.isatty() and not config.dry_run and final_exe_path and final_exe_path.exists():
            should_run = prompt_wine_execution(final_exe_path)

        if should_run and final_exe_path and final_exe_path.exists():
            try:
                wine_prefix = profile_obj.platform_hints.get("winePrefix") if profile_obj.platform_hints else None
                return WineRunner.run(final_exe_path, wine_prefix=wine_prefix if wine_prefix != "default" else None)
            except Exception as e:
                print(f"\n{RED}✗ Error ejecutando aplicación:{RESET} {e}\n", file=sys.stderr)
                return 1

        return 0

    except Exception as e:
        print(f"\n{RED}✗ Falló el proceso de construcción: {e}{RESET}", file=sys.stderr)
        return 1


def run_interactive_menu() -> int:
    """Runs the top-level application menu with interactive choices."""
    while True:
        rar_candidate = Path("Win64.rar")
        if not rar_candidate.is_file() and Path("templates/Win64.rar").is_file():
            rar_candidate = Path("templates/Win64.rar")

        status_line = SystemDoctor.get_quick_status_line(rar_candidate)
        choice = display_main_menu(status_line)

        if choice == "1":
            # 1. Crear nueva estructura / Aplicar perfil
            clear_screen()
            selected_profile = run_select_profile_prompt(Path("profiles"))
            if selected_profile:
                config = BuildConfig(
                    profile_name=selected_profile.name,
                    template_path=rar_candidate,
                    output_dir=Path("./output")
                )
                run_build_with_config(config, profile_obj=selected_profile)
            else:
                config = BuildConfig(template_path=rar_candidate, output_dir=Path("./output"))
                config = run_interactive_prompts(config)
                run_build_with_config(config)
            input(f"\n{DIM}Presiona Enter para volver al menú principal...{RESET}")

        elif choice == "2":
            # 2. Ver carpetas ya hechas
            run_manage_existing_folders_menu(Path("./output"))

        elif choice == "3":
            # 3. Ver plantillas y perfiles disponibles
            clear_screen()
            if rar_candidate.is_file():
                run_inspect(rar_candidate)
            else:
                print(f"\n{RED}Plantilla Win64.rar no encontrada.{RESET}\n")

            run_profile_list(Path("profiles"))
            input(f"\n{DIM}Presiona Enter para volver al menú principal...{RESET}")

        elif choice == "4":
            # 4. Diagnóstico del sistema y dependencias
            clear_screen()
            run_doctor(rar_candidate)
            input(f"\n{DIM}Presiona Enter para volver al menú principal...{RESET}")

        elif choice == "5":
            # 5. Limpiar artefactos temporales
            clear_screen()
            run_clean(Path("."))
            input(f"\n{DIM}Presiona Enter para volver al menú principal...{RESET}")

        elif choice == "0":
            print(f"\n{CYAN}¡Hasta pronto!{RESET}\n")
            return 0
        else:
            print(f"  {RED}⚠ Opción inválida. Elige un número del 0 al 5.{RESET}")
            time.sleep(0.8)


def main() -> int:
    args = parse_args()

    if args.command == "inspect":
        return run_inspect(args.template)
    elif args.command == "clean":
        return run_clean(args.dir)
    elif args.command == "doctor" or getattr(args, "doctor", False):
        return run_doctor(args.template)
    elif args.command == "profile":
        if args.profile_action == "list":
            return run_profile_list(args.dir)
        elif args.profile_action == "inspect":
            return run_profile_inspect(args.profile_name, args.dir)
        else:
            print(f"{RED}Unknown profile action. Use 'list' or 'inspect'.{RESET}", file=sys.stderr)
            return 1

    if getattr(args, "list_folders", False):
        folders = FilesystemBuilder.discover_existing_folders(args.output)
        display_existing_folders(folders)
        return 0

    # If running interactively with NO explicit builder flags or subcommands, open the main menu
    is_interactive = sys.stdin.isatty()
    has_builder_args = bool(args.folder or args.exe or args.layout or args.profile or args.dry_run)

    if is_interactive and not has_builder_args:
        return run_interactive_menu()

    # Configuration initialization for direct / automated CLI mode
    config = BuildConfig(
        template_path=args.template,
        profile_name=args.profile,
        profile_assets_root=args.assets_root,
        folder_name=args.folder or "",
        exe_name=args.exe or "",
        layout_type=args.layout or "",
        output_dir=args.output,
        steam_library=args.steam_library,
        custom_path=args.custom_path or "",
        collision_mode=args.collision,
        allow_external_destination=args.allow_external_destination,
        dry_run=args.dry_run,
        verbose=args.verbose,
        run_wine=getattr(args, "run_wine", False),
    )

    return run_build_with_config(config)


if __name__ == "__main__":
    sys.exit(main())


