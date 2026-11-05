/* tm-map.js — HOT Tasking Manager project points on the DRC page.
 *
 * Reads the points from <script type="application/json" id="tm-points">
 * (written at build time) and draws them in #tm-map. The map box stays
 * hidden without JavaScript or Leaflet.
 * Requires Leaflet (L) loaded before this script.
 */
(function () {
  var el = document.getElementById('tm-map');
  var dataEl = document.getElementById('tm-points');
  if (!el || !dataEl || typeof L === 'undefined') return;
  var pts;
  try { pts = JSON.parse(dataEl.textContent); } catch (e) { return; }
  if (!pts.length) return;
  el.hidden = false;

  function esc(s) {
    return String(s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }

  var map = L.map(el, { scrollWheelZoom: false });
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19, attribution: '&copy; OpenStreetMap contributors'
  }).addTo(map);

  var group = L.featureGroup();
  // Completed first so the open markers draw on top.
  pts.filter(function (p) { return !p.open; }).concat(pts.filter(function (p) { return p.open; }))
    .forEach(function (p) {
      var style = p.open
        ? { radius: 9, color: '#ffffff', weight: 2, fillColor: '#f44a52', fillOpacity: 1 }
        : { radius: 6, color: '#ffffff', weight: 1.5, fillColor: '#6b7a84', fillOpacity: 1 };
      L.circleMarker([p.lat, p.lng], style)
        .bindPopup('<strong>' + esc(p.name) + '</strong><br>' + (p.open ? 'Open' : 'Completed') +
          ' · <a href="https://tasks.hotosm.org/projects/' + encodeURIComponent(p.id) + '" target="_blank" rel="noopener">#' + esc(p.id) + '</a>')
        .addTo(group);
    });
  group.addTo(map);
  map.fitBounds(group.getBounds(), { padding: [24, 24], maxZoom: 11 });
})();
