r"""Local ETAK building search API for Eesti RenoHeat Explorer.

Run:
    py -3 backend/etak_search_server_v2.py --csv C:\Users\mowani\Downloads\etak_buildings_index.csv

Endpoints:
    GET /api/health
    GET /api/search?q=Vaksali%2017&limit=10
    GET /api/building?ads_oid=ME03885623

The server is stdlib-only and allows browser requests from local file pages.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


DEFAULT_CSV = Path.home() / "Downloads" / "etak_buildings_index.csv"


def normalize(value: str) -> str:
    return " ".join(str(value or "").casefold().replace("/", " ").replace(",", " ").split())


@dataclass
class BuildingIndex:
    rows: list[dict[str, str]]
    by_ads_oid: dict[str, dict[str, str]]
    by_ehr_gid: dict[str, dict[str, str]]
    by_etak_id: dict[str, dict[str, str]]
    searchable: list[tuple[str, dict[str, str]]]
    loaded_at: float
    csv_path: Path

    @classmethod
    def load(cls, csv_path: Path) -> "BuildingIndex":
        started = time.time()
        rows: list[dict[str, str]] = []
        by_ads_oid: dict[str, dict[str, str]] = {}
        by_ehr_gid: dict[str, dict[str, str]] = {}
        by_etak_id: dict[str, dict[str, str]] = {}
        searchable: list[tuple[str, dict[str, str]]] = []

        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                clean = {key: (value or "").strip() for key, value in row.items()}
                rows.append(clean)
                if clean.get("ads_oid"):
                    by_ads_oid.setdefault(clean["ads_oid"], clean)
                if clean.get("ehr_gid"):
                    by_ehr_gid.setdefault(clean["ehr_gid"], clean)
                if clean.get("etak_id"):
                    by_etak_id.setdefault(clean["etak_id"], clean)
                searchable.append(
                    (
                        normalize(
                            " ".join(
                                [
                                    clean.get("ads_lahiaa", ""),
                                    clean.get("ads_oid", ""),
                                    clean.get("ehr_gid", ""),
                                    clean.get("etak_id", ""),
                                    clean.get("tyyp_t", ""),
                                ]
                            )
                        ),
                        clean,
                    )
                )

        print(f"Loaded {len(rows)} ETAK buildings from {csv_path} in {time.time() - started:.1f}s", file=sys.stderr)
        return cls(rows, by_ads_oid, by_ehr_gid, by_etak_id, searchable, time.time(), csv_path)

    def search(self, query: str, limit: int = 20) -> list[dict[str, str]]:
        query_norm = normalize(query)
        if not query_norm:
            return []

        direct = (
            self.by_ads_oid.get(query.strip())
            or self.by_ehr_gid.get(query.strip())
            or self.by_etak_id.get(query.strip())
        )
        if direct:
            return [direct]

        query_parts = query_norm.split()
        matches: list[dict[str, str]] = []
        for search_text, row in self.searchable:
            if all(part in search_text for part in query_parts):
                matches.append(row)
                if len(matches) >= limit:
                    break
        return matches

    def building(self, ads_oid: str = "", ehr_gid: str = "", etak_id: str = "") -> dict[str, str] | None:
        if ads_oid and ads_oid in self.by_ads_oid:
            return self.by_ads_oid[ads_oid]
        if ehr_gid and ehr_gid in self.by_ehr_gid:
            return self.by_ehr_gid[ehr_gid]
        if etak_id and etak_id in self.by_etak_id:
            return self.by_etak_id[etak_id]
        return None


def make_handler(index: BuildingIndex) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "ETAKSearch/0.2"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            print(f"{self.address_string()} - {format % args}", file=sys.stderr)

        def _send_json(self, status: int, payload: Any) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()
            self.wfile.write(body)

        def do_OPTIONS(self) -> None:  # noqa: N802
            self._send_json(200, {"ok": True})

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            params = parse_qs(parsed.query)
            try:
                if parsed.path == "/api/health":
                    self._send_json(
                        200,
                        {
                            "ok": True,
                            "records": len(index.rows),
                            "csv": str(index.csv_path),
                            "loaded_at": index.loaded_at,
                        },
                    )
                    return

                if parsed.path == "/api/search":
                    query = params.get("q", [""])[0]
                    limit = max(1, min(50, int(params.get("limit", ["20"])[0])))
                    results = index.search(query, limit)
                    self._send_json(200, {"query": query, "count": len(results), "results": results})
                    return

                if parsed.path == "/api/building":
                    row = index.building(
                        ads_oid=params.get("ads_oid", [""])[0],
                        ehr_gid=params.get("ehr_gid", [""])[0],
                        etak_id=params.get("etak_id", [""])[0],
                    )
                    self._send_json(200 if row else 404, {"building": row})
                    return

                self._send_json(404, {"error": "Not found"})
            except Exception as exc:  # noqa: BLE001
                self._send_json(500, {"error": str(exc)})

    return Handler


def main() -> int:
    parser = argparse.ArgumentParser(description="Serve local ETAK building search API.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    if not args.csv.exists():
        print(f"Missing CSV: {args.csv}", file=sys.stderr)
        return 2

    index = BuildingIndex.load(args.csv)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(index))
    print(f"ETAK search API running at http://{args.host}:{args.port}", file=sys.stderr)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping ETAK search API", file=sys.stderr)
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
