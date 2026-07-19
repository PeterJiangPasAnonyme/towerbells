(function () {
  const FILTER_STORAGE_KEY = "towerbellsFilters";
  const MAP_VIEW_STORAGE_KEY = "towerbellsMapView";

  function getSavedFilterQuery() {
    if (window.location.pathname === "/" && window.location.search.length > 1) {
      return window.location.search.slice(1);
    }
    return sessionStorage.getItem(FILTER_STORAGE_KEY) || "";
  }

  function getSavedFilterUrl() {
    const query = getSavedFilterQuery();
    return query ? `/?${query}` : "/";
  }

  function saveFilterQuery(query) {
    if (query) {
      sessionStorage.setItem(FILTER_STORAGE_KEY, query);
    } else {
      sessionStorage.removeItem(FILTER_STORAGE_KEY);
      sessionStorage.removeItem(MAP_VIEW_STORAGE_KEY);
    }
  }

  function saveMapView(view) {
    if (!view || view.lat == null || view.lng == null || view.zoom == null) {
      return;
    }
    sessionStorage.setItem(
      MAP_VIEW_STORAGE_KEY,
      JSON.stringify({
        lat: view.lat,
        lng: view.lng,
        zoom: view.zoom,
      })
    );
  }

  function getSavedMapView() {
    const raw = sessionStorage.getItem(MAP_VIEW_STORAGE_KEY);
    if (!raw) {
      return null;
    }
    try {
      const view = JSON.parse(raw);
      if (view && view.lat != null && view.lng != null && view.zoom != null) {
        return view;
      }
    } catch {
      return null;
    }
    return null;
  }

  function wireBackToMapLink(selector) {
    const link = document.querySelector(selector || ".back-link");
    if (link) {
      link.href = getSavedFilterUrl();
    }
  }

  window.TowerbellsFilters = {
    FILTER_STORAGE_KEY,
    MAP_VIEW_STORAGE_KEY,
    getSavedFilterQuery,
    getSavedFilterUrl,
    saveFilterQuery,
    saveMapView,
    getSavedMapView,
    wireBackToMapLink,
  };
})();
