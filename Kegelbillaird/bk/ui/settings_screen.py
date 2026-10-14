"""
Einstellungsmenü (Hauptmenü → „Einstellungen“).

Aufbau: Übersicht der Bereiche → Seite mit Einträgen (Bezeichnung links,
Wert rechts). Jede Änderung wird sofort geprüft, in ``einstellungen.json``
gespeichert und übernommen (Signal ``settings_changed``).

Bedienung (Tasten aus der Tastenbelegung, Standard):
    [8] / [2]   Eintrag wählen
    [4] / [6]   Wert ändern (An/Aus, Zahlen, Auswahl)
    [Enter]     Bereich öffnen, Text/Zahl eingeben, Taste aufnehmen, Ton probehören
    [*] / [Esc] zurück
Maus: Eintrag anklicken, Doppelklick = [Enter], Mausrad blättert.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QKeyEvent, QPaintEvent
from PySide6.QtWidgets import QFileDialog, QInputDialog, QWidget

from ..autostart import Autostart, AutostartError
from ..keys import ACTIONS, DEFAULT_NAMES, KeyBindings
from ..media import list_images, list_logos, list_sounds
from ..settings import FONT_SCALES, AppSettings
from ..user_settings import UserSettingsStore
from . import keymap, theme
from .keymap import MenuKey, map_menu_key
from .widgets import Plate, _Painted

log = logging.getLogger(__name__)

CONTENT_W, CONTENT_H = 1024, 702
CAPTURE_SECONDS = 6

WINDOW_SIZES = ((1024, 768), (1280, 800), (1280, 1024), (1366, 768), (1600, 900), (1920, 1080))

ACTION_TITLES = {
    "plus": "Plus wählen", "minus": "Minus wählen / Abbruch bestätigen", "undo": "Korrektur (Rücknahme)",
    "abort": "Partie abbrechen", "up": "Menü: hoch", "down": "Menü: runter", "left": "Menü: links",
    "right": "Menü: rechts", "enter": "Bestätigen", "back": "Zurück",
}
COLOR_PARTS = ("Rot", "Grün", "Blau")


@dataclass
class Item:
    label: str
    value: Callable[[], str] = lambda: ""
    change: Callable[[int], None] | None = None      # [4]/[6]: -1 / +1
    activate: Callable[[], None] | None = None       # [Enter]
    hint: str = ""
    swatch: Callable[[], QColor] | None = None


def _on_off(value: bool) -> str:
    return "An" if value else "Aus"


def _seconds(value: float) -> str:
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text.replace(".", ",") + " s"


def _days(value: int) -> str:
    return "nie löschen" if value == 0 else f"{value} Tage"


def _cycle(options: list, current, delta: int):
    if not options:
        return current
    index = options.index(current) if current in options else -1
    return options[(index + delta) % len(options)]


def _step(value: float, delta: int, step: float, low: float, high: float) -> float:
    return round(max(low, min(high, value + delta * step)), 4)


# ============================================================== Liste
class SettingsList(_Painted):
    activated = Signal()
    selection_changed = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._items: list[Item] = []
        self._selected = 0
        self._top = 0
        self._row_rects: list[tuple[int, QRectF]] = []
        self.capturing = False

    def set_items(self, items: list[Item], selected: int = 0) -> None:
        self._items = items
        self._selected = max(0, min(selected, len(items) - 1))
        self._top = 0
        self.update()

    @property
    def selected(self) -> int:
        return self._selected

    def current(self) -> Item | None:
        return self._items[self._selected] if self._items else None

    def step(self, delta: int) -> None:
        if self._items:
            self._selected = (self._selected + delta) % len(self._items)
            self.selection_changed.emit(self._selected)
            self.update()

    # ------------------------------------------------------------- Maus
    def _row_at(self, pos) -> int | None:
        return next((i for i, rect in self._row_rects if rect.contains(pos)), None)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        index = self._row_at(event.position())
        if index is not None:
            self._selected = index
            self.selection_changed.emit(index)
            self.update()

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if self._row_at(event.position()) is not None:
            self.activated.emit()

    def wheelEvent(self, event) -> None:  # noqa: N802
        self.step(-1 if event.angleDelta().y() > 0 else 1)

    # ---------------------------------------------------------- Zeichnen
    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802
        p = self._painter()
        theme.draw_bezel(p, QRectF(self.rect()))
        inner = theme.bezel_geometry(QRectF(self.rect()))[2]
        area = inner.adjusted(inner.width() * 0.025, inner.height() * 0.03,
                              -inner.width() * 0.025, -inner.height() * 0.03)
        row_h = max(22.0, min(50.0, self.height() / 13))
        hint_h = row_h * 1.4
        visible = max(1, int((area.height() - hint_h) // row_h))
        if self._selected < self._top:
            self._top = self._selected
        elif self._selected >= self._top + visible:
            self._top = self._selected - visible + 1
        self._top = max(0, min(self._top, max(0, len(self._items) - visible)))
        font_px = theme.fitted_font("Sperrzeit nach Wertung", area.width() * 0.3, row_h * 0.5).pixelSize()
        self._row_rects = []
        y = area.top()
        for index in range(self._top, min(len(self._items), self._top + visible)):
            item = self._items[index]
            rect = QRectF(area.left(), y, area.width(), row_h * 0.9)
            self._row_rects.append((index, rect))
            selected = index == self._selected
            if selected:
                theme.draw_menu_button(p, rect.adjusted(0, 0, -3, -3), "", True)
            elif index % 2:
                p.fillRect(rect, QColor("#f4f4f0"))
            pad = rect.width() * 0.02
            p.setFont(theme.base_font(font_px, bold=selected))
            p.setPen(theme.TEXT if selected else QColor("#333333"))
            label_rect = QRectF(rect.left() + pad, rect.top(), rect.width() * 0.52, rect.height() - 3)
            p.drawText(label_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, item.label)
            value = item.value()
            if selected and self.capturing:
                value = "… jetzt die gewünschte Taste drücken …"
            elif selected and item.change is not None:
                value = f"◀  {value}  ▶"
            right = rect.right() - pad
            if item.swatch is not None:
                size = rect.height() * 0.6
                box = QRectF(right - size * 1.6, rect.top() + (rect.height() - size) / 2 - 1, size * 1.6, size)
                p.setPen(theme.OUTLINE)
                p.setBrush(item.swatch())
                p.drawRoundedRect(box, 3, 3)
                right = box.left() - pad
            value_rect = QRectF(label_rect.right(), rect.top(), right - label_rect.right(), rect.height() - 3)
            p.setFont(theme.fitted_font(value, value_rect.width(), font_px, bold=selected))
            p.setPen(theme.CURRENT if selected else QColor("#333333"))
            p.drawText(value_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignRight, value)
            y += row_h
        if len(self._items) > visible:
            info = f"{self._top + 1}–{min(len(self._items), self._top + visible)} von {len(self._items)}"
            p.setPen(theme.TEXT_MUTED)
            p.setFont(theme.base_font(font_px * 0.75))
            p.drawText(QRectF(area.left(), area.top() + visible * row_h, area.width(), row_h * 0.5),
                       Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, info)
        item = self.current()
        if item is not None and item.hint:
            hint_rect = QRectF(area.left(), area.bottom() - hint_h, area.width(), hint_h)
            p.setPen(theme.GRID_LINE)
            p.drawLine(hint_rect.topLeft(), hint_rect.topRight())
            p.setPen(theme.TEXT_MUTED)
            p.setFont(theme.base_font(font_px * 0.8))
            hint = (item.hint.replace("[4]/[6]", f"[{keymap.label('left')}]/[{keymap.label('right')}]")
                    .replace("[Enter]", f"[{keymap.label('enter')}]"))
            p.drawText(hint_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
                       | Qt.TextFlag.TextWordWrap, hint)
        p.end()


# ============================================================ Bildschirm
class SettingsScreen(QWidget):
    back_requested = Signal()
    settings_changed = Signal(object)    # AppSettings
    notice = Signal(str, bool)           # Kurzmeldung (Text, Warnung?)
    footer_changed = Signal()

    def __init__(self, store: UserSettingsStore, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._store = store
        self._plate = Plate("Einstellungen", self)
        self._list = SettingsList(self)
        self._list.activated.connect(self._activate)
        self._list.selection_changed.connect(lambda _i: self.footer_changed.emit())
        self._stack: list[tuple[str, Callable[[], list[Item]], int]] = []
        self._capture_action: str | None = None
        self._capture_timer = QTimer(self)
        self._capture_timer.setSingleShot(True)
        self._capture_timer.timeout.connect(self._cancel_capture)
        self._reset_armed = False
        self._reset_timer = QTimer(self)
        self._reset_timer.setSingleShot(True)
        self._reset_timer.timeout.connect(self._disarm_reset)
        # austauschbar (Tests): Ton probehören, Eingabefenster, Druckerliste
        self.preview_sound: Callable[[str], bool] = lambda _name: False
        self.ask_text: Callable[[str, str, str], str | None] = self._ask_text
        self.ask_int: Callable[[str, str, int, int, int], int | None] = self._ask_int
        self.ask_folder: Callable[[str, str], str | None] = self._ask_folder
        self.printer_names: Callable[[], list[str]] = _printer_names
        self.autostart = Autostart()
        self.open_page()

    @property
    def settings(self) -> AppSettings:
        return self._store.current

    # ------------------------------------------------------------ Anzeige
    def title(self) -> str:
        return "Einstellungen"

    def footer_segments(self) -> list[str]:
        if self._capture_action:
            return ["Gewünschte Taste drücken", f"Abbruch: {CAPTURE_SECONDS} s warten"]
        item = self._list.current()
        segments = [f"Wählen mit  [{keymap.label('down')}]  &  [{keymap.label('up')}]"]
        if item is not None and item.change is not None:
            segments.append(f"Ändern mit  [{keymap.label('left')}]  /  [{keymap.label('right')}]")
        if item is not None and item.activate is not None:
            segments.append(f"[{keymap.label('enter')}]  öffnen / eingeben")
        segments.append(f"Zurück mit  [{keymap.label_all('back')}]")
        return segments

    def open_page(self, title: str | None = None, builder: Callable[[], list[Item]] | None = None) -> None:
        """Seite öffnen (ohne Angaben: Übersicht)."""
        if builder is None:
            self._stack = [("Einstellungen", self._overview, 0)]
        else:
            if self._stack:   # Auswahl der aktuellen Seite merken
                t, b, _ = self._stack[-1]
                self._stack[-1] = (t, b, self._list.selected)
            self._stack.append((title or "", builder, 0))
        self._rebuild(0)

    def _rebuild(self, selected: int | None = None) -> None:
        title, builder, remembered = self._stack[-1]
        self._plate.set_text(title)
        self._list.set_items(builder(), remembered if selected is None else selected)
        self.footer_changed.emit()

    def _refresh(self) -> None:
        """Werte neu anzeigen, Auswahl behalten."""
        title, builder, _ = self._stack[-1]
        selected = self._list.selected
        self._list.set_items(builder(), selected)
        self._list.update()
        self.footer_changed.emit()

    def go_back(self) -> None:
        self._cancel_capture()
        if len(self._stack) > 1:
            self._stack.pop()
            self._rebuild(None)
        else:
            self.back_requested.emit()

    # ------------------------------------------------------------ Ändern
    def set_value(self, name: str, value) -> bool:
        try:
            new = self._store.set(name, value)
        except ValueError as exc:
            self.notice.emit(str(exc), True)
            return False
        except OSError as exc:
            log.error("Einstellungen konnten nicht gespeichert werden: %s", exc)
            self.notice.emit(f"Speichern fehlgeschlagen: {exc}", True)
            return False
        log.info("Einstellung geändert: %s = %r", name, value)
        self.settings_changed.emit(new)
        self._refresh()
        return True

    def _bool_item(self, label: str, name: str, hint: str = "") -> Item:
        def toggle(_delta: int = 1) -> None:
            self.set_value(name, not getattr(self.settings, name))
        return Item(label, lambda: _on_off(getattr(self.settings, name)), toggle, lambda: toggle(), hint)

    def _number_item(self, label: str, name: str, step: float, low: float, high: float,
                     fmt: Callable = _seconds, hint: str = "", integer: bool = False) -> Item:
        def change(delta: int) -> None:
            value = _step(getattr(self.settings, name), delta, step, low, high)
            self.set_value(name, int(value) if integer else float(value))
        return Item(label, lambda: fmt(getattr(self.settings, name)), change, None, hint)

    # ============================================================ Seiten
    def _overview(self) -> list[Item]:
        pages = [
            ("Anzeige", self._page_display, "Vollbild, Fenstergröße, Schriftgröße, Vereinsname und -logo, Autostart"),
            ("Design", self._page_design, "Farbschema: Klassisch oder eigene Primär- und Sekundärfarbe"),
            ("Eingabe", self._page_input, "Sperrzeiten, Nummernblock, NumLock"),
            ("Tasten", self._page_keys, "Welche Taste was macht – die Legende passt sich an"),
            ("Töne", self._page_sounds, "Ton zur Halbzeit, am Ende und bei +6 / +7, Lautstärke"),
            ("Bilder", self._page_images, "Bilder/GIFs bei +6/+7 und −6/−7"),
            ("Drucken & PDF", self._page_print, "Drucker, PDF-Speicherort, Auswertung nach der Partie"),
            ("Archiv & Aufräumen", self._page_archive, "Wiedergabe-Tempo, Aufbewahrungsdauer"),
        ]
        items = [Item(title, lambda: "▶", None, (lambda t=title, b=builder: self.open_page(t, b)), hint)
                 for title, builder, hint in pages]
        items.append(Item("Alle Einstellungen zurücksetzen",
                          lambda: "zum Bestätigen nochmal drücken" if self._reset_armed else "",
                          None, self._reset_all,
                          "Setzt alles auf die Werte aus config.py bzw. die Standardwerte zurück."))
        items.append(Item("Zurück zum Hauptmenü", lambda: "", None, self.back_requested.emit))
        return items

    def _page_display(self) -> list[Item]:
        s = self.settings

        def change_size(delta: int) -> None:
            options = list(WINDOW_SIZES)
            if tuple(s.window_size) not in options:
                options.append(tuple(s.window_size))
                options.sort()
            self.set_value("window_size", _cycle(options, tuple(self.settings.window_size), delta))

        def change_logo(delta: int) -> None:
            options = [""] + list_logos(self.settings.club_logo_dir)
            if self.settings.club_logo and self.settings.club_logo not in options:
                options.append(self.settings.club_logo)
            self.set_value("club_logo", _cycle(options, self.settings.club_logo, delta))

        def logo_value() -> str:
            name = self.settings.club_logo
            if not name:
                return "(kein Logo)" if list_logos(self.settings.club_logo_dir) else "(kein Bild im Ordner)"
            return name if (self.settings.club_logo_dir / name).is_file() else f"{name} (fehlt)"

        def autostart_value() -> str:
            return _on_off(self.autostart.is_enabled()) if self.autostart.available else "nur unter Windows"

        def toggle_autostart(_delta: int = 1) -> None:
            try:
                self.autostart.set_enabled(not self.autostart.is_enabled())
            except AutostartError as exc:
                self.notice.emit(str(exc), True)
                return
            on = self.autostart.is_enabled()
            self.notice.emit("Startet ab jetzt automatisch nach der Windows-Anmeldung." if on
                             else "Autostart ausgeschaltet.", False)
            self._refresh()

        def edit_club() -> None:
            text = self.ask_text("Vereinsname", "Vereinsname (Titelleiste und PDF):", self.settings.club_name)
            if text is not None and text.strip():
                self.set_value("club_name", text.strip())

        return [
            self._bool_item("Vollbild", "fullscreen", "An = Programm füllt den ganzen Bildschirm. "
                            "Aus = Fenster in der unten gewählten Größe."),
            Item("Fenstergröße", lambda: "{} × {}".format(*self.settings.window_size), change_size, None,
                 "Gilt, wenn Vollbild aus ist."),
            Item("Schriftgröße", lambda: f"{self.settings.font_scale} %",
                 lambda d: self.set_value("font_scale", _cycle(list(FONT_SCALES), self.settings.font_scale, d)),
                 None, "Große Zahlen füllen ihr Feld immer aus; Texte werden nie abgeschnitten."),
            Item("Vereinsname", lambda: self.settings.club_name, None, edit_club,
                 "Mit [Enter] ändern (normale Tastatur nötig)."),
            Item("Vereinslogo", logo_value, change_logo, None,
                 f"Bild in den Ordner „{self.settings.club_logo_dir.name}“ ziehen, dann hier auswählen "
                 "(PNG, JPG, GIF, BMP, WEBP, SVG, ICO …). Erscheint im Hauptmenü unter dem BK-Bild."),
            self._bool_item("Feld „Letzte Stöße“ anzeigen", "show_history",
                            "Aus = „Aktueller Stoß“ wird dafür breiter."),
            self._number_item("Anzahl „Letzte Stöße“", "history_length", 1, 1, 10, str, integer=True),
            self._bool_item("Feld „Eingabe“ anzeigen", "show_input_status",
                            "BEREIT / MINUS / GESPERRT. Aus = „Minus“ wird dafür breiter."),
            Item("Beim Windows-Start öffnen", autostart_value, toggle_autostart, lambda: toggle_autostart(),
                 "An = Programm startet automatisch nach der Windows-Anmeldung (Autostart)."),
        ]

    def _page_design(self) -> list[Item]:
        def mode_value() -> str:
            return "Klassisch" if self.settings.theme_mode == "klassisch" else "Eigene Farben"

        def toggle_mode(_delta: int = 1) -> None:
            self.set_value("theme_mode", "eigen" if self.settings.theme_mode == "klassisch" else "klassisch")

        items = [Item("Farbschema", mode_value, toggle_mode, lambda: toggle_mode(),
                      "Klassisch = Aussehen wie das Altprogramm. Eigene Farben = Primär- und Sekundärfarbe unten.")]
        for name, title, hint in (
                ("primary_color", "Primärfarbe", "Titel- und Fußleiste, Hintergrund, gewählter Knopf."),
                ("secondary_color", "Sekundärfarbe", "Rahmen der Anzeigen, Beschriftungen, Knöpfe, Linien.")):
            for part, part_name in enumerate(COLOR_PARTS):
                items.append(self._color_item(name, title, part, part_name, hint))
        return items

    def _color_item(self, name: str, title: str, part: int, part_name: str, hint: str) -> Item:
        def set_part(value: int) -> None:
            color = list(getattr(self.settings, name))
            color[part] = max(0, min(255, value))
            if self.set_value(name, tuple(color)) and self.settings.theme_mode != "eigen":
                self.set_value("theme_mode", "eigen")   # Farbe ändern = eigenes Farbschema

        def change(delta: int) -> None:
            set_part(getattr(self.settings, name)[part] + 5 * delta)

        def enter() -> None:
            value = self.ask_int(f"{title} – {part_name}", f"{part_name} (0 bis 255):",
                                 getattr(self.settings, name)[part], 0, 255)
            if value is not None:
                set_part(value)

        return Item(f"{title} – {part_name} (R G B)" if part == 0 else f"{title} – {part_name}",
                    lambda: str(getattr(self.settings, name)[part]), change, enter,
                    f"{hint} [4]/[6] = ±5, [Enter] = Zahl eintippen.",
                    swatch=lambda: QColor(*getattr(self.settings, name)))

    def _page_input(self) -> list[Item]:
        return [
            self._number_item("Sperrzeit nach Wertung", "input_lock_seconds", 0.5, 0, 10,
                              hint="Schutz vor Doppeleingaben. Gilt ab der nächsten Partie."),
            self._number_item("Sperre nach Korrektur", "undo_lock_seconds", 0.5, 0, 5),
            self._number_item("Wartezeit der Abbruch-Frage", "abort_confirm_seconds", 1, 1, 30),
            self._bool_item("Nur Nummernblock", "numpad_only",
                            "An = in der Partie zählen nur Tasten des Nummernblocks."),
            self._bool_item("NumLock automatisch einschalten", "auto_enable_numlock"),
        ]

    def _page_keys(self) -> list[Item]:
        items = []
        for action in ACTIONS:
            def start(a=action) -> None:
                self._start_capture(a)

            def reset(_delta: int, a=action) -> None:
                names = dict(self.settings.key_bindings.names)
                names[a] = DEFAULT_NAMES[a]
                if self.set_value("key_bindings", KeyBindings(names)):
                    self.notice.emit(f"„{ACTION_TITLES[a]}“ auf Standard zurückgesetzt.", False)

            items.append(Item(ACTION_TITLES[action],
                              lambda a=action: "[" + self.settings.key_bindings.label_all(a) + "]",
                              reset, start,
                              "[Enter] und dann die neue Taste drücken. [4]/[6] = Standardbelegung. "
                              "Die Ziffern 0–7 der Wertung sind fest."))
        return items

    def _page_sounds(self) -> list[Item]:
        def sound_item(label: str, name: str) -> Item:
            def change(delta: int) -> None:
                options = [""] + list_sounds(self.settings.sounds_dir)
                self.set_value(name, _cycle(options, getattr(self.settings, name), delta))

            def preview() -> None:
                current = getattr(self.settings, name)
                if not current:
                    self.notice.emit("Kein Ton ausgewählt.", True)
                elif not self.preview_sound(current):
                    self.notice.emit("Ton kann nicht abgespielt werden (Töne aus, Datei fehlt oder keine Tonausgabe).",
                                     True)
            return Item(label, lambda: getattr(self.settings, name) or "(kein Ton)", change, preview,
                        f"Alle .wav/.mp3 im Ordner „{self.settings.sounds_dir.name}“ werden erkannt. "
                        "[Enter] = probehören.")

        return [
            self._bool_item("Töne", "sound_enabled"),
            self._number_item("Lautstärke", "sound_volume", 10, 0, 100, lambda v: f"{v} %", integer=True),
            sound_item("Ton zur Halbzeit", "halftime_sound"),
            sound_item("Ton am Partie-Ende", "end_sound"),
            sound_item("Ton bei +6 / +7", "celebration_sound"),
        ]

    def _page_images(self) -> list[Item]:
        def folder_item(label: str, prefix: str, folder: Callable[[], Path]) -> Item:
            def count() -> str:
                names = list_images(folder())
                active = [n for n in names if f"{prefix}/{n}" not in self.settings.disabled_images]
                if not names:
                    return "keine Bilder" + (" (nimmt Plus-Bilder)" if prefix == "minus" else "")
                return f"{len(active)} von {len(names)} aktiv"
            return Item(label, count, None, lambda: self.open_page(label, lambda: self._page_image_files(prefix, folder)),
                        f"Alle Bilder/GIFs im Ordner „bilder/{prefix}“ werden automatisch verwendet. "
                        "[Enter] = einzelne ausschalten.")

        return [
            self._bool_item("Bilder anzeigen", "celebration_enabled"),
            self._number_item("Anzeigedauer", "celebration_seconds", 0.5, 0.5, 30),
            folder_item("Bilder bei +6 / +7", "plus", lambda: self.settings.images_plus_dir),
            folder_item("Bilder bei −6 / −7", "minus", lambda: self.settings.images_minus_dir),
        ]

    def _page_image_files(self, prefix: str, folder: Callable[[], Path]) -> list[Item]:
        names = list_images(folder())
        if not names:
            return [Item("Keine Bilder gefunden", lambda: "", None, None,
                         f"Bilder in den Ordner „{folder()}“ legen – sie erscheinen dann automatisch.")]
        items = []
        for name in names:
            key = f"{prefix}/{name}"

            def toggle(_delta: int = 1, k=key) -> None:
                disabled = list(self.settings.disabled_images)
                if k in disabled:
                    disabled.remove(k)
                else:
                    disabled.append(k)
                self.set_value("disabled_images", tuple(sorted(disabled)))
            items.append(Item(name, lambda k=key: "Aus" if k in self.settings.disabled_images else "An",
                              toggle, lambda t=toggle: t(), "Neue Dateien im Ordner sind automatisch aktiv."))
        return items

    def _page_print(self) -> list[Item]:
        def printer_value() -> str:
            return self.settings.printer_name or "Windows-Standarddrucker"

        def change_printer(delta: int) -> None:
            options = [""] + self.printer_names()
            self.set_value("printer_name", _cycle(options, self.settings.printer_name, delta))

        def folder_value() -> str:
            return self.settings.pdf_save_dir or "Dokumente (Standard)"

        def choose_folder() -> None:
            chosen = self.ask_folder("PDF-Speicherort wählen", self.settings.pdf_save_dir or _documents_dir())
            if chosen:
                self.set_value("pdf_save_dir", chosen)

        return [
            Item("Drucker", printer_value, change_printer, None,
                 "Gedruckt wird ohne Rückfrage. Fehlt der gewählte Drucker, wird der Standarddrucker genommen."),
            Item("PDF-Speicherort", folder_value, lambda _d: self.set_value("pdf_save_dir", ""), choose_folder,
                 "„Als PDF speichern“ legt die Datei ohne Nachfrage hier ab. [Enter] = Ordner wählen, "
                 "[4]/[6] = zurück auf Dokumente."),
            self._bool_item("Auswertung nach der Partie anzeigen", "show_report_after_game"),
            self._bool_item("PDF nach der Partie öffnen", "open_pdf_after_game"),
        ]

    def _page_archive(self) -> list[Item]:
        return [
            self._number_item("Wiedergabe-Tempo (pro Stoß)", "replay_seconds_per_stroke", 0.1, 0.1, 5),
            self._number_item("Archiv aufbewahren", "archive_retention_days", 5, 0, 3650, _days, integer=True),
            self._number_item("Protokolle aufbewahren", "log_retention_days", 5, 0, 3650, _days, integer=True),
            self._number_item("PDFs/Ergebnisse aufbewahren", "results_retention_days", 30, 0, 3650, _days,
                              integer=True, hint="Empfohlen: nie löschen."),
        ]

    # ========================================================= Zurücksetzen
    def _reset_all(self) -> None:
        if not self._reset_armed:
            self._reset_armed = True
            self._reset_timer.start(4000)
            self._refresh()
            return
        self._disarm_reset()
        try:
            new = self._store.reset()
        except OSError as exc:
            self.notice.emit(f"Speichern fehlgeschlagen: {exc}", True)
            return
        log.info("Alle Einstellungen zurückgesetzt")
        self.settings_changed.emit(new)
        self.notice.emit("Alle Einstellungen wurden zurückgesetzt.", False)
        self._refresh()

    def _disarm_reset(self) -> None:
        self._reset_timer.stop()
        if self._reset_armed:
            self._reset_armed = False
            self._refresh()

    # ========================================================= Tastenaufnahme
    def _start_capture(self, action: str) -> None:
        self._capture_action = action
        self._list.capturing = True
        self._capture_timer.start(CAPTURE_SECONDS * 1000)
        self._list.update()
        self.footer_changed.emit()

    def _cancel_capture(self) -> None:
        self._capture_timer.stop()
        if self._capture_action is not None:
            self._capture_action = None
            self._list.capturing = False
            self._list.update()
            self.footer_changed.emit()

    def _capture(self, event: QKeyEvent) -> None:
        action = self._capture_action
        self._cancel_capture()
        name = keymap.event_name(event)
        if name is None or action is None:
            self.notice.emit("Diese Taste kann nicht belegt werden.", True)
            return
        names = dict(self.settings.key_bindings.names)
        names[action] = (name,)
        if self.set_value("key_bindings", KeyBindings(names)):
            self.notice.emit(f"„{ACTION_TITLES[action]}“ = [{self.settings.key_bindings.label(action)}]", False)

    # ============================================================ Tastatur
    def handle_key(self, event: QKeyEvent) -> bool:
        if self._capture_action is not None:
            if not event.isAutoRepeat():
                self._capture(event)
            return True
        key = map_menu_key(event)
        if key is MenuKey.UP:
            self._list.step(-1)
        elif key is MenuKey.DOWN:
            self._list.step(1)
        elif key in (MenuKey.LEFT, MenuKey.RIGHT):
            item = self._list.current()
            if item is not None and item.change is not None:
                item.change(-1 if key is MenuKey.LEFT else 1)
        elif key is MenuKey.ENTER and not event.isAutoRepeat():
            self._activate()
        elif key is MenuKey.BACK and not event.isAutoRepeat():
            self.go_back()
        else:
            return False
        item = self._list.current()
        if not (key is MenuKey.ENTER and item is not None and item.activate == self._reset_all):
            self._disarm_reset()
        return True

    def _activate(self) -> None:
        item = self._list.current()
        if item is not None and item.activate is not None:
            item.activate()

    # ============================================================ Eingaben
    def _ask_text(self, title: str, label: str, current: str) -> str | None:
        text, ok = QInputDialog.getText(self, title, label, text=current)
        return text if ok else None

    def _ask_int(self, title: str, label: str, current: int, low: int, high: int) -> int | None:
        value, ok = QInputDialog.getInt(self, title, label, current, low, high, 1)
        return value if ok else None

    def _ask_folder(self, title: str, start: str) -> str | None:
        return QFileDialog.getExistingDirectory(self, title, start) or None

    # ============================================================== Layout
    def resizeEvent(self, event) -> None:  # noqa: N802
        unit = max(0.4, min(self.width() / CONTENT_W, self.height() / CONTENT_H))
        ox = (self.width() - CONTENT_W * unit) / 2
        oy = (self.height() - CONTENT_H * unit) / 2

        def place(widget: QWidget, x: float, y: float, w: float, h: float) -> None:
            widget.setGeometry(QRect(round(ox + x * unit), round(oy + y * unit), round(w * unit), round(h * unit)))

        place(self._plate, 212, 26, 600, 47)
        place(self._list, 40, 92, 944, 594)
        super().resizeEvent(event)


def _printer_names() -> list[str]:
    try:
        from PySide6.QtPrintSupport import QPrinterInfo
        return sorted(QPrinterInfo.availablePrinterNames(), key=str.lower)
    except Exception as exc:
        log.warning("Druckerliste nicht verfügbar: %s", exc)
        return []


def _documents_dir() -> str:
    from PySide6.QtCore import QStandardPaths
    return QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation) or str(Path.home())
