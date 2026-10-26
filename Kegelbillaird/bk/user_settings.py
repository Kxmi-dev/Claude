"""
Einstellungen aus dem Einstellungsmenü (Datei ``einstellungen.json``).

Reihenfolge: Werte aus ``einstellungen.json`` > ``config.py`` > eingebaute
Standardwerte. Die Datei enthält nur die im Menü geänderten Werte; alles
andere kommt weiterhin aus ``config.py``. Gespeichert wird atomar
(tmp → fsync → replace) mit Sicherungskopie ``.bak`` – wie die Spielstände.
Eine beschädigte Datei hält den Programmstart nie auf: dann wird die
Sicherung bzw. der Standard verwendet und ein Hinweis ausgegeben.

Qt-frei, damit testbar.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Callable

from .keys import ACTIONS, KeyBindings, normalize
from .settings import AppSettings

log = logging.getLogger(__name__)

FORMAT_VERSION = 1


def _bool(value: Any) -> bool:
    if not isinstance(value, bool):
        raise ValueError("kein Ja/Nein-Wert")
    return value


def _int(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or int(value) != value:
        raise ValueError("keine ganze Zahl")
    return int(value)


def _float(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("keine Zahl")
    return float(value)


def _str(value: Any) -> str:
    if not isinstance(value, str):
        raise ValueError("kein Text")
    return value


def _ints(count: int) -> Callable[[Any], tuple[int, ...]]:
    def convert(value: Any) -> tuple[int, ...]:
        if not isinstance(value, (list, tuple)) or len(value) != count:
            raise ValueError(f"erwartet {count} Zahlen")
        return tuple(_int(v) for v in value)
    return convert


def _strs(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise ValueError("keine Liste")
    return tuple(_str(v) for v in value)


def _keys(value: Any) -> KeyBindings:
    if not isinstance(value, dict):
        raise ValueError("keine Tastenbelegung")
    names = {}
    for action, (default, _desc) in ACTIONS.items():
        raw = value.get(action, list(default))
        if isinstance(raw, str):
            raw = [raw]
        names[action] = tuple(dict.fromkeys(normalize(k) for k in _strs(raw)))
    bindings = KeyBindings(names)
    bindings.validate()
    return bindings


def _encode_keys(bindings: KeyBindings) -> dict[str, list[str]]:
    return {action: list(bindings.keys(action)) for action in ACTIONS}


# Feld in AppSettings -> (aus JSON lesen, nach JSON schreiben)
FIELDS: dict[str, tuple[Callable[[Any], Any], Callable[[Any], Any]]] = {
    "fullscreen": (_bool, bool),
    "window_size": (_ints(2), list),
    "club_name": (_str, str),
    "club_logo": (_str, str),
    "font_scale": (_int, int),
    "history_length": (_int, int),
    "show_history": (_bool, bool),
    "show_input_status": (_bool, bool),
    "grid_running_total": (_bool, bool),
    "stay_on_top": (_bool, bool),
    "hide_cursor_seconds": (_float, float),
    "input_lock_seconds": (_float, float),
    "undo_lock_seconds": (_float, float),
    "abort_confirm_seconds": (_float, float),
    "result_lock_seconds": (_float, float),
    "enter_skips_lock": (_bool, bool),
    "numpad_only": (_bool, bool),
    "auto_enable_numlock": (_bool, bool),
    "key_bindings": (_keys, _encode_keys),
    "theme_mode": (_str, str),
    "primary_color": (_ints(3), list),
    "secondary_color": (_ints(3), list),
    "sound_enabled": (_bool, bool),
    "halftime_sound": (_str, str),
    "end_sound": (_str, str),
    "celebration_sound": (_str, str),
    "sound_volume": (_int, int),
    "celebration_enabled": (_bool, bool),
    "celebration_seconds": (_float, float),
    "disabled_images": (_strs, list),
    "printer_name": (_str, str),
    "pdf_save_dir": (_str, str),
    "show_report_after_game": (_bool, bool),
    "open_pdf_after_game": (_bool, bool),
    "replay_seconds_per_stroke": (_float, float),
    "archive_retention_days": (_int, int),
    "log_retention_days": (_int, int),
    "results_retention_days": (_int, int),
}


class UserSettingsStore:
    """Hält die Grundeinstellungen (config.py) und die im Menü geänderten Werte."""

    def __init__(self, base: AppSettings, path: Path | None = None) -> None:
        self._base = base
        self.path = Path(path or base.settings_file)
        self._values: dict[str, Any] = {}      # JSON-Form der geänderten Werte
        self.current = base
        self.warnings: list[str] = []

    # ------------------------------------------------------------- Laden
    def load(self) -> AppSettings:
        """Datei lesen und anwenden. Fehler werden protokolliert, nie geworfen."""
        self.warnings = []
        data = None
        for candidate in (self.path, self._backup):
            if not candidate.exists():
                continue
            try:
                data = json.loads(candidate.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("kein JSON-Objekt")
                if candidate != self.path:
                    self._warn("Einstellungen waren beschädigt – die Sicherungskopie wurde verwendet.")
                break
            except (OSError, ValueError) as exc:
                log.error("Einstellungsdatei %s nicht lesbar: %s", candidate, exc)
                data = None
        if data is None and self.path.exists():
            self._warn("Einstellungen konnten nicht gelesen werden – es gelten die Standardwerte.")
        values = (data or {}).get("values", {}) if isinstance(data, dict) else {}
        if not isinstance(values, dict):
            values = {}
        self._values = {}
        settings = self._base
        for name, raw in values.items():
            if name not in FIELDS:
                log.warning("Unbekannte Einstellung ignoriert: %s", name)
                continue
            try:
                candidate = dataclasses.replace(settings, **{name: FIELDS[name][0](raw)})
                candidate.validate()
            except (ValueError, TypeError) as exc:
                log.warning("Einstellung %s ungültig (%s) – Standard wird verwendet", name, exc)
                self._warn(f"Einstellung „{name}“ war ungültig und wurde zurückgesetzt.")
                continue
            settings = candidate
            self._values[name] = raw
        self.current = settings
        return settings

    def _warn(self, text: str) -> None:
        if text not in self.warnings:
            self.warnings.append(text)

    @property
    def _backup(self) -> Path:
        return self.path.with_name(self.path.name + ".bak")

    # ------------------------------------------------------------ Ändern
    def set(self, name: str, value: Any) -> AppSettings:
        """Einen Wert ändern, prüfen und sofort speichern. ValueError bei ungültigem Wert
        (dann bleibt alles unverändert)."""
        if name not in FIELDS:
            raise KeyError(name)
        settings = dataclasses.replace(self.current, **{name: value})
        settings.validate()
        encoded = FIELDS[name][1](value)
        if encoded == FIELDS[name][1](getattr(self._base, name)):
            self._values.pop(name, None)          # wieder Standard -> nicht speichern
        else:
            self._values[name] = encoded
        self.save()
        self.current = settings
        return settings

    def reset(self) -> AppSettings:
        """Alle im Menü geänderten Werte verwerfen."""
        self._values = {}
        self.save()
        self.current = self._base
        return self.current

    def is_changed(self, name: str) -> bool:
        return name in self._values

    # ----------------------------------------------------------- Speichern
    def save(self) -> None:
        """Atomar schreiben; die vorige Fassung bleibt als .bak erhalten. Wirft OSError."""
        data = json.dumps({"format": FORMAT_VERSION, "values": self._values}, ensure_ascii=False, indent=2)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if self.path.exists():
            try:
                shutil.copy2(self.path, self._backup)
            except OSError as exc:
                log.warning("Sicherungskopie der Einstellungen nicht möglich: %s", exc)
        os.replace(tmp, self.path)
