"""Ton und Bilder: Auswahl, fehlende Dateien, Ausfall der Tonausgabe, Einblendung in der Zählansicht."""

import dataclasses
import os
import random
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.helpers import BK50, TempDir

from bk.media import SoundPlayer, existing_files, pick_image, resolve_file

try:
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QImage, QKeyEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
except ImportError:  # pragma: no cover
    QApplication = None

import config
from bk.models import GameState
from bk.settings import AppSettings
from bk.storage import GameStorage


class MediaLogicTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()
        self.addCleanup(self.tmp.cleanup)

    def touch(self, name):
        path = self.tmp.path / name
        path.write_bytes(b"x")
        return path

    def test_resolve_and_existing_files(self):
        a = self.touch("a.gif")
        self.assertEqual(resolve_file(self.tmp.path, "a.gif"), a)
        self.assertIsNone(resolve_file(self.tmp.path, "fehlt.gif"))
        self.assertIsNone(resolve_file(self.tmp.path, ""))
        self.assertEqual(existing_files(self.tmp.path, ["fehlt.png", "a.gif", "a.gif", ""]), [a])

    def test_single_file_is_always_chosen(self):
        a = self.touch("a.gif")
        for _ in range(20):
            self.assertEqual(pick_image([a], last=a), a)

    def test_several_files_random_but_never_twice_in_a_row(self):
        files = [self.touch(n) for n in ("a.gif", "b.png", "c.jpg")]
        rng, last, seen = random.Random(1), None, set()
        for _ in range(60):
            chosen = pick_image(files, last, rng)
            self.assertNotEqual(chosen, last)
            seen.add(chosen)
            last = chosen
        self.assertEqual(seen, set(files))

    def test_empty_list_gives_nothing(self):
        self.assertIsNone(pick_image([]))

    def test_sound_failure_is_swallowed(self):
        def broken(path):
            raise OSError("kein Audiogerät")
        self.assertFalse(SoundPlayer(broken).play(Path("x.wav")))
        self.assertFalse(SoundPlayer(broken).play(None))

    def test_sound_plays(self):
        played = []
        self.assertTrue(SoundPlayer(played.append).play(Path("x.wav")))
        self.assertEqual(played, [Path("x.wav")])


@unittest.skipIf(QApplication is None, "PySide6 nicht installiert")
class MediaUiTests(unittest.TestCase):
    LOCK = 0.1

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = TempDir()
        (self.tmp.path / "bilder").mkdir()
        (self.tmp.path / "sounds").mkdir()
        img = QImage(40, 30, QImage.Format.Format_RGB32)
        img.fill(0xFFCC00)
        img.save(str(self.tmp.path / "bilder" / "a.png"))
        (self.tmp.path / "sounds" / "h.wav").write_bytes(b"x")
        self.settings = dataclasses.replace(
            AppSettings.from_config(config),
            data_dir=self.tmp.path / "data", results_dir=self.tmp.path / "results",
            logs_dir=self.tmp.path / "logs", input_lock_seconds=self.LOCK, undo_lock_seconds=0.05,
            auto_enable_numlock=False, fullscreen=False,
            images_dir=self.tmp.path / "bilder", sounds_dir=self.tmp.path / "sounds",
            celebration_images=("a.png",), halftime_sound="h.wav", celebration_seconds=5.0)
        self.storage = GameStorage(self.settings.data_dir, self.settings.results_dir)
        self.storage.ensure_directories()
        self.windows = []

    def tearDown(self):
        for w in self.windows:
            w.close()
            w.deleteLater()
        QTest.qWait(20)
        self.tmp.cleanup()

    def screen(self, settings=None):
        from bk.game import Game
        from bk.ui.game_screen import GameScreen
        screen = GameScreen(settings or self.settings, self.storage)
        screen.resize(1024, 768)
        screen.show()
        self.windows.append(screen)
        played = []
        screen._sound = SoundPlayer(played.append)
        screen.played_sounds = played
        screen.start_game(Game(GameState.new(BK50)))
        return screen

    def press(self, screen, value):
        if value < 0:
            screen.handle_key(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Minus,
                                        Qt.KeyboardModifier.KeypadModifier, "", False))
        key = getattr(Qt.Key, f"Key_{abs(value)}")
        screen.handle_key(QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.KeypadModifier, "", False))
        QTest.qWait(int(self.LOCK * 1000) + 60)

    def test_image_only_for_configured_values(self):
        screen = self.screen()
        self.press(screen, 5)
        self.assertFalse(screen._celebration.isVisible())
        self.press(screen, 6)
        self.assertTrue(screen._celebration.isVisible())
        self.press(screen, 3)
        self.assertFalse(screen._celebration.isVisible())
        self.press(screen, -5)                       # nur -6/-7 lösen bei Minus aus
        self.assertFalse(screen._celebration.isVisible())
        self.press(screen, -6)
        self.assertTrue(screen._celebration.isVisible())
        self.press(screen, 7)
        self.assertTrue(screen._celebration.isVisible())

    def test_minus_values_use_own_images_or_fall_back(self):
        QImage(10, 10, QImage.Format.Format_RGB32).save(str(self.tmp.path / "bilder" / "m.png"))
        own = self.screen(dataclasses.replace(self.settings, celebration_minus_images=("m.png",)))
        self.press(own, -7)
        self.assertEqual(own._last_image.name, "m.png")
        self.press(own, 6)
        self.assertEqual(own._last_image.name, "a.png")
        off = self.screen(dataclasses.replace(self.settings, celebration_minus_values=()))
        self.press(off, -7)
        self.assertFalse(off._celebration.isVisible())

    def test_undo_hides_image(self):
        screen = self.screen()
        self.press(screen, 7)
        self.assertTrue(screen._celebration.isVisible())
        screen.handle_key(QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Slash, Qt.KeyboardModifier.KeypadModifier,
                                    "", False))
        self.assertFalse(screen._celebration.isVisible())

    def test_missing_or_broken_images_do_not_disturb(self):
        broken = self.tmp.path / "bilder" / "kaputt.gif"
        broken.write_bytes(b"kein gif")
        for names in ((), ("fehlt.png",), ("kaputt.gif",)):
            screen = self.screen(dataclasses.replace(self.settings, celebration_images=names))
            self.press(screen, 7)
            self.assertFalse(screen._celebration.isVisible())
            self.assertEqual(screen.game.played, 1)

    def test_halftime_sound_and_flash(self):
        screen = self.screen()
        for _ in range(24):
            self.press(screen, 1)
        self.assertEqual(screen.played_sounds, [])
        self.press(screen, 2)                        # 25. Stoß = Halbzeit bei 50 Stoß
        self.assertEqual(screen.played_sounds, [self.tmp.path / "sounds" / "h.wav"])
        self.assertNotEqual(screen.halftime_box._fill.name(), "#ffffff")
        self.press(screen, 1)
        self.assertEqual(len(screen.played_sounds), 1)

    def test_halftime_without_sound_file_or_disabled_still_works(self):
        for kw in ({"halftime_sound": "fehlt.wav"}, {"halftime_sound": ""}, {"sound_enabled": False}):
            screen = self.screen(dataclasses.replace(self.settings, **kw))
            for _ in range(25):
                self.press(screen, 1)
            self.assertEqual(screen.played_sounds, [])
            self.assertEqual(screen.game.played, 25)

    def test_old_config_without_new_settings_still_loads(self):
        import types
        old = types.SimpleNamespace(**{k: getattr(config, k) for k in dir(config) if k.isupper()})
        for name in ("SOUND_ENABLED", "HALFTIME_SOUND", "CELEBRATION_ENABLED", "CELEBRATION_VALUES",
                     "CELEBRATION_IMAGES", "CELEBRATION_MINUS_VALUES", "CELEBRATION_MINUS_IMAGES", "CELEBRATION_SECONDS", "SOUNDS_DIR", "IMAGES_DIR"):
            delattr(old, name)
        settings = AppSettings.from_config(old)
        self.assertEqual(settings.celebration_values, (6, 7))
        self.assertEqual(settings.celebration_images, ())


if __name__ == "__main__":
    unittest.main()
