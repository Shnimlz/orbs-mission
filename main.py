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

from src.cli import (
    parse_args,
    run_interactive_prompts,
    print_banner,
    clear_screen,
    animate_text,
    display_build_plan,
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


def run_inspect(template_path: Path) -> int:
    try:
        print_banner(animated=True)
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
    print_banner(animated=False)
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


def main() -> int:
    args = parse_args()

    if args.command == "inspect":
        return run_inspect(args.template)
    elif args.command == "clean":
        return run_clean(args.dir)
    elif args.command == "profile":
        if args.profile_action == "list":
            return run_profile_list(args.dir)
        elif args.profile_action == "inspect":
            return run_profile_inspect(args.profile_name, args.dir)
        else:
            print(f"{RED}Unknown profile action. Use 'list' or 'inspect'.{RESET}", file=sys.stderr)
            return 1

    # Configuration initialization
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
    )

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

    # Load or construct Profile
    profile_obj: Profile
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

    # Execute BuildPlan
    col_mode = CollisionMode(config.collision_mode)

    print()
    try:
        with Spinner("Ejecutando plan de construcción transaccional") as sp:
            final_destinations = FilesystemBuilder.execute_plan(
                plan=plan,
                collision_mode=col_mode
            )
            sp.stop("Estructura confirmada exitosamente")

        print("\n" + f"{GREEN}================================================================{RESET}")
        print(f" {GREEN}✓ Operación completada con éxito!{RESET}")
        for dest in final_destinations:
            print(f" {BOLD}Destino:{RESET} {CYAN}{dest}{RESET}")
        print(f"{GREEN}================================================================{RESET}\n")
        return 0

    except Exception as e:
        print(f"\n{RED}✗ Falló el proceso de construcción: {e}{RESET}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
