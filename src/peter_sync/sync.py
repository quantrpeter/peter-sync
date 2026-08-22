"""Bidirectional last-write-wins folder sync."""

from __future__ import annotations

import filecmp
import shutil
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path


IGNORE_NAMES = {".DS_Store", "Thumbs.db"}


@dataclass
class SyncAction:
    """One file copy or delete performed during a sync."""

    kind: str
    source: str
    destination: str


@dataclass
class SyncResult:
    """Summary of a bidirectional sync run."""

    copied: list[SyncAction] = field(default_factory=list)
    deleted: list[SyncAction] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    snapshot: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        return bool(self.copied or self.deleted)


class SyncError(RuntimeError):
    """A folder pair cannot be synced."""


def sync_pair(
    left: Path,
    right: Path,
    *,
    snapshot: Iterable[str] | None = None,
) -> SyncResult:
    """Sync two folders both ways using last-write-wins.

    Newer files overwrite older ones. Identical files are left alone.
    If both sides changed independently (same mtime, different content),
    the file is recorded as a conflict and left untouched.

    ``snapshot`` is the relative file list from the previous successful
    sync. New files (not in the snapshot) are copied to the other side.
    Files that disappear from one side after being snapshotted are
    deleted from the other side.
    """
    left = left.expanduser().resolve()
    right = right.expanduser().resolve()
    if not left.is_dir():
        raise SyncError(f"Left folder does not exist: {left}")
    if not right.is_dir():
        raise SyncError(f"Right folder does not exist: {right}")
    if left == right:
        raise SyncError("Left and right folders must be different.")

    result = SyncResult()
    known = set(snapshot or [])
    left_files = _index_files(left)
    right_files = _index_files(right)
    relative_paths = set(left_files) | set(right_files) | known

    for relative in sorted(relative_paths):
        left_file = left_files.get(relative)
        right_file = right_files.get(relative)

        if left_file and right_file:
            _sync_both_present(left_file, right_file, relative, result)
        elif left_file and not right_file:
            if relative in known:
                _delete_file(left_file, result)
            else:
                _copy_file(left_file, right / relative, result)
        elif right_file and not left_file:
            if relative in known:
                _delete_file(right_file, result)
            else:
                _copy_file(right_file, left / relative, result)

    result.snapshot = sorted(set(_index_files(left)) | set(_index_files(right)))
    return result


def _index_files(root: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.name in IGNORE_NAMES:
            continue
        relative = path.relative_to(root).as_posix()
        files[relative] = path
    return files


def _sync_both_present(left_file: Path, right_file: Path, relative: str, result: SyncResult) -> None:
    if filecmp.cmp(left_file, right_file, shallow=False):
        result.skipped.append(relative)
        return

    left_mtime = left_file.stat().st_mtime
    right_mtime = right_file.stat().st_mtime
    if left_mtime > right_mtime:
        _copy_file(left_file, right_file, result)
    elif right_mtime > left_mtime:
        _copy_file(right_file, left_file, result)
    else:
        result.conflicts.append(relative)


def _copy_file(source: Path, destination: Path, result: SyncResult) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    result.copied.append(
        SyncAction(kind="copy", source=str(source), destination=str(destination))
    )


def _delete_file(path: Path, result: SyncResult) -> None:
    path.unlink()
    result.deleted.append(SyncAction(kind="delete", source=str(path), destination=""))
    _remove_empty_parents(path.parent)


def _remove_empty_parents(directory: Path) -> None:
    while directory.exists() and not any(directory.iterdir()):
        parent = directory.parent
        try:
            directory.rmdir()
        except OSError:
            return
        directory = parent
