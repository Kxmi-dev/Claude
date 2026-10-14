"""Autostart mit Windows: Registry-Eintrag setzen/entfernen, Pfad korrigieren, Menüeintrag."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from bk.autostart import Autostart, AutostartError


class FakeRegistry:
    def __init__(self, value=None, fail=False):
        self.value, self.fail = value, fail

    def get(self):
        return self.value

    def set(self, command):
        if self.fail:
            raise PermissionError("Zugriff verweigert")
        self.value = command

    def delete(self):
        if self.fail:
            raise PermissionError("Zugriff verweigert")
        self.value = None


CMD = '"C:\\BK-Scoreboard\\BK-Scoreboard.exe"'


class AutostartTests(unittest.TestCase):
    def test_enable_and_disable(self):
        reg = FakeRegistry()
        auto = Autostart(reg, CMD, available=True)
        self.assertFalse(auto.is_enabled())
        auto.set_enabled(True)
        self.assertEqual(reg.value, CMD)
        self.assertTrue(auto.is_enabled())
        auto.set_enabled(False)
        self.assertIsNone(reg.value)
        self.assertFalse(auto.is_enabled())

    def test_moved_folder_is_corrected_only_when_enabled(self):
        reg = FakeRegistry('"D:\\alt\\BK-Scoreboard.exe"')
        self.assertTrue(Autostart(reg, CMD, available=True).refresh())
        self.assertEqual(reg.value, CMD)
        self.assertFalse(Autostart(reg, CMD, available=True).refresh())     # schon richtig
        off = FakeRegistry()
        self.assertFalse(Autostart(off, CMD, available=True).refresh())
        self.assertIsNone(off.value)                                         # nie ungefragt einschalten

    def test_errors_and_other_systems(self):
        with self.assertRaises(AutostartError):
            Autostart(FakeRegistry(fail=True), CMD, available=True).set_enabled(True)
        self.assertFalse(Autostart(FakeRegistry(CMD, fail=True), '"neu"', available=True).refresh())
        other = Autostart(FakeRegistry(CMD), CMD, available=False)
        self.assertFalse(other.is_enabled())
        with self.assertRaises(AutostartError):
            other.set_enabled(True)


try:
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
except ImportError:  # pragma: no cover
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 fehlt")
class AutostartMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from tests.helpers import TempDir
        from tests.test_settings_menu import base_settings
        from bk.storage import GameStorage
        from bk.user_settings import UserSettingsStore
        from bk.ui.main_window import MainWindow
        self.tmp = TempDir()
        settings = base_settings(self.tmp.path)
        storage = GameStorage(settings.data_dir, settings.results_dir)
        storage.ensure_directories()
        self.window = MainWindow(settings, storage, UserSettingsStore(settings))
        self.window.resize(1280, 800)
        self.window.show()
        QTest.qWait(450)
        self.screen = self.window.settings_screen

    def tearDown(self):
        self.window.close()
        self.window.deleteLater()
        QTest.qWait(20)
        self.tmp.cleanup()

    def key(self, key):
        QApplication.sendEvent(self.window, QKeyEvent(QEvent.Type.KeyPress, key,
                                                      Qt.KeyboardModifier.KeypadModifier, "", False))

    def open_item(self, reg):
        self.screen.autostart = Autostart(reg, CMD, available=True)
        self.window.show_settings()
        self.screen.open_page("Anzeige", self.screen._page_display)
        while self.screen._list.current().label != "Beim Windows-Start öffnen":
            self.key(Qt.Key.Key_2)
        return self.screen._list.current()

    def test_toggle_in_display_settings(self):
        reg = FakeRegistry()
        item = self.open_item(reg)
        self.assertEqual(item.value(), "Aus")
        self.key(Qt.Key.Key_6)
        self.assertEqual(reg.value, CMD)
        self.assertEqual(item.value(), "An")
        self.key(Qt.Key.Key_Enter)
        self.assertIsNone(reg.value)
        self.assertEqual(item.value(), "Aus")

    def test_failure_shows_notice(self):
        self.open_item(FakeRegistry(fail=True))
        self.key(Qt.Key.Key_6)
        self.assertIn("Autostart", self.window.footer.current_text())


if __name__ == "__main__":
    unittest.main()
