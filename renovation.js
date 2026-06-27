const RENOVATION_PACKAGES = {
  light: {
    label: "Light envelope tune-up",
    targetClass: "D/C",
    demandReduction: 0.18,
    costPerM2: 120,
  },
  c: {
    label: "Deep renovation to class C",
    targetClass: "C",
    demandReduction: 0.35,
    costPerM2: 260,
  },
  b: {
    label: "Deep renovation to class B",
    targetClass: "B",
    demandReduction: 0.5,
    costPerM2: 420,
  },
  a: {
    label: "Near-zero renovation to class A",
    targetClass: "A",
    demandReduction: 0.62,
    costPerM2: 620,
  },
};

const RENOVATION_MEASURES = {
  facade: {
    label: "Factory facade insulation",
    costPerM2: 160,
    demandReduction: 0.2,
  },
  roof: {
    label: "Roof insulation",
    costPerM2: 70,
    demandReduction: 0.08,
  },
  windows: {
    label: "Window and door replacement",
    costPerM2: 95,
    demandReduction: 0.1,
  },
  ventilation: {
    label: "Ventilation heat recovery",
    costPerM2: 120,
    demandReduction: 0.15,
  },
  pvBattery: {
    label: "PV roof and battery package",
    costPerM2: 0,
    demandReduction: 0,
  },
  balconies: {
    label: "Balconies and accessibility extras",
    costPerM2: 85,
    demandReduction: 0,
  },
};

const RENOVATION_DEFAULTS = {
  grantPercent: 50,
  loanInterestPercent: 4.2,
  loanTermYears: 20,
};

document.addEventListener("DOMContentLoaded", () => {
  if (!document.querySelector("#renovation-target")) return;
  bindRenovationControls();
  updateRenovationPlanner();
  observeHeatingDashboardChanges();
});

function bindRenovationControls() {
  document.querySelector("#renovation-target").addEventListener("change", updateRenovationPlanner);
  document.querySelector("#renovation-grant").addEventListener("input", updateRenovationPlanner);
  document.querySelector("#renovation-loan-rate").addEventListener("input", updateRenovationPlanner);
  document.querySelector("#renovation-loan-term").addEventListener("input", updateRenovationPlanner);
  document.querySelectorAll("[data-renovation-measure]").forEach((checkbox) => {
    checkbox.addEventListener("change", updateRenovationPlanner);
  });
}

function observeHeatingDashboardChanges() {
  const watchedNodes = [
    "#ehr-code",
    "#net-area-readout",
    "#demand-readout",
    "#current-annual-cost",
    "#new-annual-cost",
    "#annual-demand",
  ]
    .map((selector) => document.querySelector(selector))
    .filter(Boolean);

  let scheduled = false;
  const observer = new MutationObserver(() => {
    if (scheduled) return;
    scheduled = true;
    window.requestAnimationFrame(() => {
      scheduled = false;
      updateRenovationPlanner();
    });
  });

  watchedNodes.forEach((node) => {
    observer.observe(node, { childList: true, characterData: true, subtree: true });
  });
}

function updateRenovationPlanner() {
  const metrics = readDashboardMetrics();
  const controls = readRenovationControls(metrics.netAreaM2);
  const result = calculateRenovationScenario(metrics, controls);
  renderRenovationScenario(metrics, controls, result);
}

function readDashboardMetrics() {
  const netAreaM2 = parseLocalizedNumber(document.querySelector("#net-area-readout")?.textContent) || 0;
  const demandPerM2 = parseLocalizedNumber(document.querySelector("#demand-readout")?.textContent) || 0;
  const currentAnnualCost = parseLocalizedNumber(document.querySelector("#current-annual-cost")?.textContent) || 0;
  const newAnnualCost = parseLocalizedNumber(document.querySelector("#new-annual-cost")?.textContent) || 0;
  const annualDemandKwh =
    parseLocalizedNumber(document.querySelector("#annual-demand")?.textContent) || netAreaM2 * demandPerM2;
  const currentLabel = document.querySelector("#energy-badge")?.textContent?.trim() || "-";
  const ehrCode = document.querySelector("#ehr-code")?.textContent?.trim() || "-";

  return {
    ehrCode,
    netAreaM2,
    demandPerM2,
    annualDemandKwh,
    currentAnnualCost,
    newAnnualCost,
    currentLabel,
  };
}

function readRenovationControls(netAreaM2) {
  const packageKey = document.querySelector("#renovation-target").value;
  const grantPercent = Number(document.querySelector("#renovation-grant").value || RENOVATION_DEFAULTS.grantPercent);
  const loanInterestPercent = Number(document.querySelector("#renovation-loan-rate").value || RENOVATION_DEFAULTS.loanInterestPercent);
  const loanTermYears = Number(document.querySelector("#renovation-loan-term").value || RENOVATION_DEFAULTS.loanTermYears);
  const selectedMeasures = Array.from(document.querySelectorAll("[data-renovation-measure]:checked")).map(
    (input) => input.dataset.renovationMeasure,
  );
  const pvCapacityKw = Math.max(4, Math.min(63, netAreaM2 * 0.12));
  const batteryKwh = Math.max(5, Math.min(30, pvCapacityKw * 0.5));

  return {
    packageKey,
    packageConfig: RENOVATION_PACKAGES[packageKey],
    selectedMeasures,
    grantPercent,
    loanInterestPercent,
    loanTermYears,
    pvCapacityKw,
    batteryKwh,
  };
}

function calculateRenovationScenario(metrics, controls) {
  const selectedMeasureConfigs = controls.selectedMeasures.map((key) => RENOVATION_MEASURES[key]);
  const additiveReduction = selectedMeasureConfigs.reduce((sum, measure) => sum + measure.demandReduction, 0);
  const demandReduction = Math.min(0.78, controls.packageConfig.demandReduction + additiveReduction * 0.45);
  const basePackageCost = metrics.netAreaM2 * controls.packageConfig.costPerM2;
  const measureCost = controls.selectedMeasures.reduce((sum, key) => {
    if (key === "pvBattery") {
      return sum + calculatePvBatteryCost(controls.pvCapacityKw, controls.batteryKwh);
    }
    return sum + metrics.netAreaM2 * RENOVATION_MEASURES[key].costPerM2;
  }, 0);
  const grossInvestment = basePackageCost + measureCost;
  const grantAmount = grossInvestment * (controls.grantPercent / 100);
  const netInvestment = Math.max(0, grossInvestment - grantAmount);
  const renovatedDemandKwh = metrics.annualDemandKwh * (1 - demandReduction);
  const envelopeAnnualCost = metrics.currentAnnualCost * (1 - demandReduction);
  const pvOffset = controls.selectedMeasures.includes("pvBattery")
    ? Math.min(envelopeAnnualCost * 0.32, controls.pvCapacityKw * 850 * 0.18)
    : 0;
  const renovatedAnnualCost = Math.max(0, envelopeAnnualCost - pvOffset);
  const renovationAnnualSavings = Math.max(0, metrics.currentAnnualCost - renovatedAnnualCost);
  const paybackYears = renovationAnnualSavings > 0 ? netInvestment / renovationAnnualSavings : Infinity;
  const monthlyLoanPayment = calculateMonthlyLoanPayment(
    netInvestment,
    controls.loanInterestPercent / 100,
    controls.loanTermYears,
  );
  const combinedHeatingUpgradeBill = Math.max(
    0,
    metrics.newAnnualCost * (1 - demandReduction) - pvOffset * 0.65,
  );
  const combinedAnnualSavings = Math.max(0, metrics.currentAnnualCost - combinedHeatingUpgradeBill);

  return {
    demandReduction,
    grossInvestment,
    grantAmount,
    netInvestment,
    renovatedDemandKwh,
    renovatedAnnualCost,
    renovationAnnualSavings,
    paybackYears,
    monthlyLoanPayment,
    combinedHeatingUpgradeBill,
    combinedAnnualSavings,
    pvOffset,
  };
}

function calculatePvBatteryCost(pvCapacityKw, batteryKwh) {
  const pvCostWithVat = pvCapacityKw * 650 * 1.22;
  const batteryCostWithVat = batteryKwh * 350 * 1.22;
  return roundToNearest(pvCostWithVat + batteryCostWithVat, 1000);
}

function calculateMonthlyLoanPayment(principal, annualRate, years) {
  if (principal <= 0 || years <= 0) return 0;
  const monthlyRate = annualRate / 12;
  const months = years * 12;
  if (monthlyRate === 0) return principal / months;
  return (principal * monthlyRate) / (1 - Math.pow(1 + monthlyRate, -months));
}

function renderRenovationScenario(metrics, controls, result) {
  setText("#renovation-grant-output", `${formatNumber(controls.grantPercent, 0)}%`);
  setText("#renovation-loan-rate-output", `${formatNumber(controls.loanInterestPercent, 1)}%`);
  setText("#renovation-loan-term-output", `${formatNumber(controls.loanTermYears, 0)} years`);
  setText("#renovation-gross-cost", formatEuro(result.grossInvestment));
  setText("#renovation-grant-amount", formatEuro(result.grantAmount));
  setText("#renovation-net-cost", formatEuro(result.netInvestment));
  setText("#renovation-energy-reduction", `${formatNumber(result.demandReduction * 100, 0)}%`);
  setText("#renovation-renovated-demand", `${formatNumber(result.renovatedDemandKwh, 0)} kWh/year`);
  setText("#renovation-renovated-bill", formatEuro(result.renovatedAnnualCost));
  setText("#renovation-annual-savings", `${formatEuro(result.renovationAnnualSavings)} / year`);
  setText("#renovation-payback", Number.isFinite(result.paybackYears) ? `${formatNumber(result.paybackYears, 1)} years` : "No payback");
  setText("#renovation-monthly-loan", `${formatEuro(result.monthlyLoanPayment)} / month`);
  setText("#renovation-combined-bill", formatEuro(result.combinedHeatingUpgradeBill));
  setText("#renovation-combined-savings", `${formatEuro(result.combinedAnnualSavings)} / year`);
  setText("#renovation-target-class", `${metrics.currentLabel} -> ${controls.packageConfig.targetClass}`);
  setText(
    "#renovation-source-note",
    `Assumptions follow the Soft Academy workbook structure: renovation cost, grant support, PV/battery extras, and loan cash-flow are editable inputs.`,
  );
  updateRenovationBars(metrics.currentAnnualCost, result.renovatedAnnualCost, result.combinedHeatingUpgradeBill);
}

function updateRenovationBars(currentAnnualCost, renovatedAnnualCost, combinedHeatingUpgradeBill) {
  const maxCost = Math.max(currentAnnualCost, renovatedAnnualCost, combinedHeatingUpgradeBill, 1);
  setBar("#renovation-bar-current", currentAnnualCost / maxCost);
  setBar("#renovation-bar-envelope", renovatedAnnualCost / maxCost);
  setBar("#renovation-bar-combined", combinedHeatingUpgradeBill / maxCost);
}

function setBar(selector, ratio) {
  const element = document.querySelector(selector);
  if (!element) return;
  element.style.width = `${Math.max(4, Math.min(100, ratio * 100))}%`;
}

function setText(selector, text) {
  const element = document.querySelector(selector);
  if (element) element.textContent = text;
}

function parseLocalizedNumber(value) {
  if (!value) return 0;
  const normalized = String(value)
    .replace(/\u00a0/g, " ")
    .replace(/[^\d,.\-]/g, "")
    .replace(/\s/g, "");
  if (!normalized) return 0;
  const commaIndex = normalized.lastIndexOf(",");
  const dotIndex = normalized.lastIndexOf(".");
  const decimalSeparator = commaIndex > dotIndex ? "," : ".";
  const machineNumber =
    decimalSeparator === ","
      ? normalized.replace(/\./g, "").replace(",", ".")
      : normalized.replace(/,/g, "");
  const parsed = Number(machineNumber);
  return Number.isFinite(parsed) ? parsed : 0;
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

function roundToNearest(value, increment) {
  return Math.round(value / increment) * increment;
}
