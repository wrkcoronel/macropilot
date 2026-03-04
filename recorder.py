from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any

from pynput import keyboard, mouse

from models import Macro, MacroStep
from utils import generate_id, now_iso


MODIFIER_KEYS = {
    keyboard.Key.shift: "shift",
    keyboard.Key.shift_l: "shift",
    keyboard.Key.shift_r: "shift",
    keyboard.Key.ctrl: "ctrl",
    keyboard.Key.ctrl_l: "ctrl",
    keyboard.Key.ctrl_r: "ctrl",
    keyboard.Key.alt: "alt",
    keyboard.Key.alt_l: "alt",
    keyboard.Key.alt_r: "alt",
    keyboard.Key.cmd: "win",
    keyboard.Key.cmd_l: "win",
    keyboard.Key.cmd_r: "win",
}

MODIFIER_PRIORITY = {"ctrl": 0, "shift": 1, "alt": 2, "win": 3}


@dataclass(slots=True)
class _RecordedEvent:
    ts: float
    payload: dict[str, Any]


class MacroRecorder:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._is_recording = False
        self._mouse_listener: mouse.Listener | None = None
        self._keyboard_listener: keyboard.Listener | None = None

        self._macro_name = "Nova Macro"
        self._created_at = ""

        self._events: list[_RecordedEvent] = []
        self._typing_buffer: list[str] = []
        self._typing_started_at: float | None = None
        self._pressed_modifiers: set[str] = set()

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    def start(self, macro_name: str) -> None:
        with self._lock:
            if self._is_recording:
                raise RuntimeError("Já existe uma gravação em andamento")

            self._is_recording = True
            self._macro_name = macro_name.strip() or "Nova Macro"
            self._created_at = now_iso()
            self._events.clear()
            self._typing_buffer.clear()
            self._typing_started_at = None
            self._pressed_modifiers.clear()

            self._mouse_listener = mouse.Listener(on_click=self._on_click, on_scroll=self._on_scroll)
            self._keyboard_listener = keyboard.Listener(
                on_press=self._on_key_press,
                on_release=self._on_key_release,
            )

            self._mouse_listener.start()
            self._keyboard_listener.start()

    def stop(self) -> Macro:
        with self._lock:
            if not self._is_recording:
                raise RuntimeError("Nenhuma gravação ativa")

            self._flush_typing_locked(time.perf_counter())
            self._is_recording = False

            if self._mouse_listener is not None:
                self._mouse_listener.stop()
                self._mouse_listener = None

            if self._keyboard_listener is not None:
                self._keyboard_listener.stop()
                self._keyboard_listener = None

            return self._build_macro_locked()

    def _on_click(self, x: int, y: int, button: mouse.Button, pressed: bool) -> None:
        if not pressed:
            return

        with self._lock:
            if not self._is_recording:
                return

            now = time.perf_counter()
            self._flush_typing_locked(now)
            self._events.append(
                _RecordedEvent(
                    ts=now,
                    payload={
                        "id": generate_id(),
                        "type": "click",
                        "x": int(x),
                        "y": int(y),
                        "button": str(button).split(".")[-1],
                    },
                )
            )

    def _on_scroll(self, x: int, y: int, dx: int, dy: int) -> None:
        with self._lock:
            if not self._is_recording:
                return

            now = time.perf_counter()
            self._flush_typing_locked(now)
            self._events.append(
                _RecordedEvent(
                    ts=now,
                    payload={
                        "id": generate_id(),
                        "type": "scroll",
                        "x": int(x),
                        "y": int(y),
                        "dx": int(dx),
                        "dy": int(dy),
                    },
                )
            )

    def _on_key_press(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        with self._lock:
            if not self._is_recording:
                return

            now = time.perf_counter()
            modifier_name = self._modifier_name(key)
            if modifier_name is not None:
                self._pressed_modifiers.add(modifier_name)
                return

            active_modifiers = self._sorted_modifiers()

            if isinstance(key, keyboard.KeyCode) and key.char is not None:
                key_char = self._decode_control_char(key.char)
                if any(item != "shift" for item in active_modifiers):
                    self._flush_typing_locked(now)
                    self._append_hotkey_event_locked(now, active_modifiers + [key_char.lower()])
                    return
                self._append_text_char_locked(key_char, now)
                return

            if key == keyboard.Key.space:
                if any(item != "shift" for item in active_modifiers):
                    self._flush_typing_locked(now)
                    self._append_hotkey_event_locked(now, active_modifiers + ["space"])
                    return
                self._append_text_char_locked(" ", now)
                return

            key_name = self._normalize_key_name(key)
            if key_name is None:
                return

            if active_modifiers:
                self._flush_typing_locked(now)
                self._append_hotkey_event_locked(now, active_modifiers + [key_name])
                return

            self._flush_typing_locked(now)
            self._events.append(
                _RecordedEvent(
                    ts=now,
                    payload={
                        "id": generate_id(),
                        "type": "key",
                        "key": key_name,
                    },
                )
            )

    def _on_key_release(self, key: keyboard.Key | keyboard.KeyCode) -> None:
        with self._lock:
            if not self._is_recording:
                return

            modifier_name = self._modifier_name(key)
            if modifier_name is not None and modifier_name in self._pressed_modifiers:
                self._pressed_modifiers.remove(modifier_name)

    def _append_text_char_locked(self, value: str, ts: float) -> None:
        if self._typing_started_at is None:
            self._typing_started_at = ts
        self._typing_buffer.append(value)

    def _append_hotkey_event_locked(self, ts: float, keys: list[str]) -> None:
        self._events.append(
            _RecordedEvent(
                ts=ts,
                payload={
                    "id": generate_id(),
                    "type": "hotkey",
                    "keys": keys,
                },
            )
        )

    def _flush_typing_locked(self, ts: float) -> None:
        if not self._typing_buffer:
            return

        event_ts = self._typing_started_at if self._typing_started_at is not None else ts
        self._events.append(
            _RecordedEvent(
                ts=event_ts,
                payload={
                    "id": generate_id(),
                    "type": "write",
                    "text": "".join(self._typing_buffer),
                    "interval": 0.05,
                },
            )
        )

        self._typing_buffer.clear()
        self._typing_started_at = None

    def _build_macro_locked(self) -> Macro:
        events = sorted(self._events, key=lambda item: item.ts)
        steps: list[MacroStep] = []

        for index, event in enumerate(events):
            payload = event.payload.copy()

            if index < len(events) - 1:
                next_event = events[index + 1]
                delay_after = max(0.0, next_event.ts - event.ts)
            else:
                delay_after = 0.2

            payload["delay_after"] = round(delay_after, 4)
            steps.append(MacroStep.from_dict(payload))

        return Macro(
            id=generate_id(),
            name=self._macro_name,
            created_at=self._created_at or now_iso(),
            steps=steps,
        )

    @staticmethod
    def _normalize_key_name(key: keyboard.Key | keyboard.KeyCode) -> str | None:
        if isinstance(key, keyboard.KeyCode):
            return key.char

        name = getattr(key, "name", None)
        if not name:
            return None

        aliases = {
            "return": "enter",
            "esc": "esc",
        }
        return aliases.get(name, name)

    @staticmethod
    def _modifier_name(key: keyboard.Key | keyboard.KeyCode) -> str | None:
        if isinstance(key, keyboard.KeyCode):
            return None
        return MODIFIER_KEYS.get(key)

    def _sorted_modifiers(self) -> list[str]:
        return sorted(self._pressed_modifiers, key=lambda item: MODIFIER_PRIORITY.get(item, 99))

    @staticmethod
    def _decode_control_char(value: str) -> str:
        if len(value) == 1:
            code = ord(value)
            if 1 <= code <= 26:
                return chr(ord("a") + code - 1)
        return value
