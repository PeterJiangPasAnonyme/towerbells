const siteId = window.location.pathname.split("/").pop();

const backLink = document.querySelector(".back-link");
const editLink = document.getElementById("editLink");
const mapExpandBtn = document.getElementById("mapExpandBtn");
const mapCloseBtn = document.getElementById("mapCloseBtn");
const mapFullscreen = document.getElementById("mapFullscreen");

if (editLink) {
  editLink.href = `/admin?site=${encodeURIComponent(siteId)}`;
}
if (window.TowerbellsFilters?.wireBackToMapLink) {
  window.TowerbellsFilters.wireBackToMapLink(".back-link");
} else if (backLink) {
  const saved = sessionStorage.getItem("towerbellsFilters");
  backLink.href = saved ? `/?${saved}` : "/";
}

let miniMap = null;
let fullMap = null;
let mapCoords = null;

function section(title, text) {
  if (!text || !text.trim()) return "";
  return `<section><h2>${title}</h2><pre>${escapeHtml(text.trim())}</pre></section>`;
}

function renderRemarksPanel(remarks) {
  if (!remarks?.has_content || !remarks.paragraphs?.length) return "";
  const body = remarks.paragraphs.map((paragraph) => `<p>${escapeHtml(paragraph)}</p>`).join("");
  return `<section class="remarks-panel"><h2>Remarks</h2>${body}</section>`;
}

function renderLinksPanel(links) {
  if (!links?.has_content || !links.paragraphs?.length) return "";
  const body = links.paragraphs
    .map((paragraph) => `<p class="links-paragraph">${paragraph.html || ""}</p>`)
    .join("");
  return `<section class="links-panel"><h2>Links</h2>${body}</section>`;
}

function isMiddleC(key) {
  return Boolean(key && !key.gap && key.midi === 60 && key.keyboard === "C");
}

function midiOctave(midi) {
  return Math.floor(midi / 12) - 1;
}

function formatNoteWithOctave(pitchName, midi) {
  if (!pitchName || midi == null) return null;
  return `${pitchName}${midiOctave(midi)}`;
}

function keyNoteLabels(key, transpositionSemitones) {
  if (key.midi == null || !key.keyboard) return null;
  const keyboardNote = formatNoteWithOctave(key.keyboard, key.midi);
  if (!keyboardNote) return null;
  if (key.gap) return { keyboardNote };
  const shift = transpositionSemitones ?? 0;
  const playedPitch = key.concert || key.keyboard;
  const playedNote = formatNoteWithOctave(playedPitch, key.midi + shift);
  return { keyboardNote, playedNote: playedNote || keyboardNote };
}

function keyTooltipDataAttrs(key, transpositionSemitones) {
  const labels = keyNoteLabels(key, transpositionSemitones);
  if (!labels) return "";
  if (key.gap) {
    return ` data-missing-note="${escapeHtml(labels.keyboardNote)}"`;
  }
  return ` data-keyboard-note="${escapeHtml(labels.keyboardNote)}" data-played-note="${escapeHtml(labels.playedNote)}"`;
}

let keyboardFloatingTooltip = null;
let activeKeyboardKey = null;

function getKeyboardFloatingTooltip() {
  if (!keyboardFloatingTooltip) {
    keyboardFloatingTooltip = document.createElement("div");
    keyboardFloatingTooltip.className = "keyboard-key-tooltip keyboard-key-tooltip--floating";
    keyboardFloatingTooltip.setAttribute("role", "tooltip");
    keyboardFloatingTooltip.hidden = true;
    document.body.appendChild(keyboardFloatingTooltip);
  }
  return keyboardFloatingTooltip;
}

function hideKeyboardFloatingTooltip() {
  if (!keyboardFloatingTooltip) return;
  keyboardFloatingTooltip.hidden = true;
  keyboardFloatingTooltip.classList.remove("keyboard-key-tooltip--shown");
  activeKeyboardKey = null;
}

function positionKeyboardFloatingTooltip(keyEl, tooltip) {
  const missingNote = keyEl.dataset.missingNote;
  if (missingNote) {
    tooltip.innerHTML = `<span class="keyboard-key-tooltip-line">Missing Note: ${escapeHtml(
      missingNote
    )}</span>`;
  } else {
    const keyboardNote = keyEl.dataset.keyboardNote;
    const playedNote = keyEl.dataset.playedNote;
    if (!keyboardNote || !playedNote) return;

    tooltip.innerHTML = `<span class="keyboard-key-tooltip-line">Keyboard Note: ${escapeHtml(
      keyboardNote
    )}</span><span class="keyboard-key-tooltip-line">Played Note: ${escapeHtml(playedNote)}</span>`;
  }
  tooltip.hidden = false;
  tooltip.classList.add("keyboard-key-tooltip--shown");

  tooltip.style.left = "-9999px";
  tooltip.style.top = "0px";

  const keyRect = keyEl.getBoundingClientRect();
  const tipRect = tooltip.getBoundingClientRect();
  const isHands = Boolean(keyEl.closest(".keyboard-section--hands"));
  const margin = 8;
  const gap = 6;

  let left = keyRect.left + keyRect.width / 2 - tipRect.width / 2;
  left = Math.max(margin, Math.min(left, window.innerWidth - tipRect.width - margin));

  let top = isHands ? keyRect.top - tipRect.height - gap : keyRect.bottom + gap;
  top = Math.max(margin, Math.min(top, window.innerHeight - tipRect.height - margin));

  tooltip.style.left = `${left}px`;
  tooltip.style.top = `${top}px`;
}

function showKeyboardFloatingTooltip(keyEl) {
  if (!keyEl.dataset.keyboardNote && !keyEl.dataset.missingNote) return;
  activeKeyboardKey = keyEl;
  positionKeyboardFloatingTooltip(keyEl, getKeyboardFloatingTooltip());
}

function bindKeyboardTooltips(root) {
  if (root.dataset.tooltipsBound === "1") return;
  root.dataset.tooltipsBound = "1";

  const reposition = () => {
    if (!activeKeyboardKey) return;
    positionKeyboardFloatingTooltip(activeKeyboardKey, getKeyboardFloatingTooltip());
  };

  root.addEventListener("mouseover", (event) => {
    const key = event.target.closest(".keyboard-key");
    if (!key || !root.contains(key)) return;
    if (activeKeyboardKey === key) return;
    showKeyboardFloatingTooltip(key);
  });

  root.addEventListener("mouseout", (event) => {
    const key = event.target.closest(".keyboard-key");
    if (!key || activeKeyboardKey !== key) return;
    const to = event.relatedTarget;
    if (to && key.contains(to)) return;
    hideKeyboardFloatingTooltip();
  });

  root.querySelectorAll(".keyboard-scroll-inner").forEach((el) => {
    el.addEventListener("scroll", reposition, { passive: true });
  });
  window.addEventListener("resize", reposition, { passive: true });
  window.addEventListener("scroll", reposition, { passive: true });
}

function annotateKeyMidis(keys) {
  let prevMidi = null;
  return keys.map((key) => {
    if (key.midi != null) {
      if (!key.gap && !key.empty) {
        prevMidi = key.midi;
      }
      return key;
    }
    const midi = prevMidi != null ? prevMidi + 1 : null;
    if (midi != null) prevMidi = midi;
    return { ...key, midi };
  });
}

function keyboardLayoutMetrics(variant) {
  if (variant === "pedals") {
    return { tubeW: 0.75, gap: 1, sharpW: 0.75 };
  }
  return { tubeW: 0.8, gap: 0.4, sharpW: 0.67 };
}

function overlayPos(afterNatural) {
  return Math.max(afterNatural + 1, 0);
}

function slotBounds(slot, layout) {
  const step = layout.tubeW + layout.gap;
  if (slot.type === "natural" || (slot.type === "gap" && slot.naturalIdx != null)) {
    const left = slot.naturalIdx * step;
    return { left, right: left + layout.tubeW };
  }
  const pos = overlayPos(slot.afterNatural);
  const center = pos * step - layout.gap / 2;
  return { left: center - layout.tubeW / 2, right: center + layout.tubeW / 2 };
}

function computeLeadingOffset(slots, layout) {
  let minLeft = 0;
  for (const slot of slots) {
    const { left } = slotBounds(slot, layout);
    minLeft = Math.min(minLeft, left);
  }
  const inset = 0.08;
  return minLeft < 0 ? -minLeft + inset : 0;
}

function buildKeyboardSlots(keys) {
  const slots = [];
  let naturalIdx = -1;
  for (const key of keys) {
    if (key.gap && !key.is_sharp) {
      naturalIdx += 1;
      slots.push({ key, type: "gap", naturalIdx });
    } else if (!key.gap && !key.is_sharp) {
      naturalIdx += 1;
      slots.push({ key, type: "natural", naturalIdx });
    } else {
      slots.push({
        key,
        type: key.gap ? "gap" : "sharp",
        afterNatural: naturalIdx,
      });
    }
  }
  return slots;
}

function buildOctaveMarkers(keys, variant) {
  const layout = keyboardLayoutMetrics(variant);
  const annotated = annotateKeyMidis(keys);
  const slots = buildKeyboardSlots(annotated);
  const leadingOffset = computeLeadingOffset(slots, layout);

  const placed = slots.map((slot) => ({
    slot,
    bounds: slotBounds(slot, layout),
    key: slot.key,
  }));

  const active = placed.filter(({ key }) => key.midi != null && !key.gap);
  const cSlots = active.filter(({ key }) => key.keyboard === "C");
  let octaves = [];
  const cLabels = [];

  if (!active.length) {
    return { octaves, cLabels, leadingOffset };
  }

  let preCBracket = null;
  const firstC = cSlots[0];
  if (firstC) {
    const beforeC = active.filter(({ bounds }) => bounds.right <= firstC.bounds.left + 0.001);
    if (beforeC.length) {
      const oct = midiOctave(beforeC[0].key.midi);
      const left = Math.min(...beforeC.map(({ bounds }) => bounds.left));
      if (oct === midiOctave(firstC.key.midi)) {
        preCBracket = { oct, left };
      } else {
        octaves.push([
          oct,
          {
            left,
            right: firstC.bounds.left - layout.gap,
            keyCount: beforeC.length,
          },
        ]);
      }
    }
  }

  for (let i = 0; i < cSlots.length; i += 1) {
    const cSlot = cSlots[i];
    const oct = midiOctave(cSlot.key.midi);
    const nextC = cSlots[i + 1];
    const group = active.filter(({ key, bounds }) => {
      if (midiOctave(key.midi) !== oct) return false;
      if (bounds.left < cSlot.bounds.left - 0.001) return false;
      if (nextC && bounds.left >= nextC.bounds.left) return false;
      return true;
    });
    if (!group.length) continue;

    let left = Math.min(...group.map(({ bounds }) => bounds.left));
    const right = Math.max(...group.map(({ bounds }) => bounds.right));
    if (preCBracket && preCBracket.oct === oct && cSlot === firstC) {
      left = preCBracket.left;
      preCBracket = null;
    }

    octaves.push([oct, { left, right, keyCount: group.length }]);

    cLabels.push({
      label: `C${oct}`,
      left: cSlot.bounds.left + layout.tubeW / 2,
      middle: cSlot.key.midi === 60,
    });
  }

  const bracketedOcts = new Set(octaves.map(([oct]) => oct));
  const leftovers = new Map();
  for (const item of active) {
    const oct = midiOctave(item.key.midi);
    if (bracketedOcts.has(oct)) continue;
    if (!leftovers.has(oct)) leftovers.set(oct, []);
    leftovers.get(oct).push(item);
  }
  for (const [oct, group] of [...leftovers.entries()].sort((a, b) => a[0] - b[0])) {
    octaves.push([
      oct,
      {
        left: Math.min(...group.map(({ bounds }) => bounds.left)),
        right: Math.max(...group.map(({ bounds }) => bounds.right)),
        keyCount: group.length,
      },
    ]);
  }

  octaves.sort((a, b) => a[0] - b[0]);
  octaves = collapseLonerOctaves(octaves, active);

  return { octaves, cLabels, leadingOffset };
}

function collapseLonerOctaves(octaves, active) {
  if (octaves.length < 2) return octaves;

  const collapsed = [];
  for (const [oct, bounds] of octaves) {
    const isLoneC =
      bounds.keyCount === 1 &&
      active.some(
        ({ key, bounds: keyBounds }) =>
          key.keyboard === "C" &&
          midiOctave(key.midi) === oct &&
          Math.abs(keyBounds.left - bounds.left) < 0.001 &&
          Math.abs(keyBounds.right - bounds.right) < 0.001
      );

    if (isLoneC && collapsed.length) {
      const prev = collapsed[collapsed.length - 1];
      prev[1].right = Math.max(prev[1].right, bounds.right);
      continue;
    }

    collapsed.push([oct, { left: bounds.left, right: bounds.right, keyCount: bounds.keyCount }]);
  }

  return collapsed;
}

function renderOctaveMap(keys, variant, leadingOffset = 0) {
  const { octaves, cLabels } = buildOctaveMarkers(keys, variant);
  if (!octaves.length) return "";

  const brackets = octaves
    .map(([oct, bounds]) => {
      const width = bounds.right - bounds.left;
      const left = bounds.left + leadingOffset;
      return `<div class="keyboard-octave" style="left:${left}rem;width:${width}rem">
        <div class="keyboard-octave-bracket" aria-hidden="true">
          <span class="keyboard-octave-tick keyboard-octave-tick--left"></span>
          <span class="keyboard-octave-bar"></span>
          <span class="keyboard-octave-tick keyboard-octave-tick--right"></span>
        </div>
        <span class="keyboard-octave-number">${oct}</span>
      </div>`;
    })
    .join("");

  const cMarks = cLabels
    .map(({ label, left, middle }) => {
      const middleClass = middle ? " keyboard-c-label--middle-c" : "";
      return `<span class="keyboard-c-label${middleClass}" style="left:${left + leadingOffset}rem">${escapeHtml(label)}</span>`;
    })
    .join("");

  return `<div class="keyboard-octave-map">${cMarks}${brackets}</div>`;
}

function renderNaturalKey(key, isPedal, transpositionSemitones) {
  const middleClass = isMiddleC(key) ? " keyboard-key--middle-c" : "";
  const tipAttrs = keyTooltipDataAttrs(key, transpositionSemitones);
  if (isPedal) {
    return `<div class="keyboard-key keyboard-key--natural${middleClass}"${tipAttrs}>
      <div class="keyboard-pedal keyboard-pedal--natural" aria-hidden="true">
        <span class="keyboard-pedal-stem"></span>
      </div>
    </div>`;
  }
  return `<div class="keyboard-key keyboard-key--natural${middleClass}"${tipAttrs}>
    <div class="keyboard-baton keyboard-baton--natural" aria-hidden="true">
      <span class="keyboard-baton-cap"></span>
      <span class="keyboard-baton-stem"></span>
    </div>
  </div>`;
}

function renderNaturalGapKey(key, isPedal, transpositionSemitones) {
  const labels = keyNoteLabels(key, transpositionSemitones);
  const ariaLabel = labels ? `Missing ${labels.keyboardNote}` : "Missing key";
  const tipAttrs = keyTooltipDataAttrs(key, transpositionSemitones);
  if (isPedal) {
    return `<div class="keyboard-key keyboard-key--gap" aria-label="${escapeHtml(ariaLabel)}"${tipAttrs}>
      <div class="keyboard-pedal keyboard-pedal--natural keyboard-pedal--gap" aria-hidden="true">
        <span class="keyboard-pedal-stem"></span>
      </div>
    </div>`;
  }
  return `<div class="keyboard-key keyboard-key--gap" aria-label="${escapeHtml(ariaLabel)}"${tipAttrs}>
    <div class="keyboard-baton keyboard-baton--natural keyboard-baton--gap" aria-hidden="true">
      <span class="keyboard-baton-cap"></span>
      <span class="keyboard-baton-stem"></span>
    </div>
  </div>`;
}

function renderOverlayKey(key, isPedal, transpositionSemitones) {
  const labels = keyNoteLabels(key, transpositionSemitones);
  const ariaLabel = labels ? `Missing ${labels.keyboardNote}` : "Missing key";
  const tipAttrs = keyTooltipDataAttrs(key, transpositionSemitones);
  if (key.gap) {
    if (isPedal) {
      return `<div class="keyboard-key keyboard-key--gap" aria-label="${escapeHtml(ariaLabel)}"${tipAttrs}>
        <div class="keyboard-pedal keyboard-pedal--sharp keyboard-pedal--gap" aria-hidden="true">
          <span class="keyboard-pedal-stem"></span>
        </div>
      </div>`;
    }
    return `<div class="keyboard-key keyboard-key--gap" aria-label="${escapeHtml(ariaLabel)}"${tipAttrs}>
      <div class="keyboard-baton keyboard-baton--sharp keyboard-baton--gap" aria-hidden="true">
        <span class="keyboard-baton-cap"></span>
        <span class="keyboard-baton-stem"></span>
      </div>
    </div>`;
  }
  if (isPedal) {
    return `<div class="keyboard-key keyboard-key--sharp"${tipAttrs}>
      <div class="keyboard-pedal keyboard-pedal--sharp" aria-hidden="true">
        <span class="keyboard-pedal-stem"></span>
      </div>
    </div>`;
  }
  return `<div class="keyboard-key keyboard-key--sharp"${tipAttrs}>
    <div class="keyboard-baton keyboard-baton--sharp" aria-hidden="true">
      <span class="keyboard-baton-cap"></span>
      <span class="keyboard-baton-stem"></span>
    </div>
  </div>`;
}

function renderKeyboardKeys(keys, variant, transpositionSemitones) {
  if (!Array.isArray(keys) || !keys.length) return "";
  const isPedal = variant === "pedals";
  const annotated = annotateKeyMidis(keys);

  const naturals = [];
  const overlays = [];
  let naturalIdx = -1;

  for (const key of annotated) {
    if (key.gap && !key.is_sharp) {
      naturalIdx += 1;
      naturals.push({ key, isGap: true });
    } else if (!key.gap && !key.is_sharp) {
      naturalIdx += 1;
      naturals.push({ key, isGap: false });
    } else {
      overlays.push({ key, afterNatural: naturalIdx });
    }
  }

  const slots = buildKeyboardSlots(annotated);
  const layout = keyboardLayoutMetrics(variant);
  const leadingOffset = computeLeadingOffset(slots, layout);

  const naturalCols = naturals
    .map(({ key, isGap }) => {
      const inner = isGap
        ? renderNaturalGapKey(key, isPedal, transpositionSemitones)
        : renderNaturalKey(key, isPedal, transpositionSemitones);
      return `<div class="keyboard-col">${inner}</div>`;
    })
    .join("");

  const overlayItems = overlays
    .map(({ key, afterNatural }) => {
      const pos = overlayPos(afterNatural);
      return `<div class="keyboard-overlay" style="--key-pos:${pos}">${renderOverlayKey(
        key,
        isPedal,
        transpositionSemitones
      )}</div>`;
    })
    .join("");

  return `<div class="keyboard-keys keyboard-keys--${variant}" style="--key-leading-offset:${leadingOffset}rem">
    <div class="keyboard-piano">
      <div class="keyboard-naturals">${naturalCols}</div>
      <div class="keyboard-overlays">${overlayItems}</div>
    </div>
    ${renderOctaveMap(annotated, variant, leadingOffset)}
  </div>`;
}

function renderKeyboardSection(sectionData, title, variant, transpositionSemitones) {
  if (!sectionData?.keys?.length) return "";

  return `<div class="keyboard-section keyboard-section--${variant}">
    <div class="keyboard-section-head">
      <h3 class="keyboard-section-title">${escapeHtml(title)}</h3>
    </div>
    <div class="keyboard-scroll">
      <div class="keyboard-scroll-inner">${renderKeyboardKeys(
        sectionData.keys,
        variant,
        transpositionSemitones
      )}</div>
    </div>
  </div>`;
}

function renderSpecSubitems(subitems) {
  return subitems
    .map((sub) => {
      if (sub.subitems?.length) {
        const nested = renderSpecSubitems(sub.subitems);
        return `<li class="technical-spec-subitem technical-spec-subitem--group">
          <span class="technical-spec-label">${escapeHtml(sub.label)}:</span>
          <ul class="technical-spec-sublist">${nested}</ul>
        </li>`;
      }
      return `<li class="technical-spec-subitem"><span class="technical-spec-label">${escapeHtml(
        sub.label
      )}:</span> ${escapeHtml(sub.value)}</li>`;
    })
    .join("");
}

function renderTechnicalSpecList(technical) {
  if (!technical?.items?.length) return "";

  const rows = technical.items
    .map((item) => {
      if (item.subitems?.length) {
        const nested = renderSpecSubitems(item.subitems);
        return `<li class="technical-spec-item technical-spec-item--group">
          <span class="technical-spec-label">${escapeHtml(item.label)}:</span>
          <ul class="technical-spec-sublist">${nested}</ul>
        </li>`;
      }
      return `<li class="technical-spec-item">
        <span class="technical-spec-label">${escapeHtml(item.label)}:</span>
        ${escapeHtml(item.value)}
      </li>`;
    })
    .join("");

  let html = `<ul class="technical-spec-list">${rows}</ul>`;
  if (technical.tech_info_year) {
    html += `<p class="technical-spec-footnote">Year of latest technical information: ${escapeHtml(
      technical.tech_info_year
    )}</p>`;
  }
  return html;
}

function renderKeyboardDiagram(keyboard, { compact = false } = {}) {
  if (!keyboard?.has_content || keyboard?.hide_diagram) return "";
  if (keyboard.mode !== "structured") return "";

  const parts = [`<div class="keyboard-display${compact ? " keyboard-display--compact" : ""}">`];
  parts.push('<div class="keyboard-display-head">');
  if (keyboard.keyboard_range_raw) {
    parts.push(`<p class="keyboard-range-raw">${escapeHtml(keyboard.keyboard_range_raw)}</p>`);
  }
  if (keyboard.transposition_badge != null && keyboard.transposition_badge !== "") {
    parts.push(
      `<span class="keyboard-transposition-badge">Transposition: ${escapeHtml(
        keyboard.transposition_badge
      )}</span>`
    );
  }
  parts.push("</div>");

  const transpositionSemitones = keyboard.transposition_semitones ?? null;
  parts.push(renderKeyboardSection(keyboard.hands, "Batons", "hands", transpositionSemitones));
  parts.push(renderKeyboardSection(keyboard.pedals, "Pedals", "pedals", transpositionSemitones));

  parts.push("</div>");
  return parts.join("");
}

function renderTimelineEvents(events) {
  return (events || [])
    .map((event) => {
      const bullets = (event.bullets || [])
        .map((item) => `<li>${escapeHtml(item)}</li>`)
        .join("");
      const keyboardBullets = (event.keyboard_bullets || [])
        .map((item) => `<li>${escapeHtml(item)}</li>`)
        .join("");
      const bulletList =
        bullets || keyboardBullets
          ? `<ul class="prior-history-bullets">${bullets}${keyboardBullets}</ul>`
          : "";
      const keyboard = event.keyboard ? renderKeyboardDiagram(event.keyboard, { compact: true }) : "";

      return `<article class="prior-history-event">
        <div class="prior-history-marker" aria-hidden="true"><span class="prior-history-dot"></span></div>
        <div class="prior-history-content">
          <div class="prior-history-event-year">${escapeHtml(String(event.year))}</div>
          <p class="prior-history-event-headline">${escapeHtml(event.headline || "")}</p>
          ${bulletList}
          ${keyboard}
        </div>
      </article>`;
    })
    .join("");
}

function renderTimelinePanel(title, timeline) {
  if (!timeline?.has_content || !timeline.events?.length) return "";

  return `<section class="prior-history-display"><h2>${escapeHtml(title)}</h2><div class="prior-history-timeline">${renderTimelineEvents(
    timeline.events
  )}</div></section>`;
}

function renderPriorHistoryPanel(priorHistory) {
  return renderTimelinePanel("Prior history", priorHistory);
}

function renderFormerLocationsPanel(formerLocations) {
  return renderTimelinePanel("Former locations", formerLocations);
}

function renderTechnicalPanel(site, keyboard, technical) {
  const showDiagram = Boolean(keyboard?.has_content && !keyboard?.hide_diagram);
  const hasSpec = Boolean(technical?.items?.length);
  const hasProse = Boolean(keyboard?.prose?.trim());

  if (!showDiagram && !hasSpec && !hasProse && !technical?.has_content) return "";

  const parts = ['<section class="technical-display"><h2>Technical data</h2>'];

  if (showDiagram) {
    parts.push(renderKeyboardDiagram(keyboard));
  }

  if (hasSpec) {
    parts.push(renderTechnicalSpecList(technical));
  }

  if (hasProse) {
    parts.push(`<pre class="keyboard-prose">${escapeHtml(keyboard.prose.trim())}</pre>`);
  }

  parts.push("</section>");
  return parts.join("");
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
  const building = location.building || {};
  const buildingLine =
    building.line ||
    location.name ||
    null;
  const buildingTranslation =
    building.translation ||
    (Array.isArray(location.also_known_as) ? location.also_known_as[0] : null) ||
    null;
  let cityRegion = location.city_region || null;
  let country = location.country || null;
  if (!cityRegion && location.locality) {
    const localityParts = String(location.locality)
      .split(",")
      .map((part) => part.trim())
      .filter(Boolean);
    if (localityParts.length >= 2) {
      country = country || localityParts[localityParts.length - 1];
      cityRegion = localityParts.slice(0, -1).join(", ");
    } else {
      cityRegion = location.locality;
    }
  }

  const hideBuilding =
    pageBadge &&
    buildingLine &&
    /mobile carillon|in storage/i.test(pageBadge) &&
    /mobile carillon|in storage/i.test(buildingLine);

  if (buildingLine && !hideBuilding && !location.hide_building) {
    parts.push(`<p class="location-building">${escapeHtml(buildingLine)}</p>`);
    if (buildingTranslation) {
      parts.push(`<p class="location-building-translation">${escapeHtml(buildingTranslation)}</p>`);
    }
  }

  const localityParts = [];
  if (location.address_lines?.length) {
    localityParts.push(
      `<div class="location-address">${location.address_lines
        .map((line) => `<p>${escapeHtml(line)}</p>`)
        .join("")}</div>`
    );
  }
  if (cityRegion) {
    localityParts.push(`<p class="location-city-region">${escapeHtml(cityRegion)}</p>`);
  }
  if (country) {
    localityParts.push(`<p class="location-country">${escapeHtml(country)}</p>`);
  }
  if (localityParts.length) {
    parts.push(`<div class="location-locality-block">${localityParts.join("")}</div>`);
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
  const title = carillonist?.title || "Carillonist";
  return renderPeoplePanel(title, carillonist);
}

function formatPastLifespan(lifespan) {
  if (!lifespan) return "";
  if (lifespan === "(–)" || lifespan === "(-)") return "†";
  return lifespan;
}

function renderPastCarillonistEvent(entry) {
  const cert = entry.cert_label
    ? `<span class="contact-person-cert">(${escapeHtml(entry.cert_label)})</span>`
    : "";
  const lifespanText = formatPastLifespan(entry.lifespan);
  const lifespan = lifespanText
    ? `<span class="past-timeline-lifespan">${escapeHtml(lifespanText)}</span>`
    : "";
  const title = entry.person_title
    ? `<p class="contact-person-title">${escapeHtml(entry.person_title).replace(/\n/g, "<br>")}</p>`
    : "";
  const yearLine = entry.date_label
    ? `<div class="past-carillonist-event-year">${escapeHtml(entry.date_label)}</div>`
    : "";
  const name = entry.person_name
    ? `<p class="contact-person-name">${escapeHtml(entry.person_name)}${cert ? ` ${cert}` : ""} ${lifespan}</p>`
    : "";
  const kindClass = entry.kind ? ` past-carillonist-event--${entry.kind}` : "";

  return `<article class="prior-history-event past-carillonist-event${kindClass}">
    <div class="prior-history-marker" aria-hidden="true"><span class="prior-history-dot"></span></div>
    <div class="prior-history-content">
      ${yearLine}
      <div class="past-timeline-card-body">
        ${name}
        ${title}
      </div>
    </div>
  </article>`;
}

function collectPastCarillonistEntries(past) {
  const entries = [];
  for (const timeline of past.timelines || []) {
    entries.push(...(timeline.entries || []));
  }
  entries.push(...(past.unknown_time || []));
  return entries.sort((a, b) => {
    const ay = a.start_year ?? a.end_year ?? a.anchor_year ?? -1;
    const by = b.start_year ?? b.end_year ?? b.anchor_year ?? -1;
    if (ay !== by) return ay - by;
    return String(a.date_label || "").localeCompare(String(b.date_label || ""));
  });
}

function renderPastCarillonistPanel(past) {
  if (!past?.has_content) return "";

  const entries = collectPastCarillonistEntries(past);
  if (!entries.length) return "";

  const events = entries.map((entry) => renderPastCarillonistEvent(entry)).join("");
  return `<section class="past-carillonists-display"><h2>${escapeHtml(
    past.title || "Past carillonists"
  )}</h2><div class="prior-history-timeline">${events}</div></section>`;
}

const MAP_TILE_URL = "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png";

function addMapMarker(map, coords) {
  L.circleMarker(coords, {
    radius: 6,
    color: "#1d4ed8",
    fillColor: "#2563eb",
    fillOpacity: 0.9,
    weight: 1.5,
  }).addTo(map);
}

function initMiniMap(coords) {
  if (miniMap) {
    miniMap.setView(coords, 13);
    return;
  }
  miniMap = L.map("miniMap", { zoomControl: true, attributionControl: false }).setView(coords, 13);
  L.tileLayer(MAP_TILE_URL, {
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
    L.tileLayer(MAP_TILE_URL, {
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
  try {
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
    const pageTitleTranslation = display.title_translation || "";
    const pageSubtitle = display.subtitle || "";

    document.title = `${pageTitle} — TowerBells`;
    document.getElementById("title").textContent = pageTitle;

    const titleTranslationEl = document.getElementById("titleTranslation");
    if (titleTranslationEl) {
      if (pageTitleTranslation) {
        titleTranslationEl.textContent = pageTitleTranslation;
        titleTranslationEl.classList.remove("hidden");
        titleTranslationEl.removeAttribute("aria-hidden");
      } else {
        titleTranslationEl.textContent = "";
        titleTranslationEl.classList.add("hidden");
        titleTranslationEl.setAttribute("aria-hidden", "true");
      }
    }

    document.getElementById("subtitle").textContent = pageSubtitle;

    const legacyLink = document.getElementById("legacyLink");
    if (legacyLink && site.page_url) {
      legacyLink.href = site.page_url;
      legacyLink.classList.remove("hidden");
      legacyLink.removeAttribute("aria-hidden");
    } else if (legacyLink) {
      legacyLink.classList.add("hidden");
      legacyLink.setAttribute("aria-hidden", "true");
    }

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
      renderFormerLocationsPanel(display.former_locations),
      renderCarillonistPanel(display.carillonist),
      renderPastCarillonistPanel(display.past_carillonists),
      renderContactPanel(display.contact),
      renderSchedulePanel(display.schedule),
      renderTechnicalPanel(site, display.keyboard, display.technical),
      renderPriorHistoryPanel(display.prior_history),
      renderRemarksPanel(display.remarks),
      renderLinksPanel(display.links),
    ].join("");

    document.querySelectorAll(".keyboard-display").forEach(bindKeyboardTooltips);

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
  } catch (error) {
    console.error(error);
    document.getElementById("title").textContent = "Could not load site";
    document.getElementById("detailContent").innerHTML =
      '<p class="detail-empty">This page failed to load. Try refreshing.</p>';
  }
}

load();
