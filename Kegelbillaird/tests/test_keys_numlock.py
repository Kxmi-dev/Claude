"""Tests der Tastenzuordnung (Nummernblock) und des NumLock-Schutzes gegen Hin-und-her-Schalten."""

import os
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.helpers import PROJECT_DIR  # setzt den Projektpfad

assert PROJECT_DIR.is_dir()

try:
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QApplication, QWidget
except ImportError:  # pragma: no cover
    QApplication = None

from bk.input_logic import GameKey
from bk.numlock import NumLockResult


def key_event(key, keypad=True):
    modifier = Qt.KeyboardModifier.KeypadModifier if keypad else Qt.KeyboardModifier.NoModifier
    return QKeyEvent(QEvent.Type.KeyPress, key, modifier)


@unittest.skipIf(QApplication is None, "PySide6 nicht installiert")
class KeymapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_numpad_keys(self):
        from bk.ui.keymap import map_game_key
        K = Qt.Key
        self.assertEqual(map_game_key(key_event(K.Key_Plus), True), (GameKey.PLUS, None))
        self.assertEqual(map_game_key(key_event(K.Key_Minus), True), (GameKey.MINUS, None))
        self.assertEqual(map_game_key(key_event(K.Key_Slash), True), (GameKey.UNDO, None))
        self.assertEqual(map_game_key(key_event(K.Key_Asterisk), True), (GameKey.ABORT, None))
        for digit in range(10):
            self.assertEqual(map_game_key(key_event(getattr(K, f"Key_{digit}")), True), (GameKey.DIGIT, digit))

    def test_numpad_without_numlock_fallback(self):
        from bk.ui.keymap import map_game_key
        K = Qt.Key
        expected = {K.Key_Insert: 0, K.Key_End: 1, K.Key_Down: 2, K.Key_PageDown: 3, K.Key_Left: 4,
                    K.Key_Clear: 5, K.Key_Right: 6, K.Key_Home: 7}
        for key, digit in expected.items():
            self.assertEqual(map_game_key(key_event(key), True), (GameKey.DIGIT, digit))
            self.assertIsNone(map_game_key(key_event(key, keypad=False), False))   # echte Pfeiltasten

    def test_main_keyboard_only_when_allowed(self):
        from bk.ui.keymap import map_game_key
        K = Qt.Key
        self.assertIsNone(map_game_key(key_event(K.Key_5, keypad=False), True))
        self.assertIsNone(map_game_key(key_event(K.Key_Plus, keypad=False), True))
        self.assertEqual(map_game_key(key_event(K.Key_5, keypad=False), False), (GameKey.DIGIT, 5))
        self.assertIsNone(map_game_key(key_event(K.Key_Return, keypad=False), False))
        self.assertIsNone(map_game_key(key_event(K.Key_Backspace, keypad=False), False))


class FakeNumLock:
    """Simuliert Windows: der Tastendruck wirkt erst verzögert (nach Nachrichtenverarbeitung)."""

    def __init__(self, on=False):
        self.on = on
        self.presses = 0

    def ensure(self):
        if self.on:
            return NumLockResult.ALREADY_ON
        self.presses += 1
        return NumLockResult.TOGGLED


@unittest.skipIf(QApplication is None, "PySide6 nicht installiert")
class NumLockGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def make_guard(self, fake, auto=True):
        from bk.ui import main_window

        class ActiveWidget(QWidget):
            def isActiveWindow(self):  # noqa: N802
                return True

        self.widget = ActiveWidget()
        patches = [
            mock.patch.object(main_window.numlock, "is_supported", return_value=True),
            mock.patch.object(main_window.numlock, "is_numlock_on", side_effect=lambda: fake.on),
            mock.patch.object(main_window.numlock, "ensure_numlock_on", side_effect=fake.ensure),
        ]
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        self.warnings = []
        guard = main_window.NumLockGuard(self.widget, auto, 2)
        guard.status.connect(self.warnings.append)
        return guard

    def test_already_on_does_nothing(self):
        fake = FakeNumLock(on=True)
        guard = self.make_guard(fake)
        guard.check()
        self.assertEqual(fake.presses, 0)
        self.assertEqual(self.warnings[-1], None)

    def test_no_repeated_toggling_while_state_is_not_yet_updated(self):
        fake = FakeNumLock(on=False)
        guard = self.make_guard(fake)
        for _ in range(10):          # schnelle Wiederholungen: nur EIN Tastendruck
            guard.check()
        self.assertEqual(fake.presses, 1)
        self.assertIsNotNone(self.warnings[-1])

    def test_attempts_are_limited(self):
        fake = FakeNumLock(on=False)
        guard = self.make_guard(fake)
        for _ in range(10):
            guard._last_attempt -= 10          # Wartezeit künstlich verstreichen lassen
            guard.check()
        self.assertEqual(fake.presses, guard.MAX_ATTEMPTS)
        self.assertIn("[Num]", self.warnings[-1])

    def test_success_clears_warning_and_resets_attempts(self):
        fake = FakeNumLock(on=False)
        guard = self.make_guard(fake)
        guard.check()
        fake.on = True
        guard.check()
        self.assertIsNone(self.warnings[-1])
        self.assertEqual(guard._attempts, 0)

    def test_without_auto_enable_only_warns(self):
        fake = FakeNumLock(on=False)
        guard = self.make_guard(fake, auto=False)
        guard.check()
        self.assertEqual(fake.presses, 0)
        self.assertIn("[Num]", self.warnings[-1])


if __name__ == "__main__":
    unittest.main()
