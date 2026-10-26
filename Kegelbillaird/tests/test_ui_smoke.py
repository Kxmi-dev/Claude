"""Oberflächentests: echte Qt-Tastenereignisse an das Hauptfenster (ohne Bildschirm)."""

import dataclasses
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
from bk.models import GameState
from bk.settings import AppSettings
from bk.storage import GameStorage

KP = Qt.KeyboardModifier.KeypadModifier if QApplication else None
NO = Qt.KeyboardModifier.NoModifier if QApplication else None


@unittest.skipIf(QApplication is None, "PySide6 nicht installiert")
class UiSmokeTests(unittest.TestCase):
    LOCK = 0.25
    RESULT_LOCK = 0.6

    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = TempDir()
        self.settings = dataclasses.replace(
            AppSettings.from_config(config),
            data_dir=self.tmp.path / "data", results_dir=self.tmp.path / "results",
            logs_dir=self.tmp.path / "logs", input_lock_seconds=self.LOCK, undo_lock_seconds=0.1,
            abort_confirm_seconds=2.0, auto_enable_numlock=False, fullscreen=False,
            result_lock_seconds=self.RESULT_LOCK)
        self.storage = GameStorage(self.settings.data_dir, self.settings.results_dir)
        self.storage.ensure_directories()
        self.windows = []

    def tearDown(self):
        for window in self.windows:
            window.close()
            window.deleteLater()
        QTest.qWait(20)
        self.tmp.cleanup()

    # ------------------------------------------------------------ Hilfen
    def open_window(self):
        from bk.ui.main_window import MainWindow
        window = MainWindow(self.settings, self.storage)
        window.resize(1280, 800)
        window.show()
        QTest.qWait(450)                       # Start-Prüfung (unterbrochene Partie) abwarten
        self.windows.append(window)
        return window

    def key(self, window, key, modifier=None, autorepeat=False):
        event = QKeyEvent(QEvent.Type.KeyPress, key, modifier if modifier is not None else KP, "", autorepeat)
        QApplication.sendEvent(window, event)

    def score(self, window, value):
        if value < 0:                                            # Plus ist voreingestellt
            self.key(window, Qt.Key.Key_Minus)
        self.key(window, getattr(Qt.Key, f"Key_{abs(value)}"))

    def start_game(self, window, mode_index=1):
        for _ in range(mode_index):
            self.key(window, Qt.Key.Key_2)                       # [2] = nach unten
        self.key(window, Qt.Key.Key_Enter)                       # startet sofort, ohne Spielerdaten
        self.assertIs(window.stack.currentWidget(), window.game_screen)
        return window.game_screen.game

    # ------------------------------------------------------------- Tests
    def test_score_lock_and_undo_via_numpad(self):
        window = self.open_window()
        game = self.start_game(window)
        self.assertEqual(game.state.mode.key, "BK50")
        self.score(window, 5)
        self.assertEqual(game.state.strokes, [5])
        self.score(window, 3)                                    # während Sperre -> ignoriert
        self.key(window, Qt.Key.Key_5)                           # prellende Taste -> ignoriert
        self.assertEqual(game.state.strokes, [5])
        self.assertIn("gesperrt", window.footer.current_text().lower())
        QTest.qWait(int(self.LOCK * 1000) + 120)
        self.score(window, -3)
        self.assertEqual(game.state.strokes, [5, -3])
        self.assertEqual(window.game_screen.score_box.text(), "2")
        self.key(window, Qt.Key.Key_Slash)                       # Korrektur: Korrekturfeld öffnet sich
        self.assertEqual(game.state.strokes, [5, -3])
        self.assertEqual(window.game_screen.status_box.text(), "KORREKTUR")
        self.assertEqual(window.game_screen.grid._pending, 1)    # Kästchen gelb hinterlegt
        overlay = window.overlay
        self.assertTrue(overlay.isVisible())
        self.assertEqual(overlay.content.title, "Korrektur  Stoß 2")
        self.assertEqual(overlay.content.top_lines, ["Alte Punktzahl:   \u22123"])
        self.assertEqual(overlay.content.big, "Neue Punktzahl:   _")
        self.key(window, Qt.Key.Key_Enter)                       # ohne neue Zahl: Feld bleibt offen
        self.assertTrue(overlay.isVisible())
        self.key(window, Qt.Key.Key_4)                           # vertippt …
        self.key(window, Qt.Key.Key_Minus)                       # … Minus nachträglich
        self.assertEqual(overlay.content.big, "Neue Punktzahl:   \u22124")
        self.key(window, Qt.Key.Key_2)                           # andere Ziffer überschreibt
        self.assertEqual(overlay.content.big, "Neue Punktzahl:   \u22122")
        self.assertEqual(game.state.strokes, [5, -3])            # noch nichts geändert
        self.key(window, Qt.Key.Key_Enter)                       # übernehmen
        self.assertFalse(overlay.isVisible())
        self.assertEqual(game.state.strokes, [5, -2])
        self.assertIsNone(window.game_screen.grid._pending)
        self.assertEqual(window.game_screen.score_box.text(), "3")
        self.assertEqual(self.storage.load_active().state.strokes, [5, -2])
        self.assertEqual(window.game_screen.strokes_box.text(), "2")         # gespielte Stöße
        QTest.qWait(100)                                         # kurze Sperre der Korrektur-Taste
        self.key(window, Qt.Key.Key_Slash)                       # Korrektur abbrechen mit [*]
        self.key(window, Qt.Key.Key_7)
        self.key(window, Qt.Key.Key_Asterisk)
        self.assertFalse(overlay.isVisible())
        self.assertEqual(game.state.strokes, [5, -2])
        self.score(window, 1)                                    # nächster Stoß sofort möglich
        self.assertEqual(game.state.strokes, [5, -2, 1])

    def test_non_numpad_and_autorepeat_keys_are_ignored(self):
        window = self.open_window()
        game = self.start_game(window)
        self.key(window, Qt.Key.Key_Plus, NO)                   # normale Tastatur
        self.key(window, Qt.Key.Key_4, NO)
        self.assertEqual(game.played, 0)
        self.key(window, Qt.Key.Key_Plus)
        self.key(window, Qt.Key.Key_4, autorepeat=True)          # gehaltene Taste
        self.assertEqual(game.played, 0)
        self.key(window, Qt.Key.Key_Return, NO)                  # keine Bestätigungstaste nötig/wirksam
        self.key(window, Qt.Key.Key_Backspace, NO)               # kein Backspace
        self.key(window, Qt.Key.Key_4)
        self.assertEqual(game.state.strokes, [4])

    def test_full_game_finishes_with_pdf(self):
        window = self.open_window()
        game = self.start_game(window)
        for i in range(50):
            self.score(window, (i % 15) - 7)
            QTest.qWait(int(self.LOCK * 1000) + 40)
        self.assertTrue(game.is_complete)
        total = game.total
        QTest.qWait(300)
        self.assertIs(window.stack.currentWidget(), window.game_screen)   # wartet auf [Enter]
        self.assertEqual(window.game_screen.status_box.text(), "ENDE")
        self.key(window, Qt.Key.Key_Enter)
        result = window.result_screen                             # Auswertung im Hauptfenster
        self.assertIs(window.stack.currentWidget(), result)
        self.assertEqual(result._plate._text, "Endergebnis")
        self.assertEqual(result.boxes["total"].text(), str(total).replace("-", "\u2212"))
        self.assertEqual(result.stats[0].rows()[0][:2], ("Ausgeführte Stöße", "50"))
        self.assertEqual(result.button_texts(),
                         ["Partie speichern", "Partie drucken", "Tabelle ansehen", "Neue Partie", "Hauptmenü"])
        pdfs = list(self.settings.results_dir.glob("BK50_*.pdf"))
        self.assertEqual(len(pdfs), 1)                            # PDF wurde automatisch gespeichert
        self.assertFalse(self.storage.has_active_files())
        self.assertEqual(len(list((self.settings.data_dir / "archive").glob("*_beendet.json"))), 1)
        self.key(window, Qt.Key.Key_Enter)                       # noch gesperrt -> bleibt stehen
        self.assertIs(window.stack.currentWidget(), result)
        self.assertIn("gesperrt", window.footer.current_text())
        QTest.qWait(int(self.RESULT_LOCK * 1000) + 100)
        self.key(window, Qt.Key.Key_Enter)                       # "Hauptmenü" ist vorgewählt
        self.assertIs(window.stack.currentWidget(), window.menu_screen)

    def test_undo_of_last_stroke_during_lock_prevents_finish(self):
        state = GameState.new(BK50)
        state.strokes.extend([1] * 49)
        self.storage.save_active(state)
        window = self.open_window()
        self.key(window, Qt.Key.Key_Enter)                       # PARTIE FORTSETZEN
        game = window.game_screen.game
        self.assertEqual(game.played, 49)
        self.score(window, 7)
        self.assertTrue(game.is_complete)
        self.key(window, Qt.Key.Key_Slash)                       # Korrektur nach dem letzten Stoß
        self.key(window, Qt.Key.Key_2)
        self.key(window, Qt.Key.Key_Enter)                       # übernimmt (beendet die Partie nicht)
        QTest.qWait(int(self.LOCK * 1000) + 300)
        self.assertFalse(window.overlay.isVisible())
        self.assertEqual(game.played, 50)
        self.assertEqual(game.state.strokes[-1], 2)
        self.assertIs(window.stack.currentWidget(), window.game_screen)
        self.key(window, Qt.Key.Key_Enter)                       # erst jetzt: Auswertung
        self.assertEqual(window.result_screen.boxes["total"].text(), "51")

    def test_result_screen_statistics_and_new_game(self):
        state = GameState.new(BK50)
        state.strokes.extend([7, -2, 0] + [1] * 46)
        state.corrections = 2
        self.storage.save_active(state)
        window = self.open_window()
        self.key(window, Qt.Key.Key_Enter)                       # PARTIE FORTSETZEN
        self.score(window, 5)
        self.key(window, Qt.Key.Key_Enter)                       # Enter: Sperre aus + Auswertung
        result = window.result_screen
        self.assertIs(window.stack.currentWidget(), result)
        counts = {name: box.text() for name, box in result.analysis.items()}
        self.assertEqual((counts["1er"], counts["5er"], counts["7er"], counts["Leer"], counts["Minus"]),
                         ("46", "1", "1", "1", "1"))
        rows = {label: value for table in result.stats for label, value, _ in table.rows()}
        self.assertEqual(rows["Summe positive Punkte"], "58")
        self.assertEqual(rows["Summe Minuspunkte"], "\u22122")
        self.assertEqual(rows["Höchstes Stoßergebnis"], "7")
        self.assertEqual(rows["Halbzeitergebnis"], "27")             # 7 − 2 + 0 + 22 × 1
        self.assertEqual(rows["Punkte 2. Halbzeit"], "29")
        self.assertEqual(rows["Korrekturen"], "2")
        QTest.qWait(int(self.RESULT_LOCK * 1000) + 100)
        self.key(window, Qt.Key.Key_4)                           # „Neue Partie“
        self.key(window, Qt.Key.Key_Enter)
        self.assertIs(window.stack.currentWidget(), window.game_screen)
        self.assertEqual(window.game_screen.game.state.mode.key, "BK50")
        self.assertEqual(window.game_screen.game.played, 0)

    def test_abort_with_star_and_minus(self):
        window = self.open_window()
        game = self.start_game(window)
        self.score(window, 2)
        self.key(window, Qt.Key.Key_Asterisk)
        self.assertTrue(window.overlay.isVisible())
        self.key(window, Qt.Key.Key_5)                           # andere Taste -> kein Abbruch
        self.assertFalse(window.overlay.isVisible())
        self.assertIs(window.stack.currentWidget(), window.game_screen)
        self.assertEqual(game.played, 1)
        self.key(window, Qt.Key.Key_Asterisk)
        self.key(window, Qt.Key.Key_Minus)
        self.assertIs(window.stack.currentWidget(), window.menu_screen)
        self.assertFalse(self.storage.has_active_files())
        self.assertEqual(len(list((self.settings.data_dir / "archive").glob("*_abgebrochen.json"))), 1)

    def test_resume_or_new_game_after_crash(self):
        state = GameState.new(BK50)
        state.strokes.extend([3, 4, -1])
        self.storage.save_active(state)
        window = self.open_window()
        self.assertTrue(window.overlay.interactive)
        self.assertEqual(window.overlay.content.title, "Unterbrochene Partie gefunden")
        self.key(window, Qt.Key.Key_2)                           # NEUE PARTIE wählen
        self.key(window, Qt.Key.Key_Enter)
        self.assertIs(window.stack.currentWidget(), window.menu_screen)
        self.assertFalse(self.storage.has_active_files())
        self.assertEqual(len(list((self.settings.data_dir / "archive").glob("*_verworfen.json"))), 1)
        game = self.start_game(window)
        self.assertEqual(game.played, 0)
        self.assertNotEqual(game.state.game_id, state.game_id)

    def test_corrupt_save_is_reported(self):
        self.storage.active_path.write_text("{kaputt", encoding="utf-8")
        window = self.open_window()
        self.assertEqual(window.overlay.content.title, "Spielstand beschädigt")
        self.key(window, Qt.Key.Key_Enter)
        self.assertIs(window.stack.currentWidget(), window.menu_screen)
        self.assertEqual(len(list((self.settings.data_dir / "corrupt").iterdir())), 1)

    def test_billiard_vs_fussball_starts_with_25_strokes(self):
        window = self.open_window()
        self.key(window, Qt.Key.Key_2)
        self.key(window, Qt.Key.Key_2)                           # "Billiard vs Fußball"
        self.key(window, Qt.Key.Key_Enter)
        self.assertIs(window.stack.currentWidget(), window.game_screen)
        game = window.game_screen.game
        self.assertEqual(game.state.mode.key, "BK25")
        self.assertEqual(game.state.mode.strokes, 25)
        self.assertEqual(window.title_bar._title, "Partie: Billiard vs Fußball")

    def test_grid_shows_points_per_row(self):
        from bk.ui.widgets import ScoreGrid
        grid = ScoreGrid()
        grid.configure(25, 10, None, 5)
        grid.set_values([1] * 10 + [-2, 3])
        self.assertEqual(grid.row_sums(), [10, 1, None])

    def test_grid_running_total_and_empty_mark(self):
        from bk.ui.widgets import ScoreGrid
        grid = ScoreGrid()
        grid.configure(25, 10, None, 5)
        grid.set_values([3, 3, 3, 0, -2, 5])
        self.assertEqual(grid.cell_texts(), ["3", "3", "3", "X", "\u22122", "5"])
        grid.set_running_total(True)
        self.assertEqual(grid.cell_texts(), ["3", "6", "9", "X", "7", "12"])
        grid.resize(600, 200)
        grid.grab()                                              # zeichnet ohne Fehler

    def test_halftime_stays_yellow_and_enter_skips_lock(self):
        from bk.ui.game_screen import HALFTIME_TINT
        state = GameState.new(BK50)
        state.strokes.extend([1] * 24)
        self.storage.save_active(state)
        window = self.open_window()
        self.key(window, Qt.Key.Key_Enter)                       # PARTIE FORTSETZEN
        screen = window.game_screen
        self.assertNotEqual(screen.halftime_box._fill, HALFTIME_TINT)
        self.score(window, 2)                                    # 25. Stoß = Halbzeit
        self.assertEqual(screen.status_box.text(), "GESPERRT")
        self.key(window, Qt.Key.Key_Enter)                       # Sperre sofort beenden
        self.assertEqual(screen.status_box.text(), "BEREIT")
        self.score(window, 4)
        self.assertEqual(screen.game.played, 26)
        QTest.qWait(500)
        self.assertEqual(screen.halftime_box._fill, HALFTIME_TINT)   # bleibt gelb
        self.key(window, Qt.Key.Key_Slash)
        self.key(window, Qt.Key.Key_5)                           # andere Taste = keine Korrektur
        self.assertEqual(screen.game.played, 26)

    def test_minus_mode_applies_to_one_stroke_only(self):
        window = self.open_window()
        game = self.start_game(window)
        self.key(window, Qt.Key.Key_Minus)
        self.assertTrue(window.game_screen.controller.minus_selected)
        self.assertEqual(window.game_screen.status_box.text(), "MINUS")
        self.key(window, Qt.Key.Key_3)
        self.assertEqual(game.state.strokes, [-3])
        self.assertFalse(window.game_screen.controller.minus_selected)
        QTest.qWait(int(self.LOCK * 1000) + 120)
        self.assertEqual(window.game_screen.status_box.text(), "BEREIT")
        self.key(window, Qt.Key.Key_3)                           # ohne Vorzeichen -> Plus
        self.assertEqual(game.state.strokes, [-3, 3])
        QTest.qWait(int(self.LOCK * 1000) + 120)
        self.key(window, Qt.Key.Key_Minus)
        self.key(window, Qt.Key.Key_Plus)                        # Minus wieder aufgehoben
        self.key(window, Qt.Key.Key_2)
        self.assertEqual(game.state.strokes, [-3, 3, 2])
        self.assertEqual(window.title_bar._title, "Partie: 50 Stoß")

    # ------------------------------------------------ Archiv, Statistik, Wiedergabe
    def _archive_two_games(self):
        """Eine beendete und eine abgebrochene Partie ins Archiv legen."""
        from bk.game import Game
        finished = GameState.new(BK50, started_at="2026-09-28T19:00:00")
        game = Game(finished)
        for i in range(50):
            game.record((i % 8) - 1)
        game.finish()
        self.storage.archive_active(finished, "beendet")
        aborted = GameState.new(BK50, started_at="2026-09-29T10:00:00")
        game = Game(aborted)
        for value in (3, 4, -2):
            game.record(value)
        game.abort()
        self.storage.archive_active(aborted, "abgebrochen")
        return finished, aborted

    def open_archive(self, window):
        for _ in range(3):
            self.key(window, Qt.Key.Key_2)                       # bis "Archiv" nach unten
        self.key(window, Qt.Key.Key_Enter)
        self.assertIs(window.stack.currentWidget(), window.archive_screen)

    def test_archive_lists_games_newest_first(self):
        finished, aborted = self._archive_two_games()
        window = self.open_window()
        self.open_archive(window)
        entries = window.archive_screen._entries
        self.assertEqual([e.state.game_id for e in entries], [aborted.game_id, finished.game_id])
        self.assertEqual([e.status_label for e in entries], ["abgebrochen", "beendet"])
        recent = window.archive_screen._recent                    # Abschnitt „Letzte Partien“
        self.assertEqual([e.state.game_id for e in recent], [finished.game_id])
        self.assertEqual(window.archive_screen.selected_entry().state.game_id, finished.game_id)
        self.key(window, Qt.Key.Key_2)                           # weiter in die Gesamtliste
        self.assertEqual(window.archive_screen.selected_entry().state.game_id, aborted.game_id)
        self.key(window, Qt.Key.Key_8)                           # und zurück
        self.assertEqual(window.archive_screen.selected_entry().state.game_id, finished.game_id)
        self.key(window, Qt.Key.Key_Asterisk)                    # [*] = zurück
        self.assertIs(window.stack.currentWidget(), window.menu_screen)

    def test_result_screen_save_and_print(self):
        from PySide6.QtPrintSupport import QPrinter
        finished, _ = self._archive_two_games()
        window = self.open_window()
        self.open_archive(window)                                # beendete Partie ist oben vorgewählt
        self.key(window, Qt.Key.Key_Enter)
        self.assertEqual(window.overlay.content.choices, ["AUSWERTUNG ANZEIGEN", "WIEDERGABE", "ZURÜCK"])
        self.key(window, Qt.Key.Key_Enter)                       # AUSWERTUNG ANZEIGEN
        result = window.result_screen
        self.assertIs(window.stack.currentWidget(), result)      # kein Extra-Fenster
        self.assertEqual(result.button_texts(), ["Partie speichern", "Partie drucken", "Tabelle ansehen", "Zurück"])
        self.key(window, Qt.Key.Key_4)                           # „Tabelle ansehen“
        self.key(window, Qt.Key.Key_Enter)
        self.assertTrue(result.table_mode)
        self.assertTrue(result.grid.isVisible())
        self.assertEqual(len(result.grid.cell_texts()), 50)
        self.key(window, Qt.Key.Key_Asterisk)                    # zurück zur Auswertung, nicht ins Archiv
        self.assertFalse(result.table_mode)
        self.assertIs(window.stack.currentWidget(), result)
        self.assertEqual(result.stats[2].rows()[3], ("Korrekturen", "0", False))
        self.assertEqual(result.state.strokes, finished.strokes)
        saved = result.save_pdf(self.tmp.path / "usb" / "bericht")    # Endung wird ergänzt
        self.assertEqual(saved.name, "bericht.pdf")
        self.assertTrue(saved.read_bytes().startswith(b"%PDF"))
        from bk.ui import report_output
        if report_output.choose_printer(self.settings)[0] is None:  # hier kein Drucker vorhanden:
            self.assertFalse(result.print_report())                 # klare Meldung, kein Dialog
            self.assertIn("Standarddrucker", result.note_text())
        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setOutputFormat(QPrinter.OutputFormat.PdfFormat)
        printer.setOutputFileName(str(self.tmp.path / "druck.pdf"))
        self.assertTrue(result.print_report(printer))
        self.assertGreater((self.tmp.path / "druck.pdf").stat().st_size, 10_000)
        self.key(window, Qt.Key.Key_Asterisk)                    # zurück
        self.assertIs(window.stack.currentWidget(), window.archive_screen)

    def test_replay_shows_game_without_saving(self):
        finished, _ = self._archive_two_games()
        window = self.open_window()
        self.open_archive(window)
        self.key(window, Qt.Key.Key_Enter)
        self.key(window, Qt.Key.Key_2)                           # WIEDERGABE
        self.key(window, Qt.Key.Key_Enter)
        screen = window.game_screen
        self.assertIs(window.stack.currentWidget(), screen)
        self.assertTrue(screen.is_replay)
        self.assertIn("Wiedergabe", window.title_bar._title)
        for _ in range(6):
            self.key(window, Qt.Key.Key_Plus)                    # schnellstes Tempo
        self.key(window, Qt.Key.Key_5)                           # Wertungstasten wirken nicht
        QTest.qWait(700)
        self.assertGreater(screen.game.played, 1)
        self.key(window, Qt.Key.Key_Enter)                       # Pause
        paused_at = screen.game.played
        QTest.qWait(400)
        self.assertEqual(screen.game.played, paused_at)
        self.key(window, Qt.Key.Key_Enter)                       # weiter
        QTest.qWait(50 * 150 + 500)
        self.assertEqual(screen.game.state.strokes, finished.strokes)
        self.assertFalse(self.storage.has_active_files())        # nichts gespeichert
        self.assertFalse(screen.has_live_game)
        self.key(window, Qt.Key.Key_Enter)                       # am Ende: Statistik
        self.assertIs(window.stack.currentWidget(), window.result_screen)
        self.key(window, Qt.Key.Key_Escape)                      # zurück zur Wiedergabe
        self.assertIs(window.stack.currentWidget(), screen)
        self.key(window, Qt.Key.Key_Escape)                      # Wiedergabe verlassen
        self.assertIs(window.stack.currentWidget(), window.archive_screen)
        window.close()
        self.assertFalse(self.storage.has_active_files())        # Schließen speichert keine Wiedergabe

    def test_continue_aborted_game_from_archive(self):
        _, aborted = self._archive_two_games()
        window = self.open_window()
        self.open_archive(window)
        self.key(window, Qt.Key.Key_2)                           # aus „Letzte Partien“ in die Gesamtliste
        self.key(window, Qt.Key.Key_Enter)                       # abgebrochene Partie (neueste)
        self.assertEqual(window.overlay.content.choices[2], "WEITERSPIELEN")
        self.key(window, Qt.Key.Key_2)
        self.key(window, Qt.Key.Key_2)
        self.key(window, Qt.Key.Key_Enter)
        game = window.game_screen.game
        self.assertFalse(window.game_screen.is_replay)
        self.assertEqual(game.state.strokes, [3, 4, -2])
        self.assertTrue(game.is_running)
        self.assertEqual(self.storage.load_active().state.game_id, aborted.game_id)
        self.assertEqual(len(list((self.settings.data_dir / "archive").glob("*_abgebrochen.json"))), 0)
        self.score(window, 6)
        self.assertEqual(self.storage.load_active().state.strokes, [3, 4, -2, 6])


if __name__ == "__main__":
    unittest.main()
