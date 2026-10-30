from constants import SAVE_FILE, COLS, ROWS, Cell, Player, Mode, directions
import random
import json
import os
import curses
import tempfile


# Handles the board grid and basic board operations.
class Board:
    def reset_board(self):
        self.board = [[Cell.EMPTY for _ in range(COLS)] for _ in range(ROWS)]
    
    def __init__(self):
        self.reset_board()

    def is_full(self) -> bool:
        return Cell.EMPTY not in self.board[0]

    def is_valid_column(self, c: int) -> bool:
        return 0 <= c < COLS
    
    def is_column_full(self, c: int) -> bool:
        return self.board[0][c] != Cell.EMPTY
    
    def get_valid_columns(self) -> list[int]:
        valid_columns = []
        for c in range(COLS):
            if not self.is_column_full(c):
                valid_columns.append(c)
        return valid_columns
    
    # Drops a token into the lowest empty cell of the chosen column.
    def drop_token(self, c: int, cell_type: Cell) -> int:
        for r in range(ROWS - 1, -1, -1):
            if self.board[r][c] == Cell.EMPTY:
                self.board[r][c] = cell_type
                return r
        raise ValueError("Column is full.")

    def top_border(self):
        line = "\u250C"
        for c in range(COLS):
            line += "\u2500\u2500"
            if c == COLS - 1:
                line += "\u2510"
            else:
                line += "\u252C"
        return line
    
    def mid_border(self):
        line = "\u251C"
        for c in range(COLS):
            line += "\u2500\u2500"
            if c == COLS - 1:
                line += "\u2524"
            else:
                line += "\u253C"
        return line

    def bottom_border(self):
        line =  "\u2514"
        for c in range(COLS):
            line += "\u2500\u2500"
            if c == COLS - 1:
                line += "\u2518"
            else:
                line += "\u2534"
        return line

    def row_line(self, r: int):
        line =  "\u2502"
        for c in range(COLS):
            line += self.board[r][c].value
            line += "\u2502"
        return line

# Controls the game state, turns, win checking, AI, and draw detection.
class Game:
    def __init__(self):
        self.board = Board()
        self.current_player = Player.WHITE

    @property
    def current_cell(self) -> Cell:
        return self.current_player.value
    
    @property
    def token(self) -> str:
        return self.current_cell.value
        
    def switch_player(self):
        self.current_player = self.current_player.opposite()
    
    def available_cells(self, row: int, col: int, dr: int, dc: int) -> int:
        count = 0
        r, c = row + dr, col + dc

        while 0 <= r < ROWS and 0 <= c < COLS:
            count += 1
            r += dr
            c += dc

        return count
    
    # Checks whether the last move created four connected tokens.
    def check_win(self, row: int, col: int, cell_type: Cell) -> bool:
        for dr, dc in directions:
            possible = (
                1
                + self.available_cells(row, col, dr, dc)
                + self.available_cells(row, col, -dr, -dc)
            )

            if possible < 4:
                continue

            count = 1

            r, c = row + dr, col + dc
            while 0 <= r < ROWS and 0 <= c < COLS and self.board.board[r][c] == cell_type:
                count += 1
                r += dr
                c += dc
            r, c = row - dr, col - dc
            while 0 <= r < ROWS and 0 <= c < COLS and self.board.board[r][c] == cell_type:
                count += 1
                r -= dr
                c -= dc
            
            if count >= 4:
                return True
            
        return False
    
    def remove_token(self, row: int, col: int) -> None:
        self.board.board[row][col] = Cell.EMPTY

    # Temporarily tries a move, checks if it wins, then removes the token.
    def would_win(self, col: int, cell_type: Cell) -> bool:
        row = self.board.drop_token(col, cell_type)
        flag = self.check_win(row, col, cell_type)
        self.remove_token(row, col)
        return flag
    
    # ----- AI helpers -----
    def find_winning_column(self, cell_type: Cell) -> int | None:
        valid_columns = self.board.get_valid_columns()
        wins = []
        for col in valid_columns:
            if self.would_win(col,cell_type):
                wins.append(col)
        if wins:
            return random.choice(wins)
        return None
    
    # The AI first looks for a winning move, then blocks the opponent, then scores possible moves.
    def get_ai_column(self, ai_cell: Cell) -> int:
        human_cell = Cell.BLACK if ai_cell is Cell.WHITE else Cell.WHITE
        valid_columns = self.board.get_valid_columns()

        col = self.find_winning_column(ai_cell)
        if col is not None:
            return col
        
        col = self.find_winning_column(human_cell)
        if col is not None:
            return col
        
        moves = {}
        for c in valid_columns:
            r = self.board.drop_token(c, ai_cell)
            score = self.score_board(ai_cell)
            if self.find_winning_column(human_cell) is not None:
                score -= 10000
            moves[c] = score
            self.remove_token(r, c)

        max_score = max(moves.values())
        top_moves = [move for move, score in moves.items() if score == max_score]

        return random.choice(top_moves)

    # Gives a score to a group of 4 cells based on how useful it is for the AI.
    def score_window(self, window: list, ai_cell: Cell) -> int:   
        human_cell = Cell.BLACK if ai_cell is Cell.WHITE else Cell.WHITE
        ai = window.count(ai_cell)
        human = window.count(human_cell)
        empty = 4 - ai - human

        if ai > 0 and human > 0:
            return 0
        elif ai == 3 and empty == 1:
            return 50
        elif ai == 2 and empty == 2:
            return 10
        elif ai == 1 and empty == 3:
            return 1
        elif human == 3 and empty == 1:
            return -80
        elif human == 2 and empty == 2:
            return -15
        elif human == 1 and empty == 3:
            return -1
        else:
            return 0
    
    def score_board(self, ai_cell: Cell) -> int:
        score = 0
        for row in range(ROWS):
            for col in range(COLS):
                for dr, dc in directions:
                    window = self.window_cells(row, col, dr, dc)
                    if len(window) == 4:
                        score += self.score_window(window, ai_cell)
        return score
    
    # ----- Early draw helpers -----
    def window_cells(self, row: int, col: int, dr: int, dc: int) -> list[Cell]:
        cells = []
        for _ in range(4):
            if 0 <= row < ROWS and 0 <= col < COLS:
                cells.append(self.board.board[row][col])
                row += dr
                col += dc
            else:
                break
        return cells

    # A player can still win if at least one 4-cell window is not blocked by the opponent.
    def player_can_still_win(self, cell_type: Cell) -> bool:
        opp = Cell.BLACK if cell_type is Cell.WHITE else Cell.WHITE
        for row in range(ROWS):
            for col in range(COLS):
                for dr, dc in directions:
                    window = self.window_cells(row, col, dr, dc)
                    if len(window) == 4 and opp not in window:
                        return True
        return False

    def is_early_draw(self) -> bool:
        white_can_win = self.player_can_still_win(Cell.WHITE)
        black_can_win = self.player_can_still_win(Cell.BLACK)

        return not white_can_win and not black_can_win

    # Main TUI game loop for both multiplayer and single-player modes.
    def play_tui(self, stdscr, mode: Mode, player: Player = Player.WHITE) -> str:
        status_message = "Game started."

        while True:
            draw_game_screen(stdscr, self, status_message=status_message)

            if mode is Mode.SINGLEPLAYER:
                if player is self.current_player:
                    col = get_column_tui(stdscr, self, status_message)
                    if col is None:
                        if ask_save_tui(stdscr, self):
                            if save_game_tui(stdscr, self, mode, player):
                                return "saved"
                            continue
                        else:
                            return "quit"

                    status_message = f"Player {self.token} played column {col + 1}."
                else:
                    draw_game_screen(stdscr, self, status_message="Computer is thinking...")
                    curses.napms(700)
                    col = self.get_ai_column(self.current_cell)
                    status_message = f"computer({self.token}) played column {col + 1}"
            else:
                col = get_column_tui(stdscr, self, status_message)
                if col is None:
                    if ask_save_tui(stdscr, self):
                        if save_game_tui(stdscr, self, mode, player):
                            return "saved"
                        continue
                    else:
                        return "quit"
                status_message = f"Player {self.token} played column {col + 1}."

            row = self.board.drop_token(col, self.current_cell)

            if self.check_win(row, col, self.current_cell):
                draw_game_screen(stdscr, self, status_message=f"Player {self.token} wins! Press any key.")
                stdscr.getch()
                return "finished"

            if self.board.is_full():
                draw_game_screen(stdscr, self, status_message="Draw! Press any key.")
                stdscr.getch()
                return "finished"

            if self.is_early_draw():
                draw_game_screen(stdscr, self, status_message="Early draw! Press any key.")
                stdscr.getch()
                return "finished"

            self.switch_player()

# ----- Save and load helpers -----
# Converts Cell enum values into strings so they can be saved as JSON.
def board_to_strings(game: Game) -> list[list[str]]:
    board_data = []

    for row in game.board.board:
        string_row = []
        for cell in row:
            string_row.append(cell.name)
        board_data.append(string_row)

    return board_data

# Converts saved string values back into Cell enum values.
def strings_to_board(board_data: list[list[str]]) -> list[list[Cell]]:
    board = []

    for row in board_data:
        cell_row = []
        for cell_name in row:
            cell_row.append(Cell[cell_name])
        board.append(cell_row)

    return board

# Saves the unfinished game state to a JSON file.
def save_game(game: Game, mode: Mode, player: Player) -> None:
    data = {
        "board": board_to_strings(game),
        "current_player": game.current_player.name,
        "mode": mode.name,
        "player": player.name,
    }

    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=SAVE_FILE.parent,
            prefix=".savegame.", suffix=".tmp", delete=False,
        ) as file:
            temporary_path = file.name
            json.dump(data, file, indent=4)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary_path, SAVE_FILE)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                os.unlink(temporary_path)
            except FileNotFoundError:
                pass

# Loads a saved game and restores the board, mode, and current player.
def load_game() -> tuple[Game, Mode, Player] | None:
    try:
        with open(SAVE_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, UnicodeError) as error:
        raise ValueError("Save file is not valid UTF-8 JSON.") from error

    if not isinstance(data, dict):
        raise ValueError("Save data must be a JSON object.")

    for field, enum_type in (("current_player", Player), ("mode", Mode), ("player", Player)):
        if not isinstance(data.get(field), str) or data[field] not in enum_type.__members__:
            raise ValueError(f"Save data has a missing or invalid {field}.")

    board_data = data.get("board")
    if not isinstance(board_data, list) or len(board_data) != ROWS:
        raise ValueError(f"Saved board must have {ROWS} rows.")
    for row in board_data:
        if not isinstance(row, list) or len(row) != COLS:
            raise ValueError(f"Each saved row must have {COLS} cells.")
        if any(not isinstance(cell, str) or cell not in Cell.__members__ for cell in row):
            raise ValueError("Saved board contains an invalid cell.")

    game = Game()
    game.current_player = Player[data["current_player"]]
    mode = Mode[data["mode"]]
    player = Player[data["player"]]
    game.board.board = strings_to_board(board_data)

    for col in range(COLS):
        found_token = False
        for row in range(ROWS):
            if game.board.board[row][col] is Cell.EMPTY:
                if found_token:
                    raise ValueError("Saved board contains a floating token.")
            else:
                found_token = True

    white = sum(row.count(Cell.WHITE) for row in game.board.board)
    black = sum(row.count(Cell.BLACK) for row in game.board.board)
    if white == black:
        expected_player = Player.WHITE
    elif white == black + 1:
        expected_player = Player.BLACK
    else:
        raise ValueError("Saved token counts do not match alternating turns.")
    if game.current_player is not expected_player:
        raise ValueError("Saved current player does not match the token counts.")

    # Saves are made before a turn; completed games cannot be resumed.
    for row in range(ROWS):
        for col in range(COLS):
            cell = game.board.board[row][col]
            if cell is not Cell.EMPTY and game.check_win(row, col, cell):
                raise ValueError("Saved game already has a winner.")
    if game.board.is_full() or game.is_early_draw():
        raise ValueError("Saved game has already ended in a draw.")

    return game, mode, player

def delete_save_file():
    try:
        os.remove(SAVE_FILE)
    except FileNotFoundError:
        pass

# ----- TUI helpers -----
def draw_text(stdscr, y: int, x: int, text: str, *attributes) -> None:
    height, width = stdscr.getmaxyx()
    if 0 <= y < height and 0 <= x < width - 1:
        try:
            # Leave the last column unused to avoid curses' bottom-right error.
            stdscr.addnstr(y, x, text, width - x - 1, *attributes)
        except curses.error:
            # A resize can occur between checking dimensions and writing.
            pass


def prepare_screen(stdscr) -> None:
    while True:
        height, width = stdscr.getmaxyx()
        stdscr.clear()
        if height >= 24 and width >= 80:
            return
        draw_text(stdscr, 0, 0, "Resize terminal to at least 80 columns and 24 rows.")
        draw_text(stdscr, 1, 0, f"Current size: {width} columns, {height} rows.")
        stdscr.refresh()
        stdscr.getch()


# Draws the main game screen using curses.
def draw_game_screen(stdscr, game: Game, selected_col: int | None = None, status_message: str = "") -> None:
    prepare_screen(stdscr)

    y = 1
    x = 4

    draw_text(stdscr, y, x, "⚪ CONNECT FOUR ⚫")
    y += 2

    draw_text(stdscr, y, x, f"Current player: {game.token}")
    y += 1

    draw_text(stdscr, y, x, "Use LEFT/RIGHT or 1-6. ENTER to play. Press q to quit.")
    y += 2

    if selected_col is not None:
        marker = "    "
        for c in range(COLS):
            if c == selected_col:
                marker += "↓  "
            else:
                marker += "   "
        draw_text(stdscr, y, x, marker)
        y += 1

    numbers = "    "
    for c in range(COLS):
        numbers += f"{c + 1}  "
    draw_text(stdscr, y, x, numbers)
    y += 1

    draw_text(stdscr, y, x, f"  {game.board.top_border()}")
    y += 1

    for r in range(ROWS):
        draw_text(stdscr, y, x, f"{r + 1} {game.board.row_line(r)}")
        y += 1

        if r != ROWS - 1:
            draw_text(stdscr, y, x, f"  {game.board.mid_border()}")
            y += 1

    draw_text(stdscr, y, x, f"  {game.board.bottom_border()}")
    y += 2

    if status_message:
        draw_text(stdscr, y, x, status_message)

    stdscr.refresh()

# Lets the player choose a column using arrows, number keys, or q to quit.
def get_column_tui(stdscr, game: Game, status_message: str = "") -> int | None:
    selected_col = 0

    while True:
        draw_game_screen(stdscr, game, selected_col, status_message)

        key = stdscr.getch()

        if key == curses.KEY_LEFT:
            selected_col = (selected_col - 1) % COLS

        elif key == curses.KEY_RIGHT:
            selected_col = (selected_col + 1) % COLS

        elif key in [10, 13, curses.KEY_ENTER]:
            if game.board.is_column_full(selected_col):
                status_message = "That column is full. Choose another one."
            else:
                return selected_col
            
        elif ord("1") <= key <= ord(str(COLS)):
            chosen_col = key - ord("1")

            if game.board.is_column_full(chosen_col):
                status_message = "That column is full. Choose another one."
            else:
                return chosen_col

        elif key == ord("q"):
            return None

# Asks the player whether to save before quitting an unfinished game.
def ask_save_tui(stdscr, game: Game) -> bool:
    while True:
        draw_game_screen(stdscr,game, status_message="Save game? Press y for yes, n for no.")
        key = stdscr.getch()

        if key in [ord("y"), ord("Y")]:
            return True

        if key in [ord("n"), ord("N")]:
            return False

def save_game_tui(stdscr, game: Game, mode: Mode, player: Player) -> bool:
    while True:
        try:
            save_game(game, mode, player)
        except OSError:
            while True:
                draw_game_screen(
                    stdscr, game,
                    status_message="Save failed. Press r to retry or g to return to game.",
                )
                key = stdscr.getch()
                if key in (ord("g"), ord("G")):
                    return False
                if key in (ord("r"), ord("R")):
                    break
        else:
            draw_game_screen(stdscr, game, status_message="Game saved. Press any key.")
            stdscr.getch()
            return True

def draw_message_screen(stdscr, message: str) -> None:
    prepare_screen(stdscr)

    y = 1
    x = 4

    draw_text(stdscr, y, x, "⚪ CONNECT FOUR ⚫")
    y += 2

    draw_text(stdscr, y, x, message)
    y += 1
    
    draw_text(stdscr, y, x, "Press any key to continue.")
    stdscr.refresh()
   
def show_help_tui(stdscr) -> None:
    prepare_screen(stdscr)

    y = 1
    x = 4

    lines = [
        "CONNECT FOUR HELP",
        "",
        "The board is 6x6.",
        "Use LEFT/RIGHT arrows to choose a column.",
        "Press ENTER to drop a piece.",
        "Press q during your turn to quit or save.",
        "First player to connect 4 wins.",
        "Connections can be horizontal, vertical, or diagonal.",
        "If no player can win, the game is a draw.",
        "",
        "Press any key to return to the menu.",
    ]

    for line in lines:
        draw_text(stdscr, y, x, line)
        y += 1

    stdscr.refresh()
    stdscr.getch()

def load_saved_game(stdscr) -> None:
    try:
        loaded = load_game()
    except ValueError as error:
        draw_message_screen(stdscr, f"Cannot load game: {error}")
        stdscr.getch()
        return
    except OSError:
        draw_message_screen(stdscr, "Cannot read save file. Check file permissions.")
        stdscr.getch()
        return
    if loaded is None:
        draw_message_screen(stdscr, "No saved game found.")
        stdscr.getch()
    else:
        game, mode, player = loaded
        result = game.play_tui(stdscr, mode, player)

        if result == "finished":
            try:
                delete_save_file()
            except OSError:
                draw_message_screen(stdscr, "Warning: could not remove the completed game's save file.")
                stdscr.getch()

# Draws a selectable menu box.
def draw_menu_tui(stdscr, options: list[str], selected_index: int) -> None:
    prepare_screen(stdscr)

    y = 1
    x = 4

    width = 25

    draw_text(stdscr, y, x, "┌" + "─" * width + "┐")
    y += 1

    draw_text(stdscr, y, x, "│     ⚪CONNECT FOUR⚫    │")
    y += 1

    draw_text(stdscr, y, x, "├" + "─" * width + "┤")
    y += 1

    for i, option in enumerate(options):
        text = f"{i + 1}) {option}"

        text = text.ljust(width - 2)

        if i == selected_index:
            draw_text(stdscr, y, x, "│ ")
            draw_text(stdscr, y, x + 2, text, curses.A_REVERSE)
            draw_text(stdscr, y, x + width, " │")
        else:
            draw_text(stdscr, y, x, f"│ {text} │")

        y += 1

    draw_text(stdscr, y, x, "└" + "─" * width + "┘")
    y += 2

    draw_text(stdscr, y, x, "Use UP/DOWN arrows, number keys, or ENTER.")

    stdscr.refresh()

# Handles menu navigation and returns the selected option.
def get_menu_choice_tui(stdscr, options: list[str]) -> int:
    selected_index = 0

    while True:
        draw_menu_tui(stdscr, options, selected_index)
        key = stdscr.getch()

        if key == curses.KEY_UP:
            selected_index = (selected_index - 1) % len(options)

        elif key == curses.KEY_DOWN:
            selected_index = (selected_index + 1) % len(options)

        elif ord("1") <= key <= ord(str(len(options))):
            return key - ord("1")

        elif key in [10, 13, curses.KEY_ENTER]:
            return selected_index

# Main program loop for the TUI menu.      
def main_tui(stdscr):
    curses.curs_set(0)
    stdscr.keypad(True)

    while True:
        options = [
            "Continue Saved Game",
            "Human vs Human",
            "Human vs AI",
            "Help / How to play",
            "Exit",
        ]

        choice = get_menu_choice_tui(stdscr, options)

        if choice == 0:
            load_saved_game(stdscr)

        elif choice == 1:
            game = Game()
            game.play_tui(stdscr, Mode.MULTIPLAYER)

        elif choice == 2:
            colors = [
                "White",
                "Black",
            ]

            color_num = get_menu_choice_tui(stdscr, colors)

            if color_num == 0:
                color = Player.WHITE
            else:
                color = Player.BLACK

            game = Game()
            game.play_tui(stdscr, Mode.SINGLEPLAYER, color)

        elif choice == 3:
            show_help_tui(stdscr)

        elif choice == 4:
            break

if __name__ == "__main__":
    curses.wrapper(main_tui)
