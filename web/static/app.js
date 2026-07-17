const map = L.map("map", { zoomControl: true }).setView([30, 0], 2);
L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; CARTO',
  subdomains: "abcd",
  maxZoom: 19,
}).addTo(map);

let markersLayer = L.layerGroup().addTo(map);
let debounceTimer = null;
let filterOptions = {};
let activeSiteId = null;

const els = {
  search: document.getElementById("searchInput"),
  continent: document.getElementById("continent"),
  country: document.getElementById("country"),
  state: document.getElementById("state"),
  yearMin: document.getElementById("yearMin"),
  yearMax: document.getElementById("yearMax"),
  yearEventTypes: document.getElementById("yearEventTypes"),
  yearSliderMin: document.getElementById("yearSliderMin"),
  yearSliderMax: document.getElementById("yearSliderMax"),
  yearRangeFill: document.getElementById("yearRangeFill"),
  instrumentType: document.getElementById("instrumentType"),
  bourdonPitch: document.getElementById("bourdonPitch"),
  transposition: document.getElementById("transposition"),
  rangeClass: document.getElementById("rangeClass"),
  bellfounder: document.getElementById("bellfounder"),
  denomination: document.getElementById("denomination"),
  institutionType: document.getElementById("institutionType"),
  denominationField: document.getElementById("denominationField"),
  rangeClassInfo: document.getElementById("rangeClassInfo"),
  rangeClassDialog: document.getElementById("rangeClassDialog"),
  rangeClassDialogBody: document.getElementById("rangeClassDialogBody"),
  rangeClassDialogClose: document.getElementById("rangeClassDialogClose"),
  rangeClassDialogTitle: document.getElementById("rangeClassDialogTitle"),
  stateField: document.getElementById("stateField"),
  resultsMeta: document.getElementById("resultsMeta"),
  resultsList: document.getElementById("resultsList"),
};

/** @param {string | {value:string,label:string,count:number}} item */
function normalizeFacetItem(item) {
  if (typeof item === "string") {
    return { value: item, label: item, count: null };
  }
  return item;
}

/** @param {{value:string,label:string,count:number}[] | string[]} items */
function fillCountedSelect(select, items) {
  const current = select.value;
  select.innerHTML = '<option value="">Any</option>';
  for (const raw of items) {
    const item = normalizeFacetItem(raw);
    const opt = document.createElement("option");
    opt.value = item.value;
    opt.textContent =
      item.count != null ? `${item.label} (${item.count})` : item.label;
    select.appendChild(opt);
  }
  if ([...select.options].some((o) => o.value === current)) {
    select.value = current;
  }
}

const RANGE_CLASS_MAJOR_ORDER = ["Group 1", "Group 2", "Group 3", "Group 4", "Other"];

function rangeClassMajorLabel(value) {
  const match = value.match(/^Group (\d+)/);
  return match ? `Group ${match[1]}` : "Other";
}

function rangeClassShortLabel(value) {
  return value.replace(/^Group /, "");
}

/** @param {{value:string,label:string,count:number}[]} items */
function fillRangeClassSelect(select, items) {
  const current = select.value;
  select.innerHTML = '<option value="">Any</option>';

  const grouped = new Map(RANGE_CLASS_MAJOR_ORDER.map((label) => [label, []]));
  for (const raw of items) {
    const item = normalizeFacetItem(raw);
    const major = rangeClassMajorLabel(item.value);
    if (!grouped.has(major)) grouped.set(major, []);
    grouped.get(major).push(item);
  }

  for (const major of RANGE_CLASS_MAJOR_ORDER) {
    const groupItems = grouped.get(major) || [];
    if (!groupItems.length) continue;

    const optgroup = document.createElement("optgroup");
    optgroup.label = major;
    for (const item of groupItems) {
      const opt = document.createElement("option");
      opt.value = item.value;
      const shortLabel = rangeClassShortLabel(item.value);
      opt.textContent =
        item.count != null ? `${shortLabel} (${item.count})` : shortLabel;
      optgroup.appendChild(opt);
    }
    select.appendChild(optgroup);
  }

  if ([...select.options].some((o) => o.value === current)) {
    select.value = current;
  }
}

function formatMusicText(str) {
  return escapeHtml(str)
    .replace(/♭/g, '<span class="accidental-flat">♭</span>')
    .replace(/♯/g, '<span class="accidental-sharp">♯</span>');
}

let locationFacets = { show_states: false };

const DENOMINATION_INSTITUTION_TYPES = new Set([
  "Religious Institutions",
  "Educational Institutions",
]);

const FILTER_STORAGE_KEY = "towerbellsFilters";
const DEFAULT_YEAR_EVENT_TYPES = ["installed"];

const YEAR_SCALE = {
  breakYear: 1900,
  compressedRatio: 0.15,
  steps: 1000,
  defaultMinYear: 1900,
};

let yearScaleBounds = { min: 1500, max: 2025 };

function yearScaleCompressedEnd() {
  return YEAR_SCALE.steps * YEAR_SCALE.compressedRatio;
}

function yearScaleBreakYear() {
  const { min, max } = yearScaleBounds;
  return Math.min(Math.max(YEAR_SCALE.breakYear, min), max);
}

function clampYear(year) {
  const { min, max } = yearScaleBounds;
  return Math.min(Math.max(Math.round(year), min), max);
}

function yearToSliderPosition(year) {
  const { min, max } = yearScaleBounds;
  const breakYear = yearScaleBreakYear();
  const y = clampYear(year);
  const compressedEnd = yearScaleCompressedEnd();

  if (max <= breakYear) {
    return Math.round(((y - min) / (max - min || 1)) * compressedEnd);
  }
  if (min >= breakYear) {
    const modernSpan = YEAR_SCALE.steps - compressedEnd;
    return Math.round(compressedEnd + ((y - min) / (max - min || 1)) * modernSpan);
  }
  if (y <= breakYear) {
    return Math.round(((y - min) / (breakYear - min || 1)) * compressedEnd);
  }
  const modernSpan = YEAR_SCALE.steps - compressedEnd;
  return Math.round(compressedEnd + ((y - breakYear) / (max - breakYear || 1)) * modernSpan);
}

function sliderPositionToYear(position) {
  const { min, max } = yearScaleBounds;
  const breakYear = yearScaleBreakYear();
  const pos = Math.min(Math.max(position, 0), YEAR_SCALE.steps);
  const compressedEnd = yearScaleCompressedEnd();

  if (max <= breakYear) {
    return clampYear(min + (pos / (compressedEnd || 1)) * (max - min));
  }
  if (min >= breakYear) {
    const modernSpan = YEAR_SCALE.steps - compressedEnd;
    return clampYear(min + ((pos - compressedEnd) / (modernSpan || 1)) * (max - min));
  }
  if (pos <= compressedEnd) {
    return clampYear(min + (pos / (compressedEnd || 1)) * (breakYear - min));
  }
  const modernSpan = YEAR_SCALE.steps - compressedEnd;
  return clampYear(breakYear + ((pos - compressedEnd) / (modernSpan || 1)) * (max - breakYear));
}

function updateYearScaleMarker() {
  const breakEl = document.getElementById("yearRangeBreak");
  if (breakEl) {
    const { min, max } = yearScaleBounds;
    const showBreak = min < YEAR_SCALE.breakYear && max > YEAR_SCALE.breakYear;
    breakEl.style.display = showBreak ? "block" : "none";
    breakEl.style.left = `${YEAR_SCALE.compressedRatio * 100}%`;
  }
  const minLabel = document.getElementById("yearScaleMinLabel");
  const maxLabel = document.getElementById("yearScaleMaxLabel");
  const breakLabel = document.querySelector(".year-scale-break-label");
  if (minLabel) minLabel.textContent = String(yearScaleBounds.min);
  if (maxLabel) maxLabel.textContent = String(yearScaleBounds.max);
  if (breakLabel) {
    const showBreak =
      yearScaleBounds.min < YEAR_SCALE.breakYear && yearScaleBounds.max > YEAR_SCALE.breakYear;
    breakLabel.style.display = showBreak ? "block" : "none";
  }
}

function getSelectedYearEventTypes() {
  return [...els.yearEventTypes.querySelectorAll('input[type="checkbox"]:checked')]
    .map((input) => input.value)
    .filter(Boolean);
}

function renderYearEventTypes(options) {
  const current = new Set(getSelectedYearEventTypes());
  const hasSelection = current.size > 0;
  els.yearEventTypes.innerHTML = "";
  for (const option of options || []) {
    const label = document.createElement("label");
    const input = document.createElement("input");
    input.type = "checkbox";
    input.name = "year_event_type";
    input.value = option.value;
    input.checked = hasSelection ? current.has(option.value) : option.value === "installed";
    label.appendChild(input);
    label.append(option.label);
    els.yearEventTypes.appendChild(label);
  }
}

function setYearEventTypes(values) {
  const selected = new Set(values?.length ? values : DEFAULT_YEAR_EVENT_TYPES);
  els.yearEventTypes.querySelectorAll('input[type="checkbox"]').forEach((input) => {
    input.checked = selected.has(input.value);
  });
}

function institutionShowsDenomination(value) {
  return DENOMINATION_INSTITUTION_TYPES.has(value);
}

function updateStateFieldVisibility() {
  const show =
    Boolean(els.country.value) && locationFacets.show_states && (locationFacets.states?.length || 0) >= 2;
  els.stateField.classList.toggle("filter-hidden", !show);
  els.state.disabled = !show;
  if (!show) {
    els.state.innerHTML = '<option value="">Any</option>';
    els.state.value = "";
  }
}

function updateDenominationFieldVisibility() {
  const show = institutionShowsDenomination(els.institutionType.value);
  els.denominationField.classList.toggle("filter-hidden", !show);
  els.denomination.disabled = !show;
  if (!show) {
    els.denomination.value = "";
  }
}

function updateYearRangeFill() {
  const min = +els.yearSliderMin.min;
  const max = +els.yearSliderMin.max;
  const lo = +els.yearSliderMin.value;
  const hi = +els.yearSliderMax.value;
  const span = max - min || 1;
  const left = ((lo - min) / span) * 100;
  const width = ((hi - lo) / span) * 100;
  els.yearRangeFill.style.left = `${left}%`;
  els.yearRangeFill.style.width = `${width}%`;
}

function initYearSliders(minYear, maxYear) {
  yearScaleBounds = { min: minYear, max: maxYear };
  const steps = YEAR_SCALE.steps;

  els.yearSliderMin.min = "0";
  els.yearSliderMax.min = "0";
  els.yearSliderMin.max = String(steps);
  els.yearSliderMax.max = String(steps);
  els.yearSliderMin.step = "1";
  els.yearSliderMax.step = "1";

  els.yearMin.min = String(minYear);
  els.yearMax.min = String(minYear);
  els.yearMin.max = String(maxYear);
  els.yearMax.max = String(maxYear);

  const defaultLo = Math.max(minYear, YEAR_SCALE.defaultMinYear);
  els.yearMin.value = String(defaultLo);
  els.yearMax.value = String(maxYear);
  syncYearFromInputs();
  updateYearScaleMarker();
}

function syncYearFromSliders() {
  let lo = +els.yearSliderMin.value;
  let hi = +els.yearSliderMax.value;
  if (lo > hi) {
    if (document.activeElement === els.yearSliderMin) {
      lo = hi;
      els.yearSliderMin.value = String(lo);
    } else {
      hi = lo;
      els.yearSliderMax.value = String(hi);
    }
  }
  els.yearMin.value = String(sliderPositionToYear(lo));
  els.yearMax.value = String(sliderPositionToYear(hi));
  updateYearRangeFill();
}

function syncYearFromInputs() {
  let lo = clampYear(+els.yearMin.value || yearScaleBounds.min);
  let hi = clampYear(+els.yearMax.value || yearScaleBounds.max);
  if (lo > hi) [lo, hi] = [hi, lo];
  els.yearSliderMin.value = String(yearToSliderPosition(lo));
  els.yearSliderMax.value = String(yearToSliderPosition(hi));
  els.yearMin.value = String(lo);
  els.yearMax.value = String(hi);
  updateYearRangeFill();
}

function getParams() {
  const params = new URLSearchParams();
  if (els.search.value.trim()) params.set("q", els.search.value.trim());
  if (els.continent.value) params.set("continent", els.continent.value);
  if (els.country.value) params.set("country", els.country.value);
  if (els.state.value) params.set("state", els.state.value);
  if (els.yearMin.value) params.set("year_min", els.yearMin.value);
  if (els.yearMax.value) params.set("year_max", els.yearMax.value);
  const yearEventTypes = getSelectedYearEventTypes();
  if (yearEventTypes.length) params.set("year_event_types", yearEventTypes.join(","));
  if (els.instrumentType.value) params.set("instrument_type", els.instrumentType.value);
  if (els.bourdonPitch.value) params.set("bourdon_pitch", els.bourdonPitch.value);
  if (els.transposition.value) params.set("transposition", els.transposition.value);
  if (els.rangeClass.value) params.set("range_class", els.rangeClass.value);
  if (els.bellfounder.value) params.set("bellfounder", els.bellfounder.value);
  if (els.denomination.value) params.set("denomination", els.denomination.value);
  if (els.institutionType.value) params.set("institution_type", els.institutionType.value);
  return params;
}

function getSavedFilterParams() {
  if (window.location.search.length > 1) {
    return window.location.search.slice(1);
  }
  return sessionStorage.getItem(FILTER_STORAGE_KEY) || "";
}

function saveFilterState() {
  const params = getParams().toString();
  if (params) {
    sessionStorage.setItem(FILTER_STORAGE_KEY, params);
    history.replaceState(null, "", `/?${params}`);
  } else {
    sessionStorage.removeItem(FILTER_STORAGE_KEY);
    history.replaceState(null, "", "/");
  }
}

function applyFilterParams(paramString) {
  if (!paramString) return false;
  const params = new URLSearchParams(paramString);

  els.search.value = params.get("q") || "";
  els.continent.value = params.get("continent") || "";
  els.country.value = params.get("country") || "";
  els.state.value = params.get("state") || "";
  if (params.get("year_min")) els.yearMin.value = params.get("year_min");
  if (params.get("year_max")) els.yearMax.value = params.get("year_max");
  if (params.get("year_event_types")) {
    setYearEventTypes(params.get("year_event_types").split(","));
  } else {
    setYearEventTypes(DEFAULT_YEAR_EVENT_TYPES);
  }
  els.instrumentType.value = params.get("instrument_type") || "";
  els.bourdonPitch.value = params.get("bourdon_pitch") || "";
  els.transposition.value = params.get("transposition") || "";
  els.rangeClass.value = params.get("range_class") || "";
  els.bellfounder.value = params.get("bellfounder") || "";
  els.denomination.value = params.get("denomination") || "";
  els.institutionType.value = params.get("institution_type") || "";
  syncYearFromInputs();
  updateDenominationFieldVisibility();
  return true;
}

function renderResults(data) {
  els.resultsMeta.textContent = `${data.total} matching · ${data.with_coordinates} on map · showing ${data.returned}`;

  els.resultsList.innerHTML = "";
  markersLayer.clearLayers();
  const bounds = [];

  for (const site of data.results) {
    const li = document.createElement("li");
    const a = document.createElement("a");
    a.href = `/carillon/${site.site_id}`;
    a.dataset.siteId = site.site_id;
    a.innerHTML = `
      <div class="name">${escapeHtml(site.display_title || site.site_id)}</div>
      <div class="meta">${escapeHtml(formatMeta(site))}</div>
    `;
    a.addEventListener("mouseenter", () => highlightMarker(site.site_id));
    li.appendChild(a);
    els.resultsList.appendChild(li);

    if (site.latitude != null && site.longitude != null) {
      const marker = L.circleMarker([site.latitude, site.longitude], {
        radius: 7,
        color: "#c9a227",
        fillColor: "#e05a5a",
        fillOpacity: 0.85,
        weight: 2,
      });
      marker.siteId = site.site_id;
      marker.bindPopup(`
        <div class="popup-title">${escapeHtml(site.display_title || site.short_name || site.site_id)}</div>
        <div>${escapeHtml(formatMeta(site))}</div>
        <a class="popup-link" href="/carillon/${site.site_id}">View details →</a>
      `);
      marker.on("click", () => {
        activeSiteId = site.site_id;
        highlightListItem(site.site_id);
        saveFilterState();
        window.location.href = `/carillon/${site.site_id}`;
      });
      markersLayer.addLayer(marker);
      bounds.push([site.latitude, site.longitude]);
    }
  }

  if (bounds.length) {
    map.fitBounds(bounds, { padding: [40, 40], maxZoom: 12 });
  }
}

function formatMeta(site) {
  return site.display_subtitle || "";
}

function highlightListItem(siteId) {
  els.resultsList.querySelectorAll("a").forEach((a) => {
    a.classList.toggle("active", a.dataset.siteId === siteId);
  });
}

function highlightMarker(siteId) {
  markersLayer.eachLayer((layer) => {
    if (layer.siteId === siteId) layer.openPopup();
  });
}

function escapeHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

async function refreshLocationFacets() {
  const params = getParams();
  params.delete("state");
  try {
    const res = await fetch(`/api/filters/location?${params}`);
    if (!res.ok) return;
    const data = await res.json();
    locationFacets = data;
    fillCountedSelect(els.continent, data.continents || []);
    fillCountedSelect(els.country, data.countries || []);
    if (data.show_states && els.country.value) {
      fillCountedSelect(els.state, data.states || []);
    }
    updateStateFieldVisibility();
  } catch (err) {
    console.error("Failed to refresh location facets:", err);
  }
}

async function refreshFilterFacets() {
  const params = getParams();
  try {
    const res = await fetch(`/api/filters/facets?${params}`);
    if (!res.ok) return;
    const data = await res.json();
    fillCountedSelect(els.instrumentType, data.instrument_types || []);
    fillCountedSelect(els.bourdonPitch, data.bourdon_pitches || []);
    fillCountedSelect(els.transposition, data.transposition_semitones || []);
    fillRangeClassSelect(els.rangeClass, data.range_classifications || []);
    fillCountedSelect(els.bellfounder, data.bellfounders || []);
    fillCountedSelect(els.denomination, data.denominations || []);
    fillCountedSelect(els.institutionType, data.institution_types || []);
  } catch (err) {
    console.error("Failed to refresh filter facets:", err);
  }
}

async function runSearch() {
  els.resultsMeta.textContent = "Searching…";
  const params = getParams();
  saveFilterState();
  try {
    const searchRes = await fetch(`/api/search?${params}`).then(async (response) => {
      if (!response.ok) {
        throw new Error(`Search failed (${response.status})`);
      }
      return response.json();
    });
    await Promise.all([refreshLocationFacets(), refreshFilterFacets()]);
    renderResults(searchRes);
  } catch (err) {
    console.error("Search failed:", err);
    els.resultsMeta.textContent = "Search failed — try refreshing the page.";
    els.resultsList.innerHTML = "";
    markersLayer.clearLayers();
  }
}

function scheduleSearch() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(runSearch, 250);
}

function normalizeRangeLegend(legend) {
  if (!legend) return legend;
  if (legend.groups?.length) return legend;

  const subgroupMap = new Map(
    (legend.subgroups || []).map((subgroup) => [String(subgroup.code), subgroup])
  );
  const majorGroups = legend.major_groups || [];
  if (!majorGroups.length) return legend;

  return {
    ...legend,
    groups: majorGroups.map((major) => {
      const majorNumber = String(major.label || "").replace(/^Group\s+/i, "");
      const subgroups = (legend.subgroups || []).filter((subgroup) =>
        String(subgroup.code).startsWith(majorNumber)
      );
      return {
        label: major.label,
        description: major.description,
        subgroups,
      };
    }),
  };
}

function renderRangeClassLegend(legend) {
  if (!legend || !els.rangeClassDialogBody) return;
  legend = normalizeRangeLegend(legend);

  if (els.rangeClassDialogTitle && legend.title) {
    els.rangeClassDialogTitle.textContent = legend.title;
  }

  const groups = (legend.groups || [])
    .map((group) => {
      const subgroups = (group.subgroups || [])
        .map(
          (subgroup) =>
            `<li><span class="legend-code">${escapeHtml(subgroup.code)}</span> ${formatMusicText(subgroup.description)}</li>`
        )
        .join("");
      return `
        <section class="legend-group">
          <h3>${escapeHtml(group.label)}</h3>
          <p>${formatMusicText(group.description)}</p>
          <ul class="legend-subgroups">${subgroups}</ul>
        </section>
      `;
    })
    .join("");

  els.rangeClassDialogBody.innerHTML = `
    <p>${formatMusicText(legend.intro || "")}</p>
    ${groups}
    ${legend.note ? `<p class="legend-note">${formatMusicText(legend.note)}</p>` : ""}
  `;
}

function initRangeClassInfo() {
  if (!els.rangeClassInfo || !els.rangeClassDialog) return;

  els.rangeClassInfo.addEventListener("click", () => {
    if (typeof els.rangeClassDialog.showModal === "function") {
      els.rangeClassDialog.showModal();
    }
  });

  els.rangeClassDialogClose?.addEventListener("click", () => {
    els.rangeClassDialog.close();
  });

  els.rangeClassDialog.addEventListener("click", (event) => {
    if (event.target === els.rangeClassDialog) {
      els.rangeClassDialog.close();
    }
  });
}

async function loadFilters() {
  try {
    const res = await fetch("/api/filters");
    if (!res.ok) throw new Error(`filters HTTP ${res.status}`);
    filterOptions = await res.json();
    renderRangeClassLegend(filterOptions.range_classification_legend);
    renderYearEventTypes(filterOptions.year_event_types || []);
    fillCountedSelect(els.instrumentType, filterOptions.instrument_types || []);
    fillCountedSelect(els.bourdonPitch, filterOptions.bourdon_pitches || []);
    fillCountedSelect(els.transposition, filterOptions.transposition_semitones || []);
    fillRangeClassSelect(els.rangeClass, filterOptions.range_classifications || []);
    fillCountedSelect(els.bellfounder, filterOptions.bellfounders || []);
    fillCountedSelect(els.denomination, filterOptions.denominations || []);
    fillCountedSelect(els.institutionType, filterOptions.institution_types || []);

    const yr = filterOptions.year_range || [1850, 2025];
    initYearSliders(yr[0] || 1850, yr[1] || 2025);
  } catch (err) {
    console.error("Failed to load filters:", err);
    els.resultsMeta.textContent = "Filters unavailable — search still works.";
    renderYearEventTypes([
      { value: "installed", label: "Installed" },
      { value: "founded", label: "Founded" },
      { value: "recast", label: "Recast" },
    ]);
    initYearSliders(1850, 2025);
  }
  updateStateFieldVisibility();
  updateDenominationFieldVisibility();
}

[
  els.search,
  els.continent,
  els.country,
  els.state,
  els.yearMin,
  els.yearMax,
  els.instrumentType,
  els.bourdonPitch,
  els.transposition,
  els.rangeClass,
  els.bellfounder,
  els.denomination,
  els.institutionType,
].forEach((el) => el.addEventListener("input", scheduleSearch));

els.yearEventTypes.addEventListener("change", scheduleSearch);

els.institutionType.addEventListener("change", updateDenominationFieldVisibility);

els.country.addEventListener("change", () => {
  els.state.value = "";
  updateStateFieldVisibility();
  updateDenominationFieldVisibility();
});

els.continent.addEventListener("change", () => {
  if (els.country.value) {
    const stillValid = [...els.country.options].some(
      (o) => o.value === els.country.value
    );
    if (!stillValid) {
      els.country.value = "";
      els.state.value = "";
    }
  }
  updateStateFieldVisibility();
  updateDenominationFieldVisibility();
});

els.yearSliderMin.addEventListener("input", () => {
  syncYearFromSliders();
  scheduleSearch();
});
els.yearSliderMax.addEventListener("input", () => {
  syncYearFromSliders();
  scheduleSearch();
});
els.yearMin.addEventListener("change", () => {
  syncYearFromInputs();
  scheduleSearch();
});
els.yearMax.addEventListener("change", () => {
  syncYearFromInputs();
  scheduleSearch();
});

const root = document.documentElement;
const sidebarTop = document.getElementById("sidebarTop");
const sidebarResize = document.getElementById("sidebarResize");
const filtersResize = document.getElementById("filtersResize");

function clamp(value, min, max) {
  return Math.min(Math.max(value, min), max);
}

function setSidebarWidth(px) {
  root.style.setProperty("--sidebar-width", `${px}px`);
  localStorage.setItem("sidebarWidth", String(px));
  map.invalidateSize();
}

function setFiltersHeight(px) {
  root.style.setProperty("--filters-height", `${px}px`);
  localStorage.setItem("filtersHeight", String(px));
}

function initPanelSizes() {
  const storedWidth = Number(localStorage.getItem("sidebarWidth"));
  if (storedWidth) {
    setSidebarWidth(clamp(storedWidth, 280, Math.min(720, window.innerWidth * 0.7)));
  }

  const storedHeight = Number(localStorage.getItem("filtersHeight"));
  if (storedHeight) {
    setFiltersHeight(
      clamp(storedHeight, 180, window.innerHeight - 140)
    );
  }
}

function startDrag(handle, axis, onMove) {
  handle.classList.add("active");
  document.body.classList.add(axis === "x" ? "resizing-col" : "resizing-row");

  const move = (event) => onMove(event);
  const stop = () => {
    handle.classList.remove("active");
    document.body.classList.remove("resizing-col", "resizing-row");
    window.removeEventListener("mousemove", move);
    window.removeEventListener("mouseup", stop);
    if (axis === "x") map.invalidateSize();
  };

  window.addEventListener("mousemove", move);
  window.addEventListener("mouseup", stop);
}

sidebarResize?.addEventListener("mousedown", (event) => {
  event.preventDefault();
  const startX = event.clientX;
  const startWidth = sidebarTop.closest(".sidebar").offsetWidth;

  startDrag(sidebarResize, "x", (moveEvent) => {
    const nextWidth = clamp(
      startWidth + (moveEvent.clientX - startX),
      280,
      Math.min(720, window.innerWidth * 0.7)
    );
    setSidebarWidth(nextWidth);
  });
});

filtersResize?.addEventListener("mousedown", (event) => {
  event.preventDefault();
  const sidebar = sidebarTop.closest(".sidebar");
  const startY = event.clientY;
  const startHeight = sidebarTop.offsetHeight;

  startDrag(filtersResize, "y", (moveEvent) => {
    const maxHeight = sidebar.clientHeight - 140;
    const nextHeight = clamp(startHeight + (moveEvent.clientY - startY), 180, maxHeight);
    setFiltersHeight(nextHeight);
  });
});

window.addEventListener("resize", () => {
  const width = Number(localStorage.getItem("sidebarWidth"));
  if (width) {
    setSidebarWidth(clamp(width, 280, Math.min(720, window.innerWidth * 0.7)));
  }
  const height = Number(localStorage.getItem("filtersHeight"));
  if (height && sidebarTop) {
    const maxHeight = sidebarTop.closest(".sidebar").clientHeight - 140;
    setFiltersHeight(clamp(height, 180, maxHeight));
  }
});

initPanelSizes();
initRangeClassInfo();

loadFilters().then(async () => {
  const restored = applyFilterParams(getSavedFilterParams());
  if (!restored) {
    const trad = filterOptions.instrument_types?.find((t) => {
      const value = typeof t === "string" ? t : t.value;
      return value.toLowerCase().includes("traditional carillon");
    });
    if (trad) {
      els.instrumentType.value = typeof trad === "string" ? trad : trad.value;
    }
  }
  updateStateFieldVisibility();
  updateDenominationFieldVisibility();
  await runSearch();
});

document.addEventListener("click", (event) => {
  const link = event.target.closest('a[href^="/carillon/"]');
  if (link) saveFilterState();
});
