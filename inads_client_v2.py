"""Small In-ADS Gazetteer client for real Estonian address lookup.

Usage:
    py -3 backend/inads_client_v2.py "Vaksali 17, Tartu"

Use this v2 file in preference to `inads_client.py`; it includes the observed
In-ADS response keys from the live endpoint.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from typing import Any


GAZETTEER_URL = "https://inaadress.maaamet.ee/inaadress/gazetteer"


def _records_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [record for record in payload if isinstance(record, dict)]
    if isinstance(payload, dict):
        for key in ("addresses", "aadressid", "results", "result", "features"):
            value = payload.get(key)
            if isinstance(value, list):
                return [record for record in value if isinstance(record, dict)]
        return [payload]
    return []


def geocode_address(address: str, timeout: int = 20) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode({"address": address})
    request = urllib.request.Request(
        f"{GAZETTEER_URL}?{query}",
        headers={"Accept": "application/json", "User-Agent": "Eesti-RenoHeat-Explorer/0.1"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        charset = response.headers.get_content_charset() or "utf-8"
        payload = json.loads(response.read().decode(charset))
    return _records_from_payload(payload)


def normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "ads_oid": record.get("ads_oid") or record.get("ADS_OID"),
        "adr_id": record.get("adr_id") or record.get("ADR_ID"),
        "adob_id": record.get("adob_id") or record.get("ADOB_ID"),
        "address": record.get("taisaadress")
        or record.get("pikkaadress")
        or record.get("aadresstekst")
        or record.get("aadress")
        or record.get("address"),
        "lat": record.get("viitepunkt_b") or record.get("lat"),
        "lon": record.get("viitepunkt_l") or record.get("lon"),
        "x_3301": record.get("viitepunkt_x"),
        "y_3301": record.get("viitepunkt_y"),
        "bounding_box_3301": record.get("boundingbox"),
        "bounding_box_wgs84": record.get("g_boundingbox") or record.get("boundingbox"),
        "quality": record.get("kvaliteet"),
        "object_type": record.get("liikVal"),
        "raw": record,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Look up an Estonian address via In-ADS.")
    parser.add_argument("address")
    parser.add_argument("--all", action="store_true", help="Print all returned records")
    args = parser.parse_args()

    try:
        records = [normalize_record(record) for record in geocode_address(args.address)]
    except Exception as exc:  # noqa: BLE001 - command-line diagnostics should keep the error visible.
        print(f"In-ADS lookup failed: {exc}", file=sys.stderr)
        return 1

    selected = records if args.all else records[:1]
    print(json.dumps(selected, ensure_ascii=False, indent=2))
    return 0 if selected else 3


if __name__ == "__main__":
    raise SystemExit(main())
