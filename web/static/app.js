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

let locationFacets = { show_states: false };

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
  els.yearMin.min = els.yearMax.min = els.yearSliderMin.min = els.yearSliderMax.min = minYear;
  els.yearMin.max = els.yearMax.max = els.yearSliderMin.max = els.yearSliderMax.max = maxYear;
  els.yearMin.value = minYear;
  els.yearMax.value = maxYear;
  els.yearSliderMin.value = minYear;
  els.yearSliderMax.value = maxYear;
  updateYearRangeFill();
}

function syncYearFromSliders() {
  let lo = +els.yearSliderMin.value;
  let hi = +els.yearSliderMax.value;
  if (lo > hi) {
    if (document.activeElement === els.yearSliderMin) {
      lo = hi;
      els.yearSliderMin.value = lo;
    } else {
      hi = lo;
      els.yearSliderMax.value = hi;
    }
  }
  els.yearMin.value = lo;
  els.yearMax.value = hi;
  updateYearRangeFill();
}

function syncYearFromInputs() {
  let lo = +els.yearMin.value;
  let hi = +els.yearMax.value;
  if (lo > hi) [lo, hi] = [hi, lo];
  els.yearSliderMin.value = lo;
  els.yearSliderMax.value = hi;
  els.yearMin.value = lo;
  els.yearMax.value = hi;
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
  if (els.instrumentType.value) params.set("instrument_type", els.instrumentType.value);
  if (els.bourdonPitch.value) params.set("bourdon_pitch", els.bourdonPitch.value);
  if (els.transposition.value) params.set("transposition", els.transposition.value);
  if (els.rangeClass.value) params.set("range_class", els.rangeClass.value);
  if (els.bellfounder.value) params.set("bellfounder", els.bellfounder.value);
  if (els.denomination.value) params.set("denomination", els.denomination.value);
  if (els.institutionType.value) params.set("institution_type", els.institutionType.value);
  return params;
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
      <div class="name">${escapeHtml(site.full_title || site.short_name || site.site_id)}</div>
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
        <div class="popup-title">${escapeHtml(site.full_title || site.short_name)}</div>
        <div>${escapeHtml(formatMeta(site))}</div>
        <a class="popup-link" href="/carillon/${site.site_id}">View details →</a>
      `);
      marker.on("click", () => {
        activeSiteId = site.site_id;
        highlightListItem(site.site_id);
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
  const parts = [
    site.country_code,
    site.state_province,
    site.bell_count ? `${site.bell_count} bells` : null,
    site.installation_year,
    site.bourdon_pitch ? `bourdon ${site.bourdon_pitch}` : null,
  ].filter(Boolean);
  return parts.join(" · ");
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
    fillCountedSelect(els.rangeClass, data.range_classifications || []);
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
  const [searchRes] = await Promise.all([
    fetch(`/api/search?${params}`).then((r) => r.json()),
    refreshLocationFacets(),
    refreshFilterFacets(),
  ]);
  renderResults(searchRes);
}

function scheduleSearch() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(runSearch, 250);
}

async function loadFilters() {
  try {
    const res = await fetch("/api/filters");
    if (!res.ok) throw new Error(`filters HTTP ${res.status}`);
    filterOptions = await res.json();
    fillCountedSelect(els.instrumentType, filterOptions.instrument_types || []);
    fillCountedSelect(els.bourdonPitch, filterOptions.bourdon_pitches || []);
    fillCountedSelect(els.transposition, filterOptions.transposition_semitones || []);
    fillCountedSelect(els.rangeClass, filterOptions.range_classifications || []);
    fillCountedSelect(els.bellfounder, filterOptions.bellfounders || []);
    fillCountedSelect(els.denomination, filterOptions.denominations || []);
    fillCountedSelect(els.institutionType, filterOptions.institution_types || []);

    const yr = filterOptions.year_range || [1850, 2025];
    initYearSliders(yr[0] || 1850, yr[1] || 2025);
  } catch (err) {
    console.error("Failed to load filters:", err);
    els.resultsMeta.textContent = "Filters unavailable — search still works.";
    initYearSliders(1850, 2025);
  }
  updateStateFieldVisibility();
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

els.country.addEventListener("change", () => {
  els.state.value = "";
  updateStateFieldVisibility();
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

loadFilters().then(async () => {
  const trad = filterOptions.instrument_types?.find((t) => {
    const value = typeof t === "string" ? t : t.value;
    return value.toLowerCase().includes("traditional carillon");
  });
  if (trad) {
    els.instrumentType.value = typeof trad === "string" ? trad : trad.value;
  }
  await runSearch();
});
