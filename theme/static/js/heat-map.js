/* heat-map.js: health facilities in Senegal coloured by recent heat.
 *
 * Reads one static GeoJSON built by scripts/senegal_heat.py, so no API key
 * ever reaches the browser. Usage:
 *   <div id="heat-map" class="heat-map"
 *        data-heat="…/theme/geojson/sen_facility_heat.geojson"
 *        data-boundaries="…/theme/geojson/sen_admin1.geojson"></div>
 * Requires Leaflet (L) loaded before this script.
 */
(function () {
    'use strict';

    // Five-step ordinal ramp, coolest to hottest (one hue, validated light to dark).
    var COLORS = ['#ef9a5e', '#e57536', '#cc521b', '#a33b10', '#6b2408'];
    var NO_DATA = '#9e9e9e';
    var CLASS_LABELS = ['Coolest 20%', 'Cooler', 'Middle', 'Hotter', 'Hottest 20%'];

    function esc(s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
            return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
        });
    }

    function typeLabel(t) {
        if (!t) return 'Health facility';
        t = String(t).replace(/_/g, ' ');
        return t.charAt(0).toUpperCase() + t.slice(1);
    }

    function nameOf(p) { return p.n || 'Unnamed facility'; }

    function deg(v) { return v == null ? 'no data' : v.toFixed(1) + ' °C'; }

    function fmtDate(iso) {
        var d = new Date(iso + 'T00:00:00Z');
        return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
    }

    function popupHtml(p) {
        var html = '<div class="heat-popup"><strong>' + esc(nameOf(p)) + '</strong>' +
            '<div class="heat-popup__sub">' + esc(typeLabel(p.t)) + (p.r ? ' · ' + esc(p.r) : '') + '</div>';
        if (p.tmax == null) {
            html += '<p>No heat data for this location.</p>';
        } else {
            html += '<dl>' +
                '<dt>Hottest temperature of the day</dt><dd>' + deg(p.tmax) + '</dd>' +
                '<dt>Heat index, daily maximum</dt><dd>' + deg(p.hi) + '</dd>' +
                '<dt>WBGT, daily maximum</dt><dd>' + deg(p.wbgt) + '</dd>' +
                '</dl>' +
                '<p class="heat-popup__rank">Hotter than ' + esc(p.p) + '% of facilities in Senegal</p>';
        }
        if (p.id && /^(node|way|relation)\/\d+$/.test(p.id)) {
            html += '<a href="https://www.openstreetmap.org/' + esc(p.id) + '" target="_blank" rel="noopener">View in OpenStreetMap</a>';
        }
        return html + '</div>';
    }

    // "4 to 10 November 2026", "28 October to 3 November 2026", or one date.
    function fmtRange(a, b) {
        if (a === b) return fmtDate(a);
        var A = fmtDate(a).split(' '), B = fmtDate(b).split(' ');
        if (A[2] !== B[2]) return fmtDate(a) + ' to ' + fmtDate(b);
        if (A[1] !== B[1]) return A[0] + ' ' + A[1] + ' to ' + fmtDate(b);
        return A[0] + ' to ' + fmtDate(b);
    }

    function showMeta(meta) {
        var el = document.getElementById('heat-meta');
        if (!el) return;
        var days = meta.days === 1 ? 'on ' + fmtDate(meta.date_from)
            : 'averaged over ' + fmtRange(meta.date_from, meta.date_to);
        el.textContent = 'Hottest temperature of the day, ' + days + '. ' +
            meta.with_heat.toLocaleString('en-GB') + ' facilities. Updated ' + fmtDate(meta.generated) + '.';
        var year = document.getElementById('heat-year');
        if (year && meta.date_to) year.textContent = meta.date_to.slice(0, 4);
    }

    function showLegend(meta, hasNoData) {
        var box = document.getElementById('heat-legend');
        var list = document.getElementById('heat-legend-items');
        if (!box || !list) return;
        var items = (meta.classes || []).map(function (k) {
            var range = k.min === k.max ? deg(k.min) : k.min.toFixed(1) + ' to ' + deg(k.max);
            return '<li><span class="heat-swatch" style="background:' + COLORS[k.c - 1] + '"></span>' +
                '<span class="heat-legend__label">' + CLASS_LABELS[k.c - 1] + '</span>' +
                '<span class="heat-legend__range">' + range + '</span></li>';
        });
        if (hasNoData) {
            items.push('<li><span class="heat-swatch heat-swatch--none"></span>' +
                '<span class="heat-legend__label">No heat data</span><span class="heat-legend__range"></span></li>');
        }
        list.innerHTML = items.join('');
        box.hidden = false;
    }

    function showTop(features) {
        var body = document.getElementById('heat-top');
        var section = document.getElementById('heat-top-section');
        if (!body || !section) return;
        var top = features.filter(function (f) { return f.properties.tmax != null; })
            .sort(function (a, b) { return b.properties.tmax - a.properties.tmax; })
            .slice(0, 10);
        if (!top.length) return;
        body.innerHTML = top.map(function (f) {
            var p = f.properties;
            return '<tr><td>' + esc(nameOf(p)) + '</td><td>' + esc(typeLabel(p.t)) + '</td><td>' +
                esc(p.r || '') + '</td><td>' + deg(p.tmax) + '</td></tr>';
        }).join('');
        section.hidden = false;
    }

    function showMissing() {
        var el = document.getElementById('heat-meta');
        if (el) el.textContent = 'The heat data is not available right now.';
    }

    function init(el) {
        if (typeof L === 'undefined') return;

        // Like the other campaign maps: the page keeps the mouse wheel and
        // one-finger swipes. Zoom with the +/- buttons or a pinch.
        var map = L.map(el, {
            scrollWheelZoom: false,
            dragging: !L.Browser.mobile,
            preferCanvas: true,
            zoomSnap: 0.25
        }).setView([14.4, -14.4], 7);

        // A faded base map so the coloured facilities stand out.
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            opacity: 0.45,
            attribution: '&copy; OpenStreetMap contributors'
        }).addTo(map);

        if (el.dataset.boundaries) {
            fetch(el.dataset.boundaries)
                .then(function (r) { return r.json(); })
                .then(function (gj) {
                    L.geoJSON(gj, {
                        interactive: false,
                        style: { color: '#3c4c57', weight: 1, opacity: 0.6, fill: false }
                    }).addTo(map);
                })
                .catch(function () { /* outlines are optional */ });
        }

        var canHover = window.matchMedia && window.matchMedia('(hover: hover)').matches;
        var renderer = L.canvas({ padding: 0.5, tolerance: 6 });
        var radius = el.clientWidth < 600 ? 4 : 5;

        fetch(el.dataset.heat)
            .then(function (r) {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.json();
            })
            .then(function (gj) {
                var meta = gj.metadata || {};
                // Draw the coolest first so the hottest sit on top.
                var features = (gj.features || []).slice().sort(function (a, b) {
                    return (a.properties.c || 0) - (b.properties.c || 0);
                });
                var hasNoData = features.some(function (f) { return !f.properties.c; });

                var layer = L.geoJSON({ type: 'FeatureCollection', features: features }, {
                    attribution: 'healthsites.io (ODbL) · HeatReady · ERA5-Land, Copernicus',
                    pointToLayer: function (f, latlng) {
                        var c = f.properties.c;
                        return L.circleMarker(latlng, {
                            renderer: renderer,
                            radius: radius,
                            color: '#ffffff',
                            weight: 1,
                            fillColor: c ? COLORS[c - 1] : NO_DATA,
                            fillOpacity: c ? 0.95 : 0.7
                        });
                    },
                    onEachFeature: function (f, l) {
                        l.bindPopup(popupHtml(f.properties));
                        if (canHover) l.bindTooltip(esc(nameOf(f.properties)), { direction: 'top', offset: [0, -4] });
                    }
                }).addTo(map);

                if (layer.getBounds().isValid()) map.fitBounds(layer.getBounds(), { padding: [12, 12] });
                showMeta(meta);
                showLegend(meta, hasNoData);
                showTop(gj.features || []);
            })
            .catch(function (err) {
                console.error('Heat data not loaded:', err);
                showMissing();
            });
    }

    var el = document.getElementById('heat-map');
    if (el) init(el);
})();
