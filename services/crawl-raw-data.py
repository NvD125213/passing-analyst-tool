import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright

# Id cầu thủ trên SofaScore. Florian Wirtz là 1019322.
PLAYER_ID = 1407524
# Id giải đấu. 17 là Premier League.
# 16 là World Cup 2026.
# 10783 là Nations League.
UNIQUE_TOURNAMENT_ID = 35 
# Số trận có thống kê, lấy từ cuối mảng events. Trận mới nhất được xử lý trước.
MATCH_LIMIT = 20
# Thư mục lưu thống kê. Mỗi trận là một file JSON.
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "output" / "tests"

# Danh sách trận của player trong một giải. {player_id} lấy từ PLAYER_ID.
URL_LINK_DATA_LIST_MATCH_PLAYER_IN_TOURNAMENT = (
    "https://www.sofascore.com/api/v1/player/{player_id}"
    "/unique-tournament/{tournament_id}/events/last/0"
)
# Thống kê của player trong một trận. {match_id} là id của event.
URL_LINK_DATA_STATISTICS_PLAYER_IN_MATCH = (
    "https://www.sofascore.com/api/v1/event/{match_id}/player/{player_id}/rating-breakdown"
)

HOME_URL = "https://www.sofascore.com/"
CHROME_PATH = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
PROFILE_DIR = Path(__file__).resolve().parents[1] / ".chrome-profile"
DEBUG_PORT = 9333


def _chrome_debug_ready() -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{DEBUG_PORT}/json/version", timeout=1):
            return True
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def _stop_profile_chrome() -> None:
    """Close only the Chrome window started for this profile."""
    marker = str(PROFILE_DIR).replace("'", "''")
    subprocess.run(
        [
            "powershell",
            "-NoProfile",
            "-Command",
            (
                "Get-CimInstance Win32_Process -Filter \"Name = 'chrome.exe'\" | "
                f"Where-Object {{ $_.CommandLine -like '*{marker}*' }} | "
                "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
            ),
        ],
        check=False,
        capture_output=True,
    )


def _start_chrome() -> None:
    if not CHROME_PATH.exists():
        raise FileNotFoundError(f"Google Chrome was not found at {CHROME_PATH}")

    _stop_profile_chrome()
    PROFILE_DIR.mkdir(exist_ok=True)
    subprocess.Popen(
        [
            str(CHROME_PATH),
            f"--remote-debugging-port={DEBUG_PORT}",
            f"--user-data-dir={PROFILE_DIR}",
            "--no-first-run",
            "--no-default-browser-check",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.time() + 20
    while time.time() < deadline:
        if _chrome_debug_ready():
            return
        time.sleep(0.3)
    raise RuntimeError("Chrome did not open its debugging port.")


def _fetch_in_page(page, url: str) -> dict:
    return page.evaluate(
        """async (targetUrl) => {
            const response = await fetch(targetUrl, {
                credentials: "include",
                headers: {
                    accept: "*/*",
                    "x-requested-with": "898581",
                },
            });
            return { status: response.status, body: await response.text() };
        }""",
        url,
    )


def _open_sofascore_page(playwright):
    browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{DEBUG_PORT}")
    context = browser.contexts[0]
    page = context.new_page()
    page.goto(HOME_URL, wait_until="commit", timeout=60_000)

    if "captcha" in page.url:
        print(
            "Chrome đang mở trang kiểm tra SofaScore. Nếu có captcha, hãy xác nhận trên cửa sổ đó.",
            file=sys.stderr,
        )

    deadline = time.time() + 90
    while "captcha" in page.url and time.time() < deadline:
        page.wait_for_timeout(1_000)

    if "captcha" in page.url:
        raise RuntimeError("SofaScore vẫn ở trang captcha. Hãy xác nhận trên Chrome rồi chạy lại.")

    page.wait_for_timeout(2_000)
    return browser, page


def _fetch_json(page, url: str) -> dict:
    result = _fetch_in_page(page, url)
    for _ in range(4):
        if result["status"] == 200:
            break
        page.wait_for_timeout(2_000)
        result = _fetch_in_page(page, url)

    raw_body = result["body"]
    try:
        body = json.loads(raw_body)
    except json.JSONDecodeError:
        body = raw_body

    if result["status"] != 200:
        raise RuntimeError(f"SofaScore returned HTTP {result['status']} for {url}: {raw_body[:500]}")

    if not isinstance(body, dict):
        raise RuntimeError(f"SofaScore returned a non-JSON object for {url}")

    return body


def _events_newest_first(events: list[dict]) -> list[dict]:
    """Đi từ cuối mảng events lên, trận có chỉ số lớn hơn được xét trước."""
    return list(reversed(events))


def _match_file_name(event: dict, used_names: set[str]) -> str:
    home = event.get("homeTeam", {}).get("name", "home")
    away = event.get("awayTeam", {}).get("name", "away")
    base = re.sub(r'[<>:"/\\|?*]', "-", f"{home} vs {away}").strip().rstrip(".")
    name = f"{base}.json"
    if name in used_names:
        name = f"{base}-{event['id']}.json"
    used_names.add(name)
    return name


def crawl_player_match_statistics() -> list[Path]:
    """Lấy các trận mới nhất trong giải của PLAYER_ID, rồi lưu thống kê từng trận."""
    _start_chrome()
    try:
        with sync_playwright() as playwright:
            browser, page = _open_sofascore_page(playwright)
            try:
                list_url = URL_LINK_DATA_LIST_MATCH_PLAYER_IN_TOURNAMENT.format(
                    player_id=PLAYER_ID,
                    tournament_id=UNIQUE_TOURNAMENT_ID,
                )
                matches = _fetch_json(page, list_url)
                events = matches.get("events") or []

                OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
                written: list[Path] = []
                used_names: set[str] = set()
                for event in _events_newest_first(events):
                    if len(written) == MATCH_LIMIT:
                        break
                    if event.get("hasEventPlayerStatistics") is False:
                        continue

                    statistics_url = URL_LINK_DATA_STATISTICS_PLAYER_IN_MATCH.format(
                        match_id=event["id"],
                        player_id=PLAYER_ID,
                    )
                    try:
                        statistics = _fetch_json(page, statistics_url)
                    except RuntimeError as exc:
                        if "HTTP 404" not in str(exc):
                            raise
                        continue

                    destination = OUTPUT_DIR / _match_file_name(event, used_names)
                    destination.write_text(
                        json.dumps(statistics, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                    written.append(destination)

                if len(written) < MATCH_LIMIT:
                    print(
                        f"Chỉ có {len(written)}/{MATCH_LIMIT} trận có thống kê. Bỏ qua các trận còn thiếu.",
                        file=sys.stderr,
                    )
            finally:
                page.close()
                browser.close()
    finally:
        _stop_profile_chrome()

    return written


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    saved_files = crawl_player_match_statistics()
    for path in saved_files:
        print(path)
