# ETAK Building Indexing Steps

The browser should not load the full `ETAK_Eesti_pohikaart_2024_SHP.zip` directly.
It contains 910,283 building records in `E_401_hoone_ka`, so it should be converted
into a compact index and served by a backend/API.

## Confirm The Source

Detected source:

```text
C:\Users\mowani\Downloads\ETAK_Eesti_pohikaart_2024_SHP.zip
```

Important layer:

```text
ETAK_Eesti_pohikaart_2024_SHP/Kihid/E_401_hoone_ka.dbf
```

Useful fields:

```text
etak_id,ehr_gid,ads_oid,ads_lahiaa,kov_id,korgus_m,tyyp_t,muutmisaeg,geom_muutm
```

## Create The Full CSV Index

Run this from a normal PowerShell terminal:

```powershell
cd "C:\Users\mowani\Documents\Learning Codex"
py -3 .\estonian-heating-upgrade-calculator-geoportal\backend\etak_building_indexer_stdout.py "C:\Users\mowani\Downloads\ETAK_Eesti_pohikaart_2024_SHP.zip" > .\estonian-heating-upgrade-calculator-geoportal\data\etak_buildings_index.csv
```

Expected result:

```text
estonian-heating-upgrade-calculator-geoportal\data\etak_buildings_index.csv
```

This CSV can then be loaded into SQLite, DuckDB, PostGIS, or a small backend search API.

## Why Not Put It Directly In The Browser?

The full building index is too large for a simple static browser page. The right design is:

```text
Browser address search
  -> backend search API
  -> ETAK index by ads_oid/ehr_gid/address
  -> calculator prefill
```

The current static page can keep its three demo buildings, while the backend handles the
910k real ETAK records.
