"""Tests des automatischen Aufräumens (Archiv, Logs, Ergebnisse) und der Log-Einstellungen."""

import os
import time
import unittest

from tests.helpers import TempDir

from bk.logging_setup import crash_log_mode
from bk.maintenance import SECONDS_PER_DAY, delete_older_than, run_cleanup

NOW = time.time()


def make_file(path, age_days):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("x", encoding="utf-8")
    stamp = NOW - age_days * SECONDS_PER_DAY
    os.utime(path, (stamp, stamp))
    return path


class CleanupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()
        self.data = self.tmp.path / "data"
        self.logs = self.tmp.path / "logs"
        self.results = self.tmp.path / "results"

    def tearDown(self):
        self.tmp.cleanup()

    def test_only_files_older_than_limit_are_deleted(self):
        old = make_file(self.data / "archive" / "alt.json", 31)
        young = make_file(self.data / "archive" / "neu.json", 29)
        removed = delete_older_than(self.data / "archive", 30, ("*.json",), NOW)
        self.assertEqual(removed, [old])
        self.assertFalse(old.exists())
        self.assertTrue(young.exists())

    def test_zero_days_means_never(self):
        old = make_file(self.data / "archive" / "alt.json", 400)
        self.assertEqual(delete_older_than(self.data / "archive", 0, ("*.json",), NOW), [])
        self.assertTrue(old.exists())

    def test_missing_folder_is_no_error(self):
        self.assertEqual(delete_older_than(self.tmp.path / "gibt_es_nicht", 30, ("*",), NOW), [])

    def test_run_cleanup_respects_each_setting(self):
        archive_old = make_file(self.data / "archive" / "a.json", 45)
        corrupt_old = make_file(self.data / "corrupt" / "kaputt.json.bak", 45)
        log_old = make_file(self.logs / "application.log.2026-08-01", 45)
        log_current = make_file(self.logs / "application.log", 45)     # aktuelle Datei nie löschen
        crash = make_file(self.logs / "crash.log", 45)
        result_old = make_file(self.results / "BK50_2026-08-01_18-00.pdf", 45)
        active = make_file(self.data / "active_game.json", 45)          # laufende Partie nie löschen
        result = run_cleanup(self.data, self.logs, self.results, 30, 30, 0, NOW)
        self.assertEqual((result.archive, result.logs, result.results), (2, 1, 0))
        self.assertFalse(archive_old.exists())
        self.assertFalse(corrupt_old.exists())
        self.assertFalse(log_old.exists())
        self.assertTrue(log_current.exists())
        self.assertTrue(crash.exists())
        self.assertTrue(result_old.exists())                            # RESULTS_RETENTION_DAYS = 0
        self.assertTrue(active.exists())

    def test_results_are_deleted_only_when_configured(self):
        result_old = make_file(self.results / "BK50_2026-08-01_18-00.pdf", 45)
        json_old = make_file(self.results / "BK50_2026-08-01_18-00.json", 45)
        result = run_cleanup(self.data, self.logs, self.results, 30, 30, 40, NOW)
        self.assertEqual(result.results, 2)
        self.assertFalse(result_old.exists() or json_old.exists())

    def test_subfolders_are_not_touched(self):
        nested = make_file(self.data / "archive" / "unterordner" / "x.json", 90)
        run_cleanup(self.data, self.logs, self.results, 30, 30, 0, NOW)
        self.assertTrue(nested.exists())


class CrashLogTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()

    def tearDown(self):
        self.tmp.cleanup()

    def test_old_crash_log_is_cleared(self):
        path = make_file(self.tmp.path / "crash.log", 31)
        self.assertEqual(crash_log_mode(path, 30, NOW), "w")

    def test_recent_crash_log_is_kept(self):
        path = make_file(self.tmp.path / "crash.log", 3)
        self.assertEqual(crash_log_mode(path, 30, NOW), "a")
        self.assertEqual(crash_log_mode(self.tmp.path / "fehlt.log", 30, NOW), "a")
        self.assertEqual(crash_log_mode(path, 0, NOW + 999 * SECONDS_PER_DAY), "a")


if __name__ == "__main__":
    unittest.main()
