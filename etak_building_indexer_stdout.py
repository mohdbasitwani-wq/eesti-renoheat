"""Print a compact ETAK building index to stdout.

This variant avoids creating files directly, which is useful in restricted
environments. Redirect stdout in a normal terminal to save a CSV:

    py -3 backend/etak_building_indexer_stdout.py C:\...\ETAK_Eesti_pohikaart_2024_SHP.zip > data\etak_buildings_index.csv
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


def read_dbf_header(handle: BinaryIO) -> tuple[int, int, list[DbfField]]:
    header = handle.read(32)
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
    return record_count, record_length, fields


def parse_value(raw: bytes, field: DbfField) -> str:
    text = decode_text(raw)
    if field.field_type == "D" and len(text) == 8:
        return f"{text[:4]}-{text[4:6]}-{text[6:]}"
    return text


def find_building_dbf(zip_file: zipfile.ZipFile) -> str:
    matches = [name for name in zip_file.namelist() if name.endswith(BUILDING_DBF_SUFFIX)]
    if not matches:
        raise ValueError(f"Could not find {BUILDING_DBF_SUFFIX} inside ZIP")
    return matches[0]


def stream_index(zip_path: Path, limit: int | None = None) -> int:
    writer = csv.DictWriter(sys.stdout, fieldnames=OUTPUT_COLUMNS, lineterminator="\n")
    writer.writeheader()
    with zipfile.ZipFile(zip_path) as zf:
        with zf.open(find_building_dbf(zf)) as dbf:
            record_count, record_length, fields = read_dbf_header(dbf)
            field_map = {field.name: field for field in fields}
            written = 0
            for _index in range(record_count):
                if limit is not None and written >= limit:
                    break
                record = dbf.read(record_length)
                if len(record) < record_length:
                    break
                if record[:1] == b"*":
                    continue
                row = {
                    column: parse_value(
                        record[field_map[column].offset : field_map[column].offset + field_map[column].length],
                        field_map[column],
                    )
                    for column in OUTPUT_COLUMNS
                }
                if not row["ads_oid"] and not row["ehr_gid"] and not row["ads_lahiaa"]:
                    continue
                writer.writerow(row)
                written += 1
    return written


def main() -> int:
    parser = argparse.ArgumentParser(description="Print compact ETAK building index CSV to stdout.")
    parser.add_argument("zip_path", type=Path)
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    if not args.zip_path.exists():
        print(f"Missing ZIP: {args.zip_path}", file=sys.stderr)
        return 2
    written = stream_index(args.zip_path, args.limit)
    print(f"# wrote {written} records", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
