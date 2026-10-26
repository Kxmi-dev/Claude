"""Tests der Eingabelogik: Plus automatisch, Minus nur für einen Stoß, Sperrzeit, Rücknahme, Abbruch."""

import unittest

from tests.helpers import FakeClock

from bk.input_logic import Action, GameKey, ScoreInputController

P, M, D, U, A = GameKey.PLUS, GameKey.MINUS, GameKey.DIGIT, GameKey.UNDO, GameKey.ABORT


def make(lock=3.0, undo_lock=1.0, abort=5.0):
    clock = FakeClock()
    return ScoreInputController(lock, undo_lock, abort, clock), clock


class ScoreEntryTests(unittest.TestCase):
    def test_digit_alone_is_plus_0_to_7(self):
        for digit in range(8):
            with self.subTest(digit=digit):
                ctrl, _ = make()
                result = ctrl.press(D, digit)
                self.assertEqual(result.action, Action.SCORE)
                self.assertEqual(result.value, digit)

    def test_explicit_plus_still_works(self):
        ctrl, _ = make()
        self.assertEqual(ctrl.press(P).action, Action.PLUS_SELECTED)
        self.assertEqual(ctrl.press(D, 5).value, 5)

    def test_minus_0_to_7(self):
        for digit in range(8):
            with self.subTest(digit=digit):
                ctrl, _ = make()
                self.assertEqual(ctrl.press(M).action, Action.MINUS_SELECTED)
                self.assertTrue(ctrl.minus_selected)
                result = ctrl.press(D, digit)
                self.assertEqual(result.action, Action.SCORE)
                self.assertEqual(result.value, -digit if digit else 0)

    def test_minus_zero_is_zero_not_negative(self):
        ctrl, _ = make()
        ctrl.press(M)
        value = ctrl.press(D, 0).value
        self.assertEqual(value, 0)
        self.assertEqual(str(value), "0")

    def test_minus_applies_to_one_stroke_only(self):
        ctrl, clock = make()
        ctrl.press(M)
        self.assertEqual(ctrl.press(D, 3).value, -3)
        self.assertFalse(ctrl.minus_selected)          # automatisch zurück auf Plus
        clock.advance(3.0)
        self.assertEqual(ctrl.press(D, 3).value, 3)

    def test_plus_cancels_minus(self):
        ctrl, _ = make()
        ctrl.press(M)
        ctrl.press(P)
        self.assertFalse(ctrl.minus_selected)
        self.assertEqual(ctrl.press(D, 4).value, 4)

    def test_digits_8_and_9_are_invalid_and_keep_minus(self):
        ctrl, _ = make()
        ctrl.press(M)
        self.assertEqual(ctrl.press(D, 8).action, Action.IGNORED_INVALID)
        self.assertEqual(ctrl.press(D, 9).action, Action.IGNORED_INVALID)
        self.assertTrue(ctrl.minus_selected)
        self.assertEqual(ctrl.press(D, 4).value, -4)

    def test_invalid_digit_types(self):
        ctrl, _ = make()
        for bad in (-1, 10, None, True):
            self.assertEqual(ctrl.press(D, bad).action, Action.IGNORED_INVALID)
        self.assertFalse(ctrl.is_locked())

    def test_bouncing_digit_is_counted_once(self):
        """Doppelter/prellender Tastendruck: die zweite Ziffer fällt in die Sperre."""
        ctrl, clock = make()
        self.assertEqual(ctrl.press(D, 5).action, Action.SCORE)
        clock.advance(0.05)
        self.assertEqual(ctrl.press(D, 5).action, Action.IGNORED_LOCKED)


class LockTests(unittest.TestCase):
    def test_digits_are_blocked_for_lock_time(self):
        ctrl, clock = make(lock=3.0)
        ctrl.press(D, 5)
        self.assertTrue(ctrl.is_locked())
        clock.advance(2.99)
        self.assertEqual(ctrl.press(D, 3).action, Action.IGNORED_LOCKED)
        clock.advance(0.01)
        self.assertFalse(ctrl.is_locked())
        self.assertEqual(ctrl.press(D, 3).value, 3)

    def test_minus_can_be_preselected_during_lock(self):
        """Ein früh gedrücktes Minus geht nicht verloren – die Ziffer danach wird Minus."""
        ctrl, clock = make(lock=3.0)
        ctrl.press(D, 2)
        clock.advance(2.5)
        self.assertEqual(ctrl.press(M).action, Action.MINUS_SELECTED)
        self.assertEqual(ctrl.press(D, 4).action, Action.IGNORED_LOCKED)   # Ziffer noch gesperrt
        self.assertTrue(ctrl.minus_selected)
        clock.advance(0.5)
        self.assertEqual(ctrl.press(D, 4).value, -4)

    def test_lock_countdown_values(self):
        ctrl, clock = make(lock=3.0)
        ctrl.press(D, 1)
        self.assertAlmostEqual(ctrl.lock_remaining(), 3.0)
        self.assertAlmostEqual(ctrl.lock_fraction(), 1.0)
        clock.advance(1.5)
        self.assertAlmostEqual(ctrl.lock_remaining(), 1.5)
        self.assertAlmostEqual(ctrl.lock_fraction(), 0.5)
        clock.advance(5)
        self.assertEqual(ctrl.lock_remaining(), 0.0)

    def test_lock_zero_disables_lock(self):
        ctrl, _ = make(lock=0)
        ctrl.press(D, 2)
        self.assertFalse(ctrl.is_locked())
        self.assertEqual(ctrl.press(D, 2).action, Action.SCORE)

    def test_changed_lock_constant_is_used(self):
        ctrl, clock = make(lock=5.0)
        ctrl.press(D, 2)
        clock.advance(4.9)
        self.assertTrue(ctrl.is_locked())
        clock.advance(0.1)
        self.assertFalse(ctrl.is_locked())


class UndoTests(unittest.TestCase):
    def test_undo_directly_after_score_is_allowed_and_releases_lock(self):
        ctrl, _ = make()
        ctrl.press(D, 5)
        self.assertTrue(ctrl.is_locked())
        self.assertEqual(ctrl.press(U).action, Action.UNDO)
        self.assertFalse(ctrl.is_locked())
        self.assertEqual(ctrl.press(D, 3).value, 3)      # Korrektur sofort möglich

    def test_undo_bounce_protection(self):
        ctrl, clock = make(undo_lock=1.0)
        self.assertEqual(ctrl.press(U).action, Action.UNDO)
        self.assertEqual(ctrl.press(U).action, Action.IGNORED_UNDO_LOCKED)
        clock.advance(1.0)
        self.assertEqual(ctrl.press(U).action, Action.UNDO)

    def test_undo_resets_to_plus(self):
        ctrl, _ = make()
        ctrl.press(M)
        ctrl.press(U)
        self.assertFalse(ctrl.minus_selected)
        self.assertEqual(ctrl.press(D, 4).value, 4)


class AbortTests(unittest.TestCase):
    def test_star_then_minus_confirms(self):
        ctrl, _ = make()
        self.assertEqual(ctrl.press(A).action, Action.ABORT_REQUESTED)
        self.assertTrue(ctrl.abort_pending())
        self.assertEqual(ctrl.press(M).action, Action.ABORT_CONFIRMED)
        self.assertFalse(ctrl.abort_pending())
        self.assertFalse(ctrl.minus_selected)

    def test_any_other_key_cancels_and_is_consumed(self):
        for key, digit in ((P, None), (D, 3), (U, None), (A, None)):
            with self.subTest(key=key):
                ctrl, _ = make()
                ctrl.press(A)
                self.assertEqual(ctrl.press(key, digit).action, Action.ABORT_CANCELLED)
                self.assertFalse(ctrl.is_locked())       # die Ziffer wurde NICHT gewertet

    def test_abort_times_out(self):
        ctrl, clock = make(abort=5.0)
        ctrl.press(A)
        clock.advance(4.9)
        self.assertIsNone(ctrl.check_timeouts())
        clock.advance(0.1)
        self.assertEqual(ctrl.check_timeouts().action, Action.ABORT_CANCELLED)
        self.assertEqual(ctrl.press(M).action, Action.MINUS_SELECTED)   # "-" wieder normales Minus

    def test_expired_abort_does_not_swallow_next_key(self):
        ctrl, clock = make(abort=5.0)
        ctrl.press(A)
        clock.advance(6)
        self.assertEqual(ctrl.press(D, 2).value, 2)

    def test_abort_resets_to_plus(self):
        ctrl, _ = make()
        ctrl.press(M)
        ctrl.press(A)
        ctrl.press(D, 2)      # verwirft Abbruch, wird nicht gewertet
        self.assertEqual(ctrl.press(D, 2).value, 2)


class UndoConfirmAndEnterTests(unittest.TestCase):
    E = GameKey.ENTER

    def make(self, skip=True):
        clock = FakeClock()
        return ScoreInputController(3.0, 1.0, 5.0, clock, undo_confirm_seconds=5.0, enter_skips_lock=skip), clock

    def test_undo_needs_enter(self):
        ctrl, _ = self.make()
        ctrl.press(D, 4)
        self.assertEqual(ctrl.press(U).action, Action.UNDO_REQUESTED)
        self.assertTrue(ctrl.undo_pending())
        self.assertEqual(ctrl.press(U).action, Action.UNDO_REQUESTED)    # Prellen: Frage bleibt offen
        self.assertEqual(ctrl.press(self.E).action, Action.UNDO)
        self.assertFalse(ctrl.undo_pending())
        self.assertFalse(ctrl.is_locked())                              # korrigierter Stoß sofort möglich

    def test_other_key_or_timeout_cancels_undo(self):
        ctrl, clock = self.make()
        ctrl.press(U)
        self.assertEqual(ctrl.press(D, 3).action, Action.UNDO_CANCELLED)  # Ziffer wird NICHT gewertet
        clock.advance(1.5)
        ctrl.press(U)
        clock.advance(5.1)
        self.assertEqual(ctrl.check_timeouts().action, Action.UNDO_CANCELLED)
        self.assertEqual(ctrl.press(self.E).action, Action.CONFIRM)

    def test_enter_skips_lock(self):
        ctrl, _ = self.make()
        ctrl.press(D, 2)
        self.assertEqual(ctrl.press(D, 2).action, Action.IGNORED_LOCKED)
        self.assertEqual(ctrl.press(self.E).action, Action.LOCK_SKIPPED)
        self.assertEqual(ctrl.press(D, 2).action, Action.SCORE)

    def test_enter_skip_can_be_switched_off(self):
        ctrl, _ = self.make(skip=False)
        ctrl.press(D, 2)
        self.assertEqual(ctrl.press(self.E).action, Action.CONFIRM)
        self.assertTrue(ctrl.is_locked())


if __name__ == "__main__":
    unittest.main()
