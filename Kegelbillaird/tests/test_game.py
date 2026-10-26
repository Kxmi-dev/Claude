"""Tests der Spiel-Engine: Wertungen, Stoßzähler, Rücknahme, Abschluss."""

import unittest

from tests.helpers import BK50, BK100

from bk.game import Game, GameError
from bk.models import GameState, GameStatus


def new_game(mode=BK50) -> Game:
    return Game(GameState.new(mode))


class RecordTests(unittest.TestCase):
    def test_all_valid_values_from_minus7_to_plus7(self):
        game = new_game(BK100)
        for value in range(-7, 8):
            game.record(value)
        self.assertEqual(game.state.strokes, list(range(-7, 8)))
        self.assertEqual(game.total, 0)
        self.assertEqual(game.played, 15)

    def test_invalid_values_are_rejected_without_state_change(self):
        game = new_game()
        for bad in (8, -8, 100, 1.5, True, False, "3", None):
            with self.subTest(bad=bad):
                with self.assertRaises(GameError):
                    game.record(bad)  # type: ignore[arg-type]
        self.assertEqual(game.played, 0)
        self.assertEqual(game.total, 0)

    def test_stroke_counter(self):
        game = new_game()
        self.assertEqual(game.current_stroke_number, 1)
        game.record(3)
        self.assertEqual(game.played, 1)
        self.assertEqual(game.current_stroke_number, 2)

    def test_running_totals_in_entries(self):
        game = new_game()
        for value in (3, 5, -2):
            game.record(value)
        self.assertEqual([(e.number, e.value, e.running_total) for e in game.entries()],
                         [(1, 3, 3), (2, 5, 8), (3, -2, 6)])

    def test_history_returns_last_entries_oldest_first(self):
        game = new_game()
        for value in (1, 2, 3, 4, 5, 6, 7):
            game.record(value)
        self.assertEqual([e.number for e in game.history(5)], [3, 4, 5, 6, 7])
        self.assertEqual(game.history(0), [])


class CompletionTests(unittest.TestCase):
    def _play_full(self, mode):
        game = new_game(mode)
        for i in range(mode.strokes):
            self.assertFalse(game.is_complete)
            game.record((i % 15) - 7)
        return game

    def test_bk50_completes_exactly_at_50(self):
        game = self._play_full(BK50)
        self.assertTrue(game.is_complete)
        self.assertEqual(game.played, 50)
        self.assertEqual(game.current_stroke_number, 50)
        with self.assertRaises(GameError):
            game.record(1)
        self.assertEqual(game.played, 50)

    def test_bk100_completes_exactly_at_100(self):
        game = self._play_full(BK100)
        self.assertTrue(game.is_complete)
        with self.assertRaises(GameError):
            game.record(0)
        game.finish()
        self.assertEqual(game.state.status, GameStatus.FINISHED)
        self.assertIsNotNone(game.state.finished_at)

    def test_finish_before_last_stroke_is_refused(self):
        game = new_game()
        game.record(4)
        with self.assertRaises(GameError):
            game.finish()
        self.assertTrue(game.is_running)

    def test_no_changes_after_finish(self):
        game = self._play_full(BK50)
        game.finish()
        with self.assertRaises(GameError):
            game.undo()
        with self.assertRaises(GameError):
            game.record(1)

    def test_abort(self):
        game = new_game()
        game.record(2)
        game.abort()
        self.assertEqual(game.state.status, GameStatus.ABORTED)
        with self.assertRaises(GameError):
            game.record(1)


class UndoTests(unittest.TestCase):
    def test_undo_removes_last_score_completely(self):
        game = new_game()
        for value in (3, 4):
            game.record(value)
        game.record(5)                       # Stoß 3: +5
        removed = game.undo()
        self.assertEqual((removed.number, removed.value), (3, 5))
        self.assertEqual(game.total, 7)
        self.assertEqual(game.played, 2)
        self.assertEqual(game.current_stroke_number, 3)
        self.assertEqual(game.state.strokes, [3, 4])

    def test_multiple_undos(self):
        game = new_game()
        for value in (1, -2, 3):
            game.record(value)
        game.undo()
        game.undo()
        self.assertEqual(game.state.strokes, [1])
        game.undo()
        self.assertEqual(game.state.strokes, [])
        self.assertIsNone(game.undo())       # nichts mehr zurückzunehmen
        self.assertEqual(game.total, 0)

    def test_undo_of_last_stroke_reopens_game(self):
        game = new_game()
        for _ in range(50):
            game.record(2)
        self.assertTrue(game.is_complete)
        game.undo()
        self.assertFalse(game.is_complete)
        self.assertEqual(game.current_stroke_number, 50)

    def test_replace_last_changes_only_last_stroke(self):
        game = new_game()
        self.assertIsNone(game.replace_last(3))   # noch kein Stoß
        game.record(4)
        game.record(-3)
        old, entry = game.replace_last(-2)
        self.assertEqual(old, -3)
        self.assertEqual((entry.number, entry.value, entry.running_total), (2, -2, 2))
        self.assertEqual(game.state.strokes, [4, -2])   # frühere Stöße bleiben fest
        self.assertEqual(game.state.corrections, 1)
        game.replace_last(-2)                            # gleicher Wert zählt nicht als Korrektur
        self.assertEqual(game.state.corrections, 1)
        with self.assertRaises(GameError):
            game.replace_last(8)


class ValueCountTests(unittest.TestCase):
    def test_counts_for_every_value(self):
        game = new_game(BK50)
        for value in (1, 1, 2, 3, 3, 3, 0, -2, 7, -7):
            game.record(value)
        counts = dict(game.value_counts())
        self.assertEqual(list(counts), list(range(-7, 8)))          # immer alle Werte -7 … +7
        self.assertEqual((counts[1], counts[2], counts[3], counts[0]), (2, 1, 3, 1))
        self.assertEqual((counts[-2], counts[7], counts[-7], counts[5]), (1, 1, 1, 0))
        self.assertEqual(sum(counts.values()), game.played)


class FigureTests(unittest.TestCase):
    def test_minus_halftime_prognosis(self):
        game = new_game(BK50)
        self.assertIsNone(game.prognosis)
        self.assertIsNone(game.halftime_score)
        values = [2, -1, 3, -2] * 6 + [4]    # 25 Stöße
        for value in values:
            game.record(value)
        self.assertEqual(game.minus_total, -18)
        self.assertEqual(game.halftime_score, sum(values))
        self.assertEqual(game.prognosis, round(sum(values) / 25 * 50))
        game.record(7)
        self.assertEqual(game.halftime_score, sum(values))   # Halbzeit bleibt fest


if __name__ == "__main__":
    unittest.main()


class SettingsCompatibilityTests(unittest.TestCase):
    def test_old_config_without_new_settings_still_works(self):
        """Eine config.py aus einer älteren Version (ohne neue Einträge) darf nicht zum Absturz führen."""
        import types

        import config
        from bk.settings import AppSettings

        old = types.ModuleType("old_config")
        for name in dir(config):
            if name.isupper() and name not in ("SHOW_REPORT_AFTER_GAME", "REPLAY_SECONDS_PER_STROKE"):
                setattr(old, name, getattr(config, name))
        settings = AppSettings.from_config(old)
        self.assertTrue(settings.show_report_after_game)
        self.assertEqual(settings.replay_seconds_per_stroke, 0.8)


class CorrectionCountTests(unittest.TestCase):
    def test_undo_is_counted_and_saved(self):
        from bk.models import GameState
        game = new_game(BK50)
        self.assertEqual(game.state.corrections, 0)
        game.record(3)
        game.undo()
        game.undo()                                  # nichts mehr da -> zählt nicht
        self.assertEqual(game.state.corrections, 1)
        loaded = GameState.from_dict(game.state.to_dict())
        self.assertEqual(loaded.corrections, 1)

    def test_old_saves_without_counter_load(self):
        from bk.models import GameState
        data = new_game(BK50).state.to_dict()
        del data["corrections"]
        self.assertIsNone(GameState.from_dict(data).corrections)
        data["corrections"] = -1
        with self.assertRaises(ValueError):
            GameState.from_dict(data)

