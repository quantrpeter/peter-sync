# peter-sync

Bidirectional folder sync from the command line. Define folder pairs, save them as JSON, and keep both sides up to date.

## Install

```bash
pip install peter-sync
```

From a local checkout:

```bash
python -m pip install -e ".[dev]"
```

## Usage

Open the interactive menu:

```bash
peter-sync
```

Or use subcommands:

```bash
peter-sync add notes ~/Documents/Notes ~/Dropbox/Notes
peter-sync add code ~/src/app ~/backup/app --exclude node_modules --exclude .git
peter-sync list
peter-sync exclude code
peter-sync exclude code --add dist
peter-sync exclude code --remove .git
peter-sync exclude code --set node_modules dist
peter-sync sync notes
peter-sync sync
peter-sync watch notes
peter-sync watch --interval 5
peter-sync remove notes
```

`watch` is a long-running process. It polls the folders on an interval (default 2 seconds), reloads settings each cycle, and keeps copying or deleting until you press Ctrl+C. Omit the pair name to watch every saved pair.

Settings are stored at `~/.peter-sync/settings.json` unless you pass `--settings`.

Example settings file:

```json
{
  "pairs": [
    {
      "name": "notes",
      "left": "/Users/you/Documents/Notes",
      "right": "/Users/you/Dropbox/Notes",
      "snapshot": ["todo.md"],
      "exclude": ["node_modules", ".git"]
    }
  ]
}
```

## How sync works

- New files are copied to the other folder.
- When both sides have the same file, the newer modification time wins.
- Identical files are left alone.
- If both files differ and have the same mtime, the pair is reported as a conflict and left unchanged.
- Each pair can exclude folders. A bare name such as `node_modules` is skipped anywhere in the tree. A relative path such as `build/tmp` is skipped only at that location. Excluded folders are not copied, updated, or deleted.
- After the first sync, deleting a file on one side deletes it on the other. The last file list is stored in the settings JSON.

## Publish to PyPI

1. Create an API token at https://pypi.org/manage/account/token/
2. Build and upload:

```bash
python -m pip install build twine
python -m build
python -m twine upload dist/*
```

Or publish a GitHub Release and use `.github/workflows/publish.yml` with trusted publishing (or a `PYPI_API_TOKEN` repository secret).

## Develop

```bash
python -m pip install -e ".[dev]"
pytest
```
