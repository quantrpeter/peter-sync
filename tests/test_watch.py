from __future__ import annotations

from pathlib import Path

import pytest

from peter_sync.cli import main
from peter_sync.settings import SettingsError, SettingsStore
from peter_sync.watch import run_watch


def test_watch_syncs_new_file_across_cycles(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    (left / "first.txt").write_text("one", encoding="utf-8")

    store = SettingsStore(tmp_path / "settings.json")
    store.add_pair("notes", str(left), str(right))

    def sleep(_seconds: float) -> None:
        (left / "second.txt").write_text("two", encoding="utf-8")

    assert run_watch(store, name="notes", interval=0.01, cycles=2, sleep=sleep) == 0
    assert (right / "first.txt").read_text(encoding="utf-8") == "one"
    assert (right / "second.txt").read_text(encoding="utf-8") == "two"


def test_watch_rejects_invalid_interval(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    with pytest.raises(SettingsError, match="greater than 0"):
        run_watch(store, interval=0, cycles=1)


def test_watch_missing_pair(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "settings.json")
    store.load()
    with pytest.raises(SettingsError, match="No pair named"):
        run_watch(store, name="missing", cycles=1)


def test_cli_watch_cycles(tmp_path: Path, capsys) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    (left / "hello.txt").write_text("hello", encoding="utf-8")
    settings = tmp_path / "settings.json"

    assert main(["--settings", str(settings), "add", "notes", str(left), str(right)]) == 0
    assert main(
        ["--settings", str(settings), "watch", "notes", "--interval", "0.01", "--cycles", "1"]
    ) == 0
    assert (right / "hello.txt").read_text(encoding="utf-8") == "hello"
    assert "Synced 'notes'" in capsys.readouterr().out
