"""JSON settings for bidirectional folder pairs."""

from __future__ import annotations

import json
import os
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


DEFAULT_SETTINGS_PATH = Path.home() / ".peter-sync" / "settings.json"


def normalize_exclude(patterns: Iterable[str] | None) -> list[str]:
    """Return unique relative folder patterns, preserving order."""
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in patterns or []:
        if not isinstance(raw, str):
            raise SettingsError("Each exclude must be a string.")
        pattern = raw.strip().replace("\\", "/").strip("/")
        if not pattern:
            continue
        parts = [part for part in pattern.split("/") if part and part != "."]
        if not parts or any(part == ".." for part in parts):
            raise SettingsError(f"Invalid exclude folder: {raw}")
        if Path(pattern).is_absolute() or pattern.startswith("/"):
            raise SettingsError(f"Exclude must be a relative folder: {raw}")
        pattern = "/".join(parts)
        if pattern not in seen:
            seen.add(pattern)
            normalized.append(pattern)
    return normalized


@dataclass
class FolderPair:
    """A named pair of folders kept in bidirectional sync."""

    name: str
    left: str
    right: str
    snapshot: list[str] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)

    def resolved(self) -> tuple[Path, Path]:
        return Path(self.left).expanduser().resolve(), Path(self.right).expanduser().resolve()


class SettingsError(ValueError):
    """Invalid settings file or pair definition."""


class SettingsStore:
    """Load and save folder-pair settings as JSON."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path is not None else DEFAULT_SETTINGS_PATH
        self.pairs: list[FolderPair] = []

    def load(self) -> None:
        if not self.path.exists():
            self.pairs = []
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise SettingsError(f"Settings file is not valid JSON: {self.path}") from exc
        self.pairs = [self._pair_from_dict(item) for item in raw.get("pairs", [])]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"pairs": [asdict(pair) for pair in self.pairs]}
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, self.path)

    def add_pair(
        self,
        name: str,
        left: str,
        right: str,
        exclude: Iterable[str] | None = None,
    ) -> FolderPair:
        name = name.strip()
        if not name:
            raise SettingsError("Pair name cannot be empty.")
        if any(pair.name == name for pair in self.pairs):
            raise SettingsError(f"A pair named {name!r} already exists.")

        left_path = Path(left).expanduser()
        right_path = Path(right).expanduser()
        if not left_path.is_dir():
            raise SettingsError(f"Left folder does not exist: {left_path}")
        if not right_path.is_dir():
            raise SettingsError(f"Right folder does not exist: {right_path}")

        left_resolved = left_path.resolve()
        right_resolved = right_path.resolve()
        if left_resolved == right_resolved:
            raise SettingsError("Left and right folders must be different.")

        pair = FolderPair(
            name=name,
            left=str(left_resolved),
            right=str(right_resolved),
            exclude=normalize_exclude(exclude),
        )
        self.pairs.append(pair)
        self.save()
        return pair

    def remove_pair(self, name: str) -> FolderPair:
        for index, pair in enumerate(self.pairs):
            if pair.name == name:
                removed = self.pairs.pop(index)
                self.save()
                return removed
        raise SettingsError(f"No pair named {name!r}.")

    def get_pair(self, name: str) -> FolderPair:
        for pair in self.pairs:
            if pair.name == name:
                return pair
        raise SettingsError(f"No pair named {name!r}.")

    def update_snapshot(self, name: str, snapshot: list[str]) -> None:
        pair = self.get_pair(name)
        pair.snapshot = list(snapshot)
        self.save()

    def update_exclude(self, name: str, exclude: Iterable[str] | None) -> FolderPair:
        pair = self.get_pair(name)
        pair.exclude = normalize_exclude(exclude)
        self.save()
        return pair

    @staticmethod
    def _pair_from_dict(item: Any) -> FolderPair:
        if not isinstance(item, dict):
            raise SettingsError("Each pair must be a JSON object.")
        try:
            snapshot = item.get("snapshot", [])
            if not isinstance(snapshot, list) or not all(isinstance(entry, str) for entry in snapshot):
                raise SettingsError("Pair snapshot must be a list of file paths.")
            exclude = item.get("exclude", [])
            if not isinstance(exclude, list):
                raise SettingsError("Pair exclude must be a list of folder paths.")
            return FolderPair(
                name=str(item["name"]),
                left=str(item["left"]),
                right=str(item["right"]),
                snapshot=list(snapshot),
                exclude=normalize_exclude(exclude),
            )
        except KeyError as exc:
            raise SettingsError(f"Pair is missing required field: {exc.args[0]}") from exc

