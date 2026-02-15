"""Download Python snippets from Rosetta Code task pages."""

from __future__ import annotations

from dataclasses import dataclass
from html import unescape
import json
from pathlib import Path
import re
import time
from typing import Iterable
from urllib.parse import urljoin, urlparse, unquote
from urllib.request import Request, urlopen

BASE_URL = "https://rosettacode.org"
CATEGORY_URL = f"{BASE_URL}/wiki/Category:Python"
USER_AGENT = "TinyLanguage-RosettaFetcher/1.0"


@dataclass
class DownloadSummary:
    requested: int
    discovered_tasks: int
    downloaded: int
    skipped_without_python: int
    destination: str
    resumed_from: str | None
    last_downloaded: str | None



def _fetch_html(url: str, timeout: float = 20.0) -> str:
    request = Request(url, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:  # noqa: S310
        return response.read().decode("utf-8", errors="replace")



def _iter_task_urls(category_html: str) -> Iterable[str]:
    seen: set[str] = set()
    for path in re.findall(r'href="(/wiki/[^"#?]+)"', category_html):
        if not path.startswith("/wiki/"):
            continue
        title = unquote(path[len("/wiki/") :])
        if not title or title.startswith("Category:"):
            continue
        if ":" in title:
            continue
        if title in {"Rosetta_Code", "Programming_Languages"}:
            continue
        if path in seen:
            continue
        seen.add(path)
        yield urljoin(BASE_URL, path)



def _extract_page_title(url: str) -> str:
    parsed = urlparse(url)
    title = parsed.path.rsplit("/", 1)[-1]
    return unquote(title) or "task"



def _sanitize_filename(title: str) -> str:
    cleaned = title.replace(" ", "_")
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", cleaned)
    cleaned = cleaned.strip("._")
    return cleaned or "task"



def _extract_python_block(task_html: str) -> str | None:
    heading = re.search(
        r'<span class="mw-headline" id="Python[^"]*"[^>]*>.*?</span>',
        task_html,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if not heading:
        return None

    section_start = heading.end()
    next_heading = re.search(r"<h2[^>]*>", task_html[section_start:], flags=re.IGNORECASE)
    section_end = section_start + next_heading.start() if next_heading else len(task_html)
    section_html = task_html[section_start:section_end]

    blocks = re.findall(r"<pre[^>]*>(.*?)</pre>", section_html, flags=re.IGNORECASE | re.DOTALL)
    if not blocks:
        return None

    code = blocks[0]
    code = re.sub(r"<[^>]+>", "", code)
    code = unescape(code)
    code = code.replace("\r\n", "\n").strip("\n")
    return code or None


def _read_state(state_path: Path) -> dict[str, object]:
    if not state_path.exists():
        return {}
    try:
        loaded = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _write_state(state_path: Path, state: dict[str, object]) -> None:
    state_path.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def _start_index(task_urls: list[str], last_downloaded_url: str | None) -> int:
    if not last_downloaded_url:
        return 0
    try:
        return task_urls.index(last_downloaded_url) + 1
    except ValueError:
        return 0



def download_rosetta_python_scripts(
    destination: str,
    limit: int = 50,
    delay_seconds: float = 0.25,
    state_file_name: str = ".rosetta_python_downloader_state.json",
) -> dict[str, object]:
    """Download up to ``limit`` Python snippets from Rosetta Code tasks."""
    destination_path = Path(destination)
    destination_path.mkdir(parents=True, exist_ok=True)
    state_path = destination_path / state_file_name
    state = _read_state(state_path)
    last_downloaded_url = state.get("last_downloaded_url") if isinstance(state.get("last_downloaded_url"), str) else None

    category_html = _fetch_html(CATEGORY_URL)
    task_urls = list(_iter_task_urls(category_html))
    start_index = _start_index(task_urls, last_downloaded_url)

    downloaded = 0
    skipped = 0
    most_recent_url = last_downloaded_url
    for url in task_urls[start_index:]:
        if downloaded >= limit:
            break

        task_html = _fetch_html(url)
        code = _extract_python_block(task_html)
        if not code:
            skipped += 1
            continue

        title = _extract_page_title(url)
        filename = _sanitize_filename(title) + ".py"
        output_path = destination_path / filename
        output_path.write_text(f"# Source: {url}\n\n{code}\n", encoding="utf-8")
        downloaded += 1
        most_recent_url = url
        _write_state(
            state_path,
            {
                "last_downloaded_url": most_recent_url,
                "last_downloaded_script": filename,
                "updated_at_epoch": time.time(),
            },
        )
        if delay_seconds > 0:
            time.sleep(delay_seconds)

    summary = DownloadSummary(
        requested=limit,
        discovered_tasks=len(task_urls),
        downloaded=downloaded,
        skipped_without_python=skipped,
        destination=str(destination_path.resolve()),
        resumed_from=last_downloaded_url,
        last_downloaded=most_recent_url,
    )
    return {
        "requested": summary.requested,
        "discovered_tasks": summary.discovered_tasks,
        "downloaded": summary.downloaded,
        "skipped_without_python": summary.skipped_without_python,
        "destination": summary.destination,
        "resumed_from": summary.resumed_from,
        "last_downloaded": summary.last_downloaded,
    }


def download_from_args_json(raw_args_json: str | None) -> dict[str, object]:
    """Parse Tiny-provided JSON args and run the downloader.

    JSON format: [dest?, "--limit", "50", "--delay", "0.1"]
    """
    args = []
    if raw_args_json:
        args = json.loads(raw_args_json)

    destination = "rosetta_python_samples"
    limit = 50
    delay_seconds = 0.25

    index = 0
    if index < len(args) and args[index] not in {"--limit", "--delay"}:
        destination = str(args[index])
        index += 1

    while index < len(args):
        flag = args[index]
        if flag == "--limit" and index + 1 < len(args):
            limit = int(args[index + 1])
            index += 2
            continue
        if flag == "--delay" and index + 1 < len(args):
            delay_seconds = float(args[index + 1])
            index += 2
            continue
        index += 1

    return download_rosetta_python_scripts(destination, limit=limit, delay_seconds=delay_seconds)
