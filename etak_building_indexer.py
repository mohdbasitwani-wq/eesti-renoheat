"""Create a compact ETAK building index from the national SHP ZIP.

The full ETAK ZIP is too large to load in the browser. This script extracts
only the building attributes needed for lookup and calculator prefill.

Input layer:
    ETAK_Eesti_pohikaart_2024_SHP/Kihid/E_401_hoone_ka.dbf

Output columns:
    etak_id,ehr_gid,ads_oid,ads_lahiaa,kov_id,korgus_m,tyyp_t,muutmisaeg,geom_muutm
"""

from __future__ import annotations

import argparse
import csv
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO


BUILDING_DBF_SUFFIX = "E_401_hoone_ka.dbf"
OUTPUT_COLUMNS = [
    "etak_id",
    "ehr_gid",
    "ads_oid",
    "ads_lahiaa",
    "kov_id",
    "korgus_m",
    "tyyp_t",
    "muutmisaeg",
    "geom_muutm",
]


@dataclass(frozen=True)
class DbfField:
    name: str
    field_type: str
    length: int
    decimals: int
    offset: int


def decode_text(raw: bytes) -> str:
    raw = raw.rstrip(b"\x00 ")
    if not raw:
        return ""
    for encoding in ("utf-8", "cp1257", "cp775", "latin-1"):
        try:
            return raw.decode(encoding).strip()
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1", errors="replace").strip()


def read_dbf_header(handle: BinaryIO) -> tuple[int, int, int, list[DbfField]]:
    header = handle.read(32)
    if len(header) < 32:
        raise ValueError("DBF header is incomplete")

    record_count = int.from_bytes(header[4:8], "little")
    header_length = int.from_bytes(header[8:10], "little")
    record_length = int.from_bytes(header[10:12], "little")

    raw_descriptors = handle.read(header_length - 32)
    fields: list[DbfField] = []
    record_offset = 1
    offset = 0
    while offset + 32 <= len(raw_descriptors):
        if raw_descriptors[offset] == 0x0D:
            break
        descriptor = raw_descriptors[offset : offset + 32]
        name = decode_text(descriptor[:11])
        field_type = chr(descriptor[11])
        length = descriptor[16]
        decimals = descriptor[17]
        fields.append(DbfField(name, field_type, length, decimals, record_offset))
        record_offset += length
        offset += 32

    return record_count, header_length, record_length, fields


def parse_value(raw: bytes, field: DbfField) -> str:
    text = decode_text(raw)
    if not text:
        return ""
    if field.field_type in {"N", "F"}:
        return text
    if field.field_type == "D" and len(text) == 8:
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text


def find_building_dbf(zip_file: zipfile.ZipFile) -> str:
    matches = [name for name in zip_file.namelist() if name.endswith(BUILDING_DBF_SUFFIX)]
    if not matches:
        raise ValueError(f"Could not find {BUILDING_DBF_SUFFIX} inside ZIP")
    return matches[0]


def create_index(zip_path: Path, output_path: Path, limit: int | None = None) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        dbf_name = find_building_dbf(zf)
        with zf.open(dbf_name) as dbf, output_path.open("w", newline="", encoding="utf-8") as out:
            record_count, _header_length, record_length, fields = read_dbf_header(dbf)
            field_map = {field.name: field for field in fields}
            missing = [name for name in OUTPUT_COLUMNS if name not in field_map]
            if missing:
                raise ValueError(f"Building DBF missing expected fields: {missing}")

            writer = csv.DictWriter(out, fieldnames=OUTPUT_COLUMNS)
            writer.writeheader()
            written = 0
            for index in range(record_count):
                if limit is not None and written >= limit:
                    break
                record = dbf.read(record_length)
                if len(record) < record_length:
                    break
                if record[:1] == b"*":
                    continue

                row = {}
                for column in OUTPUT_COLUMNS:
                    field = field_map[column]
                    raw = record[field.offset : field.offset + field.length]
                    row[column] = parse_value(raw, field)

                if not row["ads_oid"] and not row["ehr_gid"] and not row["ads_lahiaa"]:
                    continue
                writer.writerow(row)
                written += 1

                if written and written % 100000 == 0:
                    print(f"indexed {written} buildings", file=sys.stderr)

    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Extract compact ETAK building index CSV.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("estonian-heating-upgrade-calculator-geoportal/data/etak_buildings_index.csv"),
    )
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    if not args.zip_path.exists():
        print(f"Missing ZIP: {args.zip_path}", file=sys.stderr)
        return 2

    written = create_index(args.zip_path, args.output, args.limit)
    print(f"Wrote {written} building records to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
