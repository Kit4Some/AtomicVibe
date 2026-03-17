"""Unit tests for workspace.py — Workspace class."""

from __future__ import annotations

import pytest

from architect.core.exceptions import WorkspaceError
from architect.core.models import CodeFile
from architect.execute.workspace import Workspace


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_write_files_creates_files(tmp_path) -> None:
    """Write CodeFiles and verify they exist on disk."""
    ws = Workspace(str(tmp_path / "ws"))
    files = [
        CodeFile(path="hello.py", content="print('hello')\n", action="create"),
        CodeFile(path="world.py", content="print('world')\n", action="create"),
    ]
    ws.write_files(files)

    assert (tmp_path / "ws" / "hello.py").read_text() == "print('hello')\n"
    assert (tmp_path / "ws" / "world.py").read_text() == "print('world')\n"


def test_write_files_creates_parent_dirs(tmp_path) -> None:
    """Nested paths should have parent directories auto-created."""
    ws = Workspace(str(tmp_path / "ws"))
    files = [
        CodeFile(path="src/core/models.py", content="# models\n", action="create"),
    ]
    ws.write_files(files)

    assert (tmp_path / "ws" / "src" / "core" / "models.py").is_file()


def test_write_files_append_mode(tmp_path) -> None:
    """Append action should add content to existing file."""
    ws = Workspace(str(tmp_path / "ws"))
    ws.write_files([CodeFile(path="log.txt", content="line1\n", action="create")])
    ws.write_files([CodeFile(path="log.txt", content="line2\n", action="append")])

    content = (tmp_path / "ws" / "log.txt").read_text()
    assert "line1\n" in content
    assert "line2\n" in content


def test_read_file_returns_content(tmp_path) -> None:
    """Read a file that was previously written."""
    ws = Workspace(str(tmp_path / "ws"))
    ws.write_files([CodeFile(path="data.txt", content="hello data", action="create")])

    assert ws.read_file("data.txt") == "hello data"


def test_read_file_missing_raises(tmp_path) -> None:
    """Reading a nonexistent file raises WorkspaceError."""
    ws = Workspace(str(tmp_path / "ws"))

    with pytest.raises(WorkspaceError):
        ws.read_file("nonexistent.py")


def test_git_commit_creates_commit(tmp_path) -> None:
    """Write files, commit, and verify via git log."""
    ws = Workspace(str(tmp_path / "ws"))
    ws.write_files([CodeFile(path="a.py", content="# a\n", action="create")])
    ws.git_commit("feat: add a.py")

    # Verify commit exists in log
    log_output = ws._repo.git.log("--oneline")
    assert "feat: add a.py" in log_output


def test_git_tag_and_rollback(tmp_path) -> None:
    """Tag v1, write v2, rollback to v1, verify content restored."""
    ws = Workspace(str(tmp_path / "ws"))

    # v1
    ws.write_files([CodeFile(path="x.py", content="v1\n", action="create")])
    ws.git_commit("v1")
    ws.git_tag("v1")

    # v2
    ws.write_files([CodeFile(path="x.py", content="v2\n", action="replace")])
    ws.git_commit("v2")

    # Verify v2
    assert ws.read_file("x.py") == "v2\n"

    # Rollback to v1
    ws.git_rollback("v1")
    assert ws.read_file("x.py") == "v1\n"
