"""Frei wählbare Tastenbelegung aus der config.py: Prüfung, Legende, Wirkung im Spiel."""

import dataclasses
import os
import types
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.helpers import TempDir

from bk.keys import ACTIONS, KeyBindings, normalize

try:
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
except ImportError:  # pragma: no cover
    QApplication = None

import config
from bk.settings import AppSettings
from bk.storage import GameStorage


def cfg(**keys):
    """config.py-Ersatz mit einzelnen KEY_*-Werten."""
    return types.SimpleNamespace(**{f"KEY_{k.upper()}": v for k, v in keys.items()})


class KeyNameTests(unittest.TestCase):
    def test_names_are_normalized(self):
        for raw, expected in (("esc", "Esc"), ("ESCAPE", "Esc"), ("return", "Enter"), ("a", "A"),
                              ("f5", "F5"), ("Stern", "*"), ("minus", "-"), ("pgup", "PageUp"), ("5", "5")):
            self.assertEqual(normalize(raw), expected)

    def test_unknown_names_are_rejected(self):
        for bad in ("", "blubb", "Strg+X", "ä"):
            with self.assertRaises(ValueError):
                normalize(bad)

    def test_defaults_are_valid_and_match_old_behaviour(self):
        kb = KeyBindings.from_config(cfg())
        self.assertEqual(kb.label("minus"), "−")
        self.assertEqual(kb.label("undo"), "/")
        self.assertEqual(kb.label_all("back"), "*]  oder  [Esc")
        self.assertEqual(kb.keys("enter"), ("Enter",))

    def test_custom_keys_and_single_string(self):
        kb = KeyBindings.from_config(cfg(abort="F10", undo=["u", "Backspace"]))
        self.assertEqual(kb.keys("abort"), ("F10",))
        self.assertEqual(kb.keys("undo"), ("U", "Backspace"))
        self.assertEqual(kb.label("undo"), "U")

    def test_double_assignment_is_reported(self):
        with self.assertRaises(ValueError) as ctx:
            KeyBindings.from_config(cfg(undo="*"))            # * ist schon "abort"
        self.assertIn("doppelt", str(ctx.exception))
        with self.assertRaises(ValueError):
            KeyBindings.from_config(cfg(enter="8"))           # 8 ist schon "up"
        with self.assertRaises(ValueError):
            KeyBindings.from_config(cfg(plus="Esc"))          # Wiedergabe: Esc ist "back"

    def test_digits_and_empty_lists_are_rejected(self):
        with self.assertRaises(ValueError):
            KeyBindings.from_config(cfg(undo="5"))
        with self.assertRaises(ValueError):
            KeyBindings.from_config(cfg(abort=[]))
        with self.assertRaises(ValueError) as ctx:
            KeyBindings.from_config(cfg(abort="Strg"))
        self.assertIn("KEY_ABORT", str(ctx.exception))

    def test_every_action_has_a_default(self):
        self.assertEqual(set(KeyBindings().names), set(ACTIONS))


@unittest.skipIf(QApplication is None, "PySide6 nicht installiert")
class KeyBindingUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from bk.ui import keymap
        self.keymap = keymap
        self.tmp = TempDir()
        kb = KeyBindings.from_config(cfg(undo="U", abort="F10", minus="M", enter="Space", back="Q"))
        self.settings = dataclasses.replace(
            AppSettings.from_config(config),
            data_dir=self.tmp.path / "data", results_dir=self.tmp.path / "results",
            logs_dir=self.tmp.path / "logs", input_lock_seconds=0.1, undo_lock_seconds=0.05,
            abort_confirm_seconds=2.0, auto_enable_numlock=False, fullscreen=False, key_bindings=kb)
        self.storage = GameStorage(self.settings.data_dir, self.settings.results_dir)
        self.storage.ensure_directories()
        self.windows = []

    def tearDown(self):
        self.keymap.configure(KeyBindings())
        for w in self.windows:
            w.close()
            w.deleteLater()
        QTest.qWait(20)
        self.tmp.cleanup()

    def key(self, window, key, keypad=False):
        mod = Qt.KeyboardModifier.KeypadModifier if keypad else Qt.KeyboardModifier.NoModifier
        QApplication.sendEvent(window, QKeyEvent(QEvent.Type.KeyPress, key, mod, "", False))

    def test_legend_and_keys_follow_config(self):
        from bk.ui.main_window import MainWindow
        window = MainWindow(self.settings, self.storage)
        window.resize(1280, 800)
        window.show()
        QTest.qWait(450)
        self.windows.append(window)
        self.key(window, Qt.Key.Key_Space)                       # Enter ist jetzt die Leertaste
        screen = window.game_screen
        self.assertIs(window.stack.currentWidget(), screen)
        legend = " | ".join(screen.footer_segments())
        self.assertIn("Korrektur letzter Stoß mit  [U]", legend)
        self.assertIn("Minus:  [M]", legend)
        self.assertIn("Partie-Abbruch mit  [F10]  &  [M]", legend)
        self.assertNotIn("[/]", legend)

        self.key(window, Qt.Key.Key_5, keypad=True)              # +5
        QTest.qWait(150)
        self.assertEqual(screen.game.played, 1)
        self.key(window, Qt.Key.Key_Slash, keypad=True)          # altes Zeichen tut nichts mehr
        self.assertEqual(screen.game.played, 1)
        self.key(window, Qt.Key.Key_U)                           # neue Rücknahme-Taste (kein Nummernblock nötig)
        self.assertTrue(screen.controller.correction_pending())  # Korrekturfeld …
        self.key(window, Qt.Key.Key_M)                           # … neue Punktzahl −2
        self.key(window, Qt.Key.Key_2, keypad=True)
        self.key(window, Qt.Key.Key_Space)                       # … übernommen mit der Enter-Taste
        self.assertEqual(screen.game.state.strokes, [-2])

        self.key(window, Qt.Key.Key_F10)                         # Abbruch-Frage
        self.assertTrue(screen.controller.abort_pending())
        self.key(window, Qt.Key.Key_M)                           # bestätigen mit der Minus-Taste
        QTest.qWait(100)
        self.assertFalse(screen.has_live_game)


if __name__ == "__main__":
    unittest.main()
