# Real Data Pipeline For Eesti RenoHeat Explorer

This project should use three public Estonian data streams:

1. **In-ADS address search**
   - Source: https://inaadress.maaamet.ee/inaadress/
   - Working lookup endpoint: `https://inaadress.maaamet.ee/inaadress/gazetteer?address=...`
   - Purpose: turns a typed address into official address identifiers, coordinates, and bounding box.
   - Useful fields returned by In-ADS: `ads_oid`, `adr_id`, `adob_id`, `viitepunkt_b`, `viitepunkt_l`.

2. **ETAK building geometry**
   - Provided file: `C:\Users\mowani\Downloads\ETAK_Eesti_SHP_ehitised.zip`
   - Main building layer: `E_401_hoone_ka`
   - Record count inspected locally: `924416`
   - Useful fields found locally: `etak_id`, `ehr_gid`, `ads_oid`, `ads_lahiaa`, `korgus_m`.
   - Purpose: supplies real building footprint geometry and height for envelope calculations.

3. **EHR building/energy data**
   - Still needed for a fully real calculator.
   - Purpose: supplies construction year, closed net area, building use, and heating/energy system attributes.
   - Expected backend fields in `energy_transition_processor.py`: `ehr_kood`, `ehitusaasta`, `suletud_netopind`, `peamine_soojusallikas`, `ads_adr_id`.

## Join Logic

Preferred path:

```text
User address
  -> In-ADS Gazetteer
  -> ads_oid / adr_id / coordinate
  -> ETAK E_401_hoone_ka by ads_oid, or nearest footprint around coordinate
  -> EHR by ehr_gid/ehr_kood or ADS address identifier
  -> heating + renovation calculation
```

Fallback path:

```text
User address
  -> In-ADS coordinate
  -> spatial nearest ETAK footprint
  -> EHR by ehr_gid when available
```

## What Is Already Ready

- The browser page can collect addresses and display map markers.
- `backend/energy_transition_processor.py` already contains the thermodynamic and ROI calculation model.
- `backend/etak_zip_inspector.py` can inspect the provided ETAK ZIPs without installing GIS libraries.

## What Must Be Added Next

1. Install backend GIS dependencies from `backend/requirements.txt`.
2. Build an API endpoint `/api/geocode` that proxies In-ADS so the browser does not depend on CORS.
3. Build an API endpoint `/api/building/{ads_oid}` that reads ETAK/EHR and returns one normalized building record.
4. Export/cache the large ETAK SHP layer into a faster local format such as GeoPackage or Parquet.
5. Load EHR open data and map its identifiers to ETAK `ehr_gid` and/or address identifiers.

## Minimal API Shape

```json
{
  "input_address": "Vaksali 17, Tartu",
  "in_ads": {
    "ads_oid": "ME00750651",
    "adr_id": "3062467",
    "lat": 58.372612,
    "lon": 26.709876
  },
  "etak": {
    "etak_id": "...",
    "ehr_gid": "...",
    "height_m": 12.4,
    "footprint_area_m2": 820.0,
    "perimeter_m": 118.0
  },
  "ehr": {
    "construction_year": 1983,
    "closed_net_area_m2": 2850.0,
    "main_heat_source": "district_heating"
  }
}
```

## Important Note

ETAK makes the map and building geometry real. It does **not** by itself contain all energy/renovation inputs. For true heating and renovation results, the missing dataset is EHR/open building registry data or an exported EHR table with construction year, area, and heating system fields.
