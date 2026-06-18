'use strict';
const MapEngine = (() => {
  const DELHI_CENTER = [28.6139, 77.2090];
  const DEFAULT_ZOOM = 11;
  let MAPTILER_KEY = '';

  function initMap(containerId, options = {}) {
    const el = document.getElementById(containerId);
    if (!el || typeof L === 'undefined') return null;
    const map = L.map(containerId, {
      center: options.center || DELHI_CENTER,
      zoom: options.zoom || DEFAULT_ZOOM,
      zoomControl: false,
    });
    const tileUrl = MAPTILER_KEY
      ? `https://api.maptiler.com/maps/hybrid/{z}/{x}/{y}.jpg?key=${MAPTILER_KEY}`
      : 'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png';
    L.tileLayer(tileUrl, { maxZoom: 19, attribution: '© OpenStreetMap' }).addTo(map);
    L.control.zoom({ position: 'bottomright' }).addTo(map);
    return map;
  }

  function renderIssues(map, issues, role = 'gov') {
    if (!map) return;
    const group = L.layerGroup().addTo(map);
    (issues || []).filter(i => i.lat && i.lng).forEach(issue => {
      const color = issue.severity === 'high' ? '#dc2626' : issue.severity === 'medium' ? '#d97706' : '#16a34a';
      const icon = L.divIcon({
        className: '',
        html: `<div style="width:12px;height:12px;border-radius:50%;background:${color};border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.3)"></div>`,
        iconSize: [12, 12], iconAnchor: [6, 6],
      });
      L.marker([issue.lat, issue.lng], { icon })
        .bindPopup(`<strong>#AP-${issue.id}</strong><br>${issue.area} — ${issue.tag}<br>${issue.description || ''}`)
        .addTo(group);
    });
    return group;
  }

  return { initMap, renderIssues };
})();
window.MapEngine = MapEngine;
