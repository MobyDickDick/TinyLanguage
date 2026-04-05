"""Python-backed GUI runner for TinyLanguage stdlib.gui."""
from __future__ import annotations

from typing import Any


def _as_text_list(values: Any) -> list[str]:
    """Normalize Tiny arrays/lists to a list of strings."""
    if not isinstance(values, list):
        return []
    return [str(value) for value in values]


def run_app(title: str, width: int, height: int, labels: Any, buttons: Any) -> dict[str, Any]:
    """Launch a small Tkinter window with labels and close-buttons.

    Returns a status map so Tiny callers can handle missing displays gracefully.
    """
    safe_title = str(title)
    safe_width = int(width)
    safe_height = int(height)
    safe_labels = _as_text_list(labels)
    safe_buttons = _as_text_list(buttons)

    summary = {
        "backend": "tkinter",
        "title": safe_title,
        "width": safe_width,
        "height": safe_height,
        "widget_count": len(safe_labels) + len(safe_buttons),
    }

    try:
        import tkinter as tk
    except Exception as exc:  # pragma: no cover - environment dependent
        return {"ok": False, "error": f"tkinter import failed: {exc}", "summary": summary}

    try:
        root = tk.Tk()
        root.title(safe_title)
        root.geometry(f"{safe_width}x{safe_height}")

        for text in safe_labels:
            tk.Label(root, text=text).pack()
        for text in safe_buttons:
            tk.Button(root, text=text, command=root.destroy).pack()

        root.mainloop()
        return {"ok": True, "summary": summary}
    except Exception as exc:  # pragma: no cover - environment dependent
        return {"ok": False, "error": f"gui launch failed: {exc}", "summary": summary}
