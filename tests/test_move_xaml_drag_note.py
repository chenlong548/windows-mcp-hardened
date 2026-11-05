"""Issue #506: the Move tool must warn that XAML shell surfaces ignore drag."""

from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "windows_mcp" / "tools" / "input.py"
# Fork note: the upstream README moved to docs/UPSTREAM_README.md (the root
# README is now the hardened-fork overview). The documentation contract still
# applies -- the XAML drag limit must live somewhere durable -- so it is
# checked against the moved file.
README = Path(__file__).resolve().parents[1] / "docs" / "UPSTREAM_README.md"


def test_move_description_mentions_xaml_shell_surfaces():
    text = SRC.read_text(encoding="utf-8")
    assert "XAML shell surfaces such as Start menu" in text


def test_readme_documents_xaml_drag_limit():
    text = README.read_text(encoding="utf-8")
    assert "Drag is not supported on XAML shell surfaces" in text
