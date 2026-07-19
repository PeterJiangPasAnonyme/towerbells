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

if (window.TowerbellsFilters?.wireBackToMapLink) {
  window.TowerbellsFilters.wireBackToMapLink(".back-link");
} else {
  const backLink = document.querySelector(".back-link");
  if (backLink) {
    const saved = sessionStorage.getItem("towerbellsFilters");
    backLink.href = saved ? `/?${saved}` : "/";
  }
}

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
  "display_title_translation_override",
  "remarks",
  "prior_history",
  "technical_data",
  "location_display_override",
  "schedule_display_override",
  "contact_display_override",
  "carillonist_display_override",
  "keyboard_display_override",
];

let activeSiteId = null;
let searchTimer = null;
let originalIndexFields = {};
let originalSiteFields = {};
let autoDisplayTitle = "";
let autoDisplayTitleTranslation = "";
let activeAutoLocation = null;
let activeAutoSchedule = null;
let activeAutoContact = null;
let activeAutoCarillonist = null;

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
  building: { line: null, translation: null },
  hide_building: false,
  address_lines: [],
  city_region: null,
  country: null,
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

function fillKeyboardOverrideField(site, display, editorText) {
  const shown = (editorText || "").trim();
  fillField("keyboard_display_override", shown);
  originalSiteFields.keyboard_display_override = (site.keyboard_display_override || "").trim();
}

function locationForEditor(location) {
  if (!location) {
    return { ...LOCATION_OVERRIDE_DEFAULTS };
  }
  const building = location.building || {};
  return {
    badge: location.badge ?? null,
    building: {
      line: building.line ?? null,
      translation: building.translation ?? null,
    },
    hide_building: Boolean(location.hide_building),
    address_lines: Array.isArray(location.address_lines) ? location.address_lines : [],
    city_region: location.city_region ?? null,
    country: location.country ?? null,
    notes: Array.isArray(location.notes) ? location.notes : [],
    hide_maps: Boolean(location.hide_maps),
  };
}

function migrateLegacyLocationOverride(raw) {
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) {
    return raw;
  }
  const migrated = { ...raw };
  if (!migrated.building && Object.prototype.hasOwnProperty.call(migrated, "name")) {
    const name = migrated.name;
    const hide = Boolean(migrated.hide_name);
    let translation = null;
    const aka = Array.isArray(migrated.also_known_as) ? migrated.also_known_as : [];
    for (const item of aka) {
      const text = String(item || "").trim().replace(/^\(|\)$/g, "");
      if (/church|chapel|tower|cathedral|building|university|memorial|our lady|st\./i.test(text)) {
        translation = text;
        break;
      }
    }
    if (hide) {
      migrated.hide_building = true;
    } else if (name) {
      migrated.building = {
        line: String(name).trim(),
        translation,
      };
    }
    delete migrated.name;
    delete migrated.also_known_as;
  }
  if (Object.prototype.hasOwnProperty.call(migrated, "hide_name")) {
    migrated.hide_building = Boolean(migrated.hide_name);
    delete migrated.hide_name;
  }
  if (!Object.prototype.hasOwnProperty.call(migrated, "city_region") && Object.prototype.hasOwnProperty.call(migrated, "locality")) {
    const locality = String(migrated.locality || "").trim();
    if (locality) {
      const parts = locality.split(",").map((part) => part.trim()).filter(Boolean);
      if (parts.length >= 2) {
        migrated.country = parts[parts.length - 1];
        migrated.city_region = parts.slice(0, -1).join(", ");
      } else {
        migrated.city_region = locality;
      }
    }
    delete migrated.locality;
  }
  return migrated;
}

function normalizeBuildingEditor(building) {
  const source = building && typeof building === "object" ? building : {};
  return {
    line: source.line ?? null,
    translation: source.translation ?? null,
  };
}

function buildingFieldDiff(editedBuilding, autoBuilding) {
  const edited = normalizeBuildingEditor(editedBuilding);
  const auto = normalizeBuildingEditor(autoBuilding);
  const diff = {};
  if (edited.line !== auto.line) {
    diff.line = edited.line;
  }
  if (edited.translation !== auto.translation) {
    diff.translation = edited.translation;
  }
  return Object.keys(diff).length ? diff : null;
}

function overrideDiff(edited, auto, { nestedKeys = {} } = {}) {
  const diff = {};
  for (const key of Object.keys({ ...auto, ...edited })) {
    if (nestedKeys[key]) {
      const nestedDiff = nestedKeys[key](edited[key], auto[key]);
      if (nestedDiff) {
        diff[key] = nestedDiff;
      }
      continue;
    }
    if (JSON.stringify(edited[key]) !== JSON.stringify(auto[key])) {
      diff[key] = edited[key];
    }
  }
  return diff;
}

function locationOverrideDiff(edited, auto) {
  return overrideDiff(edited, auto, {
    nestedKeys: {
      building: buildingFieldDiff,
    },
  });
}

function parseOverrideJson(rawText, label) {
  const trimmed = rawText.trim();
  if (!trimmed) {
    return null;
  }
  let parsed;
  try {
    parsed = JSON.parse(trimmed);
  } catch {
    throw new Error(`${label} must be valid JSON.`);
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error(`${label} must be a JSON object.`);
  }
  return parsed;
}

function buildEditedOverride(parsed, defaults, { migrateFn, nestedKeys = {} } = {}) {
  const normalized = migrateFn ? migrateFn({ ...parsed }) : { ...parsed };
  const edited = {};
  for (const [key, defaultValue] of Object.entries(defaults)) {
    if (nestedKeys[key]) {
      edited[key] = nestedKeys[key](key in normalized ? normalized[key] : defaultValue);
      continue;
    }
    edited[key] = key in normalized ? normalized[key] : defaultValue;
  }
  return edited;
}

function normalizeOverrideForSave(rawText, autoDisplay, defaults, label, options = {}) {
  const parsed = parseOverrideJson(rawText, label);
  if (!parsed) {
    return "";
  }
  const edited = buildEditedOverride(parsed, defaults, options);
  const auto = { ...defaults, ...(autoDisplay || {}) };
  const diff = overrideDiff(edited, auto, options);
  return Object.keys(diff).length ? JSON.stringify(diff, null, 2) : "";
}

function formatLocationOverrideJson(obj) {
  if (!obj || !Object.keys(obj).length) return "";
  return JSON.stringify(obj, null, 2);
}

function normalizeLocationOverrideForSave(rawText, autoLocation) {
  return normalizeOverrideForSave(
    rawText,
    locationForEditor(autoLocation),
    LOCATION_OVERRIDE_DEFAULTS,
    "Location override",
    {
      migrateFn: migrateLegacyLocationOverride,
      nestedKeys: {
        building: normalizeBuildingEditor,
      },
    }
  );
}

function normalizeScheduleOverrideForSave(rawText, autoSchedule) {
  return normalizeOverrideForSave(
    rawText,
    scheduleForEditor(autoSchedule),
    SCHEDULE_OVERRIDE_DEFAULTS,
    "Schedule override"
  );
}

function normalizeContactOverrideForSave(rawText, autoContact) {
  return normalizeOverrideForSave(
    rawText,
    contactForEditor(autoContact),
    CONTACT_OVERRIDE_DEFAULTS,
    "Contact override"
  );
}

function normalizeCarillonistOverrideForSave(rawText, autoCarillonist) {
  return normalizeOverrideForSave(
    rawText,
    carillonistForEditor(autoCarillonist),
    CARILLONIST_OVERRIDE_DEFAULTS,
    "Carillonist override"
  );
}

function normalizeKeyboardOverrideForSave(rawText) {
  const trimmed = rawText.trim();
  if (!trimmed) return "";

  let parsed;
  try {
    parsed = JSON.parse(trimmed);
  } catch {
    throw new Error("Keyboard override must be valid JSON.");
  }
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Keyboard override must be a JSON object.");
  }
  return trimmed;
}

function fillField(name, value) {
  const input = els.form.elements[name];
  if (!input) return;
  input.value = value ?? "";
}

function fillLocationOverrideField(site, display, locationAuto) {
  activeAutoLocation = locationForEditor(locationAuto);
  const effective = locationForEditor(display?.location);
  const shown = formatLocationOverrideJson(effective);
  fillField("location_display_override", shown);
  originalSiteFields.location_display_override = (site.location_display_override || "").trim();
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

function fillScheduleOverrideField(site, display, scheduleAuto) {
  activeAutoSchedule = scheduleForEditor(scheduleAuto);
  const effective = scheduleForEditor(display?.schedule);
  fillField("schedule_display_override", formatLocationOverrideJson(effective));
  originalSiteFields.schedule_display_override = (site.schedule_display_override || "").trim();
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

function fillContactOverrideField(site, display, contactAuto) {
  activeAutoContact = contactForEditor(contactAuto);
  const effective = contactForEditor(display?.contact);
  fillField("contact_display_override", formatLocationOverrideJson(effective));
  originalSiteFields.contact_display_override = (site.contact_display_override || "").trim();
}

function carillonistForEditor(carillonist) {
  if (!carillonist) {
    return { ...CARILLONIST_OVERRIDE_DEFAULTS, mode: "hidden" };
  }
  return {
    mode: carillonist.mode ?? CARILLONIST_OVERRIDE_DEFAULTS.mode,
    entries: Array.isArray(carillonist.entries) ? carillonist.entries : [],
    prose: carillonist.prose ?? null,
    force_prose: Boolean(carillonist.force_prose),
  };
}

function fillCarillonistOverrideField(site, display, carillonistAuto) {
  activeAutoCarillonist = carillonistForEditor(carillonistAuto);
  const effective = carillonistForEditor(display?.carillonist);
  fillField("carillonist_display_override", formatLocationOverrideJson(effective));
  originalSiteFields.carillonist_display_override = (site.carillonist_display_override || "").trim();
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
    if (field === "location_display_override" || field === "schedule_display_override" || field === "contact_display_override" || field === "carillonist_display_override" || field === "keyboard_display_override") continue;
    if (field === "display_title_override") {
      autoDisplayTitle = data.display?.title_auto || data.display?.title || "";
      autoDisplayTitleTranslation =
        data.display?.title_translation_auto || data.display?.title_translation || "";
      const shown = (site.display_title_override || "").trim() || autoDisplayTitle;
      fillField(field, shown);
      originalSiteFields[field] = site.display_title_override ?? "";
      continue;
    }
    if (field === "display_title_translation_override") {
      autoDisplayTitleTranslation =
        data.display?.title_translation_auto || data.display?.title_translation || "";
      const shown =
        (site.display_title_translation_override || "").trim() ||
        autoDisplayTitleTranslation ||
        "";
      fillField(field, shown);
      originalSiteFields[field] = site.display_title_translation_override ?? "";
      continue;
    }
    fillField(field, site[field]);
    originalSiteFields[field] = site[field] ?? "";
  }
  fillLocationOverrideField(site, data.display, data.location_auto);
  fillScheduleOverrideField(site, data.display, data.schedule_auto);
  fillContactOverrideField(site, data.display, data.contact_auto);
  fillCarillonistOverrideField(site, data.display, data.carillonist_auto);
  fillKeyboardOverrideField(site, data.display, data.keyboard_display_override_editor);

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
        if (!activeAutoLocation) {
          throw new Error("Auto-parsed location is unavailable. Reload the site and try again.");
        }
        value = normalizeLocationOverrideForSave(value, activeAutoLocation);
      } catch (err) {
        els.saveStatus.textContent = err.message;
        return;
      }
    }
    if (field === "schedule_display_override") {
      try {
        if (!activeAutoSchedule) {
          throw new Error("Auto-parsed schedule is unavailable. Reload the site and try again.");
        }
        value = normalizeScheduleOverrideForSave(value, activeAutoSchedule);
      } catch (err) {
        els.saveStatus.textContent = err.message;
        return;
      }
    }
    if (field === "contact_display_override") {
      try {
        if (!activeAutoContact) {
          throw new Error("Auto-parsed contact is unavailable. Reload the site and try again.");
        }
        value = normalizeContactOverrideForSave(value, activeAutoContact);
      } catch (err) {
        els.saveStatus.textContent = err.message;
        return;
      }
    }
    if (field === "carillonist_display_override") {
      try {
        if (!activeAutoCarillonist) {
          throw new Error("Auto-parsed carillonist is unavailable. Reload the site and try again.");
        }
        value = normalizeCarillonistOverrideForSave(value, activeAutoCarillonist);
      } catch (err) {
        els.saveStatus.textContent = err.message;
        return;
      }
    }
    if (field === "keyboard_display_override") {
      try {
        value = normalizeKeyboardOverrideForSave(value);
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
    if (field === "display_title_translation_override") {
      value = value.trim();
      const stored = (originalSiteFields[field] ?? "").trim();
      if (value === stored) {
        continue;
      }
      if (!value || value === autoDisplayTitleTranslation.trim()) {
        site_fields[field] = null;
      } else {
        site_fields[field] = value;
      }
      continue;
    }
    if (
      field === "location_display_override" ||
      field === "schedule_display_override" ||
      field === "contact_display_override" ||
      field === "carillonist_display_override" ||
      field === "keyboard_display_override"
    ) {
      if (String(value ?? "") !== String(original ?? "")) {
        site_fields[field] = value || null;
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

    window.location.href = `/carillon/${encodeURIComponent(activeSiteId)}`;
  } catch (err) {
    els.saveStatus.textContent = err.message;
  }
});

const initial = new URLSearchParams(window.location.search).get("site");
if (initial) {
  els.search.value = initial;
  runSearch().then(() => loadSite(initial.toUpperCase()));
}
