/* campaign-map.js — shared Leaflet map for country, region and Senegal pages.
 *
 * Usage: <div id="map" class="campaign-map"
 *             data-geojson="…/theme/geojson/cod_admin1.geojson"
 *             data-lat="-2.9" data-lng="23.6" data-zoom="5"></div>
 * Requires Leaflet (L) loaded before this script.
 */
(function () {
    'use strict';

    // Region name: QGIS exports use adm1_name; older files use name / ADM1_*.
    function regionName(p) {
        return p.adm1_name || p.name || p.ADM1_FR || p.ADM1_EN || 'Unnamed area';
    }

    function escapeHtml(s) {
        return String(s).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }

    function styleFor(feature) {
        var status = (feature.properties.status || '').toLowerCase();
        var fill = status === 'complete' ? '#2e7d32'   // green - validated
                 : status === 'active'   ? '#f44a52'   // brand - in progress
                 : '#9e9e9e';                          // grey  - planned
        return {
            color: '#000000',
            weight: 1,
            opacity: 0.8,
            fillColor: fill,
            fillOpacity: status ? 0.35 : 0.05
        };
    }

    function init(el) {
        if (typeof L === 'undefined') return;

        var lat = parseFloat(el.dataset.lat);
        var lng = parseFloat(el.dataset.lng);
        var zoom = parseInt(el.dataset.zoom, 10);
        var map = L.map(el).setView(
            [isNaN(lat) ? 14.5 : lat, isNaN(lng) ? -14.5 : lng],
            isNaN(zoom) ? 6 : zoom
        );

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            attribution: '&copy; OpenStreetMap contributors'
        }).addTo(map);

        if (!el.dataset.geojson) return;

        var canHover = window.matchMedia && window.matchMedia('(hover: hover)').matches;

        fetch(el.dataset.geojson)
            .then(function (r) { return r.json(); })
            .then(function (geojson) {
                L.geoJSON(geojson, {
                    style: styleFor,
                    onEachFeature: function (feature, layer) {
                        var p = feature.properties || {};
                        var name = escapeHtml(regionName(p));
                        var html = '<strong>' + name + '</strong>';
                        if (p.facility_count) html += '<br>' + escapeHtml(p.facility_count) + ' facilities';
                        if (p.status)         html += '<br>Status: ' + escapeHtml(p.status);
                        layer.bindPopup(html);
                        if (canHover) layer.bindTooltip(name, { sticky: true });
                    }
                }).addTo(map);
            })
            .catch(function (err) { console.error('Error loading GeoJSON:', err); });
    }

    document.querySelectorAll('.campaign-map[data-geojson]').forEach(init);
})();
