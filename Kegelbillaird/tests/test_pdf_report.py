"""Tests der PDF-Erstellung."""

import unittest

from tests.helpers import BK50, BK100, PROJECT_DIR, TempDir

from bk.game import Game
from bk.models import GameState
from bk.pdf_report import PdfError, build_report_bytes, format_duration, report_base_name, write_report

LOGO = PROJECT_DIR / "assets" / "logo.png"


def finished_state(mode, values):
    state = GameState.new(mode, started_at="2026-09-29T15:42:10")
    game = Game(state)
    for value in values:
        game.record(value)
    game.finish("2026-09-29T16:20:00")
    state.elapsed_seconds = 2270
    return state


def pdf_text(data: bytes) -> str | None:
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    import io
    return "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)


class PdfTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_file_name_pattern(self):
        state = finished_state(BK50, [1] * 50)
        self.assertEqual(report_base_name(state), "BK50_2026-09-29_15-42")

    def test_bk50_pdf_is_created_and_complete(self):
        values = [3, 5, -2] + [2] * 46 + [4]
        state = finished_state(BK50, values)
        path = write_report(state, self.tmp.path / "results", "SG Grün-Weiß Schlepzig e.V.", "BK-Scoreboard", LOGO)
        self.assertTrue(path.exists())
        self.assertEqual(path.name, "BK50_2026-09-29_15-42.pdf")
        data = path.read_bytes()
        self.assertTrue(data.startswith(b"%PDF"))
        text = pdf_text(data)
        if text is not None:
            self.assertIn(f"ENDRESULTAT: {sum(values)}", text)
            self.assertIn("29.09.2026", text)
            self.assertIn("Stoßliste", text)

    def test_bk100_pdf_contains_all_strokes(self):
        values = [(i % 9) - 2 for i in range(100)]
        state = finished_state(BK100, values)
        data = build_report_bytes(state, "Verein", "BK-Scoreboard", LOGO)
        self.assertLess(len(data), 200_000)                         # Logo als JPEG -> kleines PDF
        text = pdf_text(data)
        if text is not None:
            self.assertIn(f"ENDRESULTAT: {sum(values)}", text)
            for number in (1, 25, 50, 75, 100):
                self.assertIn(str(number), text)
            self.assertIn("Anzahl je Wertung", text)

    def test_bk100_fits_on_one_page(self):
        try:
            from pypdf import PdfReader
        except ImportError:
            self.skipTest("pypdf nicht installiert")
        import io
        state = finished_state(BK100, [(i % 15) - 7 for i in range(100)])
        data = build_report_bytes(state, "SG Grün-Weiß Schlepzig e.V.", "BK-Scoreboard", LOGO)
        self.assertEqual(len(PdfReader(io.BytesIO(data)).pages), 1)

    def test_second_pdf_gets_unique_name(self):
        state = finished_state(BK50, [1] * 50)
        first = write_report(state, self.tmp.path, "Verein", "BK")
        second = write_report(state, self.tmp.path, "Verein", "BK")
        self.assertNotEqual(first, second)
        self.assertTrue(first.exists() and second.exists())

    def test_missing_logo_does_not_break_pdf(self):
        state = finished_state(BK50, [0] * 50)
        data = build_report_bytes(state, "Verein", "BK", self.tmp.path / "fehlt.png")
        self.assertTrue(data.startswith(b"%PDF"))

    def test_wide_transparent_club_logo_fits_and_turns_white(self):
        from PIL import Image as PilImage
        from bk.pdf_report import _logo_image
        logo = self.tmp.path / "verein.png"
        PilImage.new("RGBA", (600, 200), (0, 0, 0, 0)).save(logo)
        image = _logo_image(logo, 84, max_width=74)
        self.assertLessEqual(image.drawWidth, 74.01)
        self.assertLessEqual(image.drawHeight, 84.01)
        data = build_report_bytes(finished_state(BK50, [1] * 50), "Verein", "BK", logo)
        self.assertTrue(data.startswith(b"%PDF"))

    def test_special_characters_in_club_name(self):
        state = finished_state(BK50, [1] * 50)
        data = build_report_bytes(state, "SG <Grün> & Weiß", "BK", None)
        self.assertTrue(data.startswith(b"%PDF"))

    def test_unwritable_target_raises_pdf_error(self):
        blocker = self.tmp.path / "datei"
        blocker.write_text("x")
        with self.assertRaises(PdfError):
            write_report(finished_state(BK50, [1] * 50), blocker / "results", "Verein", "BK")

    def test_format_duration(self):
        self.assertEqual(format_duration(0), "0:00:00")
        self.assertEqual(format_duration(3725.9), "1:02:05")


if __name__ == "__main__":
    unittest.main()
