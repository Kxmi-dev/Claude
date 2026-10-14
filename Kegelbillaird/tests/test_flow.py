"""Durchgängige Abläufe ohne Oberfläche: Tasten → Wertung → Speichern → Absturz → Fortsetzen → PDF."""

import random
import unittest

from tests.helpers import BK50, BK100, FakeClock, TempDir

from bk.game import Game, GameError
from bk.input_logic import Action, GameKey, ScoreInputController
from bk.models import GameState, GameStatus
from bk.pdf_report import write_report
from bk.storage import GameStorage, LoadStatus


class Operator:
    """Simuliert den Bediener am Nummernblock (wie die Zählansicht)."""

    def __init__(self, storage: GameStorage, game: Game, lock: float = 3.0):
        self.clock = FakeClock()
        self.ctrl = ScoreInputController(lock, 1.0, 5.0, self.clock)
        self.storage = storage
        self.game = game

    def press(self, key: GameKey, digit=None) -> Action:
        result = self.ctrl.press(key, digit)
        if result.action is Action.SCORE:
            self.game.record(result.value)
            self.storage.save_active(self.game.state)
        elif result.action is Action.UNDO:
            if self.game.undo() is not None:
                self.storage.save_active(self.game.state)
        return result.action

    def enter(self, value: int) -> Action:
        if value < 0:                         # Plus ist voreingestellt, Minus wird extra gewählt
            self.press(GameKey.MINUS)
        action = self.press(GameKey.DIGIT, abs(value))
        self.clock.advance(3.0)   # Sperrzeit abwarten
        return action


class FlowTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()
        self.storage = GameStorage(self.tmp.path / "data", self.tmp.path / "results")

    def tearDown(self):
        self.tmp.cleanup()

    def _new(self, mode):
        state = GameState.new(mode)
        self.storage.save_active(state)
        return Game(state)

    def _finish(self, game):
        game.finish()
        self.storage.save_active(game.state)
        pdf = write_report(game.state, self.storage.results_dir, "Verein", "BK")
        self.storage.archive_active(game.state, "beendet")
        return pdf

    def test_full_bk50_game_with_corrections_and_crashes(self):
        rnd = random.Random(50)
        game = self._new(BK50)
        op = Operator(self.storage, game)
        expected: list[int] = []
        while len(expected) < 50:
            value = rnd.randint(-7, 7)
            self.assertEqual(op.enter(value), Action.SCORE)
            expected.append(value)
            if rnd.random() < 0.15:                 # Fehler bemerkt -> "/" -> neu eingeben
                op.clock.advance(1.0)
                self.assertEqual(op.press(GameKey.UNDO), Action.UNDO)
                expected.pop()
            if rnd.random() < 0.1:                  # Absturz: alles neu von Platte laden
                loaded = GameStorage(self.storage.data_dir, self.storage.results_dir).load_active()
                self.assertEqual(loaded.status, LoadStatus.OK)
                game = Game(loaded.state)
                op = Operator(self.storage, game)
            self.assertEqual(game.state.strokes, expected)
        self.assertTrue(game.is_complete)
        self.assertEqual(game.played, 50)
        self.assertEqual(game.total, sum(expected))
        pdf = self._finish(game)
        self.assertTrue(pdf.exists())
        self.assertFalse(self.storage.has_active_files())

    def test_full_bk100_game_finishes_exactly_at_100(self):
        game = self._new(BK100)
        op = Operator(self.storage, game)
        for i in range(100):
            self.assertFalse(game.is_complete)
            op.enter(i % 8)
        self.assertTrue(game.is_complete)
        with self.assertRaises(GameError):                 # ein 101. Stoß ist unmöglich
            op.enter(5)
        self.assertEqual(game.played, 100)
        self._finish(game)
        self.assertEqual(game.state.status, GameStatus.FINISHED)
        self.assertEqual(game.total, sum(i % 8 for i in range(100)))

    def test_input_during_lock_is_not_counted(self):
        game = self._new(BK50)
        op = Operator(self.storage, game)
        op.press(GameKey.DIGIT, 4)
        for _ in range(5):                                   # Prellen / Mehrfachdruck
            op.press(GameKey.DIGIT, 4)
            op.press(GameKey.MINUS)
            op.press(GameKey.DIGIT, 4)
            op.clock.advance(0.3)
        self.assertEqual(game.state.strokes, [4])
        self.assertEqual(self.storage.load_active().state.strokes, [4])

    def test_multiple_undo_updates_saved_state(self):
        game = self._new(BK50)
        op = Operator(self.storage, game)
        for value in (1, 2, 3, 4):
            op.enter(value)
        for _ in range(3):
            op.press(GameKey.UNDO)
            op.clock.advance(1.0)
        self.assertEqual(game.state.strokes, [1])
        self.assertEqual(self.storage.load_active().state.strokes, [1])

    def test_resume_before_last_stroke_then_finish(self):
        game = self._new(BK50)
        op = Operator(self.storage, game)
        for _ in range(49):
            op.enter(2)
        restored = Game(GameStorage(self.storage.data_dir, self.storage.results_dir).load_active().state)
        self.assertEqual(restored.current_stroke_number, 50)
        op = Operator(self.storage, restored)
        op.enter(-3)
        self.assertTrue(restored.is_complete)
        self.assertEqual(restored.total, 95)
        self.assertTrue(self._finish(restored).exists())


if __name__ == "__main__":
    unittest.main()
