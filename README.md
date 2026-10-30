# Connect Four

A Python terminal implementation of Connect Four on a 6×6 board, with local
two-player play, a heuristic computer opponent, and save/load support.

## Features

- Play against another person or the computer; choose either color in single-player mode.
- Connect four horizontally, vertically, or diagonally. White moves first.
- The computer prioritizes immediate wins and blocks, then scores candidate moves
  and randomly selects among equally rated options.
- Detect full-board draws and positions where neither player can form a winning line.
- Resume saved games with the board, turn, mode, and human color restored.
- Resize the terminal during play without losing game state.

## Requirements

- Python 3.10 or newer.
- Python's standard-library `curses` module, normally available on Linux and macOS.
- An interactive UTF-8 terminal with arrow-key support, at least 80 columns and
  24 rows, and a font that displays the Unicode pieces correctly.

No third-party Python packages are required on supported systems. Standard
Windows Python installations do not include `curses`.

## Launch

Open a terminal in the project folder and run:

```bash
python3 base.py
```

## Controls

| Action | Keys |
| --- | --- |
| Navigate menus | Up/Down and Enter, or a numbered option |
| Select and play a column | Left/Right and Enter |
| Play a column directly | 1–6 |
| Quit during a human turn | `q`, then `y` to save or `n` to leave without saving |
| Retry a failed save or return to play | `r` or `g` |
| Dismiss help, load errors, or game results | Any key |

If the terminal becomes smaller than 80×24, enlarge it to resume play.

## Saved games

The game uses one save slot, `savegame.json`, beside `base.py`. Choose
**Continue Saved Game** from the menu to resume it. The game folder must be
writable and have space available.

Saving atomically replaces the slot; failures before replacement preserve the
previous save. Loading checks the saved board and turn information and reports
invalid saves without modifying them.

Completing a resumed game removes its save file, with a warning if removal
fails. Leaving without saving preserves any previous save.

## Tests

From the project folder:

```bash
python3 -m unittest -v test_base.py
```

Tests cover game rules, immediate winning and blocking moves, save validation,
save-failure handling, and terminal resizing. Save tests use temporary files.
