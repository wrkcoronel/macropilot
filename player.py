from __future__ import annotations

import threading
import time
from collections.abc import Callable

import pyautogui
from pynput import keyboard, mouse

from models import Macro, MacroStep


StepCallback = Callable[[int, int, MacroStep], None]
FinishCallback = Callable[[bool], None]
ErrorCallback = Callable[[Exception], None]


KEY_ALIASES = {
    "return": "enter",
    "esc": "esc",
    "escape": "esc",
    "space": "space",
    "tab": "tab",
    "backspace": "backspace",
    "delete": "delete",
    "up": "up",
    "down": "down",
    "left": "left",
    "right": "right",
    "home": "home",
    "end": "end",
    "control": "ctrl",
    "page_up": "pageup",
    "page_down": "pagedown",
    "command": "win",
    "cmd": "win",
    "option": "alt",
}


class MacroPlayer:
    def __init__(self) -> None:
        pyautogui.PAUSE = 0
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._esc_listener: keyboard.Listener | None = None
        self._mouse_controller = mouse.Controller()

    @property
    def is_playing(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def play_async(
        self,
        macro: Macro,
        speed: float,
        repetitions: int,
        initial_delay: float = 0.0,
        on_step: StepCallback | None = None,
        on_finish: FinishCallback | None = None,
        on_error: ErrorCallback | None = None,
    ) -> None:
        if self.is_playing:
            raise RuntimeError("Já existe execução em andamento")

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(macro, speed, repetitions, initial_delay, on_step, on_finish, on_error),
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _run(
        self,
        macro: Macro,
        speed: float,
        repetitions: int,
        initial_delay: float,
        on_step: StepCallback | None,
        on_finish: FinishCallback | None,
        on_error: ErrorCallback | None,
    ) -> None:
        cancelled = False

        try:
            self._start_esc_listener()

            if initial_delay > 0 and not self._interruptible_sleep(initial_delay):
                cancelled = True

            for repetition in range(repetitions):
                if self._stop_event.is_set():
                    cancelled = True
                    break

                for index, step in enumerate(macro.steps, start=1):
                    if self._stop_event.is_set():
                        cancelled = True
                        break

                    self._execute_step(step)

                    if on_step is not None:
                        on_step(repetition + 1, index, step)

                    delay_real = max(0.0, float(step.delay_after)) / speed
                    if not self._interruptible_sleep(delay_real):
                        cancelled = True
                        break

                if cancelled:
                    break

            if on_finish is not None:
                on_finish(cancelled)
        except Exception as error:
            if on_error is not None:
                on_error(error)
        finally:
            self._stop_event.clear()
            self._stop_esc_listener()

    def _start_esc_listener(self) -> None:
        self._esc_listener = keyboard.Listener(on_press=self._on_key_press)
        self._esc_listener.start()

    def _stop_esc_listener(self) -> None:
        if self._esc_listener is not None:
            self._esc_listener.stop()
            self._esc_listener = None

    def _on_key_press(self, key: keyboard.Key | keyboard.KeyCode) -> bool | None:
        if key == keyboard.Key.esc:
            self.stop()
            return False
        return None

    def _execute_step(self, step: MacroStep) -> None:
        if step.type == "click":
            self._mouse_controller.position = (int(step.x or 0), int(step.y or 0))
            self._mouse_controller.click(self._normalize_button(step.button), 1)
            return

        if step.type == "write":
            pyautogui.write(step.text or "", interval=float(step.interval if step.interval is not None else 0.05))
            return

        if step.type == "key":
            key_value = step.key or "enter"
            if "+" in key_value:
                self._execute_hotkey(key_value.split("+"))
            else:
                pyautogui.press(self._normalize_key(key_value))
            return

        if step.type == "hotkey":
            self._execute_hotkey(step.keys or [])
            return

        if step.type == "scroll":
            self._mouse_controller.position = (int(step.x or 0), int(step.y or 0))
            self._mouse_controller.scroll(int(step.dx or 0), int(step.dy or 0))
            return

        raise ValueError(f"Tipo de passo não suportado: {step.type}")

    def _interruptible_sleep(self, duration: float) -> bool:
        end_time = time.perf_counter() + duration
        while time.perf_counter() < end_time:
            if self._stop_event.is_set():
                return False
            time.sleep(0.01)
        return True

    @staticmethod
    def _normalize_key(key: str) -> str:
        normalized = MacroPlayer._decode_control_char(key).lower().strip()
        return KEY_ALIASES.get(normalized, normalized)

    def _execute_hotkey(self, keys: list[str]) -> None:
        normalized_keys = [self._normalize_key(item) for item in keys if item and item.strip()]
        if not normalized_keys:
            return
        if len(normalized_keys) == 1:
            pyautogui.press(normalized_keys[0])
            return
        pyautogui.hotkey(*normalized_keys)

    @staticmethod
    def _normalize_button(button: str | None) -> mouse.Button:
        normalized = (button or "left").lower().strip()
        mapping = {
            "left": mouse.Button.left,
            "right": mouse.Button.right,
            "middle": mouse.Button.middle,
        }
        return mapping.get(normalized, mouse.Button.left)

    @staticmethod
    def _decode_control_char(value: str) -> str:
        if len(value) == 1:
            code = ord(value)
            if 1 <= code <= 26:
                return chr(ord("a") + code - 1)
        return value
