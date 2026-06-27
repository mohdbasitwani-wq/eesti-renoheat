# Eesti RenoHeat Explorer

Eesti RenoHeat Explorer is a local-first prototype for searching real Estonian ETAK building records and estimating heating-system and building-renovation impacts.

## Current Best Page

Open:

```text
index-public-v2.html
```

This page provides:

- Real ETAK building search through a local API
- Selected building summary
- Editable building, energy, and renovation inputs
- Heating upgrade outputs
- Renovation cost, grant, loan, and payback outputs
- Separate links for map and MaaRuum 3D view

## Start The Local ETAK API

The real building search needs the generated CSV:

```text
C:\Users\mowani\Downloads\etak_buildings_index.csv
```

Start the API:

```powershell
.\start-etak-api.ps1
```

Then open:

```text
file:///C:/Users/mowani/Documents/Learning%20Codex/estonian-heating-upgrade-calculator-geoportal/index-public-v2.html
```

## Data Status

Real:

- ETAK building index: 732,477 searchable building records
- Building fields: `etak_id`, `ehr_gid`, `ads_oid`, `ads_lahiaa`, `korgus_m`, building type

User-provided/estimated:

- Construction year
- Net area
- Floors
- Current heating source
- Energy label or known annual heat demand
- Energy prices
- Renovation package
- Grant support
- Loan interest and term

## Important Note

The building match is based on real ETAK data. Energy and renovation results are estimates for planning and discussion, not final engineering design.
