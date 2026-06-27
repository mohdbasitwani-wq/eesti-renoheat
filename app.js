const ENERGY_LABEL_DEMAND = {
  A: 45,
  B: 75,
  C: 95,
  D: 130,
  E: 180,
  F: 220,
  G: 260,
  H: 320,
};

const UTILITY_TARIFFS_EUR_PER_KWH = {
  electricity: 0.18,
  districtHeating: 0.08,
  naturalGas: 0.07,
};

const ENERGY_TYPE_EMISSIONS_KG_PER_KWH = {
  electricity: 0.35,
  districtHeating: 0.11,
  naturalGas: 0.202,
};

const HEATING_SYSTEMS = {
  "District Heating": {
    canonicalName: "District Heating",
    localName: "Kaugküte",
    scop: 0.95,
    energyType: "districtHeating",
    installCost: 5000,
  },
  "Gas Boiler": {
    canonicalName: "Gas Boiler",
    localName: "Gaasiküte",
    scop: 0.88,
    energyType: "naturalGas",
    installCost: null,
  },
  "Electricity/Radiators": {
    canonicalName: "Electricity/Radiators",
    localName: "Otseelekter",
    scop: 1,
    energyType: "electricity",
    installCost: null,
  },
  "Air-to-Air Heat Pump": {
    canonicalName: "Air-to-Air Heat Pump",
    localName: "Õhk-õhk soojuspump",
    scop: 2.8,
    energyType: "electricity",
    installCost: null,
  },
  "Air-to-Water Heat Pump": {
    canonicalName: "Air-to-Water Heat Pump",
    localName: "Õhk-vesi soojuspump",
    scop: 3.4,
    energyType: "electricity",
    installCost: 8500,
  },
  "Ground-Source Heat Pump": {
    canonicalName: "Ground-Source Heat Pump",
    localName: "Maaküte",
    scop: 4.2,
    energyType: "electricity",
    installCost: 13000,
  },
};

const UPGRADE_OPTIONS = [
  "Air-to-Water Heat Pump",
  "Ground-Source Heat Pump",
  "District Heating",
];

const ESTONIAN_BUILDING_DATASET = [
  {
    ehr_kood: "101023456",
    address: "Koidu 42, Tallinn, 10143",
    omavalitsus: "Tallinna linn",
    suletud_netopind: 142.5,
    soojusallikas: "Gaasiküte",
    energiatohususklass: "E",
    lat: null,
    lon: null,
    est_volume_m3: 427,
    geolocation: {
      accuracy: "unresolved",
      source: "Maa-amet In-ADS Gazetteer returned no address record for Koidu 42 variants checked on 2026-06-24",
      service: "https://inaadress.maaamet.ee/inaadress/gazetteer",
      quality: "not_found",
      ads_oid: null,
      adr_id: null,
      boundingbox: null,
    },
  },
  {
    ehr_kood: "102098765",
    address: "Vaksali 17, Tartu, 50410",
    omavalitsus: "Tartu linn",
    suletud_netopind: 85,
    soojusallikas: "Otseelekter",
    energiatohususklass: "F",
    lat: 58.372612,
    lon: 26.709876,
    est_volume_m3: 255,
    geolocation: {
      accuracy: "building",
      source: "Maa-amet In-ADS Gazetteer EHITISHOONE result",
      service: "https://inaadress.maaamet.ee/inaadress/gazetteer",
      quality: "tapne_nr",
      ads_oid: "ME00750651",
      adr_id: "3062467",
      adob_id: "9979012",
      viitepunkt_x: 658523.03,
      viitepunkt_y: 6473437.51,
      boundingbox: [58.3724650361, 58.3727494783, 26.7095910618, 26.7101602693],
    },
  },
  {
    ehr_kood: "103055441",
    address: "Mai 23, Pärnu, 80024",
    omavalitsus: "Pärnu linn",
    suletud_netopind: 210,
    soojusallikas: "Kaugküte",
    energiatohususklass: "C",
    lat: 58.37193,
    lon: 24.534157,
    est_volume_m3: 630,
    geolocation: {
      accuracy: "building",
      source: "Maa-amet In-ADS Gazetteer EHITISHOONE result",
      service: "https://inaadress.maaamet.ee/inaadress/gazetteer",
      quality: "tapne_nr",
      ads_oid: "EE00704868",
      adr_id: "3099999",
      adob_id: "8757470",
      viitepunkt_x: 531256.2,
      viitepunkt_y: 6470284.03,
      boundingbox: [58.3716532746, 58.3722071307, 24.5338276756, 24.5345025845],
    },
  },
];

const ENERGY_BADGE_CLASSES = {
  A: "bg-emerald-500 text-white",
  B: "bg-lime-500 text-zinc-950",
  C: "bg-yellow-300 text-zinc-950",
  D: "bg-amber-400 text-zinc-950",
  E: "bg-orange-500 text-white",
  F: "bg-red-500 text-white",
  G: "bg-rose-700 text-white",
  H: "bg-zinc-900 text-white",
};

const appState = {
  selectedBuilding: ESTONIAN_BUILDING_DATASET[0],
  selectedEnergyLabel: ESTONIAN_BUILDING_DATASET[0].energiatohususklass,
  netAreaOverride: ESTONIAN_BUILDING_DATASET[0].suletud_netopind,
  winterBaselinePercent: 100,
  selectedUpgrade: UPGRADE_OPTIONS[0],
  map: null,
  markersByEhrCode: new Map(),
};

const dom = {};

document.addEventListener("DOMContentLoaded", () => {
  cacheDomNodes();
  populateUpgradeOptions();
  renderEnergyLabelButtons();
  bindInterfaceEvents();
  initializeMap();
  loadBuilding(ESTONIAN_BUILDING_DATASET[0].ehr_kood);
});

function cacheDomNodes() {
  dom.searchInput = document.querySelector("#building-search");
  dom.autocompleteResults = document.querySelector("#autocomplete-results");
  dom.buildingAddress = document.querySelector("#building-address");
  dom.buildingMunicipality = document.querySelector("#building-municipality");
  dom.energyBadge = document.querySelector("#energy-badge");
  dom.ehrCode = document.querySelector("#ehr-code");
  dom.netAreaReadout = document.querySelector("#net-area-readout");
  dom.heatingSource = document.querySelector("#heating-source");
  dom.buildingVolume = document.querySelector("#building-volume");
  dom.geolocationAccuracy = document.querySelector("#geolocation-accuracy");
  dom.geolocationCoordinates = document.querySelector("#geolocation-coordinates");
  dom.geolocationSource = document.querySelector("#geolocation-source");
  dom.netAreaSlider = document.querySelector("#net-area-slider");
  dom.netAreaOutput = document.querySelector("#net-area-output");
  dom.winterBaselineSlider = document.querySelector("#winter-baseline-slider");
  dom.winterBaselineOutput = document.querySelector("#winter-baseline-output");
  dom.energyLabelButtons = document.querySelector("#energy-label-buttons");
  dom.demandReadout = document.querySelector("#demand-readout");
  dom.upgradeSelector = document.querySelector("#upgrade-selector");
  dom.currentAnnualCost = document.querySelector("#current-annual-cost");
  dom.newAnnualCost = document.querySelector("#new-annual-cost");
  dom.carbonSavings = document.querySelector("#carbon-savings");
  dom.investmentCost = document.querySelector("#investment-cost");
  dom.paybackPeriod = document.querySelector("#payback-period");
  dom.annualSavings = document.querySelector("#annual-savings");
  dom.annualDemand = document.querySelector("#annual-demand");
  dom.currentEnergyInput = document.querySelector("#current-energy-input");
  dom.newEnergyInput = document.querySelector("#new-energy-input");
  dom.mapStatus = document.querySelector("#map-status");
}

function populateUpgradeOptions() {
  dom.upgradeSelector.innerHTML = UPGRADE_OPTIONS.map((optionName) => {
    const system = HEATING_SYSTEMS[optionName];
    return `<option value="${optionName}">${system.canonicalName}</option>`;
  }).join("");
  dom.upgradeSelector.value = appState.selectedUpgrade;
}

function renderEnergyLabelButtons() {
  dom.energyLabelButtons.innerHTML = Object.keys(ENERGY_LABEL_DEMAND)
    .map((energyLabel) => {
      const badgeClass = ENERGY_BADGE_CLASSES[energyLabel];
      return `
        <button
          type="button"
          class="energy-label-button h-10 rounded-md border border-zinc-200 text-sm font-black shadow-sm transition hover:-translate-y-0.5 focus:outline-none focus:ring-2 focus:ring-teal-200 ${badgeClass}"
          data-energy-label="${energyLabel}"
          aria-label="Use energy label ${energyLabel}"
        >
          ${energyLabel}
        </button>
      `;
    })
    .join("");
}

function bindInterfaceEvents() {
  dom.searchInput.addEventListener("input", handleSearchInput);
  dom.searchInput.addEventListener("keydown", handleSearchKeyboard);
  dom.searchInput.addEventListener("focus", handleSearchInput);

  document.addEventListener("click", (event) => {
    if (!event.target.closest("#building-search") && !event.target.closest("#autocomplete-results")) {
      hideAutocomplete();
    }
  });

  dom.autocompleteResults.addEventListener("click", (event) => {
    const resultButton = event.target.closest("[data-ehr-code]");
    if (!resultButton) return;
    loadBuilding(resultButton.dataset.ehrCode);
    hideAutocomplete();
  });

  dom.netAreaSlider.addEventListener("input", () => {
    appState.netAreaOverride = Number(dom.netAreaSlider.value);
    updateDashboard();
  });

  dom.winterBaselineSlider.addEventListener("input", () => {
    appState.winterBaselinePercent = Number(dom.winterBaselineSlider.value);
    updateDashboard();
  });

  dom.energyLabelButtons.addEventListener("click", (event) => {
    const energyButton = event.target.closest("[data-energy-label]");
    if (!energyButton) return;
    appState.selectedEnergyLabel = energyButton.dataset.energyLabel;
    updateDashboard();
  });

  dom.upgradeSelector.addEventListener("change", () => {
    appState.selectedUpgrade = dom.upgradeSelector.value;
    updateDashboard();
  });
}

function initializeMap() {
  if (!window.L) {
    dom.mapStatus.textContent = "Map library unavailable";
    return;
  }

  appState.map = L.map("map", {
    scrollWheelZoom: false,
  }).setView([58.6, 25], 7);

  L.tileLayer
    .wms("https://kaart.maaamet.ee/wms/alus-geo", {
      layers: "pohi_vr2",
      format: "image/png",
      transparent: false,
      version: "1.1.1",
      attribution: "&copy; Maa-amet",
    })
    .addTo(appState.map);

  ESTONIAN_BUILDING_DATASET.forEach((building) => {
    drawGeoportalBuilding(building);
  });

  const resolvedCount = ESTONIAN_BUILDING_DATASET.filter(hasCoordinates).length;
  dom.mapStatus.textContent = `${resolvedCount} In-ADS address matches, ${
    ESTONIAN_BUILDING_DATASET.length - resolvedCount
  } unresolved sample address`;
}

function drawGeoportalBuilding(building) {
  if (!hasCoordinates(building)) return;

  if (building.geolocation?.boundingbox) {
    const footprint = L.rectangle(getLeafletBoundsFromBoundingBox(building.geolocation.boundingbox), {
      color: "#0f766e",
      weight: 1,
      fillColor: "#14b8a6",
      fillOpacity: 0.16,
    }).addTo(appState.map);

    footprint.on("click", () => {
      loadBuilding(building.ehr_kood, { focusMap: false, openPopup: true });
    });
  }

  const marker = L.circleMarker([building.lat, building.lon], {
    radius: 8,
    color: "#0f766e",
    weight: 2,
    fillColor: "#14b8a6",
    fillOpacity: 0.86,
  })
    .addTo(appState.map)
    .bindPopup(renderLocationPopup(building));

  marker.on("click", () => {
    loadBuilding(building.ehr_kood, { focusMap: false, openPopup: false });
  });

  appState.markersByEhrCode.set(building.ehr_kood, marker);
}

function renderLocationPopup(building) {
  return `
    <strong>${building.address}</strong><br />
    EHR ${building.ehr_kood}<br />
    ${getGeolocationAccuracyLabel(building)}<br />
    ADS OID ${building.geolocation.ads_oid}<br />
    ${building.lat.toFixed(6)}, ${building.lon.toFixed(6)}
  `;
}

function getLeafletBoundsFromBoundingBox(boundingbox) {
  const [south, north, west, east] = boundingbox;
  return [
    [south, west],
    [north, east],
  ];
}

function handleSearchInput() {
  const query = dom.searchInput.value.trim().toLowerCase();
  const matches = ESTONIAN_BUILDING_DATASET.filter((building) => {
    return (
      building.address.toLowerCase().includes(query) ||
      building.ehr_kood.includes(query) ||
      building.omavalitsus.toLowerCase().includes(query)
    );
  });

  renderAutocomplete(matches, query);
}

function handleSearchKeyboard(event) {
  if (event.key !== "Enter") return;

  const firstResult = dom.autocompleteResults.querySelector("[data-ehr-code]");
  if (firstResult) {
    event.preventDefault();
    loadBuilding(firstResult.dataset.ehrCode);
    hideAutocomplete();
  }
}

function renderAutocomplete(matches, query) {
  const visibleMatches = query ? matches : ESTONIAN_BUILDING_DATASET;

  if (!visibleMatches.length) {
    dom.autocompleteResults.innerHTML = `
      <div class="px-4 py-3 text-sm font-medium text-zinc-600">No sample buildings found</div>
    `;
    dom.autocompleteResults.classList.remove("hidden");
    return;
  }

  dom.autocompleteResults.innerHTML = visibleMatches
    .map((building) => {
      return `
        <button
          type="button"
          class="block w-full border-b border-zinc-100 px-4 py-3 text-left last:border-b-0 hover:bg-teal-50 focus:bg-teal-50 focus:outline-none"
          data-ehr-code="${building.ehr_kood}"
        >
          <span class="block text-sm font-semibold text-zinc-950">${building.address}</span>
          <span class="mt-1 block text-xs font-medium text-zinc-600">EHR ${building.ehr_kood} · ${getGeolocationAccuracyLabel(building)}</span>
        </button>
      `;
    })
    .join("");

  dom.autocompleteResults.classList.remove("hidden");
}

function hideAutocomplete() {
  dom.autocompleteResults.classList.add("hidden");
}

function loadBuilding(ehr_kood, options = {}) {
  const { focusMap = true, openPopup = true } = options;
  const selectedBuilding = ESTONIAN_BUILDING_DATASET.find((building) => building.ehr_kood === ehr_kood);
  if (!selectedBuilding) return;

  appState.selectedBuilding = selectedBuilding;
  appState.selectedEnergyLabel = selectedBuilding.energiatohususklass;
  appState.netAreaOverride = selectedBuilding.suletud_netopind;
  appState.winterBaselinePercent = 100;

  dom.searchInput.value = selectedBuilding.address;
  dom.netAreaSlider.value = String(selectedBuilding.suletud_netopind);
  dom.winterBaselineSlider.value = "100";

  if (appState.map && focusMap) {
    focusBuildingOnMap(selectedBuilding);
  }

  const selectedMarker = appState.markersByEhrCode.get(selectedBuilding.ehr_kood);
  if (selectedMarker && openPopup) {
    selectedMarker.openPopup();
  }

  updateDashboard();
}

function focusBuildingOnMap(building) {
  if (!hasCoordinates(building)) {
    appState.map.setView([58.6, 25], 7);
    return;
  }

  if (building.geolocation?.boundingbox) {
    appState.map.fitBounds(getLeafletBoundsFromBoundingBox(building.geolocation.boundingbox), {
      maxZoom: 18,
      padding: [40, 40],
    });
    return;
  }

  appState.map.setView([building.lat, building.lon], 17);
}

function updateDashboard() {
  const building = appState.selectedBuilding;
  const currentSystem = getHeatingSystemFromSource(building.soojusallikas);
  const upgradeSystem = HEATING_SYSTEMS[appState.selectedUpgrade];
  const calculation = calculateUpgradeScenario({
    suletud_netopind: appState.netAreaOverride,
    energyLabel: appState.selectedEnergyLabel,
    winterBaselinePercent: appState.winterBaselinePercent,
    currentSystem,
    upgradeSystem,
  });

  dom.buildingAddress.textContent = building.address;
  dom.buildingMunicipality.textContent = building.omavalitsus;
  dom.ehrCode.textContent = building.ehr_kood;
  dom.netAreaReadout.textContent = `${formatNumber(appState.netAreaOverride, 1)} m²`;
  dom.heatingSource.textContent = currentSystem.localName;
  dom.buildingVolume.textContent = `${formatNumber(building.est_volume_m3, 0)} m³`;
  dom.geolocationAccuracy.textContent = getGeolocationAccuracyLabel(building);
  dom.geolocationCoordinates.textContent = formatCoordinates(building);
  dom.geolocationSource.textContent = getGeolocationSourceText(building);
  dom.netAreaOutput.textContent = `${formatNumber(appState.netAreaOverride, 1)} m²`;
  dom.winterBaselineOutput.textContent = `${formatNumber(appState.winterBaselinePercent, 0)}%`;
  dom.demandReadout.textContent = `${ENERGY_LABEL_DEMAND[appState.selectedEnergyLabel]} kWh/m²/year`;
  dom.upgradeSelector.value = appState.selectedUpgrade;

  renderSelectedEnergyBadge(appState.selectedEnergyLabel);
  updateEnergyLabelButtonState(appState.selectedEnergyLabel);

  dom.currentAnnualCost.textContent = formatEuro(calculation.currentAnnualCost);
  dom.newAnnualCost.textContent = formatEuro(calculation.upgradeAnnualCost);
  dom.carbonSavings.textContent = formatTonnes(calculation.annualCarbonSavingsKg);
  dom.investmentCost.textContent = formatEuro(calculation.installationCost);
  dom.paybackPeriod.textContent = formatPayback(calculation.paybackYears);
  dom.annualSavings.textContent = `${formatEuro(calculation.annualSavings)} annual savings`;
  dom.annualDemand.textContent = `${formatNumber(calculation.annualDemandKwh, 0)} kWh/year`;
  dom.currentEnergyInput.textContent = `${formatNumber(calculation.currentPurchasedEnergyKwh, 0)} kWh/year`;
  dom.newEnergyInput.textContent = `${formatNumber(calculation.upgradePurchasedEnergyKwh, 0)} kWh/year`;
}

function calculateUpgradeScenario({
  suletud_netopind,
  energyLabel,
  winterBaselinePercent,
  currentSystem,
  upgradeSystem,
}) {
  const baselineMultiplier = winterBaselinePercent / 100;
  const annualDemandKwh = suletud_netopind * ENERGY_LABEL_DEMAND[energyLabel] * baselineMultiplier;
  const currentPurchasedEnergyKwh = annualDemandKwh / currentSystem.scop;
  const upgradePurchasedEnergyKwh = annualDemandKwh / upgradeSystem.scop;
  const currentAnnualCost =
    currentPurchasedEnergyKwh * UTILITY_TARIFFS_EUR_PER_KWH[currentSystem.energyType];
  const upgradeAnnualCost =
    upgradePurchasedEnergyKwh * UTILITY_TARIFFS_EUR_PER_KWH[upgradeSystem.energyType];
  const installationCost = upgradeSystem.installCost;
  const annualSavings = currentAnnualCost - upgradeAnnualCost;
  const paybackYears = annualSavings > 0 ? installationCost / annualSavings : Infinity;
  const currentCarbonKg =
    currentPurchasedEnergyKwh * ENERGY_TYPE_EMISSIONS_KG_PER_KWH[currentSystem.energyType];
  const upgradeCarbonKg =
    upgradePurchasedEnergyKwh * ENERGY_TYPE_EMISSIONS_KG_PER_KWH[upgradeSystem.energyType];
  const annualCarbonSavingsKg = currentCarbonKg - upgradeCarbonKg;

  return {
    annualDemandKwh,
    currentPurchasedEnergyKwh,
    upgradePurchasedEnergyKwh,
    currentAnnualCost,
    upgradeAnnualCost,
    installationCost,
    annualSavings,
    paybackYears,
    annualCarbonSavingsKg,
  };
}

function getHeatingSystemFromSource(soojusallikas) {
  const normalizedSource = soojusallikas.toLowerCase();

  if (normalizedSource.includes("gaas")) {
    return HEATING_SYSTEMS["Gas Boiler"];
  }

  if (normalizedSource.includes("otseelekter")) {
    return HEATING_SYSTEMS["Electricity/Radiators"];
  }

  if (normalizedSource.includes("kaug")) {
    return HEATING_SYSTEMS["District Heating"];
  }

  if (normalizedSource.includes("õhk-vesi") || normalizedSource.includes("ohk-vesi")) {
    return HEATING_SYSTEMS["Air-to-Water Heat Pump"];
  }

  if (normalizedSource.includes("õhk-õhk") || normalizedSource.includes("ohk-ohk")) {
    return HEATING_SYSTEMS["Air-to-Air Heat Pump"];
  }

  if (normalizedSource.includes("maa")) {
    return HEATING_SYSTEMS["Ground-Source Heat Pump"];
  }

  return HEATING_SYSTEMS["Electricity/Radiators"];
}

function hasCoordinates(building) {
  return Number.isFinite(building.lat) && Number.isFinite(building.lon);
}

function getGeolocationAccuracyLabel(building) {
  if (building.geolocation?.accuracy === "building") {
    return "In-ADS building match";
  }

  if (building.geolocation?.accuracy === "unresolved") {
    return "Not found in In-ADS";
  }

  return "Geoportal status unknown";
}

function formatCoordinates(building) {
  if (!hasCoordinates(building)) {
    return "No official match";
  }

  return `${building.lat.toFixed(5)}, ${building.lon.toFixed(5)}`;
}

function getGeolocationSourceText(building) {
  if (building.geolocation?.accuracy === "building") {
    return `${building.geolocation.source}; quality ${building.geolocation.quality}; ADS OID ${building.geolocation.ads_oid}; ADR ID ${building.geolocation.adr_id}.`;
  }

  return building.geolocation?.source || "No Geoportal source attached.";
}

function renderSelectedEnergyBadge(energyLabel) {
  dom.energyBadge.className = `grid h-16 w-16 shrink-0 place-items-center rounded-md text-3xl font-black shadow-sm ${ENERGY_BADGE_CLASSES[energyLabel]}`;
  dom.energyBadge.textContent = energyLabel;
  dom.energyBadge.setAttribute("aria-label", `Energy label ${energyLabel}`);
}

function updateEnergyLabelButtonState(selectedEnergyLabel) {
  dom.energyLabelButtons.querySelectorAll("[data-energy-label]").forEach((button) => {
    const isSelected = button.dataset.energyLabel === selectedEnergyLabel;
    button.classList.toggle("ring-2", isSelected);
    button.classList.toggle("ring-offset-2", isSelected);
    button.classList.toggle("ring-zinc-950", isSelected);
    button.setAttribute("aria-pressed", String(isSelected));
  });
}

function formatEuro(value) {
  return new Intl.NumberFormat("et-EE", {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatNumber(value, maximumFractionDigits) {
  return new Intl.NumberFormat("et-EE", {
    maximumFractionDigits,
  }).format(value);
}

function formatTonnes(valueKg) {
  const absoluteTonnes = Math.abs(valueKg) / 1000;
  const formatted = `${formatNumber(absoluteTonnes, 1)} tCO₂/year`;
  return valueKg >= 0 ? formatted : `-${formatted}`;
}

function formatPayback(paybackYears) {
  if (!Number.isFinite(paybackYears)) {
    return "No payback";
  }

  if (paybackYears < 1) {
    return "<1 year";
  }

  return `${formatNumber(paybackYears, 1)} years`;
}
