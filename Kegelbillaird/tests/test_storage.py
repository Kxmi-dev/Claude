"""Tests der Speicherung: atomisches Schreiben, Wiederherstellung, Beschädigung."""

import json
import unittest

from tests.helpers import BK50, BK100, TempDir

from bk.game import Game
from bk.models import GameState, GameStatus
from bk.storage import GameStorage, LoadStatus, StorageError, decode_state, encode_state


class StorageTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = TempDir()
        self.storage = GameStorage(self.tmp.path / "data", self.tmp.path / "results")

    def tearDown(self):
        self.tmp.cleanup()

    def new_state(self, mode=BK50, strokes=()):
        state = GameState.new(mode)
        state.strokes.extend(strokes)
        return state


class SaveLoadTests(StorageTestCase):
    def test_missing_directories_are_created(self):
        self.assertFalse((self.tmp.path / "data").exists())
        self.storage.save_active(self.new_state())
        self.assertTrue(self.storage.active_path.exists())

    def test_nothing_saved_means_none(self):
        self.assertEqual(self.storage.load_active().status, LoadStatus.NONE)

    def test_roundtrip_restores_everything(self):
        state = self.new_state(BK100, [3, -2, 0, 7, -7])
        state.elapsed_seconds = 123.4
        self.storage.save_active(state)
        loaded = GameStorage(self.storage.data_dir, self.storage.results_dir).load_active()
        self.assertEqual(loaded.status, LoadStatus.OK)
        restored = loaded.state
        self.assertEqual(restored.game_id, state.game_id)
        self.assertEqual(restored.mode, BK100)
        self.assertEqual(restored.strokes, [3, -2, 0, 7, -7])
        self.assertEqual(restored.status, GameStatus.RUNNING)
        self.assertEqual(restored.started_at, state.started_at)
        self.assertAlmostEqual(restored.elapsed_seconds, 123.4)
        game = Game(restored)
        self.assertEqual(game.total, 1)
        self.assertEqual(game.current_stroke_number, 6)

    def test_crash_directly_after_score(self):
        """Wertung + Speichern, danach "Absturz" (neue Objekte lesen von Platte)."""
        state = self.new_state()
        game = Game(state)
        for value in (4, 2, -3):
            game.record(value)
            self.storage.save_active(state)
        restored = GameStorage(self.storage.data_dir, self.storage.results_dir).load_active().state
        self.assertEqual(restored.strokes, [4, 2, -3])

    def test_undo_is_saved(self):
        state = self.new_state()
        game = Game(state)
        game.record(5)
        self.storage.save_active(state)
        game.undo()
        self.storage.save_active(state)
        self.assertEqual(self.storage.load_active().state.strokes, [])

    def test_backup_holds_previous_revision(self):
        state = self.new_state()
        state.strokes.append(1)
        self.storage.save_active(state)
        state.strokes.append(2)
        self.storage.save_active(state)
        backup = decode_state(self.storage.backup_path.read_bytes())
        self.assertEqual(backup.strokes, [1])
        self.assertFalse(self.storage.tmp_path.exists())

    def test_save_failure_raises_storage_error(self):
        blocker = self.tmp.path / "blocked"
        blocker.write_text("keine Ordner-Datei")
        storage = GameStorage(blocker / "data", blocker / "results")
        with self.assertRaises(StorageError):
            storage.save_active(self.new_state())


class RecoveryTests(StorageTestCase):
    def test_corrupt_main_file_recovers_from_backup(self):
        state = self.new_state(strokes=[3])
        self.storage.save_active(state)
        state.strokes.append(4)
        self.storage.save_active(state)
        self.storage.active_path.write_bytes(b'{"kaputt": ')   # halb geschrieben
        result = self.storage.load_active()
        self.assertEqual(result.status, LoadStatus.RECOVERED)
        self.assertEqual(result.state.strokes, [3])

    def test_crash_between_tmp_write_and_replace_uses_newest(self):
        state = self.new_state(strokes=[1])
        self.storage.save_active(state)
        # Simulierter Absturz: neuer Stand liegt vollständig in .tmp, Ersetzen fand nicht statt
        state.strokes.append(6)
        state.revision += 1
        self.storage.tmp_path.write_bytes(encode_state(state))
        result = self.storage.load_active()
        self.assertEqual(result.state.strokes, [1, 6])
        self.assertEqual(result.status, LoadStatus.RECOVERED)

    def test_truncated_tmp_is_ignored(self):
        state = self.new_state(strokes=[2, 2])
        self.storage.save_active(state)
        self.storage.tmp_path.write_bytes(encode_state(state)[:40])
        result = self.storage.load_active()
        self.assertEqual(result.status, LoadStatus.OK)
        self.assertEqual(result.state.strokes, [2, 2])

    def test_manipulated_file_fails_checksum(self):
        self.storage.save_active(self.new_state(strokes=[1, 2]))
        data = json.loads(self.storage.active_path.read_text(encoding="utf-8"))
        data["state"]["strokes"] = [7, 7]
        self.storage.active_path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(ValueError):
            decode_state(self.storage.active_path.read_bytes())

    def test_everything_corrupt_is_quarantined(self):
        self.storage.ensure_directories()
        self.storage.active_path.write_text("Müll", encoding="utf-8")
        self.storage.backup_path.write_bytes(b"\x00\x01")
        result = self.storage.load_active()
        self.assertEqual(result.status, LoadStatus.CORRUPT)
        moved = self.storage.quarantine_corrupt()
        self.assertEqual(len(moved), 2)
        self.assertTrue(all(p.exists() for p in moved))
        self.assertEqual(self.storage.load_active().status, LoadStatus.NONE)

    def test_restore_shortly_before_last_stroke(self):
        state = self.new_state(BK50, [2] * 49)
        self.storage.save_active(state)
        restored = self.storage.load_active().state
        game = Game(restored)
        self.assertEqual(game.current_stroke_number, 50)
        self.assertFalse(game.is_complete)
        game.record(3)
        self.assertTrue(game.is_complete)
        self.assertEqual(game.total, 101)


class ValidationTests(StorageTestCase):
    def _roundtrip_dict(self, **changes):
        data = self.new_state(strokes=[1, 2]).to_dict()
        data.update(changes)
        return GameState.from_dict(data)

    def test_invalid_values_in_file_are_rejected(self):
        for changes in ({"strokes": [1, 8]}, {"strokes": [1, "2"]}, {"strokes": [True]},
                        {"strokes": [1] * 51}, {"status": "unbekannt"},
                        {"started_at": "gestern"}, {"status": "finished"}):
            with self.subTest(changes=changes):
                with self.assertRaises(ValueError):
                    self._roundtrip_dict(**changes)


class ArchiveTests(StorageTestCase):
    def test_archive_removes_active_files(self):
        state = self.new_state(strokes=[1])
        self.storage.save_active(state)
        self.storage.save_active(state)
        target = self.storage.archive_active(state, "beendet")
        self.assertTrue(target.exists())
        self.assertIn("beendet", target.name)
        self.assertFalse(self.storage.has_active_files())
        self.assertEqual(decode_state(target.read_bytes()).strokes, [1])

    def test_new_game_after_archive_starts_clean(self):
        old = self.new_state(strokes=[5, 5])
        self.storage.save_active(old)
        self.storage.archive_active(old, "verworfen")
        new = self.new_state()
        self.storage.save_active(new)
        loaded = self.storage.load_active().state
        self.assertEqual(loaded.strokes, [])
        self.assertNotEqual(loaded.game_id, old.game_id)

    def test_old_save_with_player_name_still_loads(self):
        """Spielstände der Vorversion (mit Spielername) lassen sich weiter fortsetzen."""
        data = self.new_state(strokes=[4, 1]).to_dict()
        data["player_name"] = "Max Mustermann"
        self.assertEqual(GameState.from_dict(data).strokes, [4, 1])


if __name__ == "__main__":
    unittest.main()


class ArchiveBrowseTests(StorageTestCase):
    def test_list_archive_sorted_and_skips_corrupt(self):
        old = GameState.new(BK50, started_at="2026-09-01T10:00:00")
        new = GameState.new(BK50, started_at="2026-09-20T10:00:00")
        self.storage.archive_active(old, "verworfen")
        self.storage.archive_active(new, "verworfen")
        (self.storage.archive_dir / "kaputt.json").write_text("{", encoding="utf-8")
        entries = self.storage.list_archive()
        self.assertEqual([e.state.game_id for e in entries], [new.game_id, old.game_id])
        self.assertEqual(entries[0].status_label, "unterbrochen")
        self.assertTrue((self.storage.archive_dir / "kaputt.json").exists())   # nie gelöscht

    def test_restore_aborted_game(self):
        state = self.new_state(strokes=[2, 3])
        Game(state).abort()
        self.storage.archive_active(state, "abgebrochen")
        entry = self.storage.list_archive()[0]
        self.assertTrue(entry.can_continue)
        restored = self.storage.restore_from_archive(entry)
        self.assertEqual(restored.status, GameStatus.RUNNING)
        self.assertIsNone(restored.finished_at)
        self.assertEqual(self.storage.load_active().state.strokes, [2, 3])
        self.assertEqual(self.storage.list_archive(), [])

    def test_finished_game_cannot_be_continued(self):
        state = self.new_state(strokes=[1] * 50)
        Game(state).finish()
        self.storage.archive_active(state, "beendet")
        entry = self.storage.list_archive()[0]
        self.assertFalse(entry.can_continue)
        with self.assertRaises(StorageError):
            self.storage.restore_from_archive(entry)

    def test_restore_refused_while_active_game_exists(self):
        state = self.new_state(strokes=[2])
        Game(state).abort()
        self.storage.archive_active(state, "abgebrochen")
        self.storage.save_active(self.new_state())
        with self.assertRaises(StorageError):
            self.storage.restore_from_archive(self.storage.list_archive()[0])
