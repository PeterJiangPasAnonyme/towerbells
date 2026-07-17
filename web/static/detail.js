const siteId = window.location.pathname.split("/").pop();
const FILTER_STORAGE_KEY = "towerbellsFilters";

const backLink = document.querySelector(".back-link");
const editLink = document.getElementById("editLink");
const mapExpandBtn = document.getElementById("mapExpandBtn");
const mapCloseBtn = document.getElementById("mapCloseBtn");
const mapFullscreen = document.getElementById("mapFullscreen");

if (editLink) {
  editLink.href = `/admin?site=${encodeURIComponent(siteId)}`;
}
if (backLink) {
  const saved = sessionStorage.getItem(FILTER_STORAGE_KEY);
  backLink.href = saved ? `/?${saved}` : "/";
}

let miniMap = null;
let fullMap = null;
let mapCoords = null;

function section(title, text) {
  if (!text || !text.trim()) return "";
  return `<section><h2>${title}</h2><pre>${escapeHtml(text.trim())}</pre></section>`;
}

function escapeHtml(str) {
  return String(str || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function renderLocationPanel(location, pageBadge) {
  if (!location || !location.has_content) {
    return `<section class="location-display"><h2>Location</h2><p class="detail-empty">No location details available.</p></section>`;
  }

  const parts = ['<section class="location-display"><h2>Location</h2>'];

  const hideName =
    pageBadge &&
    location.name &&
    /mobile carillon|in storage/i.test(pageBadge) &&
    /mobile carillon|in storage/i.test(location.name);

  if (location.name && !hideName) {
    parts.push(`<p class="location-name">${escapeHtml(location.name)}</p>`);
  }
  if (location.also_known_as?.length) {
    parts.push(
      `<ul class="location-aka">${location.also_known_as
        .map((item) => `<li>${escapeHtml(item)}</li>`)
        .join("")}</ul>`
    );
  }
  if (location.address_lines?.length) {
    parts.push(
      `<div class="location-address">${location.address_lines
        .map((line) => `<p>${escapeHtml(line)}</p>`)
        .join("")}</div>`
    );
  }
  if (location.locality) {
    parts.push(`<p class="location-locality">${escapeHtml(location.locality)}</p>`);
  }
  if (location.notes?.length) {
    parts.push(
      `<ul class="location-notes">${location.notes
        .map((note) => `<li>${escapeHtml(note)}</li>`)
        .join("")}</ul>`
    );
  }
  if (location.maps_url) {
    parts.push(
      `<a class="location-maps-link" href="${escapeHtml(location.maps_url)}" target="_blank" rel="noopener">Open in Maps ↗</a>`
    );
  }

  parts.push("</section>");
  return parts.join("");
}

const SCHEDULE_DAYS = [
  ["mon", "Mon"],
  ["tue", "Tue"],
  ["wed", "Wed"],
  ["thu", "Thu"],
  ["fri", "Fri"],
  ["sat", "Sat"],
  ["sun", "Sun"],
];

function renderScheduleCalendar(calendar) {
  const days = calendar.days || {};
  const cells = SCHEDULE_DAYS.map(([key, label]) => {
    const times = days[key];
    const active = Array.isArray(times) && times.length > 0;
    const timesText = active ? times.join(", ") : "";
    return `<div class="schedule-day${active ? " is-active" : ""}"${
      active ? ` data-times="${escapeHtml(timesText)}" tabindex="0"` : ""
    }>
      <span class="schedule-day-label">${label}</span>
    </div>`;
  }).join("");

  const condition = calendar.condition
    ? `<p class="schedule-condition">${escapeHtml(calendar.condition)}</p>`
    : "";

  return `<div class="schedule-calendar">${condition}<div class="schedule-week">${cells}</div></div>`;
}

function renderScheduleNotes(prose, isBadgeMode) {
  const trimmed = prose?.trim();
  if (!trimmed) return "";

  const body = isBadgeMode
    ? `<p class="schedule-note">${escapeHtml(trimmed)}</p>`
    : `<pre class="schedule-prose">${escapeHtml(trimmed)}</pre>`;

  return `<div class="schedule-notes">
    <h3 class="schedule-notes-heading">Additional notes:</h3>
    ${body}
  </div>`;
}

function renderSchedulePanel(schedule) {
  if (!schedule?.has_content) return "";

  const parts = ['<section class="schedule-display"><h2>Schedule</h2>'];

  if (schedule.badge) {
    parts.push(`<p class="schedule-badge">${escapeHtml(schedule.badge)}</p>`);
  }

  if (schedule.mode === "structured" && schedule.calendars?.length) {
    parts.push(schedule.calendars.map((calendar) => renderScheduleCalendar(calendar)).join(""));
  }

  if (schedule.prose) {
    parts.push(renderScheduleNotes(schedule.prose, schedule.mode === "badge"));
  }

  parts.push("</section>");
  return parts.join("");
}

const CONTACT_ICON_PHONE = `<svg class="contact-row-icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M6.62 10.79a15.05 15.05 0 006.59 6.59l2.2-2.2a1 1 0 011.01-.24c1.12.37 2.33.57 3.58.57a1 1 0 011 1V20a1 1 0 01-1 1C10.07 21 3 13.93 3 5a1 1 0 011-1h3.5a1 1 0 011 1c0 1.25.2 2.46.57 3.58a1 1 0 01-.24 1.01l-2.2 2.2z"/></svg>`;

const CONTACT_ICON_EMAIL = `<svg class="contact-row-icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M20 4H4a2 2 0 00-2 2v12a2 2 0 002 2h16a2 2 0 002-2V6a2 2 0 00-2-2zm0 4l-8 5-8-5V6l8 5 8-5v2z"/></svg>`;

const CONTACT_ICON_WEBSITE = `<svg class="contact-row-icon" viewBox="0 0 24 24" aria-hidden="true"><path fill="currentColor" d="M12 2a10 10 0 100 20 10 10 0 000-20zm7.93 9h-3.18a15.3 15.3 0 00-1.08-4.72A8.02 8.02 0 0119.93 11zM12 4c.95 1.57 1.62 3.4 1.88 5H10.12c.26-1.6.93-3.43 1.88-5zM4.07 13h3.18c.22 1.68.64 3.28 1.22 4.72A8.02 8.02 0 014.07 13zm3.18-2H4.07a8.02 8.02 0 014.4-4.72C7.89 7.72 7.47 9.32 7.25 11zm1.69 6.28A13.07 13.07 0 018.12 15h7.76c-.41 1.68-1.02 3.22-1.81 4.28A8.03 8.03 0 0112 20a8.03 8.03 0 01-3.94-1.72zM15.88 15a13.07 13.07 0 01-1.69 4.28A8.03 8.03 0 0112 20a8.03 8.03 0 003.94-1.72c.79-1.06 1.4-2.6 1.81-4.28h-2.87zM13.88 9c-.26-1.6-.93-3.43-1.88-5a8.03 8.03 0 013.94 1.72c.79 1.06 1.4 2.6 1.81 4.28h-3.87zm-1.76 0H8.25c.22-1.68.64-3.28 1.22-4.72A8.02 8.02 0 0112 4c-.95 1.57-1.62 3.4-1.88 5z"/></svg>`;

function renderContactRow(href, label, icon, className, external = false) {
  const externalAttrs = external ? ' target="_blank" rel="noopener noreferrer"' : "";
  return `<a class="contact-row ${className}" href="${escapeHtml(href)}"${externalAttrs}>
    <span class="contact-row-label">${escapeHtml(label)}</span>
    ${icon}
  </a>`;
}

function renderContactEntry(entry) {
  const bodyParts = [];

  if (entry.person_name) {
    const cert = entry.cert_label
      ? `<span class="contact-person-cert">(${escapeHtml(entry.cert_label)})</span>`
      : "";
    bodyParts.push(
      `<p class="contact-person-name">${escapeHtml(entry.person_name)}${cert ? ` ${cert}` : ""}</p>`
    );
    if (entry.person_title) {
      bodyParts.push(`<p class="contact-person-title">${escapeHtml(entry.person_title)}</p>`);
    }
  }

  if (entry.organization) {
    const orgClass = entry.person_name ? "contact-organization" : "contact-org-name";
    bodyParts.push(
      `<p class="${orgClass}">${escapeHtml(entry.organization)
        .split("\n")
        .join("<br>")}</p>`
    );
  }

  if (entry.address_lines?.length) {
    bodyParts.push(
      `<div class="contact-address">${entry.address_lines
        .map((line) => `<p>${escapeHtml(line)}</p>`)
        .join("")}</div>`
    );
  }

  const rows = [];
  for (const phone of entry.phones || []) {
    rows.push(
      renderContactRow(phone.href, phone.display, CONTACT_ICON_PHONE, "contact-row-phone")
    );
  }
  for (const email of entry.emails || []) {
    rows.push(
      renderContactRow(email.href, email.display, CONTACT_ICON_EMAIL, "contact-row-email")
    );
  }
  for (const website of entry.websites || []) {
    rows.push(
      renderContactRow(
        website.href,
        website.display,
        CONTACT_ICON_WEBSITE,
        "contact-row-website",
        true
      )
    );
  }

  const bodyHtml = bodyParts.join("");
  const rowsHtml = rows.length ? `<div class="contact-rows">${rows.join("")}</div>` : "";

  return `<div class="contact-entry"><div class="contact-entry-main">${
    bodyHtml ? `<div class="contact-entry-body">${bodyHtml}</div>` : ""
  }${rowsHtml}</div></div>`;
}

function renderPeoplePanel(title, display, { showBadge = false } = {}) {
  if (!display?.has_content) return "";

  const parts = [`<section class="contact-display"><h2>${title}</h2>`];

  if (showBadge && display.badge) {
    parts.push(`<p class="contact-badge">${escapeHtml(display.badge)}</p>`);
  }

  if (display.mode === "structured" && display.entries?.length) {
    parts.push(
      `<div class="contact-entries">${display.entries.map((entry) => renderContactEntry(entry)).join("")}</div>`
    );
  }

  if (display.prose) {
    parts.push(`<pre class="contact-prose">${escapeHtml(display.prose.trim())}</pre>`);
  }

  parts.push("</section>");
  return parts.join("");
}

function renderContactPanel(contact) {
  return renderPeoplePanel("Contact", contact, { showBadge: true });
}

function renderCarillonistPanel(carillonist) {
  return renderPeoplePanel("Carillonist", carillonist);
}

function renderPastTimelineCard(entry) {
  const cert = entry.cert_label
    ? `<span class="contact-person-cert">(${escapeHtml(entry.cert_label)})</span>`
    : "";
  const lifespan = entry.lifespan
    ? `<span class="past-timeline-lifespan">${escapeHtml(entry.lifespan)}</span>`
    : "";
  const title = entry.person_title
    ? `<p class="contact-person-title">${escapeHtml(entry.person_title).replace(/\n/g, "<br>")}</p>`
    : "";
  const dateLabel = entry.date_label
    ? `<span class="past-timeline-date">${escapeHtml(entry.date_label)}</span>`
    : "";
  const name = entry.person_name
    ? `<p class="contact-person-name">${escapeHtml(entry.person_name)}${cert ? ` ${cert}` : ""} ${lifespan}</p>`
    : "";
  const flagClass =
    entry.flags?.some((f) => f.startsWith("placeholder")) ? " is-placeholder" : "";
  const kindClass = entry.kind ? ` past-timeline-card--${entry.kind}` : "";

  return `<div class="past-timeline-card${flagClass}${kindClass}" data-entry-id="${escapeHtml(entry.id)}" style="--card-top:${entry.axis_start_pct ?? 0}%; --card-lane:${entry.lane ?? 0}">
    <div class="past-timeline-connector" aria-hidden="true"></div>
    <div class="past-timeline-card-body">
      ${dateLabel}
      ${name}
      ${title}
    </div>
  </div>`;
}

function assignPastTimelineLanes(entries) {
  const sorted = [...entries].sort(
    (a, b) => (a.start_year ?? 9999) - (b.start_year ?? 9999) || (a.end_year ?? 9999) - (b.end_year ?? 9999)
  );
  const laneEnds = [];
  for (const entry of sorted) {
    const start = entry.start_year ?? 0;
    const end = entry.end_year ?? start;
    let lane = 0;
    while (lane < laneEnds.length && laneEnds[lane] > start) {
      lane += 1;
    }
    entry.lane = lane;
    laneEnds[lane] = end;
  }
}

function renderPastTimelineAxis(timeline) {
  const { year_min: yearMin, year_max: yearMax, entries } = timeline;
  const span = Math.max(yearMax - yearMin, 1);
  const tickStep = span > 120 ? 20 : span > 60 ? 10 : span > 30 ? 5 : 1;
  const firstTick = Math.ceil(yearMin / tickStep) * tickStep;
  const ticks = [];
  for (let year = firstTick; year <= yearMax; year += tickStep) {
    const pct = ((year - yearMin) / span) * 100;
    ticks.push(`<div class="past-timeline-tick" style="top:${pct}%"><span>${year}</span></div>`);
  }

  const segments = entries
    .filter((entry) => typeof entry.axis_start_pct === "number")
    .map(
      (entry) => `<div class="past-timeline-segment past-timeline-segment--${escapeHtml(entry.kind || "tenure")}" data-entry-id="${escapeHtml(entry.id)}" style="top:${entry.axis_start_pct}%; height:${Math.max((entry.axis_end_pct ?? entry.axis_start_pct) - entry.axis_start_pct, entry.kind === "dedication" ? 0.8 : 1.5)}%"></div>`
    )
    .join("");

  return `<div class="past-timeline-axis-col">
    <div class="past-timeline-axis-line" aria-hidden="true"></div>
    <div class="past-timeline-ticks">${ticks.join("")}</div>
    <div class="past-timeline-segments">${segments}</div>
  </div>`;
}

function renderPastTimeline(timeline) {
  assignPastTimelineLanes(timeline.entries || []);
  const label = timeline.label
    ? `<h3 class="past-timeline-subtitle">${escapeHtml(timeline.label)}</h3>`
    : "";
  const cards = (timeline.entries || []).map((entry) => renderPastTimelineCard(entry)).join("");
  const height = Math.max(320, Math.min(720, (timeline.year_max - timeline.year_min) * 4 + 120));

  return `<div class="past-timeline-block">
    ${label}
    <div class="past-timeline-wrap" style="--timeline-height:${height}px">
      ${renderPastTimelineAxis(timeline)}
      <div class="past-timeline-cards-col">${cards}</div>
    </div>
  </div>`;
}

function renderPastUnknownCard(entry) {
  const cert = entry.cert_label
    ? `<span class="contact-person-cert">(${escapeHtml(entry.cert_label)})</span>`
    : "";
  const lifespan = entry.lifespan
    ? `<span class="past-timeline-lifespan">${escapeHtml(entry.lifespan)}</span>`
    : "";
  const title = entry.person_title
    ? `<p class="contact-person-title">${escapeHtml(entry.person_title).replace(/\n/g, "<br>")}</p>`
    : "";
  const dateLabel = entry.date_label
    ? `<p class="past-timeline-date">${escapeHtml(entry.date_label)}</p>`
    : "";
  const name = entry.person_name
    ? `<p class="contact-person-name">${escapeHtml(entry.person_name)}${cert ? ` ${cert}` : ""} ${lifespan}</p>`
    : "";

  return `<div class="past-timeline-unknown-card">${dateLabel}${name}${title}</div>`;
}

function renderPastUnknownCards(entries) {
  return entries.map((entry) => renderPastUnknownCard(entry)).join("");
}

function bindPastTimelineHover(root) {
  root.querySelectorAll(".past-timeline-card").forEach((card) => {
    const id = card.dataset.entryId;
    card.addEventListener("mouseenter", () => {
      root.querySelectorAll(`[data-entry-id="${id}"]`).forEach((el) => el.classList.add("is-highlighted"));
    });
    card.addEventListener("mouseleave", () => {
      root.querySelectorAll(`[data-entry-id="${id}"]`).forEach((el) => el.classList.remove("is-highlighted"));
    });
  });
}

function renderPastCarillonistPanel(past) {
  if (!past?.has_content) return "";

  const parts = ['<section class="past-carillonists-display"><h2>Past carillonists</h2>'];
  for (const timeline of past.timelines || []) {
    parts.push(renderPastTimeline(timeline));
  }
  if (past.unknown_time?.length) {
    parts.push(`<div class="past-timeline-unknown">
      <h3 class="past-timeline-subtitle">Time unknown</h3>
      <div class="past-timeline-unknown-cards">${renderPastUnknownCards(past.unknown_time)}</div>
    </div>`);
  }
  parts.push("</section>");
  return parts.join("");
}

function addMapMarker(map, coords) {
  L.circleMarker(coords, {
    radius: 10,
    color: "#c9a227",
    fillColor: "#e05a5a",
    fillOpacity: 0.9,
    weight: 2,
  }).addTo(map);
}

function initMiniMap(coords) {
  miniMap = L.map("miniMap", { zoomControl: true, attributionControl: false }).setView(coords, 13);
  L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
    subdomains: "abcd",
    maxZoom: 19,
  }).addTo(miniMap);
  addMapMarker(miniMap, coords);
}

function openFullscreenMap() {
  if (!mapCoords) return;
  mapFullscreen.classList.remove("hidden");
  mapFullscreen.setAttribute("aria-hidden", "false");
  document.body.classList.add("map-fullscreen-open");

  if (!fullMap) {
    fullMap = L.map("fullMap", { zoomControl: true, attributionControl: true }).setView(mapCoords, 14);
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      subdomains: "abcd",
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a> &copy; CARTO',
    }).addTo(fullMap);
    addMapMarker(fullMap, mapCoords);
  } else {
    fullMap.setView(mapCoords, 14);
  }

  requestAnimationFrame(() => fullMap.invalidateSize());
}

function closeFullscreenMap() {
  mapFullscreen.classList.add("hidden");
  mapFullscreen.setAttribute("aria-hidden", "true");
  document.body.classList.remove("map-fullscreen-open");
}

mapExpandBtn?.addEventListener("click", openFullscreenMap);
mapCloseBtn?.addEventListener("click", closeFullscreenMap);
mapFullscreen?.addEventListener("click", (event) => {
  if (event.target === mapFullscreen) closeFullscreenMap();
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && !mapFullscreen.classList.contains("hidden")) {
    closeFullscreenMap();
  }
});

async function load() {
  const res = await fetch(`/api/sites/${siteId}`);
  const data = await res.json();
  if (data.error) {
    document.getElementById("title").textContent = "Not found";
    return;
  }

  const site = data.site;
  const idx = data.index || {};
  const display = data.display || {};

  const pageTitle = display.title || site.site_id;
  const pageSubtitle = display.subtitle || "";

  document.title = `${pageTitle} — TowerBells`;
  document.getElementById("title").textContent = pageTitle;
  document.getElementById("subtitle").textContent = pageSubtitle;

  const badgeEl = document.getElementById("titleBadge");
  const pageBadge = display.badge || null;
  if (badgeEl) {
    if (pageBadge) {
      badgeEl.textContent = pageBadge;
      badgeEl.classList.remove("hidden");
      badgeEl.removeAttribute("aria-hidden");
    } else {
      badgeEl.textContent = "";
      badgeEl.classList.add("hidden");
      badgeEl.setAttribute("aria-hidden", "true");
    }
  }

  document.getElementById("locationPanel").innerHTML = renderLocationPanel(display.location, pageBadge);

  document.getElementById("detailContent").innerHTML = [
    section("Technical data", site.technical_data),
    renderCarillonistPanel(display.carillonist),
    renderPastCarillonistPanel(display.past_carillonists),
    renderContactPanel(display.contact),
    renderSchedulePanel(display.schedule),
    section("Remarks", site.remarks),
    section("Prior history", site.prior_history),
  ].join("");

  document.querySelectorAll(".past-carillonists-display").forEach(bindPastTimelineHover);

  const events = idx.carillon_events || [];
  if (events.length) {
    document.getElementById("detailContent").insertAdjacentHTML(
      "beforeend",
      `<section><h2>History events</h2><ul class="rank-list">${events
        .map(
          (event) =>
            `<li><strong>${escapeHtml(String(event.year))}</strong> — ${escapeHtml(event.type || event.code || "")}</li>`
        )
        .join("")}</ul></section>`
    );
  }

  if (site.latitude != null && site.longitude != null) {
    mapCoords = [site.latitude, site.longitude];
    initMiniMap(mapCoords);
    mapExpandBtn.disabled = false;
  } else {
    document.getElementById("miniMap").innerHTML =
      '<p class="detail-empty detail-empty--map">No coordinates available for this site.</p>';
    mapExpandBtn.disabled = true;
    mapExpandBtn.hidden = true;
  }
}

load();
