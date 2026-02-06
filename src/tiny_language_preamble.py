"""Platform shims and interactive helpers shared across TinyLanguage tools.

This module centralizes readline fallbacks, terminal capability detection, and
argument parsing helpers that would otherwise be duplicated between the REPL
and CLI layers. The lightweight implementations are designed to degrade
gracefully on platforms without ``termios`` support while still providing
history and completion hooks when available.
"""

from __future__ import annotations

import argparse  # required to keep stitched globals available
import importlib.util  # required to keep stitched globals available
import math  # required to keep stitched globals available
import os  # required to keep stitched globals available
import sys
import threading  # required to keep stitched globals available
from pathlib import Path
try:  # pragma: no cover - platform-specific imports
    import termios  # type: ignore
    import tty  # type: ignore
    _HAS_TERMIOS = True
except ImportError:  # pragma: no cover - Windows and other platforms without termios
    termios = None  # type: ignore
    tty = None  # type: ignore
    _HAS_TERMIOS = False

from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple, Union

from tiny_errors import SourcePos, SourceSpan, StackFrame, TinyLangError, _line_info, format_error
from tiny_language_error_codes import classify_error

from stdlib import register_stdlib

class _FallbackReadline:
    """Minimal in-memory readline replacement for platforms without it."""

    def __init__(self) -> None:
        self._history: List[str] = []
        self._completions = None
        self._history_length = 1000
        self._history_index: Optional[int] = None

    # Configuration API
    def set_completer_delims(self, _delims: str) -> None:  # pragma: no cover - noop
        return

    def set_completer(self, completer) -> None:  # pragma: no cover - noop
        self._completions = completer

    def parse_and_bind(self, _cmd: str) -> None:  # pragma: no cover - noop
        return

    # History management
    def read_history_file(self, path: Path) -> None:
        if not Path(path).exists():
            return
        with open(path, "r", encoding="utf-8") as f:
            self._history = [line.rstrip("\n") for line in f]

    def write_history_file(self, path: Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            for entry in self._history[-self._history_length :]:
                f.write(entry + "\n")

    def set_history_length(self, length: int) -> None:  # pragma: no cover - simple setter
        self._history_length = max(0, length)

    def clear_history(self) -> None:
        self._history.clear()

    def add_history(self, line: str) -> None:
        self._history.append(line)
        self._history_index = None

    def get_history_item(self, index: int) -> Optional[str]:
        idx = index - 1
        if 0 <= idx < len(self._history):
            return self._history[idx]
        return None

    def get_current_history_length(self) -> int:  # pragma: no cover - trivial
        return len(self._history)

    # Interactive helpers
    def _collect_matches(self, text: str) -> List[str]:
        """Gather completion candidates from the configured completer."""

        if self._completions is None:  # No completer means no matches
            return []
        matches: List[str] = []  # Accumulate completion strings
        idx = 0  # State counter required by readline-compatible completers
        while True:
            candidate = self._completions(text, idx)  # Ask completer for the idx-th match
            if candidate is None:  # A "None" sentinel marks the end
                break
            matches.append(candidate)
            idx += 1
        return matches

    def _redraw(self, prompt: str, buffer: List[str], last_len: int) -> int:
        """Render the current prompt + buffer, padding leftover characters if needed."""

        sys.stdout.write("\r")  # Start at the beginning of the line
        rendered = prompt + "".join(buffer)  # Prompt plus current text
        sys.stdout.write(rendered)
        if last_len > len(buffer):  # Clear any extra characters from a previous render
            sys.stdout.write(" " * (last_len - len(buffer)))
        sys.stdout.write("\r")  # Return to the line start again
        sys.stdout.write(prompt + "".join(buffer))  # Write prompt and buffer
        sys.stdout.flush()
        return len(buffer)

    def _reverse_search(self, prompt: str, fd: int) -> Optional[str]:
        """Implement a simple reverse-i-search inspired by readline."""

        if not _HAS_TERMIOS:  # Without termios support, we cannot drive raw input
            return None
        sys.stdout.write("\n(reverse-search): ")  # Start a new prompt line
        sys.stdout.flush()
        termios.tcsetattr(fd, termios.TCSADRAIN, self._old_settings)  # Restore cooked mode
        try:
            query = sys.stdin.readline().rstrip("\n")  # Grab the search term
        finally:
            tty.setraw(fd)  # Return to raw mode for normal handling
        if not query:  # Empty search means abort
            return None
        for entry in reversed(self._history):  # Walk history from newest to oldest
            if query in entry:
                return entry  # Return the first entry that contains the query
        return None

    def readline(self, prompt: str = "") -> str:
        if not _HAS_TERMIOS:
            line = input(prompt)  # Fall back to default input() when raw mode is unavailable
            if line:
                self.add_history(line)  # Persist history in the in-memory buffer
            return line
        fd = sys.stdin.fileno()  # Grab the file descriptor to toggle terminal modes
        self._old_settings = termios.tcgetattr(fd)  # Remember previous termios state
        buffer: List[str] = []  # Characters typed so far
        last_len = 0  # Track the previous render length for erasing
        self._history_index = None  # Reset history navigation state

        sys.stdout.write(prompt)
        sys.stdout.flush()
        try:
            tty.setraw(fd)  # Switch to raw mode to intercept keystrokes
            while True:
                ch = sys.stdin.read(1)  # Read a single byte
                if ch in ("\n", "\r"):
                    sys.stdout.write("\n")  # Move to the next line
                    line = "".join(buffer)  # Turn the buffer into a full string
                    if line:
                        self.add_history(line)  # Save successful entries
                    return line
                if ch == "\x7f":  # Backspace
                    if buffer:
                        buffer.pop()  # Remove the last character
                        last_len = self._redraw(prompt, buffer, last_len)  # Refresh the line
                    continue
                if ch == "\t":  # Tab completion
                    prefix = "".join(buffer)
                    last_word = prefix.split()[-1] if prefix else ""  # Only complete the final token
                    matches = self._collect_matches(last_word)
                    if not matches:
                        continue  # Nothing to complete
                    if len(matches) == 1:
                        completed = matches[0]  # Single match, accept immediately
                    else:
                        shared_prefix = last_word  # Find longest shared prefix for multiple matches
                        for idx in range(len(last_word), len(max(matches, key=len)) + 1):
                            candidates = {m[:idx] for m in matches if len(m) >= idx}
                            if len(candidates) == 1:
                                shared_prefix = candidates.pop()
                            else:
                                break
                        completed = shared_prefix
                        sys.stdout.write("\n" + "  ".join(sorted(matches)) + "\n")  # Show options
                    if last_word:
                        buffer = buffer[: len(prefix) - len(last_word)] + list(completed)
                    else:
                        buffer = list(completed)
                    last_len = self._redraw(prompt, buffer, last_len)
                    continue
                if ch == "\x12":  # Ctrl+R reverse search
                    match = self._reverse_search(prompt, fd)
                    if match is not None:
                        buffer = list(match)  # Replace buffer with the match
                        last_len = self._redraw(prompt, buffer, last_len)
                    else:
                        last_len = self._redraw(prompt, buffer, last_len)
                    continue
                if ch == "\x1b":  # Escape sequences (arrow keys)
                    seq = sys.stdin.read(2)  # Read the remaining bytes of the escape code
                    if seq == "[A":  # Up
                        if self._history:
                            if self._history_index is None:
                                self._history_index = len(self._history) - 1  # Start at the newest entry
                            elif self._history_index > 0:
                                self._history_index -= 1  # Move further back in history
                            buffer = list(self._history[self._history_index])
                            last_len = self._redraw(prompt, buffer, last_len)
                    elif seq == "[B":  # Down
                        if self._history_index is not None:
                            if self._history_index < len(self._history) - 1:
                                self._history_index += 1  # Move forward in history
                                buffer = list(self._history[self._history_index])
                            else:
                                self._history_index = None  # Clear history selection at the end
                                buffer = []
                            last_len = self._redraw(prompt, buffer, last_len)
                    continue
                buffer.append(ch)  # Normal character: append to buffer
                last_len = self._redraw(prompt, buffer, last_len)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, self._old_settings)


def _load_readline():
    """Return a readline-compatible object even on platforms without it."""

    required_api = {
        "set_completer_delims",
        "set_completer",
        "parse_and_bind",
        "read_history_file",
        "write_history_file",
        "set_history_length",
        "clear_history",
        "add_history",
        "get_history_item",
        "get_current_history_length",
    }

    try:  # pragma: no cover - import may fail on some platforms
        import readline as rl  # type: ignore
    except Exception:  # pragma: no cover - fallback path
        return _FallbackReadline()

    missing = [name for name in required_api if not hasattr(rl, name)]
    if missing:  # pragma: no cover - platforms with partial readline support
        return _FallbackReadline()

    return rl


readline = _load_readline()


def _classify_error(msg: str, candidates: Optional[List[str]] = None) -> Tuple[str, Optional[str]]:
    return classify_error(msg, candidates)
