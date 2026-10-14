"""Einstellungsmenü: Speichern in einstellungen.json, Bedienung, sofortige Übernahme."""

import dataclasses
import json
import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from tests.helpers import BK50, TempDir

try:
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication
except ImportError:  # pragma: no cover
    QApplication = None

import config
from bk.game import Game
from bk.keys import KeyBindings
from bk.models import GameState
from bk.settings import AppSettings
from bk.storage import GameStorage
from bk.user_settings import UserSettingsStore


def base_settings(tmp):
    return dataclasses.replace(
        AppSettings.from_config(config),
        data_dir=tmp / "data", results_dir=tmp / "results", logs_dir=tmp / "logs",
        sounds_dir=tmp / "sounds", images_dir=tmp / "bilder", settings_file=tmp / "einstellungen.json",
        club_logo_dir=tmp / "vereinslogo",
        input_lock_seconds=0.1, undo_lock_seconds=0.05, auto_enable_numlock=False, fullscreen=False)


class StoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()
        self.addCleanup(self.tmp.cleanup)
        self.base = base_settings(self.tmp.path)

    def test_roundtrip_only_changed_values_are_saved(self):
        store = UserSettingsStore(self.base)
        self.assertEqual(store.load(), self.base)              # keine Datei -> Grundeinstellungen
        store.set("club_name", "Testverein")
        store.set("primary_color", (10, 20, 30))
        store.set("key_bindings", KeyBindings({**KeyBindings().names, "undo": ("U",)}))
        store.set("sound_volume", self.base.sound_volume)    # Standardwert -> nicht in der Datei
        data = json.loads(self.base.settings_file.read_text(encoding="utf-8"))
        self.assertEqual(set(data["values"]), {"club_name", "primary_color", "key_bindings"})
        loaded = UserSettingsStore(self.base).load()
        self.assertEqual(loaded.club_name, "Testverein")
        self.assertEqual(loaded.primary_color, (10, 20, 30))
        self.assertEqual(loaded.key_bindings.keys("undo"), ("U",))

    def test_invalid_value_is_rejected_and_nothing_saved(self):
        store = UserSettingsStore(self.base)
        store.load()
        with self.assertRaises(ValueError):
            store.set("sound_volume", 150)
        with self.assertRaises(ValueError):
            store.set("key_bindings", KeyBindings({**KeyBindings().names, "undo": ("*",)}))   # doppelt
        self.assertFalse(self.base.settings_file.exists())
        self.assertEqual(store.current, self.base)

    def test_corrupt_file_uses_backup_then_defaults(self):
        store = UserSettingsStore(self.base)
        store.load()
        store.set("club_name", "Erste")
        store.set("club_name", "Zweite")                       # .bak enthält jetzt "Erste"
        self.base.settings_file.write_text("{kaputt", encoding="utf-8")
        recovered = UserSettingsStore(self.base)
        self.assertEqual(recovered.load().club_name, "Erste")
        self.assertTrue(recovered.warnings)
        self.base.settings_file.with_name("einstellungen.json.bak").write_text("[]", encoding="utf-8")
        fresh = UserSettingsStore(self.base)
        self.assertEqual(fresh.load(), self.base)
        self.assertTrue(fresh.warnings)

    def test_invalid_or_unknown_entries_are_skipped(self):
        self.base.settings_file.write_text(json.dumps({"format": 1, "values": {
            "sound_volume": 999, "club_name": "OK", "gibtsnicht": 1, "fullscreen": "ja"}}), encoding="utf-8")
        store = UserSettingsStore(self.base)
        settings = store.load()
        self.assertEqual(settings.club_name, "OK")
        self.assertEqual(settings.sound_volume, self.base.sound_volume)
        self.assertEqual(settings.fullscreen, self.base.fullscreen)

    def test_reset(self):
        store = UserSettingsStore(self.base)
        store.load()
        store.set("club_name", "X")
        self.assertEqual(store.reset(), self.base)
        self.assertEqual(UserSettingsStore(self.base).load(), self.base)


@unittest.skipIf(QApplication is None, "PySide6 nicht installiert")
class SettingsMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from bk.ui import keymap, theme
        self.keymap, self.theme = keymap, theme
        self.tmp = TempDir()
        for folder in ("sounds", "bilder/plus", "bilder/minus"):
            (self.tmp.path / folder).mkdir(parents=True)
        for name in ("a.wav", "b.mp3"):
            (self.tmp.path / "sounds" / name).write_bytes(b"x")
        self.base = base_settings(self.tmp.path)
        self.store = UserSettingsStore(self.base)
        self.store.load()
        self.storage = GameStorage(self.base.data_dir, self.base.results_dir)
        self.storage.ensure_directories()
        from bk.ui.main_window import MainWindow
        self.window = MainWindow(self.base, self.storage, self.store)
        self.window.resize(1280, 800)
        self.window.show()
        QTest.qWait(450)
        self.screen = self.window.settings_screen

    def tearDown(self):
        self.keymap.configure(KeyBindings())
        self.theme.apply_colors("klassisch", (0, 0, 0), (0, 0, 0))
        self.theme.set_font_scale(100)
        self.window.close()
        self.window.deleteLater()
        QTest.qWait(20)
        self.tmp.cleanup()

    def key(self, key, text=""):
        QApplication.sendEvent(self.window, QKeyEvent(QEvent.Type.KeyPress, key,
                                                      Qt.KeyboardModifier.KeypadModifier, text, False))

    def open_section(self, title):
        self.window.show_settings()
        labels = [item.label for item in self.screen._list._items]
        for _ in range(labels.index(title)):
            self.key(Qt.Key.Key_2)
        self.key(Qt.Key.Key_Enter)
        self.assertEqual(self.screen._plate._text, title)

    def select(self, label):
        labels = [item.label for item in self.screen._list._items]
        while self.screen._list.current().label != label:
            self.assertIn(label, labels)
            self.key(Qt.Key.Key_2)

    def saved(self):
        return json.loads(self.base.settings_file.read_text(encoding="utf-8"))["values"]

    def test_menu_has_settings_entry(self):
        from bk.ui.menu_screen import SETTINGS
        menu = self.window.menu_screen
        self.assertIn(SETTINGS, menu._modes)
        menu.select_settings()
        self.key(Qt.Key.Key_Enter)
        self.assertIs(self.window.stack.currentWidget(), self.screen)
        self.key(Qt.Key.Key_Escape)                                # zurück ins Hauptmenü
        self.assertIs(self.window.stack.currentWidget(), menu)

    def test_toggle_and_numbers_are_saved_and_applied(self):
        self.open_section("Anzeige")
        self.select("Anzahl „Letzte Stöße“")
        self.key(Qt.Key.Key_6)
        self.assertEqual(self.window._settings.history_length, self.base.history_length + 1)
        self.assertEqual(self.window.game_screen.history_box._lines, self.base.history_length + 1)
        self.select("Vollbild")
        self.key(Qt.Key.Key_6)
        self.assertEqual(self.saved()["fullscreen"], not self.base.fullscreen)
        self.key(Qt.Key.Key_Escape)
        self.open_section("Eingabe")
        self.key(Qt.Key.Key_6)                                     # Sperrzeit +0,5 s
        self.assertAlmostEqual(self.window.game_screen._settings.input_lock_seconds, 0.6)

    def test_club_name_text_input(self):
        self.open_section("Anzeige")
        self.screen.ask_text = lambda title, label, current: "Neuer Verein"
        self.select("Vereinsname")
        self.key(Qt.Key.Key_Enter)
        self.assertEqual(self.window.title_bar._club, "Neuer Verein")
        self.assertEqual(UserSettingsStore(self.base).load().club_name, "Neuer Verein")

    def test_font_scale_is_saved_and_applied(self):
        self.open_section("Anzeige")
        self.select("Schriftgröße")
        before = self.theme.fitted_font("Text", 1000, 20).pixelSize()
        self.key(Qt.Key.Key_6)
        self.key(Qt.Key.Key_6)
        self.assertEqual(self.window._settings.font_scale, 120)
        self.assertEqual(self.saved()["font_scale"], 120)
        self.assertGreater(self.theme.fitted_font("Text", 1000, 20).pixelSize(), before)
        # Breite bleibt die Grenze: ein schmales Feld verkleinert die Schrift trotz 120 %
        # (Breite großzügig gewählt – Schriftbreiten unterscheiden sich zwischen Windows und Linux)
        from PySide6.QtGui import QFontMetricsF
        text = "Ein langer Text"
        wide = self.theme.fitted_font(text, 10000, 40)
        width = QFontMetricsF(wide).horizontalAdvance(text) / 2
        narrow = self.theme.fitted_font(text, width, 40)
        self.assertLess(narrow.pixelSize(), wide.pixelSize())
        self.assertLessEqual(QFontMetricsF(narrow).horizontalAdvance(text), width + 1)
        for _ in range(4):
            self.key(Qt.Key.Key_4)
        self.assertEqual(self.window._settings.font_scale, 80)       # 120 -> 110 -> … -> 80
        with self.assertRaises(ValueError):
            self.store.set("font_scale", 95)

    def test_club_logo_from_folder(self):
        from PySide6.QtGui import QImage
        folder = self.tmp.path / "vereinslogo"
        folder.mkdir()
        (folder / "LIESMICH.txt").write_text("x", encoding="utf-8")
        QImage(20, 10, QImage.Format.Format_RGB32).save(str(folder / "verein.png"))
        menu = self.window.menu_screen
        self.assertFalse(menu._club_logo.isVisible())
        self.open_section("Anzeige")
        self.select("Vereinslogo")
        self.assertEqual(self.screen._list.current().value(), "(kein Logo)")
        self.key(Qt.Key.Key_6)
        self.assertEqual(self.window._settings.club_logo, "verein.png")
        self.assertEqual(self.saved()["club_logo"], "verein.png")
        self.assertTrue(menu._club_logo.has_image)
        self.key(Qt.Key.Key_Escape)
        self.key(Qt.Key.Key_Escape)
        self.assertIs(self.window.stack.currentWidget(), menu)
        self.assertTrue(menu._club_logo.isVisible())
        self.assertLess(menu._logo.height(), menu.height() * 0.75)   # BK-Bild kleiner, Logo darunter
        self.assertGreater(menu._club_logo.y(), menu._logo.y() + menu._logo.height() - 1)
        # Datei verschwindet -> Hinweis, Programm läuft weiter
        (folder / "verein.png").unlink()
        self.window._load_club_logo()
        self.assertFalse(menu._club_logo.isVisible())
        self.assertIn("Vereinslogo", self.window.footer.current_text())
        self.window.show_settings()
        self.open_section("Anzeige")
        self.select("Vereinslogo")
        self.assertEqual(self.screen._list.current().value(), "verein.png (fehlt)")
        self.key(Qt.Key.Key_6)                                     # zurück auf „kein Logo“
        self.assertEqual(self.window._settings.club_logo, "")

    def test_key_capture_changes_legend(self):
        self.open_section("Tasten")
        self.select("Korrektur (Rücknahme)")
        self.key(Qt.Key.Key_Enter)
        self.assertIn("Taste drücken", self.window.footer.current_text())
        self.key(Qt.Key.Key_U, "u")
        self.assertEqual(self.window._settings.key_bindings.keys("undo"), ("U",))
        self.assertEqual(self.keymap.label("undo"), "U")
        self.select("Partie abbrechen")
        self.key(Qt.Key.Key_Enter)
        self.key(Qt.Key.Key_U, "u")                                # doppelt -> abgelehnt
        self.assertEqual(self.window._settings.key_bindings.keys("abort"), ("*",))
        self.key(Qt.Key.Key_6)                                     # [4]/[6] = Standard
        self.window.game_screen.start_game(Game(GameState.new(BK50)))
        self.assertIn("Korrektur mit  [U]", " ".join(self.window.game_screen.footer_segments()))
        self.window.game_screen.clear()

    def test_colors(self):
        self.open_section("Design")
        self.assertEqual(self.window._settings.theme_mode, "klassisch")
        self.select("Primärfarbe – Rot (R G B)")
        self.key(Qt.Key.Key_4)                                     # 223 -> 218, Schema wird "eigen"
        settings = self.window._settings
        self.assertEqual(settings.theme_mode, "eigen")
        self.assertEqual(settings.primary_color[0], self.base.primary_color[0] - 5)
        self.assertEqual(self.theme.BAR.red(), settings.primary_color[0])
        self.screen.ask_int = lambda title, label, current, low, high: 20
        for part in ("Rot (R G B)", "Grün", "Blau"):
            self.select(f"Primärfarbe – {part}")
            self.key(Qt.Key.Key_Enter)
        self.assertEqual(self.window._settings.primary_color, (20, 20, 20))
        self.assertEqual(self.theme.BAR_TEXT.name(), "#ffffff")    # dunkle Leiste -> helle Schrift
        self.select("Farbschema")
        self.key(Qt.Key.Key_Enter)                                 # zurück auf klassisch
        self.assertEqual(self.theme.BAR.name(), "#dfdeca")

    def test_sounds_are_detected_and_volume(self):
        self.open_section("Töne")
        played = []
        self.screen.preview_sound = lambda name: played.append(name) or True
        self.select("Ton am Partie-Ende")
        self.key(Qt.Key.Key_6)
        self.assertEqual(self.window._settings.end_sound, "a.wav")
        self.key(Qt.Key.Key_6)
        self.assertEqual(self.window._settings.end_sound, "b.mp3")
        self.key(Qt.Key.Key_Enter)
        self.assertEqual(played, ["b.mp3"])
        self.key(Qt.Key.Key_6)
        self.assertEqual(self.window._settings.end_sound, "")       # (kein Ton)
        self.select("Lautstärke")
        self.key(Qt.Key.Key_4)
        self.assertEqual(self.window._settings.sound_volume, self.base.sound_volume - 10)

    def test_images_can_be_switched_off(self):
        from PySide6.QtGui import QImage
        QImage(8, 8, QImage.Format.Format_RGB32).save(str(self.tmp.path / "bilder" / "plus" / "x.png"))
        self.open_section("Bilder")
        self.select("Bilder bei +6 / +7")
        self.assertEqual(self.screen._list.current().value(), "1 von 1 aktiv")
        self.key(Qt.Key.Key_Enter)
        self.assertEqual(self.screen._list.current().label, "x.png")
        self.key(Qt.Key.Key_Enter)
        self.assertEqual(self.window._settings.disabled_images, ("plus/x.png",))
        self.key(Qt.Key.Key_Escape)
        self.assertEqual(self.screen._list.current().value(), "0 von 1 aktiv")

    def test_pdf_folder_and_printer(self):
        from bk.ui import report_output
        target = self.tmp.path / "usb"
        self.open_section("Drucken & PDF")
        self.screen.ask_folder = lambda title, start: str(target)
        self.select("PDF-Speicherort")
        self.key(Qt.Key.Key_Enter)
        self.assertEqual(self.window._settings.pdf_save_dir, str(target))
        self.screen.printer_names = lambda: ["Drucker A"]
        self.select("Drucker")
        self.key(Qt.Key.Key_6)
        self.assertEqual(self.window._settings.printer_name, "Drucker A")

        game = Game(GameState.new(BK50))
        for _ in range(50):
            game.record(3)
        game.finish()
        settings = self.window._settings
        first = report_output.save_pdf(game.state, settings)      # ohne Nachfrage, freier Name
        second = report_output.save_pdf(game.state, settings)
        self.assertEqual(first.parent, target)
        self.assertNotEqual(first, second)
        self.assertTrue(second.stem.endswith("_2"))
        self.assertIn("nicht gefunden", report_output.choose_printer(settings)[1])   # "Drucker A" fehlt

    def test_reset_needs_two_presses(self):
        self.store.set("club_name", "Geändert")
        self.window.apply_settings(self.store.current)
        self.window.show_settings()
        self.select("Alle Einstellungen zurücksetzen")
        self.key(Qt.Key.Key_Enter)
        self.assertEqual(self.window._settings.club_name, "Geändert")
        self.key(Qt.Key.Key_Enter)
        self.assertEqual(self.window._settings.club_name, self.base.club_name)


if __name__ == "__main__":
    unittest.main()
