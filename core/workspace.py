"""Local workspace management: init, starter templates, and file locking.

Spec reference: MASTER_DEVELOPER_SPEC.pdf Section 2 describes the browser's
File System Access API locking onto "the user's local career directory"
with "real-time disk sync." There is no Python/desktop equivalent of that
browser permission model, so this module works directly against the local
filesystem via :mod:`pathlib`, and — per Stage 1 blueprint edge case #4
(no concurrent-write strategy was specified) — adds an explicit, advisory
file lock so the CLI and the desktop app do not corrupt dossier files if run
against the same workspace at the same time.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from types import TracebackType

from questvector.config import (
    BUNDLES_DIRNAME,
    CAPABILITIES_FILENAME,
    CHRONOLOGY_FILENAME,
    DOSSIER_FILENAMES,
    IMPACT_FILENAME,
    LOCK_FILENAME,
    STARTER_TEMPLATES_DIRNAME,
    TEMPLATES_DIRNAME,
)
from questvector.exceptions import WorkspaceError

_LOCK_STALE_SECONDS = 300  # A lock older than this is assumed abandoned.

_DOSSIER_STUBS: dict[str, str] = {
    CAPABILITIES_FILENAME: (
        "## Uncategorized\n"
        "- Add your capabilities here, grouped under '## Domain Name' headings.\n"
    ),
    CHRONOLOGY_FILENAME: (
        "## Company — Role (Start–End)\n"
        "- Add responsibilities and achievements as bullet points.\n"
    ),
    IMPACT_FILENAME: (
        "## Impact Summary\n"
        "- Add quantified impact statements as bullet points.\n"
    ),
}


@dataclass(frozen=True, slots=True)
class WorkspaceInitResult:
    """Summary of what :func:`init_workspace` created.

    Attributes:
        workspace_dir: The initialized workspace directory.
        created_files: Paths that were newly created (existing files are
            never overwritten and are not listed here).
        skipped_files: Paths that already existed and were left untouched.
    """

    workspace_dir: Path
    created_files: tuple[Path, ...] = field(default_factory=tuple)
    skipped_files: tuple[Path, ...] = field(default_factory=tuple)


def _iter_bundled_starter_templates() -> list[tuple[str, str]]:
    """Read the bundled starter mission templates from package data.

    Returns:
        A list of ``(filename, content)`` pairs for every ``.yaml`` file
        shipped under ``questvector/data/starter_templates``.
    """
    templates: list[tuple[str, str]] = []
    package = "questvector.data.starter_templates"
    for entry in resources.files(package).iterdir():
        if entry.name.endswith((".yaml", ".yml")):
            templates.append((entry.name, entry.read_text(encoding="utf-8")))
    return sorted(templates)


def init_workspace(workspace_dir: Path) -> WorkspaceInitResult:
    """Initialize (``qv launch``) a local career dossier workspace.

    Creates the workspace directory if needed, seeds dossier stub files
    (only if they don't already exist), and copies the bundled starter
    mission templates into ``templates/starter/``.

    Args:
        workspace_dir: Target directory for the new/existing workspace.

    Returns:
        A :class:`WorkspaceInitResult` describing what was created vs.
        left alone.

    Raises:
        WorkspaceError: If ``workspace_dir`` exists and is not a directory,
            or if any required path cannot be created due to a filesystem
            error (permissions, disk full, etc.).
    """
    if workspace_dir.exists() and not workspace_dir.is_dir():
        raise WorkspaceError(
            f"Workspace path exists and is not a directory: {workspace_dir}",
            context={"path": str(workspace_dir)},
        )

    try:
        workspace_dir.mkdir(parents=True, exist_ok=True)
        templates_dir = workspace_dir / TEMPLATES_DIRNAME / STARTER_TEMPLATES_DIRNAME
        templates_dir.mkdir(parents=True, exist_ok=True)
        (workspace_dir / BUNDLES_DIRNAME).mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise WorkspaceError(
            f"Could not create workspace directories under {workspace_dir}",
            context={"path": str(workspace_dir), "os_error": str(exc)},
        ) from exc

    created: list[Path] = []
    skipped: list[Path] = []

    for filename in DOSSIER_FILENAMES:
        target = workspace_dir / filename
        if target.exists():
            skipped.append(target)
            continue
        try:
            target.write_text(_DOSSIER_STUBS[filename], encoding="utf-8")
        except OSError as exc:
            raise WorkspaceError(
                f"Could not create dossier stub file: {filename}",
                context={"path": str(target), "os_error": str(exc)},
            ) from exc
        created.append(target)

    for filename, content in _iter_bundled_starter_templates():
        target = templates_dir / filename
        if target.exists():
            skipped.append(target)
            continue
        try:
            target.write_text(content, encoding="utf-8")
        except OSError as exc:
            raise WorkspaceError(
                f"Could not write starter template: {filename}",
                context={"path": str(target), "os_error": str(exc)},
            ) from exc
        created.append(target)

    return WorkspaceInitResult(
        workspace_dir=workspace_dir, created_files=tuple(created), skipped_files=tuple(skipped)
    )


class WorkspaceLock:
    """An advisory, cross-process exclusive lock over a workspace directory.

    Uses atomic exclusive file creation (``O_CREAT | O_EXCL``), which is
    portable across POSIX and Windows without a third-party dependency. A
    lock file older than :data:`_LOCK_STALE_SECONDS` is treated as
    abandoned (e.g. a prior process crashed) and is reclaimed automatically.

    Example:
        with WorkspaceLock(workspace_dir):
            ... mutate dossier files ...
    """

    def __init__(self, workspace_dir: Path) -> None:
        """Initialize the lock for a given workspace directory.

        Args:
            workspace_dir: The directory to lock.
        """
        self._lock_path = workspace_dir / LOCK_FILENAME
        self._acquired = False

    def acquire(self) -> None:
        """Acquire the lock, reclaiming a stale lock file if present.

        Raises:
            WorkspaceError: If another process currently holds a
                non-stale lock on this workspace.
        """
        try:
            fd = os.open(self._lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode("ascii"))
            os.close(fd)
            self._acquired = True
            return
        except FileExistsError:
            pass

        try:
            age_seconds = time.time() - self._lock_path.stat().st_mtime
        except OSError:
            age_seconds = float("inf")

        if age_seconds <= _LOCK_STALE_SECONDS:
            raise WorkspaceError(
                "Workspace is locked by another QuestVector process",
                context={"lock_path": str(self._lock_path), "age_seconds": age_seconds},
            )

        # Stale lock — reclaim it.
        try:
            self._lock_path.unlink(missing_ok=True)
            fd = os.open(self._lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode("ascii"))
            os.close(fd)
            self._acquired = True
        except OSError as exc:
            raise WorkspaceError(
                "Could not reclaim stale workspace lock",
                context={"lock_path": str(self._lock_path), "os_error": str(exc)},
            ) from exc

    def release(self) -> None:
        """Release the lock if currently held (idempotent, never raises)."""
        if not self._acquired:
            return
        try:
            self._lock_path.unlink(missing_ok=True)
        except OSError:
            pass  # Best-effort: a missing/unremovable lock file is not fatal.
        finally:
            self._acquired = False

    def __enter__(self) -> WorkspaceLock:
        """Acquire the lock as a context manager.

        Returns:
            This lock instance.
        """
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Release the lock on context-manager exit."""
        self.release()
