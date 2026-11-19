/* campaign-map.js — shared Leaflet map for country, region and Senegal pages.
 *
 * Usage: <div id="map" class="campaign-map"
 *             data-geojson="…/theme/geojson/cod_admin1.geojson"
 *             data-facilities="…/theme/geojson/cod_facilities.geojson"   (optional)
 *             data-country="Democratic Republic of the Congo"            (optional)
 *             data-lat="-2.9" data-lng="23.6" data-zoom="5"></div>
 *
 * data-facilities adds the health facilities that scripts/healthsites_facilities.py
 * downloads from the healthsites.io API. The file is static, so no API key ever
 * reaches the browser. It loads only when the map scrolls into view.
 * Requires Leaflet (L) loaded before this script.
 */
(function () {
    'use strict';

    var FACILITY_COLOR = '#3c4c57';

    // Region name: QGIS exports use adm1_name; older files use name / ADM1_*.
    function regionName(p) {
        return p.adm1_name || p.name || p.ADM1_FR || p.ADM1_EN || 'Unnamed area';
    }

    function escapeHtml(s) {
        return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
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

    function regionPopup(p, count) {
        var html = '<strong>' + escapeHtml(regionName(p)) + '</strong>';
        var n = typeof count === 'number' ? count : p.facility_count;
        if (typeof n === 'number') {
            html += '<br>' + escapeHtml(n.toLocaleString('en-GB')) +
                (n === 1 ? ' health facility' : ' health facilities') + ' on OpenStreetMap';
        } else if (n) {
            html += '<br>' + escapeHtml(n) + ' facilities';
        }
        if (p.status) html += '<br>Status: ' + escapeHtml(p.status);
        return html;
    }

    // ── Health facilities from the healthsites.io API (optional layer) ──

    function typeLabel(t) {
        if (!t) return 'Health facility';
        t = String(t).replace(/_/g, ' ');
        return t.charAt(0).toUpperCase() + t.slice(1);
    }

    function isHospital(p) { return /hospital/i.test(p.t || ''); }

    // Small dots when zoomed out, larger when zoomed in; hospitals a little larger.
    function radiusFor(zoom, hospital) {
        var r = zoom <= 5 ? 1.5 : zoom <= 6 ? 2 : zoom <= 8 ? 3 : 4.5;
        return hospital ? r + 1 : r;
    }

    function facilityPopup(p, country) {
        var html = '<div class="facility-popup"><strong>' + escapeHtml(p.n || 'Unnamed facility') + '</strong>' +
            '<div class="facility-popup__sub">' + escapeHtml(typeLabel(p.t)) +
            (p.r ? ' · ' + escapeHtml(p.r) : '') + '</div>';
        if (p.id && /^(node|way|relation)\/\d+$/.test(p.id)) {
            html += '<a href="https://healthsites.io/map#!/locality/' + escapeHtml(p.id) +
                '" target="_blank" rel="noopener" data-umami-event="' +
                escapeHtml((country ? country + ' ' : '') + 'Map Facility Click') +
                '">View in healthsites.io</a>';
        }
        return html + '</div>';
    }

    function addFacilities(map, url, country, regionLayers) {
        return fetch(url)
            .then(function (r) {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.json();
            })
            .then(function (gj) {
                var meta = gj.metadata || {};
                var byRegion = meta.by_region || {};
                regionLayers.forEach(function (layer) {
                    var p = layer.feature.properties || {};
                    var n = byRegion[regionName(p)];
                    if (typeof n === 'number') layer.setPopupContent(regionPopup(p, n));
                });

                var zoom = map.getZoom();
                // Hospitals last, so they draw on top.
                var features = (gj.features || []).slice().sort(function (a, b) {
                    return (isHospital(a.properties) ? 1 : 0) - (isHospital(b.properties) ? 1 : 0);
                });
                var layer = L.geoJSON({ type: 'FeatureCollection', features: features }, {
                    attribution: 'Facilities: <a href="https://healthsites.io">healthsites.io</a> (ODbL)',
                    pointToLayer: function (f, latlng) {
                        return L.circleMarker(latlng, {
                            radius: radiusFor(zoom, isHospital(f.properties)),
                            color: '#ffffff',
                            weight: 0.5,
                            fillColor: FACILITY_COLOR,
                            fillOpacity: 0.8
                        });
                    }
                });
                // One popup for the whole layer, not one per facility.
                layer.on('click', function (e) {
                    L.popup({ maxWidth: 260 })
                        .setLatLng(e.latlng)
                        .setContent(facilityPopup((e.propagatedFrom || e.layer).feature.properties || {}, country))
                        .openOn(map);
                });
                map.on('zoomend', function () {
                    var z = map.getZoom();
                    layer.eachLayer(function (m) {
                        m.setRadius(radiusFor(z, isHospital(m.feature.properties)));
                    });
                });
                layer.addTo(map);
            })
            .catch(function (err) { console.error('Health facilities not loaded:', err); });
    }

    // Run fn once the element is near the viewport.
    function whenVisible(el, fn) {
        if (!('IntersectionObserver' in window)) { fn(); return; }
        var io = new IntersectionObserver(function (entries) {
            if (entries.some(function (e) { return e.isIntersecting; })) {
                io.disconnect();
                fn();
            }
        }, { rootMargin: '200px' });
        io.observe(el);
    }

    function init(el) {
        if (typeof L === 'undefined') return;

        var lat = parseFloat(el.dataset.lat);
        var lng = parseFloat(el.dataset.lng);
        var zoom = parseInt(el.dataset.zoom, 10);
        var withFacilities = !!el.dataset.facilities;
        // The page keeps the mouse wheel and one-finger swipes, so the map
        // never traps scrolling. Zoom with the +/- buttons or a pinch.
        var options = {
            scrollWheelZoom: false,
            dragging: !L.Browser.mobile
        };
        // With facilities, regions and dots share one canvas, so a tap on a
        // dot opens the facility and a tap elsewhere opens the region.
        if (withFacilities) {
            options.preferCanvas = true;
            options.renderer = L.canvas({ padding: 0.5, tolerance: 5 });
        }
        var map = L.map(el, options).setView(
            [isNaN(lat) ? 14.5 : lat, isNaN(lng) ? -14.5 : lng],
            isNaN(zoom) ? 6 : zoom
        );

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            maxZoom: 19,
            opacity: withFacilities ? 0.6 : 1,
            attribution: '&copy; OpenStreetMap contributors'
        }).addTo(map);

        if (!el.dataset.geojson) return;

        var canHover = window.matchMedia && window.matchMedia('(hover: hover)').matches;
        var regionLayers = [];

        var regions = fetch(el.dataset.geojson)
            .then(function (r) { return r.json(); })
            .then(function (geojson) {
                L.geoJSON(geojson, {
                    style: styleFor,
                    onEachFeature: function (feature, layer) {
                        var p = feature.properties || {};
                        layer.bindPopup(regionPopup(p));
                        if (canHover) layer.bindTooltip(escapeHtml(regionName(p)), { sticky: true });
                        regionLayers.push(layer);
                    }
                }).addTo(map);
            })
            .catch(function (err) { console.error('Error loading GeoJSON:', err); });

        // Facilities draw after the regions, so they sit on top.
        if (withFacilities) {
            whenVisible(el, function () {
                regions.then(function () {
                    addFacilities(map, el.dataset.facilities, el.dataset.country || '', regionLayers);
                });
            });
        }
    }

    document.querySelectorAll('.campaign-map[data-geojson]').forEach(init);
})();
