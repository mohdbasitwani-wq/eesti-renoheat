r"""Public ETAK dashboard server for Eesti RenoHeat Explorer.

This serves the real dashboard and the ETAK API from the same public domain.

Local run:
    py -3 backend/etak_public_server.py --csv C:\Users\mowani\Downloads\etak_buildings_index.csv --host 127.0.0.1 --port 8765

Production run:
    python backend/etak_public_server.py --csv data/etak_buildings_index.csv --host 0.0.0.0 --port $PORT
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import sys
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from etak_search_server_v2 import BuildingIndex


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CSV = PROJECT_ROOT / "data" / "etak_buildings_index.csv"
DEFAULT_DASHBOARD = PROJECT_ROOT / "index-real-etak-calculator.html"


def json_bytes(payload: Any) -> bytes:
    return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def make_handler(index: BuildingIndex, dashboard_path: Path) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "EestiRenoHeat/1.0"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            print(f"{self.address_string()} - {format % args}", file=sys.stderr)

        def send_json(self, status: int, payload: Any) -> None:
            body = json_bytes(payload)
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
                    self.send_json(
                        200,
                        {
                            "ok": True,
                            "records": len(index.rows),
                            "csv": str(index.csv_path),
                            "loaded_at": index.loaded_at,
                        },
                    )
                    return

                if path == "/api/search":
                    query = params.get("q", [""])[0]
                    limit = max(1, min(50, int(params.get("limit", ["20"])[0])))
                    results = index.search(query, limit)
                    self.send_json(200, {"query": query, "count": len(results), "results": results})
                    return

                if path == "/api/building":
                    row = index.building(
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
    parser = argparse.ArgumentParser(description="Serve the public Eesti RenoHeat dashboard and real ETAK API.")
    parser.add_argument("--csv", type=Path, default=Path(os.environ.get("ETAK_CSV", DEFAULT_CSV)))
    parser.add_argument("--dashboard", type=Path, default=DEFAULT_DASHBOARD)
    parser.add_argument("--host", default=os.environ.get("HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8765")))
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"Missing CSV: {args.csv}", file=sys.stderr)
        return 2
    if not args.dashboard.exists():
        print(f"Missing dashboard HTML: {args.dashboard}", file=sys.stderr)
        return 2

    started = time.time()
    index = BuildingIndex.load(args.csv)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(index, args.dashboard))
    print(f"Eesti RenoHeat public dashboard running at http://{args.host}:{args.port}", file=sys.stderr)
    print(f"Startup finished in {time.time() - started:.1f}s", file=sys.stderr)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping Eesti RenoHeat public dashboard", file=sys.stderr)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
