"""
Template management module.
Handles archive discovery, inspection, Zip/Rar slip security validation,
dynamic executable discovery, and atomic extraction.
"""

import hashlib
import os
import shutil
import subprocess
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import List, Optional, Tuple


class TemplateManager:
    """
    Abstractions for managing the base template archive safely without modifying it.
    """

    def __init__(self, archive_path: Path):
        self.archive_path = archive_path.resolve()
        if not self.archive_path.is_file():
            raise FileNotFoundError(f"Template archive not found: {self.archive_path}")

    @staticmethod
    def get_archive_hash(archive_path: Path) -> str:
        """Calculates SHA-256 hash of the template file."""
        hasher = hashlib.sha256()
        with open(archive_path, "rb") as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    @staticmethod
    def find_extractor() -> Tuple[str, str]:
        """
        Locates an available RAR extraction utility on system PATH.
        Returns tuple of (tool_name, tool_path).
        """
        for tool in ["7z", "7zz", "unrar"]:
            path = shutil.which(tool)
            if path:
                return tool, path
        raise RuntimeError(
            "Cannot extract archive. No RAR extractor found on PATH.\n"
            "Please install one of the following:\n"
            "  - 7-Zip / 7zz (Linux: sudo apt/pacman install 7zip or 7-zip)\n"
            "  - unrar\n"
            "Windows: Install 7-Zip and ensure 7z.exe is in system PATH."
        )

    def list_entries(self) -> List[str]:
        """
        Lists all relative paths inside the RAR archive.
        """
        tool, tool_path = self.find_extractor()
        entries = []

        if tool in ("7z", "7zz"):
            cmd = [tool_path, "l", "-ba", str(self.archive_path)]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            for line in result.stdout.splitlines():
                line = line.strip()
                if not line:
                    continue
                # 7z output format: Date Time Attr Size Compressed Name
                # Split with maxsplit=5
                parts = line.split(maxsplit=5)
                if len(parts) >= 6:
                    entries.append(parts[5])
        elif tool == "unrar":
            cmd = [tool_path, "lb", str(self.archive_path)]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            for line in result.stdout.splitlines():
                if line.strip():
                    entries.append(line.strip())

        return entries

    def validate_archive_entries(self, entries: List[str]) -> str:
        """
        Validates archive entries against Zip/Rar slip path traversals, absolute paths,
        UNC paths, and returns the detected root directory name.
        """
        if not entries:
            raise ValueError(f"Archive '{self.archive_path}' appears to be empty.")

        root_candidates = set()

        for raw_entry in entries:
            # Normalize slashes for inspection
            entry_norm = raw_entry.replace("\\", "/")
            path_obj = PurePosixPath(entry_norm)

            if path_obj.is_absolute() or entry_norm.startswith("/") or entry_norm.startswith("\\"):
                raise ValueError(f"Security error: Absolute path in archive: '{raw_entry}'")

            # Check drive letters like C: or UNC \\
            if ":" in raw_entry or raw_entry.startswith("//"):
                raise ValueError(f"Security error: Invalid path specifier in archive: '{raw_entry}'")

            if ".." in path_obj.parts:
                raise ValueError(f"Security error: Path traversal ('..') detected in archive: '{raw_entry}'")

            if path_obj.parts:
                root_candidates.add(path_obj.parts[0])

        if len(root_candidates) != 1:
            raise ValueError(
                f"Expected archive to have a single root directory, found: {sorted(list(root_candidates))}"
            )

        root = list(root_candidates)[0]
        return root

    def inspect(self) -> dict:
        """
        Inspects archive content, validates safety, and identifies executables,
        languages, DLLs, and root directory.
        """
        entries = self.list_entries()
        root = self.validate_archive_entries(entries)

        root_prefix = f"{root}/"
        executables = []
        languages = []
        dlls = []
        other_files = []

        for entry in entries:
            norm = entry.replace("\\", "/")
            if not norm.startswith(root_prefix) and norm != root:
                continue

            rel_to_root = norm[len(root_prefix):]
            if not rel_to_root:
                continue

            parts = PurePosixPath(rel_to_root).parts

            # Check files directly in root
            if len(parts) == 1:
                filename = parts[0]
                if filename.lower().endswith(".exe"):
                    executables.append(filename)
                elif filename.lower().endswith(".dll"):
                    dlls.append(filename)
                else:
                    other_files.append(rel_to_root)
            else:
                # Subdirectory entries or nested files
                top_sub = parts[0]
                if top_sub not in languages and top_sub in ("en-US", "es-MX", "es-ES", "fr-FR", "de-DE", "ja-JP"):
                    languages.append(top_sub)
                other_files.append(rel_to_root)

        return {
            "archive_path": str(self.archive_path),
            "root": root,
            "executables": executables,
            "languages": languages,
            "dlls": dlls,
            "other_files": other_files,
            "entries_count": len(entries),
        }

    def extract_to(self, target_dir: Path) -> None:
        """
        Extracts archive content into target_dir.
        """
        tool, tool_path = self.find_extractor()
        target_dir.mkdir(parents=True, exist_ok=True)

        if tool in ("7z", "7zz"):
            cmd = [tool_path, "x", f"-o{target_dir}", "-y", str(self.archive_path)]
            subprocess.run(cmd, capture_output=True, text=True, check=True)
        elif tool == "unrar":
            cmd = [tool_path, "x", "-o+", str(self.archive_path), str(target_dir)]
            subprocess.run(cmd, capture_output=True, text=True, check=True)
