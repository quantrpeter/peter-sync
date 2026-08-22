from __future__ import annotations

import json
from pathlib import Path

import pytest

from peter_sync.settings import SettingsError, SettingsStore


def test_add_and_list_pairs(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    store = SettingsStore(tmp_path / "settings.json")
    store.load()

    pair = store.add_pair("docs", str(left), str(right))

    assert pair.name == "docs"
    assert Path(pair.left) == left.resolve()
    assert Path(pair.right) == right.resolve()
    saved = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert saved["pairs"][0]["name"] == "docs"


def test_rejects_duplicate_name(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    extra = tmp_path / "extra"
    left.mkdir()
    right.mkdir()
    extra.mkdir()
    store = SettingsStore(tmp_path / "settings.json")
    store.add_pair("docs", str(left), str(right))

    with pytest.raises(SettingsError, match="already exists"):
        store.add_pair("docs", str(left), str(extra))


def test_remove_pair(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    store = SettingsStore(tmp_path / "settings.json")
    store.add_pair("docs", str(left), str(right))

    removed = store.remove_pair("docs")

    assert removed.name == "docs"
    assert store.pairs == []


def test_missing_folder_is_rejected(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "settings.json")
    with pytest.raises(SettingsError, match="does not exist"):
        store.add_pair("docs", str(tmp_path / "missing"), str(tmp_path))


def test_snapshot_round_trip(tmp_path: Path) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    store = SettingsStore(tmp_path / "settings.json")
    store.add_pair("docs", str(left), str(right))
    store.update_snapshot("docs", ["notes.txt"])

    reloaded = SettingsStore(tmp_path / "settings.json")
    reloaded.load()
    assert reloaded.get_pair("docs").snapshot == ["notes.txt"]
