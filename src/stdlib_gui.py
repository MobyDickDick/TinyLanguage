"""Python-backed GUI helpers for TinyLanguage stdlib.gui.

The module intentionally exposes a tiny declarative layer so TinyLanguage
programs can build small standalone desktop windows via Tkinter without having
to call Python interop primitives directly.
"""
from __future__ import annotations

from typing import Any


def _normalize_app(app: dict[str, Any]) -> dict[str, Any]:
    """Return an app dictionary with expected keys present."""
    normalized = dict(app or {})
    normalized.setdefault("title", "Tiny App")
    normalized.setdefault("width", 480)
    normalized.setdefault("height", 320)
    widgets = normalized.get("widgets")
    if not isinstance(widgets, list):
        widgets = []
    normalized["widgets"] = widgets
    return normalized


def create_app(title: str, width: int, height: int) -> dict[str, Any]:
    """Create a new declarative app description."""
    return _normalize_app(
        {
            "title": title,
            "width": int(width),
            "height": int(height),
            "widgets": [],
        }
    )


def add_label(app: dict[str, Any], text: str) -> dict[str, Any]:
    """Append a label component to the app description."""
    normalized = _normalize_app(app)
    normalized["widgets"].append({"kind": "label", "text": str(text)})
    return normalized


def add_button(app: dict[str, Any], text: str) -> dict[str, Any]:
    """Append a button component to the app description."""
    normalized = _normalize_app(app)
    normalized["widgets"].append({"kind": "button", "text": str(text)})
    return normalized


def describe_app(app: dict[str, Any]) -> dict[str, Any]:
    """Return a serializable summary for tests and CLI feedback."""
    normalized = _normalize_app(app)
    widget_types = [str(widget.get("kind", "unknown")) for widget in normalized["widgets"]]
    return {
        "backend": "tkinter",
        "title": str(normalized["title"]),
        "width": int(normalized["width"]),
        "height": int(normalized["height"]),
        "widget_count": len(normalized["widgets"]),
        "widget_types": widget_types,
    }


def run_app(app: dict[str, Any]) -> dict[str, Any]:
    """Launch the window and render label/button widgets.

    The function returns a status map instead of raising GUI errors so callers
    can handle headless environments gracefully.
    """
    normalized = _normalize_app(app)
    summary = describe_app(normalized)
    try:
        import tkinter as tk
    except Exception as exc:  # pragma: no cover - depends on local Python build
        return {
            "ok": False,
            "error": f"tkinter import failed: {exc}",
            "summary": summary,
        }

    try:
        root = tk.Tk()
        root.title(str(normalized["title"]))
        root.geometry(f"{int(normalized['width'])}x{int(normalized['height'])}")

        for widget in normalized["widgets"]:
            kind = str(widget.get("kind", ""))
            text = str(widget.get("text", ""))
            if kind == "label":
                tk.Label(root, text=text).pack()
            elif kind == "button":
                tk.Button(root, text=text, command=root.destroy).pack()

        root.mainloop()
        return {"ok": True, "summary": summary}
    except Exception as exc:  # pragma: no cover - depends on display availability
        return {
            "ok": False,
            "error": f"gui launch failed: {exc}",
            "summary": summary,
        }
