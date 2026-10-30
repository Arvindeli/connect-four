# Connect Four

A 6×6 terminal game for two humans or one human against the computer.

## Requirements

- Python 3.10 or newer.
- Python's standard-library `curses` module, normally available on Linux and macOS.
- An interactive UTF-8 terminal with arrow-key support and enough space for the
  board and messages; use at least 80 columns and 24 rows.

No third-party Python packages are required on supported systems. Standard
Windows Python installations do not include `curses`.

## Launch

Open a terminal in the project folder, then run:

```bash
python3 base.py
```

## Controls

- Menus: Up/Down and Enter, or the numbered option.
- Game: Left/Right and Enter, or keys 1–6 to play a column immediately.
- Press `q` during a human turn to quit, then `y` to save or `n` to leave
  without saving.
- If saving fails, press `r` to retry or `g` to return to the game.
- Press any key to dismiss help, load errors, or end-of-game messages.

## Features

- White moves first. Connect four horizontally, vertically, or diagonally.
- Human vs Human and Human vs AI modes; choose either color against the AI.
- The computer takes an immediate win, blocks an immediate loss, then scores
  candidate moves and randomly chooses among equal scores.
- Full-board and early draw detection.
- One save slot, `savegame.json`, beside `base.py`. Saving replaces that slot.
- Saves are written to a temporary file in the same folder, then atomically
  replace the save slot. Failures before replacement leave the previous save intact.
- Continue Saved Game restores the board, turn, mode, and human color.
- Missing or invalid saves display a message. Invalid files are left intact.
- Windows smaller than 80 columns or 24 rows show a resize prompt. Enlarge the
  terminal to resume; game state is retained while waiting.
- Completing a resumed game removes its save file. If removal fails, a warning
  is shown before returning to the menu. Leaving without saving leaves any
  previous save intact.

## Checks

Open a terminal in the project folder, then run:

```bash
python3 -m unittest -v test_base.py
```

Tests use temporary save files and do not modify the runtime save.

## Limitations

- Piece alignment depends on the terminal's Unicode font support.
- The computer uses a heuristic, not an exhaustive search.
- Loading validates structure, gravity, turn counts, and unfinished-game status;
  it does not reconstruct the complete move history.
- Save writes require write permission and available space in the game folder.
