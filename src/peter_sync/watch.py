"""Long-running watcher that keeps folder pairs in sync."""

from __future__ import annotations

import time
from collections.abc import Callable

from peter_sync.settings import FolderPair, SettingsError, SettingsStore
from peter_sync.sync import SyncError, SyncResult, sync_pair


StatusFn = Callable[[str], None]
ResultFn = Callable[[str, SyncResult], None]
SleepFn = Callable[[float], None]


def run_watch(
    store: SettingsStore,
    *,
    name: str | None = None,
    interval: float = 2.0,
    cycles: int | None = None,
    sleep: SleepFn = time.sleep,
    on_result: ResultFn | None = None,
    on_status: StatusFn | None = None,
) -> int:
    """Poll configured pairs and sync them until stopped.

    ``cycles`` limits how many passes to run. ``None`` means run forever.
    Settings are reloaded each cycle so pair edits are picked up.
    """
    if interval <= 0:
        raise SettingsError("Watch interval must be greater than 0.")
    if cycles is not None and cycles < 1:
        raise SettingsError("Watch cycles must be at least 1.")

    completed = 0
    empty_notified = False
    while cycles is None or completed < cycles:
        store.load()
        pairs = _pairs_for_cycle(store, name)
        if not pairs:
            if on_status and not empty_notified:
                on_status("No folder pairs configured.")
                empty_notified = True
        else:
            empty_notified = False
            for pair in pairs:
                _sync_pair(store, pair, on_result=on_result, on_status=on_status)

        completed += 1
        if cycles is not None and completed >= cycles:
            break
        sleep(interval)
    return 0


def _pairs_for_cycle(store: SettingsStore, name: str | None) -> list[FolderPair]:
    if name:
        return [store.get_pair(name)]
    return list(store.pairs)


def _sync_pair(
    store: SettingsStore,
    pair: FolderPair,
    *,
    on_result: ResultFn | None,
    on_status: StatusFn | None,
) -> None:
    try:
        left, right = pair.resolved()
        result = sync_pair(left, right, snapshot=pair.snapshot, exclude=pair.exclude)
        store.update_snapshot(pair.name, result.snapshot)
    except (SettingsError, SyncError, OSError) as exc:
        if on_status:
            on_status(f"error: {pair.name}: {exc}")
        return
    if on_result and (result.changed or result.conflicts):
        on_result(pair.name, result)
