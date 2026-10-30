import copy
import curses
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import base
from constants import Cell, COLS, Mode, Player, ROWS, SAVE_FILE


class SaveTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.path = Path(temporary.name) / "savegame.json"
        patcher = patch.object(base, "SAVE_FILE", self.path)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.data = {
            "board": [["EMPTY"] * COLS for _ in range(ROWS)],
            "current_player": "WHITE",
            "mode": "SINGLEPLAYER",
            "player": "WHITE",
        }

    def write_data(self, data):
        self.path.write_text(json.dumps(data), encoding="utf-8")

    def test_save_path_is_beside_source(self):
        self.assertEqual(SAVE_FILE, Path(base.__file__).resolve().parent / "savegame.json")

    def test_missing_file(self):
        self.assertIsNone(base.load_game())
        screen = Mock()
        with patch.object(base, "draw_message_screen") as draw:
            base.load_saved_game(screen)
        draw.assert_called_once_with(screen, "No saved game found.")

    def test_malformed_file(self):
        for content in (b"", b"{", b"\xff"):
            with self.subTest(content=content):
                self.path.write_bytes(content)
                with self.assertRaises(ValueError):
                    base.load_game()

    def test_invalid_structure(self):
        cases = [None, [], 1, "save", {}]
        for field in ("board", "current_player", "mode", "player"):
            data = copy.deepcopy(self.data)
            del data[field]
            cases.append(data)
        for field in ("current_player", "mode", "player"):
            for value in (None, [], {}, 1, "UNKNOWN"):
                data = copy.deepcopy(self.data)
                data[field] = value
                cases.append(data)
        for board in (None, {}, [], [["EMPTY"] * COLS],
                      [["EMPTY"] * (COLS - 1) for _ in range(ROWS)],
                      ["EMPTY"] * ROWS,
                      [["UNKNOWN"] * COLS for _ in range(ROWS)],
                      [[{}] * COLS for _ in range(ROWS)]):
            data = copy.deepcopy(self.data)
            data["board"] = board
            cases.append(data)
        for data in cases:
            with self.subTest(data=data):
                self.write_data(data)
                with self.assertRaises(ValueError):
                    base.load_game()

    def test_invalid_game_states(self):
        floating = copy.deepcopy(self.data)
        floating["board"][0][0] = "WHITE"
        floating["current_player"] = "BLACK"
        wrong_count = copy.deepcopy(self.data)
        wrong_count["board"][-1][0] = "BLACK"
        wrong_turn = copy.deepcopy(self.data)
        wrong_turn["current_player"] = "BLACK"
        winner = copy.deepcopy(self.data)
        winner["board"][-1][:4] = ["WHITE"] * 4
        winner["board"][-2][:3] = ["BLACK"] * 3
        winner["current_player"] = "BLACK"
        draw = copy.deepcopy(self.data)
        draw["board"] = [
            ["WHITE" if (r + c // 2) % 2 == 0 else "BLACK" for c in range(COLS)]
            for r in range(ROWS)
        ]
        early_draw = copy.deepcopy(draw)
        early_draw["board"][0][2] = "EMPTY"
        early_draw["current_player"] = "BLACK"
        for data in (floating, wrong_count, wrong_turn, winner, draw, early_draw):
            with self.subTest(data=data):
                self.write_data(data)
                with self.assertRaises(ValueError):
                    base.load_game()

    def test_round_trips(self):
        for mode in Mode:
            for player in Player:
                for moves in ([], [0], [0, 1], [0, 1, 0, 2, 3]):
                    with self.subTest(mode=mode, player=player, moves=moves):
                        game = base.Game()
                        for col in moves:
                            game.board.drop_token(col, game.current_cell)
                            game.switch_player()
                        base.save_game(game, mode, player)
                        loaded, loaded_mode, loaded_player = base.load_game()
                        self.assertEqual(loaded.board.board, game.board.board)
                        self.assertIs(loaded.current_player, game.current_player)
                        self.assertIs(loaded_mode, mode)
                        self.assertIs(loaded_player, player)

    def test_failed_writes_preserve_previous_save_and_remove_temporary_file(self):
        def partial_write(data, file, **kwargs):
            file.write('{"board":')
            raise OSError("No space left on device")

        for existing_save in (False, True):
            for target, failure in (
                ("json.dump", partial_write),
                ("os.fsync", OSError("Sync failed")),
                ("os.replace", PermissionError("Replacement denied")),
                ("tempfile.NamedTemporaryFile", PermissionError("Creation denied")),
            ):
                with self.subTest(existing_save=existing_save, target=target):
                    if existing_save:
                        self.write_data(self.data)
                        original = self.path.read_bytes()
                    else:
                        self.path.unlink(missing_ok=True)
                    with patch("base." + target, side_effect=failure):
                        with self.assertRaises(OSError):
                            base.save_game(base.Game(), Mode.MULTIPLAYER, Player.WHITE)
                    if existing_save:
                        self.assertEqual(self.path.read_bytes(), original)
                    else:
                        self.assertFalse(self.path.exists())
                    self.assertEqual(
                        set(self.path.parent.iterdir()), {self.path} if existing_save else set(),
                    )

    def test_replacement_uses_complete_file_in_same_directory(self):
        self.write_data(self.data)
        original = self.path.read_bytes()
        game = base.Game()
        game.board.drop_token(2, Cell.WHITE)
        game.switch_player()
        replace = base.os.replace

        def check_replace(source, destination):
            source = Path(source)
            self.assertEqual(source.parent, self.path.parent)
            self.assertEqual(destination, self.path)
            self.assertEqual(self.path.read_bytes(), original)
            data = json.loads(source.read_text(encoding="utf-8"))
            self.assertEqual(data["board"], base.board_to_strings(game))
            self.assertEqual(data["current_player"], "BLACK")
            replace(source, destination)

        with patch.object(base.os, "replace", side_effect=check_replace) as replacement:
            base.save_game(game, Mode.MULTIPLAYER, Player.WHITE)
        replacement.assert_called_once()
        self.assertEqual(base.load_game()[0].board.board, game.board.board)
        self.assertEqual(set(self.path.parent.iterdir()), {self.path})

    def test_save_retry_only_reports_success_after_replacement(self):
        game = base.Game()
        screen = Mock()
        screen.getch.side_effect = [ord("r"), ord(" ")]
        replace = base.os.replace
        replacements = 0

        def fail_once(source, destination):
            nonlocal replacements
            replacements += 1
            if replacements == 1:
                raise PermissionError("Replacement denied")
            replace(source, destination)

        with patch.object(base.os, "replace", side_effect=fail_once), \
                patch.object(base, "draw_game_screen") as draw:
            self.assertTrue(base.save_game_tui(screen, game, Mode.SINGLEPLAYER, Player.WHITE))
        messages = [call.kwargs["status_message"] for call in draw.call_args_list]
        self.assertEqual(len(messages), 2)
        self.assertIn("Save failed", messages[0])
        self.assertEqual(messages[1], "Game saved. Press any key.")
        self.assertEqual(replacements, 2)
        self.assertEqual(base.load_game()[0].board.board, game.board.board)
        self.assertEqual(set(self.path.parent.iterdir()), {self.path})

    def test_save_failures_return_to_play_in_both_modes(self):
        for mode in Mode:
            with self.subTest(mode=mode):
                game = base.Game()
                before = copy.deepcopy(game.board.board)
                screen = Mock()
                screen.getch.side_effect = [ord("r"), ord("g")]
                with patch.object(base, "get_column_tui", side_effect=[None, None]) as choose, \
                        patch.object(base, "ask_save_tui", side_effect=[True, False]), \
                        patch.object(base, "save_game", side_effect=OSError("Write failed")) as save, \
                        patch.object(base, "draw_game_screen") as draw:
                    result = game.play_tui(screen, mode, Player.WHITE)
                self.assertEqual(result, "quit")
                self.assertEqual(choose.call_count, 2)
                self.assertEqual(save.call_count, 2)
                self.assertEqual(game.board.board, before)
                self.assertIs(game.current_player, Player.WHITE)
                messages = [call.kwargs.get("status_message", "") for call in draw.call_args_list]
                self.assertEqual(sum("Save failed" in message for message in messages), 2)
                self.assertFalse(any("Game saved" in message for message in messages))

    def test_successful_save_exits_as_saved_in_both_modes(self):
        for mode in Mode:
            with self.subTest(mode=mode):
                game = base.Game()
                screen = Mock()
                with patch.object(base, "get_column_tui", return_value=None), \
                        patch.object(base, "ask_save_tui", return_value=True), \
                        patch.object(base, "draw_game_screen"):
                    self.assertEqual(game.play_tui(screen, mode, Player.WHITE), "saved")
                self.assertEqual(base.load_game()[0].board.board, game.board.board)

    def test_load_errors_are_shown_without_changing_file(self):
        self.write_data({})
        original = self.path.read_bytes()
        screen = Mock()
        with patch.object(base, "draw_message_screen") as draw:
            base.load_saved_game(screen)
        self.assertIn("Cannot load game:", draw.call_args.args[1])
        screen.getch.assert_called_once()
        self.assertEqual(self.path.read_bytes(), original)

    def test_unreadable_file_message(self):
        screen = Mock()
        with patch.object(base, "load_game", side_effect=PermissionError), \
                patch.object(base, "draw_message_screen") as draw:
            base.load_saved_game(screen)
        self.assertIn("Cannot read save file", draw.call_args.args[1])

    def test_finished_resumed_game_deletion(self):
        for error in (None, FileNotFoundError(), PermissionError(), OSError("I/O error")):
            with self.subTest(error=error):
                self.write_data(self.data)
                original = self.path.read_bytes()
                screen = Mock()
                with patch.object(base.Game, "play_tui", return_value="finished"), \
                        patch.object(base.os, "remove", side_effect=error) as remove, \
                        patch.object(base, "draw_message_screen") as draw:
                    self.assertIsNone(base.load_saved_game(screen))
                remove.assert_called_once_with(self.path)
                if error is not None and not isinstance(error, FileNotFoundError):
                    draw.assert_called_once_with(
                        screen, "Warning: could not remove the completed game's save file.",
                    )
                    screen.getch.assert_called_once()
                    self.assertEqual(self.path.read_bytes(), original)
                else:
                    draw.assert_not_called()
                    screen.getch.assert_not_called()

    def test_delete_save_file_missing_or_present(self):
        base.delete_save_file()
        self.write_data(self.data)
        base.delete_save_file()
        self.assertFalse(self.path.exists())


class TerminalTests(unittest.TestCase):
    def test_screens_wait_for_a_large_enough_terminal(self):
        for draw in (
            lambda screen: base.draw_menu_tui(screen, ["Play", "Exit"], 0),
            lambda screen: base.draw_game_screen(screen, base.Game(), 0, "Game started."),
            lambda screen: base.draw_message_screen(screen, "No saved game found."),
            base.show_help_tui,
        ):
            for small_size in ((10, 40), (24, 1), (1, 80), (1, 1)):
                with self.subTest(draw=draw, size=small_size):
                    screen = Mock()
                    size = small_size

                    def getch():
                        nonlocal size
                        size = (24, 80)
                        return curses.KEY_RESIZE

                    def addnstr(y, x, text, limit, *attributes):
                        height, width = size
                        self.assertTrue(0 <= y < height)
                        self.assertTrue(0 <= x < width - 1)
                        self.assertLessEqual(x + min(len(text), limit), width - 1)

                    screen.getmaxyx.side_effect = lambda: size
                    screen.getch.side_effect = getch
                    screen.addnstr.side_effect = addnstr
                    draw(screen)
                    self.assertGreaterEqual(screen.getch.call_count, 1)
                    self.assertEqual(size, (24, 80))

    def test_resize_during_a_write_does_not_crash(self):
        screen = Mock()
        screen.getmaxyx.return_value = (24, 80)
        screen.addnstr.side_effect = curses.error("addwstr() returned ERR")
        base.draw_menu_tui(screen, ["Play", "Exit"], 0)

    def test_resize_preserves_selected_column_and_board(self):
        screen = Mock()
        size = (24, 80)
        events = iter((curses.KEY_RIGHT, curses.KEY_RESIZE, curses.KEY_RESIZE, 10))

        def getch():
            nonlocal size
            event = next(events)
            if event == curses.KEY_RESIZE:
                size = (10, 40) if size == (24, 80) else (24, 80)
            return event

        screen.getmaxyx.side_effect = lambda: size
        screen.getch.side_effect = getch
        game = base.Game()
        game.board.drop_token(0, Cell.WHITE)
        before = copy.deepcopy(game.board.board)
        self.assertEqual(base.get_column_tui(screen, game), 1)
        self.assertEqual(game.board.board, before)


class GameTests(unittest.TestCase):
    def test_win_directions(self):
        for coordinates in (
            [(5, c) for c in range(4)],
            [(r, 0) for r in range(2, 6)],
            [(r, r) for r in range(4)],
            [(r, 5 - r) for r in range(4)],
        ):
            game = base.Game()
            for row, col in coordinates:
                game.board.board[row][col] = Cell.WHITE
            self.assertTrue(game.check_win(*coordinates[-1], Cell.WHITE))
        self.assertFalse(base.Game().check_win(5, 0, Cell.WHITE))

    def test_gravity_and_full_column(self):
        board = base.Board()
        for row in reversed(range(ROWS)):
            self.assertEqual(board.drop_token(0, Cell.WHITE), row)
        self.assertTrue(board.is_column_full(0))
        self.assertNotIn(0, board.get_valid_columns())
        with self.assertRaises(ValueError):
            board.drop_token(0, Cell.BLACK)

    def test_ai_wins_and_blocks_without_changing_board(self):
        for cell in (Cell.BLACK, Cell.WHITE):
            game = base.Game()
            for col in range(3):
                game.board.drop_token(col, cell)
            before = copy.deepcopy(game.board.board)
            self.assertEqual(game.get_ai_column(Cell.BLACK), 3)
            self.assertEqual(game.board.board, before)


if __name__ == "__main__":
    unittest.main()
