const els = {
  search: document.getElementById("searchInput"),
  results: document.getElementById("searchResults"),
  emptyState: document.getElementById("emptyState"),
  form: document.getElementById("editForm"),
  formTitle: document.getElementById("formTitle"),
  formMeta: document.getElementById("formMeta"),
  viewLink: document.getElementById("viewLink"),
  relatedRows: document.getElementById("relatedRows"),
  milestonePrefix: document.getElementById("milestonePrefix"),
  saveStatus: document.getElementById("saveStatus"),
};

const INDEX_FIELDS = [
  "bellfounder",
  "installation_year",
  "bourdon_pitch",
  "transposition_semitones",
  "range_classification",
  "denomination",
  "institution_type",
  "instrument_type",
  "latitude",
  "longitude",
];

const SITE_FIELDS = [
  "display_title_override",
  "remarks",
  "prior_history",
  "technical_data",
  "location_display_override",
  "schedule_display_override",
  "contact_display_override",
  "carillonist_display_override",
];

let activeSiteId = null;
let searchTimer = null;
let originalIndexFields = {};
let originalSiteFields = {};
let autoDisplayTitle = "";

function escapeHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function showForm(show) {
  els.form.hidden = !show;
  els.form.classList.toggle("hidden", !show);
  els.emptyState.hidden = show;
}

async function runSearch() {
  const q = els.search.value.trim();
  if (!q) {
    els.results.innerHTML = "";
    return;
  }

  const res = await fetch(`/api/admin/search?q=${encodeURIComponent(q)}`);
  const rows = await res.json();
  els.results.innerHTML = rows
    .map(
      (row) => `
      <li>
        <button type="button" class="admin-result-btn" data-site-id="${escapeHtml(row.site_id)}">
          <strong>${escapeHtml(row.display_title || row.short_name || row.site_id)}</strong>
          <span class="admin-result-id">${escapeHtml(row.site_id)}</span>
          <span class="admin-result-meta">${escapeHtml(
            [row.country_code, row.installation_year, row.bellfounder].filter(Boolean).join(" · ")
          )}</span>
        </button>
      </li>`
    )
    .join("");
}

const LOCATION_OVERRIDE_DEFAULTS = {
  badge: null,
  name: null,
  hide_name: false,
  also_known_as: [],
  address_lines: [],
  locality: null,
  notes: [],
  hide_maps: false,
};

const SCHEDULE_OVERRIDE_DEFAULTS = {
  mode: "prose",
  badge: null,
  calendars: [],
  prose: null,
  hide_badge: false,
  force_prose: false,
};

const CONTACT_OVERRIDE_DEFAULTS = {
  mode: "prose",
  badge: null,
  entries: [],
  prose: null,
  force_prose: false,
};

const CARILLONIST_OVERRIDE_DEFAULTS = {
  mode: "structured",
  entries: [],
  prose: null,
  force_prose: false,
};

function locationForEditor(location) {
  if (!location) {
    return { ...LOCATION_OVERRIDE_DEFAULTS };
  }
  return {
    badge: location.badge ?? null,
    name: location.name ?? null,
    hide_name: Boolean(location.hide_name),
    also_known_as: Array.isArray(location.also_known_as) ? location.also_known_as : [],
    address_lines: Array.isArray(location.address_lines) ? location.address_lines : [],
    locality: location.locality ?? null,
    notes: Array.isArray(location.notes) ? location.notes : [],
    hide_maps: Boolean(location.hide_maps),
  };
}

function formatLocationOverrideJson(obj) {
  if (!obj || !Object.keys(obj).length) return "";
  return JSON.stringify(obj, null, 2);
}

function normalizeLocationOverrideForSave(rawText) {
  const trimmed = rawText.trim();
  if (!trimmed) return "";

  let parsed;
  try {
    parsed = JSON.parse(trimmed);
  } catch {
    throw new Error("Location override must be valid JSON.");
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Location override must be a JSON object.");
  }

  const normalized = { ...parsed };
  for (const [key, defaultValue] of Object.entries(LOCATION_OVERRIDE_DEFAULTS)) {
    if (!(key in normalized)) {
      normalized[key] = defaultValue;
    }
  }
  return JSON.stringify(normalized, null, 2);
}

function normalizeScheduleOverrideForSave(rawText) {
  const trimmed = rawText.trim();
  if (!trimmed) return "";

  let parsed;
  try {
    parsed = JSON.parse(trimmed);
  } catch {
    throw new Error("Schedule override must be valid JSON.");
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Schedule override must be a JSON object.");
  }

  const normalized = { ...parsed };
  for (const [key, defaultValue] of Object.entries(SCHEDULE_OVERRIDE_DEFAULTS)) {
    if (!(key in normalized)) {
      normalized[key] = defaultValue;
    }
  }
  return JSON.stringify(normalized, null, 2);
}

function normalizeContactOverrideForSave(rawText) {
  const trimmed = rawText.trim();
  if (!trimmed) return "";

  let parsed;
  try {
    parsed = JSON.parse(trimmed);
  } catch {
    throw new Error("Contact override must be valid JSON.");
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Contact override must be a JSON object.");
  }

  const normalized = { ...parsed };
  for (const [key, defaultValue] of Object.entries(CONTACT_OVERRIDE_DEFAULTS)) {
    if (!(key in normalized)) {
      normalized[key] = defaultValue;
    }
  }
  return JSON.stringify(normalized, null, 2);
}

function normalizeCarillonistOverrideForSave(rawText) {
  const trimmed = rawText.trim();
  if (!trimmed) return "";

  let parsed;
  try {
    parsed = JSON.parse(trimmed);
  } catch {
    throw new Error("Carillonist override must be valid JSON.");
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Carillonist override must be a JSON object.");
  }

  const normalized = { ...parsed };
  for (const [key, defaultValue] of Object.entries(CARILLONIST_OVERRIDE_DEFAULTS)) {
    if (!(key in normalized)) {
      normalized[key] = defaultValue;
    }
  }
  return JSON.stringify(normalized, null, 2);
}

function fillField(name, value) {
  const input = els.form.elements[name];
  if (!input) return;
  input.value = value ?? "";
}

function fillLocationOverrideField(site, display) {
  const storedOverride = (site.location_display_override || "").trim();
  const shown = storedOverride || formatLocationOverrideJson(locationForEditor(display?.location));
  fillField("location_display_override", shown);
  originalSiteFields.location_display_override = shown;
}

function scheduleForEditor(schedule) {
  if (!schedule) {
    return { ...SCHEDULE_OVERRIDE_DEFAULTS };
  }
  return {
    mode: schedule.mode ?? SCHEDULE_OVERRIDE_DEFAULTS.mode,
    badge: schedule.badge ?? null,
    calendars: Array.isArray(schedule.calendars) ? schedule.calendars : [],
    prose: schedule.prose ?? null,
    hide_badge: Boolean(schedule.hide_badge),
    force_prose: Boolean(schedule.force_prose),
  };
}

function fillScheduleOverrideField(site, display) {
  const storedOverride = (site.schedule_display_override || "").trim();
  const shown = storedOverride || formatLocationOverrideJson(scheduleForEditor(display?.schedule));
  fillField("schedule_display_override", shown);
  originalSiteFields.schedule_display_override = shown;
}

function contactForEditor(contact) {
  if (!contact) {
    return { ...CONTACT_OVERRIDE_DEFAULTS };
  }
  return {
    mode: contact.mode ?? CONTACT_OVERRIDE_DEFAULTS.mode,
    badge: contact.badge ?? null,
    entries: Array.isArray(contact.entries) ? contact.entries : [],
    prose: contact.prose ?? null,
    force_prose: Boolean(contact.force_prose),
  };
}

function fillContactOverrideField(site, display) {
  const storedOverride = (site.contact_display_override || "").trim();
  const shown = storedOverride || formatLocationOverrideJson(contactForEditor(display?.contact));
  fillField("contact_display_override", shown);
  originalSiteFields.contact_display_override = shown;
}

function carillonistForEditor(carillonist) {
  if (!carillonist?.has_content) return {};
  const payload = { mode: carillonist.mode || "structured" };
  if (carillonist.entries?.length) payload.entries = carillonist.entries;
  if (carillonist.prose) payload.prose = carillonist.prose;
  return payload;
}

function fillCarillonistOverrideField(site, display) {
  const storedOverride = (site.carillonist_display_override || "").trim();
  const shown = storedOverride || formatLocationOverrideJson(carillonistForEditor(display?.carillonist));
  fillField("carillonist_display_override", shown);
  originalSiteFields.carillonist_display_override = shown;
}

async function loadSite(siteId) {
  activeSiteId = siteId;
  els.saveStatus.textContent = "";

  const res = await fetch(`/api/admin/sites/${encodeURIComponent(siteId)}`);
  const data = await res.json();
  if (data.error) {
    els.saveStatus.textContent = "Site not found.";
    return;
  }

  showForm(true);
  const site = data.site;
  const index = data.index || {};

  els.formTitle.textContent =
    data.display?.title || site.full_title || site.short_name || site.site_id;
  els.formMeta.textContent = [
    site.site_id,
    site.country_code,
    site.state_province,
    index.instrument_type,
    site.bell_count ? `${site.bell_count} bells` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  els.viewLink.href = `/carillon/${site.site_id}`;
  els.milestonePrefix.textContent = data.milestone_prefix || site.site_id;

  for (const field of INDEX_FIELDS) {
    fillField(field, index[field]);
    originalIndexFields[field] = index[field] ?? "";
  }
  for (const field of SITE_FIELDS) {
    if (field === "location_display_override" || field === "schedule_display_override" || field === "contact_display_override" || field === "carillonist_display_override") continue;
    if (field === "display_title_override") {
      autoDisplayTitle = data.display?.title_auto || data.display?.title || "";
      const shown = (site.display_title_override || "").trim() || autoDisplayTitle;
      fillField(field, shown);
      originalSiteFields[field] = site.display_title_override ?? "";
      continue;
    }
    fillField(field, site[field]);
    originalSiteFields[field] = site[field] ?? "";
  }
  fillLocationOverrideField(site, data.display);
  fillScheduleOverrideField(site, data.display);
  fillContactOverrideField(site, data.display);
  fillCarillonistOverrideField(site, data.display);

  const related = data.related_rows || [];
  if (related.length > 1) {
    els.relatedRows.hidden = false;
    els.relatedRows.classList.remove("hidden");
    els.relatedRows.innerHTML = `
      <p><strong>${related.length} related rows</strong> share prefix <code>${escapeHtml(data.milestone_prefix)}</code>:</p>
      <ul class="admin-related-list">
        ${related
          .map(
            (row) =>
              `<li><code>${escapeHtml(row.site_id)}</code> — ${escapeHtml(row.bellfounder || "no founder")}${
                row.installation_year ? ` (${row.installation_year})` : ""
              }</li>`
          )
          .join("")}
      </ul>`;
  } else {
    els.relatedRows.hidden = true;
    els.relatedRows.classList.add("hidden");
    els.relatedRows.innerHTML = "";
  }

  [...els.results.querySelectorAll(".admin-result-btn")].forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.siteId === siteId);
  });
}

els.search.addEventListener("input", () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(runSearch, 250);
});

els.results.addEventListener("click", (event) => {
  const btn = event.target.closest(".admin-result-btn");
  if (!btn) return;
  loadSite(btn.dataset.siteId);
});

els.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (!activeSiteId) return;

  const index_fields = {};
  for (const field of INDEX_FIELDS) {
    const value = els.form.elements[field].value;
    const original = originalIndexFields[field] ?? "";
    if (String(value) !== String(original ?? "")) {
      index_fields[field] = value;
    }
  }

  const site_fields = {};
  for (const field of SITE_FIELDS) {
    let value = els.form.elements[field].value;
    const original = originalSiteFields[field] ?? "";
    if (field === "location_display_override") {
      try {
        value = normalizeLocationOverrideForSave(value);
      } catch (err) {
        els.saveStatus.textContent = err.message;
        return;
      }
    }
    if (field === "schedule_display_override") {
      try {
        value = normalizeScheduleOverrideForSave(value);
      } catch (err) {
        els.saveStatus.textContent = err.message;
        return;
      }
    }
    if (field === "contact_display_override") {
      try {
        value = normalizeContactOverrideForSave(value);
      } catch (err) {
        els.saveStatus.textContent = err.message;
        return;
      }
    }
    if (field === "carillonist_display_override") {
      try {
        value = normalizeCarillonistOverrideForSave(value);
      } catch (err) {
        els.saveStatus.textContent = err.message;
        return;
      }
    }
    if (field === "display_title_override") {
      value = value.trim();
      const stored = (originalSiteFields[field] ?? "").trim();
      if (value === stored) {
        continue;
      }
      if (!value || value === autoDisplayTitle.trim()) {
        site_fields[field] = null;
      } else {
        site_fields[field] = value;
      }
      continue;
    }
    if (String(value) !== String(original ?? "")) {
      site_fields[field] = value;
    }
  }

  if (!Object.keys(index_fields).length && !Object.keys(site_fields).length) {
    els.saveStatus.textContent = "No changes to save.";
    return;
  }

  const apply_to_milestones = els.form.elements.apply_to_milestones.checked;

  els.saveStatus.textContent = "Saving…";
  try {
    const res = await fetch(`/api/admin/sites/${encodeURIComponent(activeSiteId)}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ index_fields, site_fields, apply_to_milestones }),
    });
    const data = await res.json();
    if (!res.ok) {
      throw new Error(data.detail || data.error || "Save failed");
    }

    const count = data.updated_site_ids.length;
    els.saveStatus.textContent =
      count === 1
        ? `Saved ${activeSiteId}. Refresh the map to see changes.`
        : `Saved ${count} rows (${data.updated_site_ids.join(", ")}). Refresh the map to see changes.`;

    await runSearch();
    await loadSite(activeSiteId);
  } catch (err) {
    els.saveStatus.textContent = err.message;
  }
});

const initial = new URLSearchParams(window.location.search).get("site");
if (initial) {
  els.search.value = initial;
  runSearch().then(() => loadSite(initial.toUpperCase()));
}
