from enum import Enum
from pathlib import Path

SAVE_FILE = Path(__file__).resolve().parent / "savegame.json"

COLS = 6
ROWS = 6

class Cell(Enum):
    EMPTY = "  "
    WHITE = "⚪"
    BLACK = "⚫"

class Player(Enum):
    BLACK = Cell.BLACK
    WHITE = Cell.WHITE

    def opposite(self):
        return Player.BLACK if self is Player.WHITE else Player.WHITE

class Mode(Enum):
    SINGLEPLAYER = "singleplayer"
    MULTIPLAYER = "multiplayer"
    

directions = [
        (0, 1),   # horizontal
        (1, 0),   # vertical
        (1, 1),   # diagonal down-right
        (1, -1),  # diagonal down-left
    ]
