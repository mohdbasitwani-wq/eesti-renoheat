const ENERGY_LABEL_DEMAND = { A: 45, B: 75, C: 95, D: 130, E: 180, F: 220, G: 260, H: 320 };
const TARIFFS = { electricity: 0.18, districtHeating: 0.08, naturalGas: 0.07 };
const EMISSIONS = { electricity: 0.35, districtHeating: 0.11, naturalGas: 0.202 };
const SYSTEMS = {
  "District Heating": { localName: "Kaugküte", scop: 0.95, energyType: "districtHeating", installCost: 5000 },
  "Gas Boiler": { localName: "Gaasiküte", scop: 0.88, energyType: "naturalGas", installCost: null },
  "Electricity/Radiators": { localName: "Otseelekter", scop: 1, energyType: "electricity", installCost: null },
  "Air-to-Water Heat Pump": { localName: "Õhk-vesi soojuspump", scop: 3.4, energyType: "electricity", installCost: 8500 },
  "Ground-Source Heat Pump": { localName: "Maaküte", scop: 4.2, energyType: "electricity", installCost: 13000 },
};
const UPGRADE_OPTIONS = ["Air-to-Water Heat Pump", "Ground-Source Heat Pump", "District Heating"];
const BUILDINGS = [
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
    geolocation: { status: "Not found in In-ADS", source: "No official In-ADS match for tested Koidu 42 variants." },
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
    geolocation: { status: "In-ADS building match", source: "Maa-amet In-ADS EHITISHOONE, ADS OID ME00750651.", bounds: [58.3724650361, 58.3727494783, 26.7095910618, 26.7101602693] },
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
    geolocation: { status: "In-ADS building match", source: "Maa-amet In-ADS EHITISHOONE, ADS OID EE00704868.", bounds: [58.3716532746, 58.3722071307, 24.5338276756, 24.5345025845] },
  },
];
const BADGES = { A: "bg-emerald-500 text-white", B: "bg-lime-500 text-zinc-950", C: "bg-yellow-300 text-zinc-950", D: "bg-amber-400 text-zinc-950", E: "bg-orange-500 text-white", F: "bg-red-500 text-white", G: "bg-rose-700 text-white", H: "bg-zinc-900 text-white" };
const state = { building: BUILDINGS[1], label: BUILDINGS[1].energiatohususklass, area: BUILDINGS[1].suletud_netopind, winter: 100, upgrade: UPGRADE_OPTIONS[0], map: null, markers: new Map(), batchLayer: null };
const $ = (selector) => document.querySelector(selector);

document.addEventListener("DOMContentLoaded", () => {
  populateUpgradeOptions();
  renderLabelButtons();
  bindEvents();
  initMap();
  loadBuilding(state.building.ehr_kood);
  plotBatchAddresses();
});

function populateUpgradeOptions() {
  $("#upgrade-selector").innerHTML = UPGRADE_OPTIONS.map((name) => `<option value="${name}">${name}</option>`).join("");
  $("#upgrade-selector").value = state.upgrade;
}

function renderLabelButtons() {
  $("#energy-label-buttons").innerHTML = Object.keys(ENERGY_LABEL_DEMAND).map((label) => `<button type="button" data-energy-label="${label}" class="h-10 rounded-md border border-zinc-200 text-sm font-black shadow-sm ${BADGES[label]}">${label}</button>`).join("");
}

function bindEvents() {
  $("#building-search").addEventListener("input", searchBuildings);
  $("#building-search").addEventListener("focus", searchBuildings);
  $("#autocomplete-results").addEventListener("click", (event) => {
    const button = event.target.closest("[data-ehr-code]");
    if (button) loadBuilding(button.dataset.ehrCode);
    $("#autocomplete-results").classList.add("hidden");
  });
  $("#net-area-slider").addEventListener("input", () => { state.area = Number($("#net-area-slider").value); update(); });
  $("#winter-baseline-slider").addEventListener("input", () => { state.winter = Number($("#winter-baseline-slider").value); update(); });
  $("#energy-label-buttons").addEventListener("click", (event) => {
    const button = event.target.closest("[data-energy-label]");
    if (!button) return;
    state.label = button.dataset.energyLabel;
    update();
  });
  $("#upgrade-selector").addEventListener("change", () => { state.upgrade = $("#upgrade-selector").value; update(); });
  $("#batch-plot-button").addEventListener("click", plotBatchAddresses);
}

function initMap() {
  if (!window.L) {
    $("#map-status").textContent = "Leaflet did not load.";
    return;
  }
  state.map = L.map("map", { scrollWheelZoom: false }).setView([58.6, 25], 7);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "&copy; OpenStreetMap contributors; address attributes from Maa-amet In-ADS samples",
  }).addTo(state.map);
  state.batchLayer = L.layerGroup().addTo(state.map);
  BUILDINGS.filter(hasCoords).forEach((building) => {
    drawBuilding(building, true);
  });
  $("#map-status").textContent = "Visible OpenStreetMap basemap loaded; official In-ADS sample coordinates plotted.";
}

function drawBuilding(building, permanent) {
  if (!hasCoords(building) || !state.map) return null;
  if (building.geolocation.bounds) {
    L.rectangle(boundsToLeaflet(building.geolocation.bounds), { color: "#0f766e", weight: 1, fillColor: "#14b8a6", fillOpacity: 0.14 }).addTo(permanent ? state.map : state.batchLayer);
  }
  const marker = L.circleMarker([building.lat, building.lon], { radius: 8, color: "#0f766e", weight: 2, fillColor: "#14b8a6", fillOpacity: 0.9 })
    .addTo(permanent ? state.map : state.batchLayer)
    .bindPopup(`<strong>${building.address}</strong><br>EHR ${building.ehr_kood}<br>${building.geolocation.status}<br>${building.lat.toFixed(6)}, ${building.lon.toFixed(6)}`);
  marker.on("click", () => loadBuilding(building.ehr_kood));
  if (permanent) state.markers.set(building.ehr_kood, marker);
  return marker;
}

function searchBuildings() {
  const query = normalize($("#building-search").value);
  const matches = BUILDINGS.filter((building) => [building.address, building.ehr_kood, building.omavalitsus].some((value) => normalize(value).includes(query)));
  $("#autocomplete-results").innerHTML = matches.map((building) => `<button type="button" data-ehr-code="${building.ehr_kood}" class="block w-full border-b border-zinc-100 px-4 py-3 text-left last:border-b-0 hover:bg-teal-50"><span class="block text-sm font-semibold text-zinc-950">${building.address}</span><span class="mt-1 block text-xs font-medium text-zinc-600">${building.geolocation.status}</span></button>`).join("");
  $("#autocomplete-results").classList.toggle("hidden", !matches.length);
}

function loadBuilding(ehrCode) {
  const building = BUILDINGS.find((item) => item.ehr_kood === ehrCode);
  if (!building) return;
  state.building = building;
  state.label = building.energiatohususklass;
  state.area = building.suletud_netopind;
  state.winter = 100;
  $("#building-search").value = building.address;
  $("#net-area-slider").value = String(building.suletud_netopind);
  $("#winter-baseline-slider").value = "100";
  if (state.map && hasCoords(building)) {
    if (building.geolocation.bounds) state.map.fitBounds(boundsToLeaflet(building.geolocation.bounds), { maxZoom: 18, padding: [44, 44] });
    else state.map.setView([building.lat, building.lon], 16);
    state.markers.get(ehrCode)?.openPopup();
  }
  update();
}

function update() {
  const currentSystem = systemFromSource(state.building.soojusallikas);
  const upgradeSystem = SYSTEMS[state.upgrade];
  const calc = calculateScenario(currentSystem, upgradeSystem);
  $("#building-address").textContent = state.building.address;
  $("#building-municipality").textContent = state.building.omavalitsus;
  $("#ehr-code").textContent = state.building.ehr_kood;
  $("#net-area-readout").textContent = `${formatNumber(state.area, 1)} m²`;
  $("#heating-source").textContent = currentSystem.localName;
  $("#building-volume").textContent = `${formatNumber(state.building.est_volume_m3, 0)} m³`;
  $("#geolocation-accuracy").textContent = state.building.geolocation.status;
  $("#geolocation-coordinates").textContent = hasCoords(state.building) ? `${state.building.lat.toFixed(5)}, ${state.building.lon.toFixed(5)}` : "No official coordinate";
  $("#geolocation-source").textContent = state.building.geolocation.source;
  $("#net-area-output").textContent = `${formatNumber(state.area, 1)} m²`;
  $("#winter-baseline-output").textContent = `${formatNumber(state.winter, 0)}%`;
  $("#demand-readout").textContent = `${ENERGY_LABEL_DEMAND[state.label]} kWh/m²/year`;
  $("#energy-badge").className = `grid h-16 w-16 shrink-0 place-items-center rounded-md text-3xl font-black shadow-sm ${BADGES[state.label]}`;
  $("#energy-badge").textContent = state.label;
  $("#current-annual-cost").textContent = formatEuro(calc.currentCost);
  $("#new-annual-cost").textContent = formatEuro(calc.newCost);
  $("#carbon-savings").textContent = `${formatNumber(calc.carbonSavingsKg / 1000, 1)} tCO₂/year`;
  $("#investment-cost").textContent = formatEuro(calc.installCost);
  $("#payback-period").textContent = Number.isFinite(calc.payback) ? `${formatNumber(calc.payback, 1)} years` : "No payback";
  $("#annual-savings").textContent = `${formatEuro(calc.savings)} annual savings`;
  $("#annual-demand").textContent = `${formatNumber(calc.demand, 0)} kWh/year`;
  $("#current-energy-input").textContent = `${formatNumber(calc.currentInput, 0)} kWh/year`;
  $("#new-energy-input").textContent = `${formatNumber(calc.newInput, 0)} kWh/year`;
}

function plotBatchAddresses() {
  if (!state.map) return;
  state.batchLayer.clearLayers();
  const lines = $("#batch-addresses").value.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  const rows = lines.map((line) => {
    const match = findAddress(line);
    if (!match) return { line, status: "Not in local sample set", building: null };
    if (!hasCoords(match)) return { line, status: "Found, but no official coordinate", building: match };
    drawBuilding(match, false);
    return { line, status: "Plotted", building: match };
  });
  const plotted = rows.filter((row) => row.building && hasCoords(row.building));
  $("#batch-results").innerHTML = rows.map(renderBatchRow).join("");
  if (plotted.length) {
    const bounds = L.latLngBounds(plotted.map((row) => [row.building.lat, row.building.lon]));
    state.map.fitBounds(bounds.pad(0.35), { maxZoom: 15 });
  }
}

function renderBatchRow(row) {
  const color = row.status === "Plotted" ? "text-teal-800 bg-teal-50 border-teal-200" : "text-amber-900 bg-amber-50 border-amber-200";
  const detail = row.building ? `${row.building.address} · ${row.building.geolocation.status}` : row.line;
  return `<div class="rounded-md border px-3 py-2 ${color}"><strong>${row.status}</strong><span class="block">${detail}</span></div>`;
}

function findAddress(input) {
  const query = normalize(input);
  return BUILDINGS.find((building) => normalize(building.address).includes(query) || query.includes(normalize(building.address).replace(/,\s*\d+$/, "")) || normalize(building.ehr_kood) === query);
}

function calculateScenario(currentSystem, upgradeSystem) {
  const demand = state.area * ENERGY_LABEL_DEMAND[state.label] * (state.winter / 100);
  const currentInput = demand / currentSystem.scop;
  const newInput = demand / upgradeSystem.scop;
  const currentCost = currentInput * TARIFFS[currentSystem.energyType];
  const newCost = newInput * TARIFFS[upgradeSystem.energyType];
  const savings = currentCost - newCost;
  return {
    demand,
    currentInput,
    newInput,
    currentCost,
    newCost,
    savings,
    installCost: upgradeSystem.installCost,
    payback: savings > 0 ? upgradeSystem.installCost / savings : Infinity,
    carbonSavingsKg: currentInput * EMISSIONS[currentSystem.energyType] - newInput * EMISSIONS[upgradeSystem.energyType],
  };
}

function systemFromSource(source) {
  const text = normalize(source);
  if (text.includes("gaasi")) return SYSTEMS["Gas Boiler"];
  if (text.includes("otseelekter")) return SYSTEMS["Electricity/Radiators"];
  if (text.includes("kaug")) return SYSTEMS["District Heating"];
  return SYSTEMS["Electricity/Radiators"];
}

function boundsToLeaflet(bounds) {
  const [south, north, west, east] = bounds;
  return [[south, west], [north, east]];
}

function hasCoords(building) {
  return Number.isFinite(building.lat) && Number.isFinite(building.lon);
}

function normalize(value) {
  return String(value || "").toLowerCase().normalize("NFD").replace(/\p{Diacritic}/gu, "").replace(/\s+/g, " ").trim();
}

function formatEuro(value) {
  return new Intl.NumberFormat("et-EE", { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(value || 0);
}

function formatNumber(value, maximumFractionDigits) {
  return new Intl.NumberFormat("et-EE", { maximumFractionDigits }).format(value || 0);
}
