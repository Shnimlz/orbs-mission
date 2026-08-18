"""
Tests for TemplateManager archive inspection, security validation, and immutability.
"""

from pathlib import Path
import pytest

from src.template import TemplateManager


def _find_test_template() -> Path:
    candidates = [Path("Win64.rar"), Path("templates/Win64.rar")]
    for c in candidates:
        if c.is_file():
            return c
    pytest.skip("Win64.rar not found in current directory or templates/")


def test_template_immutability():
    rar_file = _find_test_template()
    hash_before = TemplateManager.get_archive_hash(rar_file)

    mgr = TemplateManager(rar_file)
    info = mgr.inspect()

    hash_after = TemplateManager.get_archive_hash(rar_file)
    assert hash_before == hash_after, "Template archive hash changed! Immutability violated."


def test_archive_entry_security_validation():
    rar_file = _find_test_template()
    mgr = TemplateManager(rar_file)

    # Valid entries test
    root = mgr.validate_archive_entries([
        "Win64/Rouge-Win64-Shipping.exe",
        "Win64/WordpadFilter.dll",
        "Win64/es-MX/wordpad.exe.mui",
        "Win64/en-US/"
    ])
    assert root == "Win64"

    # Zip slip absolute path test
    with pytest.raises(ValueError, match="Absolute path"):
        mgr.validate_archive_entries(["/etc/passwd", "Win64/file.exe"])

    # Path traversal test
    with pytest.raises(ValueError, match="Path traversal"):
        mgr.validate_archive_entries(["Win64/../../outside.exe"])

    # Drive letter test
    with pytest.raises(ValueError, match="Invalid path specifier"):
        mgr.validate_archive_entries(["C:\\Windows\\system32\\cmd.exe"])


def test_inspection_details():
    rar_file = _find_test_template()
    mgr = TemplateManager(rar_file)
    info = mgr.inspect()

    assert info["root"] == "Win64"
    assert "Rouge-Win64-Shipping.exe" in info["executables"]
    assert "WordpadFilter.dll" in info["dlls"]
    assert "es-MX" in info["languages"]


def test_missing_template_handling(tmp_path: Path):
    missing_file = tmp_path / "nonexistent.rar"
    with pytest.raises(FileNotFoundError):
        TemplateManager(missing_file)
