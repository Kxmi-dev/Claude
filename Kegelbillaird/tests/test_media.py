"""Ton und Bilder: Auswahl, fehlende Dateien, Ausfall der Tonausgabe, Einblendung in der Zählansicht."""

import dataclasses
import os
import random
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.helpers import BK50, TempDir

from bk.media import SoundPlayer, active_images, list_images, list_sounds, pick_image, resolve_file

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

    def test_files_are_detected_automatically(self):
        a = self.touch("a.gif")
        self.touch("B.PNG")
        self.touch("notiz.txt")
        self.touch("ton.mp3")
        self.touch("ton.wav")
        self.assertEqual(resolve_file(self.tmp.path, "a.gif"), a)
        self.assertIsNone(resolve_file(self.tmp.path, "fehlt.gif"))
        self.assertIsNone(resolve_file(self.tmp.path, ""))
        self.assertEqual(list_images(self.tmp.path), ["a.gif", "B.PNG"])
        self.assertEqual(list_sounds(self.tmp.path), ["ton.mp3", "ton.wav"])
        self.assertEqual(list_images(self.tmp.path / "gibtsnicht"), [])
        self.assertEqual(active_images(self.tmp.path, ["plus/a.gif"], "plus"), [self.tmp.path / "B.PNG"])

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
        def broken(path, volume):
            raise OSError("kein Audiogerät")
        self.assertFalse(SoundPlayer(broken).play(Path("x.wav")))
        self.assertFalse(SoundPlayer(broken).play(None))

    def test_sound_plays(self):
        played = []
        player = SoundPlayer(lambda path, volume: played.append((path, volume)))
        self.assertTrue(player.play(Path("x.mp3"), 40))
        self.assertFalse(player.play(Path("x.mp3"), 0))          # Lautstärke 0 = kein Ton
        self.assertEqual(played, [(Path("x.mp3"), 40)])


@unittest.skipIf(QApplication is None, "PySide6 nicht installiert")
class MediaUiTests(unittest.TestCase):
    LOCK = 0.1

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = TempDir()
        (self.tmp.path / "bilder" / "plus").mkdir(parents=True)
        (self.tmp.path / "bilder" / "minus").mkdir()
        (self.tmp.path / "sounds").mkdir()
        img = QImage(40, 30, QImage.Format.Format_RGB32)
        img.fill(0xFFCC00)
        img.save(str(self.tmp.path / "bilder" / "plus" / "a.png"))
        (self.tmp.path / "sounds" / "h.wav").write_bytes(b"x")
        self.settings = dataclasses.replace(
            AppSettings.from_config(config),
            data_dir=self.tmp.path / "data", results_dir=self.tmp.path / "results",
            logs_dir=self.tmp.path / "logs", input_lock_seconds=self.LOCK, undo_lock_seconds=0.05,
            auto_enable_numlock=False, fullscreen=False,
            images_dir=self.tmp.path / "bilder", sounds_dir=self.tmp.path / "sounds",
            halftime_sound="h.wav", end_sound="h.wav", sound_volume=70, celebration_seconds=5.0)
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
        screen._sound = SoundPlayer(lambda path, volume: played.append(path))
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

    def test_minus_values_use_own_folder_or_fall_back(self):
        fallback = self.screen()
        self.press(fallback, -7)                    # bilder/minus leer -> Bilder aus bilder/plus
        self.assertEqual(fallback._last_image.name, "a.png")
        QImage(10, 10, QImage.Format.Format_RGB32).save(str(self.tmp.path / "bilder" / "minus" / "m.png"))
        own = self.screen()
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
        for key in (Qt.Key.Key_Slash, Qt.Key.Key_3, Qt.Key.Key_Enter):   # Korrektur auf +3
            screen.handle_key(QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.KeypadModifier, "", False))
        self.assertFalse(screen._celebration.isVisible())

    def test_missing_disabled_or_broken_images_do_not_disturb(self):
        (self.tmp.path / "bilder" / "plus" / "a.png").unlink()
        empty = self.screen()
        self.press(empty, 7)
        self.assertFalse(empty._celebration.isVisible())
        (self.tmp.path / "bilder" / "plus" / "kaputt.gif").write_bytes(b"kein gif")
        for disabled in ((), ("plus/kaputt.gif",)):
            screen = self.screen(dataclasses.replace(self.settings, disabled_images=disabled))
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

    def test_sound_on_plus_six_and_seven(self):
        (self.tmp.path / "sounds" / "jubel.mp3").write_bytes(b"x")
        jubel = self.tmp.path / "sounds" / "jubel.mp3"
        screen = self.screen(dataclasses.replace(self.settings, celebration_sound="jubel.mp3"))
        for value in (5, -6, -7, 0):
            self.press(screen, value)
        self.assertEqual(screen.played_sounds, [])
        self.press(screen, 6)
        self.press(screen, 7)
        self.assertEqual(screen.played_sounds, [jubel, jubel])
        # auch wenn Bilder ausgeschaltet sind; ohne Ton / Töne aus -> nichts
        no_images = self.screen(dataclasses.replace(self.settings, celebration_sound="jubel.mp3",
                                                    celebration_enabled=False))
        self.press(no_images, 7)
        self.assertEqual(no_images.played_sounds, [jubel])
        for kw in ({}, {"celebration_sound": "jubel.mp3", "sound_enabled": False},
                   {"celebration_sound": "fehlt.wav"}):
            quiet = self.screen(dataclasses.replace(self.settings, **kw))
            self.press(quiet, 7)
            self.assertEqual(quiet.played_sounds, [])
            self.assertEqual(quiet.game.played, 1)

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
                     "CELEBRATION_MINUS_VALUES", "CELEBRATION_SECONDS", "SOUNDS_DIR", "IMAGES_DIR",
                     "END_SOUND", "SOUND_VOLUME", "WINDOW_SIZE"):
            if hasattr(old, name):
                delattr(old, name)
        settings = AppSettings.from_config(old)
        self.assertEqual(settings.celebration_values, (6, 7))
        self.assertEqual(settings.sound_volume, 80)


if __name__ == "__main__":
    unittest.main()
