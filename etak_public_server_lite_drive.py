r"""Low-memory public ETAK dashboard server with optional Google Drive CSV download.

Use this on small Render instances. It does not load the full ETAK CSV into RAM.

Render start command:
    python etak_public_server_lite_drive.py --csv data/etak_buildings_index.csv --dashboard index-real-etak-calculator.html --host 0.0.0.0 --port $PORT

If data/etak_buildings_index.csv is missing, set ETAK_CSV_URL to a Google Drive
"Anyone with the link" sharing URL for etak_buildings_index.csv.
"""

from __future__ import annotations

import argparse
import csv
import json
import mimetypes
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse
from urllib.request import urlopen


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CSV = PROJECT_ROOT / "data" / "etak_buildings_index.csv"
DEFAULT_DASHBOARD = PROJECT_ROOT / "index-real-etak-calculator.html"
DOWNLOAD_CSV = Path(os.environ.get("ETAK_DOWNLOAD_PATH", "/tmp/etak_buildings_index.csv"))


def normalize(value: str) -> str:
    return " ".join(str(value or "").casefold().replace("/", " ").replace(",", " ").split())


def google_drive_direct_url(url: str) -> str:
    parsed = urlparse(url)
    if "drive.google.com" not in parsed.netloc:
        return url

    parts = [part for part in parsed.path.split("/") if part]
    if "file" in parts and "d" in parts:
        file_id = parts[parts.index("d") + 1]
        return f"https://drive.google.com/uc?export=download&id={file_id}"
    return url


def ensure_csv(csv_path: Path, csv_url: str | None) -> Path | None:
    if csv_path.exists():
        return csv_path
    if not csv_url:
        return None

    target = DOWNLOAD_CSV
    target.parent.mkdir(parents=True, exist_ok=True)
    download_url = google_drive_direct_url(csv_url)
    print(f"Downloading ETAK CSV from {download_url}", file=sys.stderr)
    with urlopen(download_url, timeout=240) as response, target.open("wb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
    print(f"Downloaded ETAK CSV to {target} ({target.stat().st_size} bytes)", file=sys.stderr)
    return target


def count_records(csv_path: Path) -> int:
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        return max(0, sum(1 for _ in handle) - 1)


def search_csv(csv_path: Path, query: str, limit: int) -> list[dict[str, str]]:
    query_norm = normalize(query)
    if not query_norm:
        return []

    query_parts = query_norm.split()
    exact = query.strip()
    results: list[dict[str, str]] = []

    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            clean = {key: (value or "").strip() for key, value in row.items()}
            if exact and exact in {clean.get("ads_oid"), clean.get("ehr_gid"), clean.get("etak_id")}:
                return [clean]

            search_text = normalize(
                " ".join(
                    [
                        clean.get("ads_lahiaa", ""),
                        clean.get("ads_oid", ""),
                        clean.get("ehr_gid", ""),
                        clean.get("etak_id", ""),
                        clean.get("tyyp_t", ""),
                    ]
                )
            )
            if all(part in search_text for part in query_parts):
                results.append(clean)
                if len(results) >= limit:
                    break
    return results


def find_building(csv_path: Path, ads_oid: str = "", ehr_gid: str = "", etak_id: str = "") -> dict[str, str] | None:
    with csv_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            clean = {key: (value or "").strip() for key, value in row.items()}
            if ads_oid and clean.get("ads_oid") == ads_oid:
                return clean
            if ehr_gid and clean.get("ehr_gid") == ehr_gid:
                return clean
            if etak_id and clean.get("etak_id") == etak_id:
                return clean
    return None


def make_handler(csv_path: Path, dashboard_path: Path, record_count: int) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "EestiRenoHeatLite/1.0"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            print(f"{self.address_string()} - {format % args}", file=sys.stderr)

        def send_json(self, status: int, payload: Any) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def send_text(self, status: int, body: str, content_type: str = "text/html; charset=utf-8") -> None:
            data = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)

        def do_OPTIONS(self) -> None:  # noqa: N802
            self.send_json(200, {"ok": True})

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            path = parsed.path
            params = parse_qs(parsed.query)

            try:
                if path == "/api/health":
                    self.send_json(200, {"ok": True, "records": record_count, "csv": str(csv_path), "mode": "lite"})
                    return

                if path == "/api/search":
                    query = params.get("q", [""])[0]
                    limit = max(1, min(50, int(params.get("limit", ["20"])[0])))
                    results = search_csv(csv_path, query, limit)
                    self.send_json(200, {"query": query, "count": len(results), "results": results})
                    return

                if path == "/api/building":
                    row = find_building(
                        csv_path,
                        ads_oid=params.get("ads_oid", [""])[0],
                        ehr_gid=params.get("ehr_gid", [""])[0],
                        etak_id=params.get("etak_id", [""])[0],
                    )
                    self.send_json(200 if row else 404, {"building": row})
                    return

                if path in {"/", "/index.html", "/index-real-etak-calculator.html"}:
                    html = dashboard_path.read_text(encoding="utf-8")
                    html = html.replace(
                        'const API_BASE = "http://127.0.0.1:8765";',
                        'const API_BASE = window.location.origin;',
                    )
                    html = html.replace("Checking local ETAK API...", "Checking public ETAK API...")
                    html = html.replace("Connected to local ETAK API:", "Connected to real ETAK API:")
                    html = html.replace("Local ETAK API is not running.", "The public ETAK API is not available.")
                    self.send_text(200, html)
                    return

                asset = PROJECT_ROOT / path.lstrip("/")
                if asset.is_file() and PROJECT_ROOT in asset.resolve().parents:
                    content_type = mimetypes.guess_type(asset.name)[0] or "application/octet-stream"
                    data = asset.read_bytes()
                    self.send_response(200)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                    return

                self.send_json(404, {"error": "Not found"})
            except Exception as exc:  # noqa: BLE001
                self.send_json(500, {"error": str(exc)})

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve Eesti RenoHeat with low memory real ETAK CSV search.")
    parser.add_argument("--csv", type=Path, default=Path(os.environ.get("ETAK_CSV", DEFAULT_CSV)))
    parser.add_argument("--dashboard", type=Path, default=DEFAULT_DASHBOARD)
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8765")))
    args = parser.parse_args()

    csv_path = ensure_csv(args.csv, os.environ.get("ETAK_CSV_URL"))
    if not csv_path:
        print(f"Missing CSV: {args.csv}", file=sys.stderr)
        print("Set ETAK_CSV_URL to a public Google Drive sharing link.", file=sys.stderr)
        return 2
    if not args.dashboard.exists():
        print(f"Missing dashboard HTML: {args.dashboard}", file=sys.stderr)
        return 2

    records = count_records(csv_path)
    print(f"Using low-memory ETAK search with {records} records from {csv_path}", file=sys.stderr)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(csv_path, args.dashboard, records))
    print(f"Eesti RenoHeat lite dashboard running at http://{args.host}:{args.port}", file=sys.stderr)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping Eesti RenoHeat lite dashboard", file=sys.stderr)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
