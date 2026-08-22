"""Command-line interface and interactive menu for peter-sync."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from peter_sync import __version__
from peter_sync.settings import DEFAULT_SETTINGS_PATH, FolderPair, SettingsError, SettingsStore
from peter_sync.sync import SyncError, SyncResult, sync_pair
from peter_sync.watch import run_watch


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    store = SettingsStore(Path(args.settings) if args.settings else None)

    try:
        store.load()
        if args.command is None:
            return _run_menu(store)
        return args.func(store, args)
    except (SettingsError, SyncError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="peter-sync",
        description="Keep two folders in bidirectional sync.",
    )
    parser.add_argument(
        "--settings",
        help=f"Path to settings JSON (default: {DEFAULT_SETTINGS_PATH})",
    )
    parser.add_argument("--version", action="version", version=f"peter-sync {__version__}")
    sub = parser.add_subparsers(dest="command")

    list_parser = sub.add_parser("list", help="List saved folder pairs")
    list_parser.set_defaults(func=_cmd_list)

    add_parser = sub.add_parser("add", help="Add a folder pair")
    add_parser.add_argument("name", help="Name for this pair")
    add_parser.add_argument("left", help="First folder")
    add_parser.add_argument("right", help="Second folder")
    add_parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="FOLDER",
        help="Folder to skip (repeatable). Bare names match anywhere.",
    )
    add_parser.set_defaults(func=_cmd_add)

    remove_parser = sub.add_parser("remove", help="Remove a folder pair")
    remove_parser.add_argument("name", help="Name of the pair to remove")
    remove_parser.set_defaults(func=_cmd_remove)

    exclude_parser = sub.add_parser("exclude", help="List or change excluded folders for a pair")
    exclude_parser.add_argument("name", help="Pair name")
    exclude_group = exclude_parser.add_mutually_exclusive_group()
    exclude_group.add_argument(
        "--add",
        nargs="+",
        metavar="FOLDER",
        help="Add one or more excluded folders",
    )
    exclude_group.add_argument(
        "--remove",
        nargs="+",
        metavar="FOLDER",
        help="Remove one or more excluded folders",
    )
    exclude_group.add_argument(
        "--set",
        nargs="*",
        metavar="FOLDER",
        help="Replace the exclude list (omit folders to clear)",
    )
    exclude_parser.set_defaults(func=_cmd_exclude)

    sync_parser = sub.add_parser("sync", help="Sync one pair or all pairs")
    sync_parser.add_argument("name", nargs="?", help="Pair name (omit to sync all)")
    sync_parser.set_defaults(func=_cmd_sync)

    watch_parser = sub.add_parser("watch", help="Keep syncing pairs until stopped")
    watch_parser.add_argument("name", nargs="?", help="Pair name (omit to watch all)")
    watch_parser.add_argument(
        "--interval",
        type=float,
        default=2.0,
        metavar="SECONDS",
        help="Seconds between syncs (default: 2)",
    )
    watch_parser.add_argument(
        "--cycles",
        type=int,
        default=None,
        metavar="N",
        help="Stop after N sync cycles (default: run until interrupted)",
    )
    watch_parser.set_defaults(func=_cmd_watch)

    menu_parser = sub.add_parser("menu", help="Open the interactive menu")
    menu_parser.set_defaults(func=lambda store, _args: _run_menu(store))
    return parser


def _cmd_list(store: SettingsStore, _args: argparse.Namespace) -> int:
    _print_pairs(store)
    return 0


def _cmd_add(store: SettingsStore, args: argparse.Namespace) -> int:
    pair = store.add_pair(args.name, args.left, args.right, exclude=args.exclude)
    print(f"Added pair {pair.name!r}")
    print(f"  left : {pair.left}")
    print(f"  right: {pair.right}")
    _print_exclude(pair.exclude)
    return 0


def _cmd_remove(store: SettingsStore, args: argparse.Namespace) -> int:
    pair = store.remove_pair(args.name)
    print(f"Removed pair {pair.name!r}")
    return 0


def _cmd_exclude(store: SettingsStore, args: argparse.Namespace) -> int:
    pair = store.get_pair(args.name)
    if args.add is not None:
        pair = store.update_exclude(args.name, [*pair.exclude, *args.add])
        print(f"Updated excludes for {pair.name!r}")
    elif args.remove is not None:
        removing = {item.strip().replace("\\", "/").strip("/") for item in args.remove}
        remaining = [item for item in pair.exclude if item not in removing]
        missing = sorted(removing - set(pair.exclude))
        pair = store.update_exclude(args.name, remaining)
        print(f"Updated excludes for {pair.name!r}")
        for item in missing:
            print(f"  not excluded: {item}")
    elif args.set is not None:
        pair = store.update_exclude(args.name, args.set)
        print(f"Updated excludes for {pair.name!r}")
    _print_exclude(pair.exclude)
    return 0


def _cmd_sync(store: SettingsStore, args: argparse.Namespace) -> int:
    if args.name:
        pairs = [store.get_pair(args.name)]
    else:
        pairs = list(store.pairs)
    if not pairs:
        print("No folder pairs configured.")
        return 0
    for pair in pairs:
        _sync_and_save(store, pair)
    return 0


def _cmd_watch(store: SettingsStore, args: argparse.Namespace) -> int:
    target = args.name or "all pairs"
    if args.cycles is None:
        print(f"Watching {target} every {args.interval}s. Press Ctrl+C to stop.")
    try:
        return run_watch(
            store,
            name=args.name,
            interval=args.interval,
            cycles=args.cycles,
            on_result=_print_result,
            on_status=print,
        )
    except KeyboardInterrupt:
        print("\nStopped watching.")
        return 0


def _run_menu(store: SettingsStore) -> int:
    actions = {
        "1": lambda: _print_pairs(store),
        "2": lambda: _menu_add(store),
        "3": lambda: _menu_remove(store),
        "4": lambda: _menu_sync_all(store),
        "5": lambda: _menu_sync_one(store),
        "6": lambda: _menu_watch(store),
        "7": lambda: _menu_exclude(store),
        "8": lambda: _print_settings_path(store),
    }
    while True:
        print()
        print("peter-sync")
        print("----------")
        print("1) List folder pairs")
        print("2) Add folder pair")
        print("3) Remove folder pair")
        print("4) Sync all pairs")
        print("5) Sync one pair")
        print("6) Watch (keep syncing)")
        print("7) Edit excluded folders")
        print("8) Show settings file")
        print("q) Quit")
        try:
            choice = input("Select an option: ").strip().lower()
        except EOFError:
            print()
            return 0
        if choice in {"q", "quit", "exit"}:
            return 0
        action = actions.get(choice)
        if action is None:
            print("Unknown option.")
            continue
        try:
            action()
        except (SettingsError, SyncError, OSError) as exc:
            print(f"error: {exc}")


def _menu_add(store: SettingsStore) -> None:
    name = input("Pair name: ").strip()
    left = input("Left folder: ").strip()
    right = input("Right folder: ").strip()
    raw_exclude = input("Exclude folders (comma-separated, blank for none): ").strip()
    exclude = [item.strip() for item in raw_exclude.split(",") if item.strip()]
    pair = store.add_pair(name, left, right, exclude=exclude)
    print(f"Saved pair {pair.name!r}")
    _print_exclude(pair.exclude)


def _menu_remove(store: SettingsStore) -> None:
    if not store.pairs:
        print("No folder pairs configured.")
        return
    _print_pairs(store)
    name = input("Name to remove: ").strip()
    pair = store.remove_pair(name)
    print(f"Removed pair {pair.name!r}")


def _menu_sync_all(store: SettingsStore) -> None:
    if not store.pairs:
        print("No folder pairs configured.")
        return
    for pair in store.pairs:
        _sync_and_save(store, pair)


def _menu_sync_one(store: SettingsStore) -> None:
    if not store.pairs:
        print("No folder pairs configured.")
        return
    _print_pairs(store)
    name = input("Pair name to sync: ").strip()
    _sync_and_save(store, store.get_pair(name))


def _menu_watch(store: SettingsStore) -> None:
    if not store.pairs:
        print("No folder pairs configured.")
        return
    _print_pairs(store)
    name = input("Pair name to watch (blank for all): ").strip() or None
    raw = input("Interval in seconds [2]: ").strip()
    try:
        interval = float(raw) if raw else 2.0
    except ValueError as exc:
        raise SettingsError(f"Invalid interval: {raw}") from exc
    print(f"Watching every {interval}s. Press Ctrl+C to stop.")
    try:
        run_watch(store, name=name, interval=interval, on_result=_print_result, on_status=print)
    except KeyboardInterrupt:
        print("\nStopped watching.")


def _menu_exclude(store: SettingsStore) -> None:
    if not store.pairs:
        print("No folder pairs configured.")
        return
    _print_pairs(store)
    name = input("Pair name to edit excludes: ").strip()
    pair = store.get_pair(name)
    _print_exclude(pair.exclude)
    raw = input("New exclude list (comma-separated, blank to clear): ").strip()
    exclude = [item.strip() for item in raw.split(",") if item.strip()]
    pair = store.update_exclude(name, exclude)
    print(f"Updated excludes for {pair.name!r}")
    _print_exclude(pair.exclude)


def _sync_and_save(store: SettingsStore, pair: FolderPair) -> SyncResult:
    left, right = pair.resolved()
    result = sync_pair(left, right, snapshot=pair.snapshot, exclude=pair.exclude)
    store.update_snapshot(pair.name, result.snapshot)
    _print_result(pair.name, result)
    return result


def _print_pairs(store: SettingsStore) -> None:
    if not store.pairs:
        print("No folder pairs configured.")
        return
    print(f"Settings: {store.path}")
    for index, pair in enumerate(store.pairs, start=1):
        print(f"{index}. {pair.name}")
        print(f"   left : {pair.left}")
        print(f"   right: {pair.right}")
        if pair.exclude:
            print(f"   exclude: {', '.join(pair.exclude)}")


def _print_exclude(exclude: list[str]) -> None:
    if exclude:
        print(f"  exclude: {', '.join(exclude)}")
    else:
        print("  exclude: (none)")


def _print_settings_path(store: SettingsStore) -> None:
    print(f"Settings file: {store.path}")
    print(f"Exists: {'yes' if store.path.exists() else 'no'}")


def _print_result(name: str, result: SyncResult) -> None:
    print(
        f"Synced {name!r}: {len(result.copied)} copied, {len(result.deleted)} deleted, "
        f"{len(result.skipped)} unchanged, {len(result.conflicts)} conflicts"
    )
    for action in result.copied:
        print(f"  copy   {action.source} -> {action.destination}")
    for action in result.deleted:
        print(f"  delete {action.source}")
    for relative in result.conflicts:
        print(f"  conflict {relative} (same mtime, different content)")

