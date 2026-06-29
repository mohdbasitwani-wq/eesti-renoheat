"""Inspect ETAK building ZIP exports without requiring GIS libraries.

This is intentionally stdlib-only so it can run on a clean Windows machine.
It lists shapefile layers inside an ETAK ZIP and reads DBF field metadata,
which tells us what identifiers are available for joining with In-ADS/EHR.
"""

from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path
from typing import Any


def _decode_dbf_text(raw: bytes) -> str:
    for encoding in ("utf-8", "cp1257", "cp775", "latin-1"):
        try:
            return raw.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace").strip()


def read_dbf_fields(dbf_bytes: bytes) -> list[dict[str, Any]]:
    """Return DBF field descriptors from a .dbf byte stream."""
    if len(dbf_bytes) < 32:
        raise ValueError("DBF file is too small to contain a valid header")

    record_count = int.from_bytes(dbf_bytes[4:8], "little")
    header_length = int.from_bytes(dbf_bytes[8:10], "little")
    record_length = int.from_bytes(dbf_bytes[10:12], "little")

    fields: list[dict[str, Any]] = []
    offset = 32
    while offset + 32 <= min(header_length, len(dbf_bytes)):
        if dbf_bytes[offset] == 0x0D:
            break
        name = _decode_dbf_text(dbf_bytes[offset : offset + 11].split(b"\x00", 1)[0])
        field_type = chr(dbf_bytes[offset + 11])
        length = dbf_bytes[offset + 16]
        decimals = dbf_bytes[offset + 17]
        fields.append(
            {
                "name": name,
                "type": field_type,
                "length": length,
                "decimals": decimals,
            }
        )
        offset += 32

    return [
        {"record_count": record_count, "record_length": record_length, "fields": fields}
    ]


def inspect_zip(zip_path: Path) -> dict[str, Any]:
    with zipfile.ZipFile(zip_path) as zf:
        names = zf.namelist()
        dbf_names = [name for name in names if name.lower().endswith(".dbf")]
        shp_names = [name for name in names if name.lower().endswith(".shp")]
        prj_names = [name for name in names if name.lower().endswith(".prj")]

        layers = []
        for dbf_name in dbf_names:
            dbf_bytes = zf.read(dbf_name)
            metadata = read_dbf_fields(dbf_bytes)[0]
            layer_base = dbf_name[:-4]
            matching = {
                "shp": f"{layer_base}.shp" in names,
                "shx": f"{layer_base}.shx" in names,
                "prj": f"{layer_base}.prj" in names,
            }
            layers.append(
                {
                    "dbf": dbf_name,
                    "record_count": metadata["record_count"],
                    "record_length": metadata["record_length"],
                    "matching_files": matching,
                    "fields": metadata["fields"],
                }
            )

        return {
            "zip": str(zip_path),
            "entries": len(names),
            "shp_count": len(shp_names),
            "dbf_count": len(dbf_names),
            "prj_count": len(prj_names),
            "layers": layers,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect ETAK building ZIP exports.")
    parser.add_argument("zip_paths", nargs="+", type=Path)
    parser.add_argument("--json", action="store_true", help="Print full JSON metadata")
    args = parser.parse_args()

    reports = []
    for zip_path in args.zip_paths:
        if not zip_path.exists():
            print(f"Missing ZIP: {zip_path}", file=sys.stderr)
            return 2
        reports.append(inspect_zip(zip_path))

    if args.json:
        print(json.dumps(reports, ensure_ascii=False, indent=2))
        return 0

    for report in reports:
        print(f"\n{report['zip']}")
        print(
            f"entries={report['entries']} shp={report['shp_count']} "
            f"dbf={report['dbf_count']} prj={report['prj_count']}"
        )
        for layer in report["layers"]:
            field_names = ", ".join(field["name"] for field in layer["fields"])
            print(f"- {layer['dbf']} records={layer['record_count']}")
            print(f"  fields: {field_names}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
