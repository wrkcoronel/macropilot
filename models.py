from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


StepType = Literal["click", "write", "key", "scroll", "hotkey"]


@dataclass(slots=True)
class MacroStep:
    id: str
    type: StepType
    delay_after: float = 0.0
    x: int | None = None
    y: int | None = None
    button: str | None = None
    text: str | None = None
    interval: float | None = None
    key: str | None = None
    keys: list[str] | None = None
    dx: int | None = None
    dy: int | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "type": self.type,
            "delay_after": float(self.delay_after),
        }

        if self.type == "click":
            data.update(
                {
                    "x": int(self.x or 0),
                    "y": int(self.y or 0),
                    "button": self.button or "left",
                }
            )
        elif self.type == "write":
            data.update(
                {
                    "text": self.text or "",
                    "interval": float(self.interval if self.interval is not None else 0.05),
                }
            )
        elif self.type == "key":
            data.update({"key": self.key or "enter"})
        elif self.type == "hotkey":
            data.update({"keys": list(self.keys or [])})
        elif self.type == "scroll":
            data.update(
                {
                    "x": int(self.x or 0),
                    "y": int(self.y or 0),
                    "dx": int(self.dx or 0),
                    "dy": int(self.dy or 0),
                }
            )

        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MacroStep":
        step_type = str(data.get("type", "")).lower()
        delay_after = float(data.get("delay_after", 0.0))

        if step_type == "click":
            return cls(
                id=str(data["id"]),
                type="click",
                x=int(data.get("x", 0)),
                y=int(data.get("y", 0)),
                button=str(data.get("button", "left")),
                delay_after=delay_after,
            )

        if step_type == "write":
            return cls(
                id=str(data["id"]),
                type="write",
                text=str(data.get("text", "")),
                interval=float(data.get("interval", 0.05)),
                delay_after=delay_after,
            )

        if step_type == "key":
            return cls(
                id=str(data["id"]),
                type="key",
                key=str(data.get("key", "enter")),
                delay_after=delay_after,
            )

        if step_type == "hotkey":
            keys = [str(item) for item in data.get("keys", [])]
            return cls(
                id=str(data["id"]),
                type="hotkey",
                keys=keys,
                delay_after=delay_after,
            )

        if step_type == "scroll":
            return cls(
                id=str(data["id"]),
                type="scroll",
                x=int(data.get("x", 0)),
                y=int(data.get("y", 0)),
                dx=int(data.get("dx", 0)),
                dy=int(data.get("dy", 0)),
                delay_after=delay_after,
            )

        raise ValueError(f"Tipo de passo inválido: {step_type}")

    @property
    def summary(self) -> str:
        if self.type == "click":
            return f"click ({self.button}) em ({self.x}, {self.y})"
        if self.type == "write":
            text = self.text or ""
            preview = text if len(text) <= 30 else text[:27] + "..."
            return f"write \"{preview}\""
        if self.type == "hotkey":
            return f"hotkey {'+'.join(self.keys or [])}"
        if self.type == "scroll":
            return f"scroll dx={self.dx} dy={self.dy} em ({self.x}, {self.y})"
        return f"key {self.key}"


@dataclass(slots=True)
class Macro:
    id: str
    name: str
    created_at: str
    steps: list[MacroStep] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at,
            "steps": [step.to_dict() for step in self.steps],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Macro":
        steps_data = data.get("steps", [])
        steps = [MacroStep.from_dict(item) for item in steps_data]
        return cls(
            id=str(data["id"]),
            name=str(data.get("name", "Macro")),
            created_at=str(data.get("created_at", "")),
            steps=steps,
        )

    def remove_step(self, step_id: str) -> None:
        self.steps = [step for step in self.steps if step.id != step_id]
