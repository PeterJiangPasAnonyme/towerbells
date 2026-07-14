const siteId = window.location.pathname.split("/").pop();

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

async function load() {
  const res = await fetch(`/api/sites/${siteId}`);
  const data = await res.json();
  if (data.error) {
    document.getElementById("title").textContent = "Not found";
    return;
  }

  const site = data.site;
  const idx = data.index || {};

  document.title = `${site.full_title || site.short_name} — TowerBells`;
  document.getElementById("title").textContent = site.full_title || site.short_name || site.site_id;
  document.getElementById("subtitle").textContent = [
    site.short_name,
    site.country_code,
    site.state_province,
    idx.installation_year,
    site.bell_count ? `${site.bell_count} bells` : null,
  ]
    .filter(Boolean)
    .join(" · ");

  document.getElementById("detailContent").innerHTML = [
    section("Location", site.location_text),
    section("Technical data", site.technical_data),
    section("Carillonist", site.carillonist),
    section("Past carillonists", site.past_carillonists),
    section("Contact", site.contact),
    section("Schedule", site.schedule),
    section("Remarks", site.remarks),
    section("Prior history", site.prior_history),
  ].join("");

  const lists = data.list_appearances || [];
  if (lists.length) {
    document.getElementById("listAppearances").innerHTML = `
      <h3>Index appearances</h3>
      <ul class="rank-list">
        ${lists
          .slice(0, 20)
          .map(
            (l) =>
              `<li><strong>${escapeHtml(l.list_type || l.filename)}</strong> #${l.rank} — ${escapeHtml(l.line_suffix || "")}</li>`
          )
          .join("")}
      </ul>
    `;
  }

  if (site.latitude != null && site.longitude != null) {
    const mini = L.map("miniMap", { zoomControl: false, attributionControl: false }).setView(
      [site.latitude, site.longitude],
      13
    );
    L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
      subdomains: "abcd",
      maxZoom: 19,
    }).addTo(mini);
    L.circleMarker([site.latitude, site.longitude], {
      radius: 10,
      color: "#c9a227",
      fillColor: "#e05a5a",
      fillOpacity: 0.9,
      weight: 2,
    }).addTo(mini);
  } else {
    document.getElementById("miniMap").innerHTML =
      '<p style="padding:1rem;color:#8fa3b8;font-size:0.85rem">No coordinates available for this site.</p>';
  }
}

load();
