import argparse
import json
import logging
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy import optimize


LOGGER = logging.getLogger("estonian_heating_transition")

EPSG_ESTONIAN_NATIONAL_GRID = 3301
BASELINE_INSIDE_TEMPERATURE_C = 21.0
HARDWARE_LIFECYCLE_YEARS = 25.0

ENERGY_TARIFF_EUR_PER_KWH = {
    "electricity": 0.18,
    "district_heating": 0.08,
    "natural_gas": 0.07,
}

CURRENT_SYSTEM_MODELS = {
    "district_heating": {"efficiency": 0.95, "energy_type": "district_heating", "highly_efficient": False},
    "gas_boiler": {"efficiency": 0.88, "energy_type": "natural_gas", "highly_efficient": False},
    "direct_electric": {"efficiency": 1.0, "energy_type": "electricity", "highly_efficient": False},
    "air_to_air_heat_pump": {"efficiency": 2.8, "energy_type": "electricity", "highly_efficient": True},
    "air_to_water_heat_pump": {"efficiency": None, "energy_type": "electricity", "highly_efficient": True},
    "ground_source_heat_pump": {"efficiency": 4.1, "energy_type": "electricity", "highly_efficient": True},
}

UPGRADE_TARGETS = {
    "Air-to-Water Heat Pump": {"capex_eur": 8500.0, "mode": "dynamic_air_to_water"},
    "Ground-Source Heat Pump": {"capex_eur": 13000.0, "mode": "fixed_scop", "scop": 4.1},
}

EHR_REQUIRED_COLUMNS = {
    "ehr_kood",
    "ehitusaasta",
    "suletud_netopind",
    "peamine_soojusallikas",
    "ads_adr_id",
}

MAA_AMET_REQUIRED_COLUMNS = {
    "ads_adr_id",
    "korgus_m",
    "perimeeter_m",
    "geometry",
}


@dataclass(frozen=True)
class ProcessingConfig:
    inside_temperature_c: float = BASELINE_INSIDE_TEMPERATURE_C
    lifecycle_years: float = HARDWARE_LIFECYCLE_YEARS
    target_crs_epsg: int = EPSG_ESTONIAN_NATIONAL_GRID


class EstonianHeatingTransitionProcessor:
    def __init__(self, config: ProcessingConfig | None = None, logger: logging.Logger | None = None):
        self.config = config or ProcessingConfig()
        self.logger = logger or LOGGER

    def run(self, ehr_dataframe: pd.DataFrame, maa_amet_geometries: gpd.GeoDataFrame, outdoor_temperatures_c: np.ndarray) -> gpd.GeoDataFrame:
        ehr = self.prepare_ehr_dataframe(ehr_dataframe)
        geometries = self.prepare_maa_amet_geometries(maa_amet_geometries)
        temperatures = self.prepare_temperature_array(outdoor_temperatures_c)
        research_gdf = self.join_ehr_to_maa_amet(ehr, geometries)
        thermodynamic_gdf = self.calculate_building_envelope_metrics(research_gdf)
        thermodynamic_gdf = self.calculate_temperature_dependent_heat_demand(thermodynamic_gdf, temperatures)
        optimized_gdf = self.optimize_heating_transitions(thermodynamic_gdf, temperatures)
        return optimized_gdf

    def prepare_ehr_dataframe(self, ehr_dataframe: pd.DataFrame) -> pd.DataFrame:
        missing = EHR_REQUIRED_COLUMNS.difference(ehr_dataframe.columns)
        if missing:
            raise ValueError(f"EHR dataframe missing required columns: {sorted(missing)}")

        ehr = ehr_dataframe.copy()
        ehr["ehr_kood"] = ehr["ehr_kood"].astype(str).str.strip()
        ehr["ads_adr_id"] = ehr["ads_adr_id"].astype(str).str.strip()
        ehr["peamine_soojusallikas"] = ehr["peamine_soojusallikas"].astype(str).str.strip()
        ehr["ehitusaasta"] = pd.to_numeric(ehr["ehitusaasta"], errors="coerce").astype("Int64")
        ehr["suletud_netopind"] = pd.to_numeric(ehr["suletud_netopind"], errors="coerce")

        invalid = ehr[
            ehr["ehr_kood"].eq("")
            | ehr["ads_adr_id"].eq("")
            | ehr["ehitusaasta"].isna()
            | ehr["suletud_netopind"].isna()
            | (ehr["suletud_netopind"] <= 0)
        ]
        if not invalid.empty:
            raise ValueError(f"EHR dataframe contains {len(invalid)} invalid building records")

        duplicated_ads = ehr[ehr["ads_adr_id"].duplicated(keep=False)]
        if not duplicated_ads.empty:
            self.logger.warning("EHR contains %s duplicate ADS ADR IDs; first deterministic record retained", len(duplicated_ads))
            ehr = ehr.sort_values(["ads_adr_id", "ehr_kood"]).drop_duplicates("ads_adr_id", keep="first")

        return ehr

    def prepare_maa_amet_geometries(self, maa_amet_geometries: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        missing = MAA_AMET_REQUIRED_COLUMNS.difference(maa_amet_geometries.columns)
        if missing:
            raise ValueError(f"Maa-amet GeoDataFrame missing required columns: {sorted(missing)}")

        gdf = maa_amet_geometries.copy()
        if gdf.crs is None:
            raise ValueError("Maa-amet geometries must declare CRS before metric area and perimeter calculations")

        if gdf.crs.to_epsg() != self.config.target_crs_epsg:
            self.logger.info("Reprojecting Maa-amet geometries from %s to EPSG:%s", gdf.crs, self.config.target_crs_epsg)
            gdf = gdf.to_crs(epsg=self.config.target_crs_epsg)

        gdf["ads_adr_id"] = gdf["ads_adr_id"].astype(str).str.strip()
        gdf["korgus_m"] = pd.to_numeric(gdf["korgus_m"], errors="coerce")
        gdf["perimeeter_m"] = pd.to_numeric(gdf["perimeeter_m"], errors="coerce")
        gdf["geometry"] = gdf["geometry"].make_valid()

        invalid = gdf[
            gdf["ads_adr_id"].eq("")
            | gdf["geometry"].isna()
            | gdf["geometry"].is_empty
            | gdf["korgus_m"].isna()
            | gdf["perimeeter_m"].isna()
            | (gdf["korgus_m"] <= 0)
            | (gdf["perimeeter_m"] <= 0)
        ]
        if not invalid.empty:
            raise ValueError(f"Maa-amet GeoDataFrame contains {len(invalid)} invalid spatial records")

        duplicated_ads = gdf[gdf["ads_adr_id"].duplicated(keep=False)]
        if not duplicated_ads.empty:
            self.logger.warning("Maa-amet geometries contain %s duplicate ADS ADR IDs; largest footprint retained", len(duplicated_ads))
            gdf["_footprint_area_m2"] = gdf.geometry.area
            gdf = gdf.sort_values(["ads_adr_id", "_footprint_area_m2"], ascending=[True, False]).drop_duplicates("ads_adr_id", keep="first")
            gdf = gdf.drop(columns=["_footprint_area_m2"])

        return gdf

    def prepare_temperature_array(self, outdoor_temperatures_c: np.ndarray) -> np.ndarray:
        temperatures = np.asarray(outdoor_temperatures_c, dtype=float).reshape(-1)
        if temperatures.size != 8760:
            raise ValueError(f"Expected 8,760 hourly outdoor temperature readings, received {temperatures.size}")
        if not np.isfinite(temperatures).all():
            raise ValueError("Outdoor temperature array contains non-finite values")
        return temperatures

    def join_ehr_to_maa_amet(self, ehr: pd.DataFrame, geometries: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        ehr_ids = set(ehr["ads_adr_id"])
        geometry_ids = set(geometries["ads_adr_id"])
        missing_geometry = sorted(ehr_ids.difference(geometry_ids))
        missing_ehr = sorted(geometry_ids.difference(ehr_ids))

        if missing_geometry:
            self.logger.warning("EHR records without Maa-amet geometry: %s", json.dumps(missing_geometry[:50], ensure_ascii=False))
        if missing_ehr:
            self.logger.warning("Maa-amet geometries without EHR records: %s", json.dumps(missing_ehr[:50], ensure_ascii=False))

        joined = geometries.merge(ehr, on="ads_adr_id", how="inner", validate="one_to_one")
        joined = gpd.GeoDataFrame(joined, geometry="geometry", crs=geometries.crs)

        if joined.empty:
            raise ValueError("EHR and Maa-amet inputs produced an empty inner join on ads_adr_id")

        self.logger.info("Joined %s EHR records with Maa-amet geometries on ads_adr_id", len(joined))
        return joined

    def calculate_building_envelope_metrics(self, gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        result = gdf.copy()
        result["roof_area_m2"] = result.geometry.area
        result["facade_area_m2"] = result["perimeeter_m"] * result["korgus_m"]
        result["envelope_area_m2"] = result["facade_area_m2"] + result["roof_area_m2"]

        u_values = result["ehitusaasta"].apply(self.assign_estonian_u_values).apply(pd.Series)
        result["wall_u_w_m2k"] = u_values["wall_u_w_m2k"].astype(float)
        result["roof_u_w_m2k"] = u_values["roof_u_w_m2k"].astype(float)
        result["building_era"] = u_values["building_era"].astype(str)
        result["ua_w_per_k"] = (result["facade_area_m2"] * result["wall_u_w_m2k"]) + (result["roof_area_m2"] * result["roof_u_w_m2k"])
        result["heat_loss_w_at_design_delta_t"] = result["ua_w_per_k"] * self.config.inside_temperature_c
        return result

    def assign_estonian_u_values(self, construction_year: int | np.integer) -> dict[str, float | str]:
        year = int(construction_year)
        if year < 1940:
            return {"wall_u_w_m2k": 0.85, "roof_u_w_m2k": 0.55, "building_era": "Pre-1940 Historic wood"}
        if 1940 <= year <= 1990:
            return {"wall_u_w_m2k": 0.75, "roof_u_w_m2k": 0.48, "building_era": "1940-1990 Soviet panel"}
        if 1991 <= year <= 2010:
            return {"wall_u_w_m2k": 0.28, "roof_u_w_m2k": 0.22, "building_era": "1991-2010 Transition regulations"}
        return {"wall_u_w_m2k": 0.16, "roof_u_w_m2k": 0.12, "building_era": "Post-2010 Modern energy code"}

    def calculate_temperature_dependent_heat_demand(self, gdf: gpd.GeoDataFrame, outdoor_temperatures_c: np.ndarray) -> gpd.GeoDataFrame:
        result = gdf.copy()
        delta_t = np.maximum(self.config.inside_temperature_c - outdoor_temperatures_c, 0.0)
        air_to_water_cop = self.air_to_water_cop_curve(outdoor_temperatures_c)
        result["annual_space_heating_demand_kwh"] = result["ua_w_per_k"].to_numpy(dtype=float) * delta_t.sum() / 1000.0
        result["peak_transmission_heat_loss_kw"] = result["ua_w_per_k"].to_numpy(dtype=float) * delta_t.max() / 1000.0
        result["air_to_water_mean_cop_heating_hours"] = float(air_to_water_cop[delta_t > 0].mean()) if np.any(delta_t > 0) else float(air_to_water_cop.mean())
        result["air_to_water_min_cop_heating_year"] = float(air_to_water_cop.min())
        result["air_to_water_annual_input_kwh"] = result["ua_w_per_k"].to_numpy(dtype=float) * np.divide(delta_t, air_to_water_cop).sum() / 1000.0
        return result

    def air_to_water_cop_curve(self, outdoor_temperatures_c: np.ndarray) -> np.ndarray:
        temperatures = np.asarray(outdoor_temperatures_c, dtype=float)
        clipped = np.clip(temperatures, -20.0, 7.0)
        return np.interp(clipped, [-20.0, 7.0], [1.7, 4.5])

    def optimize_heating_transitions(self, gdf: gpd.GeoDataFrame, outdoor_temperatures_c: np.ndarray) -> gpd.GeoDataFrame:
        result = gdf.copy()
        delta_t = np.maximum(self.config.inside_temperature_c - outdoor_temperatures_c, 0.0)
        air_to_water_cop = self.air_to_water_cop_curve(outdoor_temperatures_c)

        current_metrics = result.apply(lambda row: self.calculate_current_system_cost(row, delta_t, air_to_water_cop), axis=1, result_type="expand")
        result = pd.concat([result, current_metrics], axis=1)

        candidate_records = result.apply(lambda row: self.calculate_upgrade_candidates(row), axis=1)
        candidate_frame = pd.DataFrame(candidate_records.tolist(), index=result.index)
        result = pd.concat([result, candidate_frame], axis=1)

        optimized = result.apply(lambda row: self.solve_upgrade_optimization(row), axis=1, result_type="expand")
        result = pd.concat([result, optimized], axis=1)
        result["Optimization_Target"] = (
            (~result["current_system_highly_efficient"])
            & (result["best_annual_savings_eur"] > 0)
            & (result["best_payback_years"] <= self.config.lifecycle_years)
        )
        result = gpd.GeoDataFrame(result, geometry="geometry", crs=gdf.crs)
        return result

    def calculate_current_system_cost(self, row: pd.Series, delta_t: np.ndarray, air_to_water_cop: np.ndarray) -> pd.Series:
        system_key = self.normalize_heating_system(row["peamine_soojusallikas"])
        system = CURRENT_SYSTEM_MODELS[system_key]
        annual_demand_kwh = float(row["annual_space_heating_demand_kwh"])
        ua_w_per_k = float(row["ua_w_per_k"])

        if system_key == "air_to_water_heat_pump":
            purchased_energy_kwh = ua_w_per_k * np.divide(delta_t, air_to_water_cop).sum() / 1000.0
            effective_cop = annual_demand_kwh / purchased_energy_kwh if purchased_energy_kwh > 0 else np.nan
        else:
            purchased_energy_kwh = annual_demand_kwh / float(system["efficiency"])
            effective_cop = float(system["efficiency"])

        tariff = ENERGY_TARIFF_EUR_PER_KWH[str(system["energy_type"])]
        annual_cost_eur = purchased_energy_kwh * tariff

        return pd.Series(
            {
                "current_system_key": system_key,
                "current_system_energy_type": system["energy_type"],
                "current_system_effective_cop_or_efficiency": effective_cop,
                "current_system_purchased_energy_kwh": purchased_energy_kwh,
                "current_annual_cost_eur": annual_cost_eur,
                "current_system_highly_efficient": bool(system["highly_efficient"]),
            }
        )

    def calculate_upgrade_candidates(self, row: pd.Series) -> dict[str, float]:
        annual_demand_kwh = float(row["annual_space_heating_demand_kwh"])
        air_to_water_input_kwh = float(row["air_to_water_annual_input_kwh"])
        ground_source_input_kwh = annual_demand_kwh / UPGRADE_TARGETS["Ground-Source Heat Pump"]["scop"]

        air_to_water_cost = air_to_water_input_kwh * ENERGY_TARIFF_EUR_PER_KWH["electricity"]
        ground_source_cost = ground_source_input_kwh * ENERGY_TARIFF_EUR_PER_KWH["electricity"]
        current_cost = float(row["current_annual_cost_eur"])

        air_to_water_savings = current_cost - air_to_water_cost
        ground_source_savings = current_cost - ground_source_cost

        return {
            "air_to_water_capex_eur": UPGRADE_TARGETS["Air-to-Water Heat Pump"]["capex_eur"],
            "air_to_water_proposed_input_kwh": air_to_water_input_kwh,
            "air_to_water_annual_cost_eur": air_to_water_cost,
            "air_to_water_annual_savings_eur": air_to_water_savings,
            "air_to_water_payback_years": self.calculate_payback(UPGRADE_TARGETS["Air-to-Water Heat Pump"]["capex_eur"], air_to_water_savings),
            "ground_source_capex_eur": UPGRADE_TARGETS["Ground-Source Heat Pump"]["capex_eur"],
            "ground_source_proposed_input_kwh": ground_source_input_kwh,
            "ground_source_annual_cost_eur": ground_source_cost,
            "ground_source_annual_savings_eur": ground_source_savings,
            "ground_source_payback_years": self.calculate_payback(UPGRADE_TARGETS["Ground-Source Heat Pump"]["capex_eur"], ground_source_savings),
        }

    def solve_upgrade_optimization(self, row: pd.Series) -> pd.Series:
        targets = ["Air-to-Water Heat Pump", "Ground-Source Heat Pump"]
        lifecycle_costs = np.array(
            [
                float(row["air_to_water_capex_eur"]) + (float(row["air_to_water_annual_cost_eur"]) * self.config.lifecycle_years),
                float(row["ground_source_capex_eur"]) + (float(row["ground_source_annual_cost_eur"]) * self.config.lifecycle_years),
            ],
            dtype=float,
        )

        def objective(weights: np.ndarray) -> float:
            return float(np.dot(weights, lifecycle_costs))

        solution = optimize.minimize(
            objective,
            x0=np.array([0.5, 0.5], dtype=float),
            method="SLSQP",
            bounds=[(0.0, 1.0), (0.0, 1.0)],
            constraints=[{"type": "eq", "fun": lambda weights: float(weights.sum() - 1.0)}],
            options={"ftol": 1e-9, "maxiter": 100, "disp": False},
        )

        if solution.success:
            chosen_index = int(np.argmax(solution.x))
            optimizer_success = True
        else:
            chosen_index = int(np.argmin(lifecycle_costs))
            optimizer_success = False

        if chosen_index == 0:
            annual_cost = float(row["air_to_water_annual_cost_eur"])
            annual_savings = float(row["air_to_water_annual_savings_eur"])
            capex = float(row["air_to_water_capex_eur"])
            payback = float(row["air_to_water_payback_years"])
            input_kwh = float(row["air_to_water_proposed_input_kwh"])
        else:
            annual_cost = float(row["ground_source_annual_cost_eur"])
            annual_savings = float(row["ground_source_annual_savings_eur"])
            capex = float(row["ground_source_capex_eur"])
            payback = float(row["ground_source_payback_years"])
            input_kwh = float(row["ground_source_proposed_input_kwh"])

        return pd.Series(
            {
                "best_upgrade_target": targets[chosen_index],
                "best_lifecycle_cost_eur": lifecycle_costs[chosen_index],
                "best_capex_eur": capex,
                "best_proposed_annual_cost_eur": annual_cost,
                "best_proposed_input_kwh": input_kwh,
                "best_annual_savings_eur": annual_savings,
                "best_payback_years": payback,
                "scipy_optimizer_success": optimizer_success,
            }
        )

    def calculate_payback(self, capex_eur: float, annual_savings_eur: float) -> float:
        if annual_savings_eur <= 0:
            return float("inf")
        return float(capex_eur / annual_savings_eur)

    def normalize_heating_system(self, value: str) -> str:
        text = self.normalize_estonian_text(value)
        if "kaug" in text or "district" in text:
            return "district_heating"
        if "gaas" in text or "gas" in text:
            return "gas_boiler"
        if "otseelekter" in text or "elektriradiaator" in text or "direct electric" in text or "radiator" in text:
            return "direct_electric"
        if ("ohk vesi" in text) or ("ohk-vesi" in text) or ("air to water" in text) or ("air-to-water" in text):
            return "air_to_water_heat_pump"
        if ("ohk ohk" in text) or ("ohk-ohk" in text) or ("air to air" in text) or ("air-to-air" in text):
            return "air_to_air_heat_pump"
        if "maakute" in text or "maasoojus" in text or "ground" in text:
            return "ground_source_heat_pump"
        self.logger.warning("Unknown heating source '%s'; treating as direct electric resistance", value)
        return "direct_electric"

    def normalize_estonian_text(self, value: str) -> str:
        text = str(value).strip().lower()
        translations = str.maketrans({"õ": "o", "ä": "a", "ö": "o", "ü": "u", "š": "s", "ž": "z"})
        text = text.translate(translations)
        text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
        text = text.replace("/", " ").replace("_", " ").replace(",", " ")
        return " ".join(text.split())


def read_ehr_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, dtype={"ehr_kood": str, "ads_adr_id": str})
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(path)
    if suffix in {".json", ".jsonl"}:
        return pd.read_json(path, lines=suffix == ".jsonl")
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, dtype={"ehr_kood": str, "ads_adr_id": str})
    raise ValueError(f"Unsupported EHR input format: {path.suffix}")


def read_temperature_array(path: Path) -> np.ndarray:
    suffix = path.suffix.lower()
    if suffix == ".npy":
        return np.load(path)
    if suffix == ".csv":
        frame = pd.read_csv(path)
        numeric = frame.select_dtypes(include=[np.number])
        if numeric.empty:
            raise ValueError("Temperature CSV must contain at least one numeric column")
        return numeric.iloc[:, 0].to_numpy(dtype=float)
    if suffix in {".parquet", ".pq"}:
        frame = pd.read_parquet(path)
        numeric = frame.select_dtypes(include=[np.number])
        if numeric.empty:
            raise ValueError("Temperature parquet must contain at least one numeric column")
        return numeric.iloc[:, 0].to_numpy(dtype=float)
    if suffix in {".json", ".jsonl"}:
        frame = pd.read_json(path, lines=suffix == ".jsonl")
        numeric = frame.select_dtypes(include=[np.number])
        if numeric.empty:
            raise ValueError("Temperature JSON must contain at least one numeric column")
        return numeric.iloc[:, 0].to_numpy(dtype=float)
    raise ValueError(f"Unsupported temperature input format: {path.suffix}")


def write_output(gdf: gpd.GeoDataFrame, path: Path, layer: str) -> None:
    suffix = path.suffix.lower()
    path.parent.mkdir(parents=True, exist_ok=True)
    if suffix == ".gpkg":
        gdf.to_file(path, layer=layer, driver="GPKG")
        return
    if suffix in {".geojson", ".json"}:
        gdf.to_file(path, driver="GeoJSON")
        return
    if suffix in {".parquet", ".pq"}:
        gdf.to_parquet(path, index=False)
        return
    if suffix == ".csv":
        frame = pd.DataFrame(gdf.drop(columns="geometry"))
        frame["geometry_wkt_epsg_3301"] = gdf.geometry.to_wkt()
        frame.to_csv(path, index=False)
        return
    raise ValueError(f"Unsupported output format: {path.suffix}")


def build_argument_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="energy_transition_processor", description="Process Estonian EHR and Maa-amet spatial building data for heating transition optimization")
    parser.add_argument("--ehr", required=True, type=Path, help="Path to EHR table: csv, parquet, json, jsonl, xlsx")
    parser.add_argument("--maa-amet", required=True, type=Path, help="Path to Maa-amet/ETAK/Geo3D vector file readable by GeoPandas")
    parser.add_argument("--temperatures", required=True, type=Path, help="Path to 8,760 hourly outdoor temperatures: npy, csv, parquet, json")
    parser.add_argument("--output", required=True, type=Path, help="Output file: gpkg, geojson, parquet, csv")
    parser.add_argument("--layer", default="heating_transition_optimization", help="GeoPackage layer name")
    parser.add_argument("--inside-temperature", default=BASELINE_INSIDE_TEMPERATURE_C, type=float, help="Indoor baseline temperature in Celsius")
    parser.add_argument("--lifecycle-years", default=HARDWARE_LIFECYCLE_YEARS, type=float, help="Hardware lifecycle threshold in years")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"], help="Logging level")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_argument_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(level=getattr(logging, args.log_level), format="%(asctime)s %(levelname)s %(name)s %(message)s")

    ehr_dataframe = read_ehr_table(args.ehr)
    maa_amet_geometries = gpd.read_file(args.maa_amet)
    outdoor_temperatures = read_temperature_array(args.temperatures)
    processor = EstonianHeatingTransitionProcessor(
        ProcessingConfig(
            inside_temperature_c=args.inside_temperature,
            lifecycle_years=args.lifecycle_years,
            target_crs_epsg=EPSG_ESTONIAN_NATIONAL_GRID,
        )
    )
    result = processor.run(ehr_dataframe, maa_amet_geometries, outdoor_temperatures)
    write_output(result, args.output, args.layer)
    LOGGER.info("Wrote %s optimized building records to %s", len(result), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
