from __future__ import annotations

from pathlib import Path

from peter_sync.sync import sync_pair


def test_copies_new_files_both_ways(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    (left / "a.txt").write_text("from left", encoding="utf-8")
    (right / "b.txt").write_text("from right", encoding="utf-8")

    result = sync_pair(left, right)

    assert (right / "a.txt").read_text(encoding="utf-8") == "from left"
    assert (left / "b.txt").read_text(encoding="utf-8") == "from right"
    assert len(result.copied) == 2


def test_newer_file_wins(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    left_file = left / "note.txt"
    right_file = right / "note.txt"
    left_file.write_text("old", encoding="utf-8")
    right_file.write_text("new", encoding="utf-8")
    older = 1_700_000_000
    newer = older + 60
    left_file.touch()
    import os

    os.utime(left_file, (older, older))
    os.utime(right_file, (newer, newer))

    result = sync_pair(left, right)

    assert left_file.read_text(encoding="utf-8") == "new"
    assert len(result.copied) == 1


def test_identical_files_are_skipped(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    (left / "same.txt").write_text("same", encoding="utf-8")
    (right / "same.txt").write_text("same", encoding="utf-8")

    result = sync_pair(left, right)

    assert result.skipped == ["same.txt"]
    assert result.copied == []


def test_delete_propagates_using_snapshot(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    (left / "keep.txt").write_text("keep", encoding="utf-8")
    (left / "gone.txt").write_text("stale", encoding="utf-8")

    first = sync_pair(left, right)
    assert (right / "gone.txt").exists()

    (left / "gone.txt").unlink()
    second = sync_pair(left, right, snapshot=first.snapshot)

    assert not (right / "gone.txt").exists()
    assert (left / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert (right / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert len(second.deleted) == 1


def test_exclude_skips_named_folder_anywhere(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    (left / "keep.txt").write_text("keep", encoding="utf-8")
    (left / "node_modules").mkdir()
    (left / "node_modules" / "pkg.js").write_text("skip", encoding="utf-8")
    nested = left / "src" / "node_modules"
    nested.mkdir(parents=True)
    (nested / "deep.js").write_text("skip nested", encoding="utf-8")

    result = sync_pair(left, right, exclude=["node_modules"])

    assert (right / "keep.txt").read_text(encoding="utf-8") == "keep"
    assert not (right / "node_modules").exists()
    assert not (right / "src" / "node_modules").exists()
    assert "keep.txt" in result.snapshot
    assert all("node_modules" not in path for path in result.snapshot)


def test_exclude_relative_path_is_specific(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    (left / "build" / "tmp").mkdir(parents=True)
    (left / "build" / "tmp" / "cache.bin").write_text("skip", encoding="utf-8")
    (left / "build" / "app.js").write_text("keep", encoding="utf-8")

    sync_pair(left, right, exclude=["build/tmp"])

    assert (right / "build" / "app.js").read_text(encoding="utf-8") == "keep"
    assert not (right / "build" / "tmp").exists()


def test_exclude_does_not_delete_previously_synced_files(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    vendor = left / "vendor"
    vendor.mkdir()
    (vendor / "lib.txt").write_text("lib", encoding="utf-8")

    first = sync_pair(left, right)
    assert (right / "vendor" / "lib.txt").exists()

    (vendor / "lib.txt").write_text("changed locally", encoding="utf-8")
    second = sync_pair(left, right, snapshot=first.snapshot, exclude=["vendor"])

    assert (right / "vendor" / "lib.txt").read_text(encoding="utf-8") == "lib"
    assert (left / "vendor" / "lib.txt").read_text(encoding="utf-8") == "changed locally"
    assert second.copied == []
    assert second.deleted == []
    assert "vendor/lib.txt" not in second.snapshot
