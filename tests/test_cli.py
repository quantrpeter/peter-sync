from __future__ import annotations

from pathlib import Path

from peter_sync.cli import main


def test_cli_add_list_sync_remove(tmp_path: Path, capsys) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    (left / "hello.txt").write_text("hello", encoding="utf-8")
    settings = tmp_path / "settings.json"

    assert main(["--settings", str(settings), "add", "notes", str(left), str(right)]) == 0
    assert main(["--settings", str(settings), "list"]) == 0
    assert main(["--settings", str(settings), "sync", "notes"]) == 0
    assert (right / "hello.txt").read_text(encoding="utf-8") == "hello"
    assert main(["--settings", str(settings), "remove", "notes"]) == 0

    output = capsys.readouterr().out
    assert "Added pair 'notes'" in output
    assert "notes" in output
    assert "Synced 'notes'" in output
    assert "Removed pair 'notes'" in output


def test_cli_version(capsys) -> None:
    try:
        main(["--version"])
    except SystemExit as exc:
        assert exc.code == 0
    assert "peter-sync" in capsys.readouterr().out
