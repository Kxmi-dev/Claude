"""Beenden & Herunterfahren: Befehl, Fehlerfälle, doppelte Bestätigung im Hauptmenü."""

import os
import subprocess
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from bk import power


class Result:
    def __init__(self, code, err=""):
        self.returncode, self.stderr, self.stdout = code, err, ""


class PowerTests(unittest.TestCase):
    def test_runs_silent_immediate_forced_shutdown_on_windows(self):
        calls = []
        ok, message = power.shutdown(lambda cmd, **kw: calls.append((cmd, kw)) or Result(0), platform="win32")
        self.assertTrue(ok)
        self.assertEqual(calls[0][0], ["shutdown", "/s", "/t", "0", "/f"])
        self.assertEqual(calls[0][1]["creationflags"], getattr(subprocess, "CREATE_NO_WINDOW", 0))

    def test_errors_are_reported_not_raised(self):
        ok, message = power.shutdown(lambda cmd, **kw: Result(5, "Zugriff verweigert"), platform="win32")
        self.assertFalse(ok)
        self.assertIn("Zugriff verweigert", message)

        def boom(cmd, **kw):
            raise OSError("nicht gefunden")
        ok, message = power.shutdown(boom, platform="win32")
        self.assertFalse(ok)
        self.assertIn("nicht gefunden", message)

    def test_other_systems_never_run_anything(self):
        ok, _ = power.shutdown(lambda *a, **k: self.fail("darf nicht laufen"), platform="linux")
        self.assertFalse(ok)


try:
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
except ImportError:  # pragma: no cover
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 fehlt")
class ShutdownMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from tests.test_settings_menu import base_settings
        from tests.helpers import TempDir
        from bk.storage import GameStorage
        from bk.user_settings import UserSettingsStore
        from bk.ui.main_window import MainWindow
        self.tmp = TempDir()
        settings = base_settings(self.tmp.path)
        storage = GameStorage(settings.data_dir, settings.results_dir)
        storage.ensure_directories()
        self.window = MainWindow(settings, storage, UserSettingsStore(settings))
        self.calls = []
        self.result = (True, "")
        self.window.shutdown_supported = lambda: True
        self.window.shutdown_computer = lambda: self.calls.append(1) or self.result
        self.window.resize(1280, 800)
        self.window.show()
        QTest.qWait(450)
        self.menu = self.window.menu_screen

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        QTest.qWait(20)
        self.tmp.cleanup()

    def key(self, key):
        QApplication.sendEvent(self.window, QKeyEvent(QEvent.Type.KeyPress, key,
                                                      Qt.KeyboardModifier.KeypadModifier, "", False))

    def select_shutdown(self):
        from bk.ui.menu_screen import SHUTDOWN
        while self.menu._modes[self.menu._index] != SHUTDOWN:
            self.key(Qt.Key.Key_2)
        return self.menu._buttons[self.menu._index]

    def test_two_entries(self):
        texts = [b.text() for b in self.menu._buttons]
        self.assertIn("Beenden", texts)
        self.assertIn("Beenden & Herunterfahren", texts)

    def test_needs_second_enter(self):
        button = self.select_shutdown()
        self.key(Qt.Key.Key_Enter)
        self.assertEqual(self.calls, [])
        self.assertIn("nochmal", button.text())
        self.assertTrue(self.window.isVisible())
        self.key(Qt.Key.Key_Enter)
        self.assertEqual(self.calls, [1])
        self.assertFalse(self.window.isVisible())

    def test_moving_away_or_timeout_disarms(self):
        from bk.ui import menu_screen
        button = self.select_shutdown()
        self.key(Qt.Key.Key_Enter)
        self.key(Qt.Key.Key_8)
        self.key(Qt.Key.Key_2)
        self.assertEqual(button.text(), "Beenden & Herunterfahren")
        self.key(Qt.Key.Key_Enter)                                # wieder nur der erste Druck
        self.assertEqual(self.calls, [])
        self.menu._disarm_timer.setInterval(10)
        self.menu._disarm_timer.start()
        QTest.qWait(60)
        self.assertEqual(button.text(), menu_screen.SHUTDOWN_TEXT)
        self.key(Qt.Key.Key_Enter)
        self.assertEqual(self.calls, [])

    def test_failure_keeps_program_open_with_notice(self):
        self.result = (False, "Herunterfahren nicht möglich (Code 5).")
        self.select_shutdown()
        self.key(Qt.Key.Key_Enter)
        self.key(Qt.Key.Key_Enter)
        self.assertEqual(self.calls, [1])
        self.assertTrue(self.window.isVisible())
        self.assertIn("Herunterfahren nicht möglich", self.window.footer.current_text())

    def test_plain_quit_does_not_shut_down(self):
        from bk.ui.menu_screen import QUIT
        while self.menu._modes[self.menu._index] != QUIT:
            self.key(Qt.Key.Key_2)
        self.key(Qt.Key.Key_Enter)
        self.assertFalse(self.window.isVisible())
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
