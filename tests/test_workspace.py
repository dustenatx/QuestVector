"""Unit tests for questvector.core.workspace."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from questvector.core.workspace import WorkspaceLock, init_workspace
from questvector.exceptions import WorkspaceError


def test_init_workspace_creates_dossier_stubs_and_starter_templates(tmp_path: Path) -> None:
    workspace_dir = tmp_path / "ws"
    result = init_workspace(workspace_dir)

    assert (workspace_dir / "Capabilities.md").exists()
    assert (workspace_dir / "Chronology.md").exists()
    assert (workspace_dir / "Impact.md").exists()
    starter_dir = workspace_dir / "templates" / "starter"
    starter_templates = list(starter_dir.glob("*.yaml"))
    assert len(starter_templates) == 7
    assert (workspace_dir / "bundles").is_dir()
    assert len(result.created_files) > 0


def test_init_workspace_never_overwrites_existing_dossier_file(tmp_path: Path) -> None:
    workspace_dir = tmp_path / "ws"
    workspace_dir.mkdir()
    custom_content = "## My Custom Content\n- do not clobber me\n"
    (workspace_dir / "Capabilities.md").write_text(custom_content, encoding="utf-8")

    result = init_workspace(workspace_dir)

    assert (workspace_dir / "Capabilities.md").read_text(encoding="utf-8") == custom_content
    assert workspace_dir / "Capabilities.md" in result.skipped_files


def test_init_workspace_is_idempotent(tmp_path: Path) -> None:
    workspace_dir = tmp_path / "ws"
    init_workspace(workspace_dir)
    second_result = init_workspace(workspace_dir)

    assert second_result.created_files == ()
    assert len(second_result.skipped_files) > 0


def test_init_workspace_raises_if_path_is_a_file(tmp_path: Path) -> None:
    file_path = tmp_path / "not-a-dir"
    file_path.write_text("hello", encoding="utf-8")

    with pytest.raises(WorkspaceError):
        init_workspace(file_path)


def test_workspace_lock_prevents_concurrent_acquire(tmp_path: Path) -> None:
    workspace_dir = tmp_path / "ws"
    workspace_dir.mkdir()
    lock_a = WorkspaceLock(workspace_dir)
    lock_b = WorkspaceLock(workspace_dir)

    lock_a.acquire()
    try:
        with pytest.raises(WorkspaceError):
            lock_b.acquire()
    finally:
        lock_a.release()


def test_workspace_lock_context_manager_releases_on_exit(tmp_path: Path) -> None:
    workspace_dir = tmp_path / "ws"
    workspace_dir.mkdir()

    with WorkspaceLock(workspace_dir):
        assert (workspace_dir / ".questvector.lock").exists()

    assert not (workspace_dir / ".questvector.lock").exists()


def test_workspace_lock_reclaims_stale_lock(tmp_path: Path) -> None:
    workspace_dir = tmp_path / "ws"
    workspace_dir.mkdir()
    lock_path = workspace_dir / ".questvector.lock"
    lock_path.write_text("99999999", encoding="utf-8")
    # Backdate the lock file well past the staleness threshold.
    old_time = time.time() - 10_000
    import os

    os.utime(lock_path, (old_time, old_time))

    lock = WorkspaceLock(workspace_dir)
    lock.acquire()  # Should not raise -- reclaims the stale lock.
    lock.release()


def test_workspace_lock_release_without_acquire_is_safe(tmp_path: Path) -> None:
    workspace_dir = tmp_path / "ws"
    workspace_dir.mkdir()
    lock = WorkspaceLock(workspace_dir)
    lock.release()  # Should not raise.
