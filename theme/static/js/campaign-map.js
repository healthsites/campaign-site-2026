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
 *
 * Region pages use the same two files as their country page:
 *   data-region="Saint-Louis"   zoom to this region of the boundary file, fade the
 *                               others, and show only facilities whose "r" is this region.
 *   data-region-links='{"Saint-Louis": {"url": "…", "status": "…"}}'   (optional)
 *                               region popups link to the region's campaign page.
 * The browser caches both files, so moving between a country page and its
 * region pages downloads nothing new.
 *
 * Highlighted facilities (optional), drawn larger and on top:
 *   data-highlight="…/sen_saint_louis_emergency.geojson"  (scripts/saint_louis_emergency.py)
 *   data-highlight-style="red" | "heat"   red dots, or coloured by heat class "c" (1–5)
 *   data-highlight-label="…"              one line in each popup
 *   data-highlight-dates="7–13 November 2026"  the heat week, for "heat" popups
 *   data-highlight-link="…"               popup link, e.g. to the Étape 2 page
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

    // Colour of a region. With region pages (links), the pages decide: "complete" in the
    // boundary file is validated (green), Region_tier campaign invites support (brand),
    // anything else is open data (grey). Without links, the boundary file's status, as before.
    function statusOf(p, links) {
        var s = (p.status || '').toLowerCase();
        if (!links || !Object.keys(links).length) return s;
        if (s === 'complete') return 'complete';
        var link = links[regionName(p)];
        return link && link.tier === 'campaign' ? 'active' : '';
    }

    function styleFor(feature, focus, links) {
        var name = regionName(feature.properties);
        if (focus && name !== focus) {
            // Other regions on a region page: a light veil, so the focus region stands out.
            return { color: '#9e9e9e', weight: 0.5, opacity: 0.8, fillColor: '#ffffff', fillOpacity: 0.55 };
        }
        var status = statusOf(feature.properties, links);
        var fill = status === 'complete' ? '#2e7d32'   // green - validated
                 : status === 'active'   ? '#f44a52'   // brand - in progress
                 : '#9e9e9e';                          // grey  - planned
        return {
            color: focus ? '#3c4c57' : '#000000',
            weight: focus ? 2.5 : 1,
            opacity: 0.8,
            fillColor: fill,
            fillOpacity: focus ? 0.12 : (status ? 0.35 : 0.05)
        };
    }

    // links: {"<region>": {"url": "…", "status": "<campaign_status of the region page>"}}
    function regionPopup(p, count, links, focus, country) {
        var name = regionName(p);
        var html = '<strong>' + escapeHtml(name) + '</strong>';
        var n = typeof count === 'number' ? count : p.facility_count;
        if (typeof n === 'number') {
            html += '<br>' + escapeHtml(n.toLocaleString('en-GB')) +
                (n === 1 ? ' health facility' : ' health facilities') + ' on OpenStreetMap';
        } else if (n) {
            html += '<br>' + escapeHtml(n) + ' facilities';
        }
        // Status from the region's campaign page. The boundary file's "status" only
        // colours the map: "planned" there does not mean a campaign is planned.
        var link = links && links[name];
        if (link && link.status) {
            html += '<br>' + escapeHtml(link.status);
        } else if ((p.status || '').toLowerCase() === 'complete') {
            html += '<br>Campaign complete';
        } else if (link && link.tier === 'open-data') {
            html += '<br>Open data';
        }
        if (link && link.url && name !== focus) {
            html += '<br><a href="' + escapeHtml(link.url) + '" data-umami-event="' +
                escapeHtml((country ? country + ' ' : '') + 'Map Region Click') + '">Open the ' +
                escapeHtml(name) + ' page →</a>';
        }
        return html;
    }

    function parseLinks(s) {
        if (!s) return {};
        try { return JSON.parse(s) || {}; } catch (e) { return {}; }
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

    function addFacilities(map, url, country, regionLayers, links, focus) {
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
                    if (typeof n === 'number') layer.setPopupContent(regionPopup(p, n, links, focus, country));
                });

                var zoom = map.getZoom();
                // On a region page, only that region's facilities ("r" is set by the build script).
                var features = (gj.features || []).filter(function (f) {
                    return !focus || (f.properties && f.properties.r === focus);
                });
                // Hospitals last, so they draw on top.
                features = features.sort(function (a, b) {
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

    // ── Highlighted facilities (optional layer), e.g. the 35 in Saint-Louis ──

    // The same five-step ramp as heat-map.js, coolest to hottest.
    var HEAT_COLORS = ['#ef9a5e', '#e57536', '#cc521b', '#a33b10', '#6b2408'];
    var HIGHLIGHT_RED = '#f44a52';

    function highlightStyle(p, opts, zoom) {
        var fill = opts.style === 'heat' ? (HEAT_COLORS[(p.c || 0) - 1] || '#9e9e9e') : HIGHLIGHT_RED;
        return { radius: radiusFor(zoom, false) + 3.5, color: '#ffffff', weight: 1.5,
                 fillColor: fill, fillOpacity: 0.95 };
    }

    function highlightPopup(p, opts, country) {
        var html = '<div class="facility-popup"><strong>' + escapeHtml(p.n || 'Unnamed facility') + '</strong>' +
            '<div class="facility-popup__sub">' + escapeHtml(typeLabel(p.t)) +
            (p.r ? ' · ' + escapeHtml(p.r) : '') + '</div>';
        if (opts.label) html += '<div class="facility-popup__flag">' + escapeHtml(opts.label) + '</div>';
        if (opts.style === 'heat' && typeof p.tmax === 'number') {
            html += '<div class="facility-popup__heat">Daytime high ' + escapeHtml(p.tmax.toFixed(1)) + ' °C' +
                (opts.dates ? ', ' + escapeHtml(opts.dates) : '') +
                (typeof p.p === 'number' ? '. Hotter by day than ' + escapeHtml(p.p) +
                    '% of health facilities in Senegal.' : '.') + '</div>';
        }
        if (p.id && /^(node|way|relation)\/\d+$/.test(p.id)) {
            html += '<a href="https://healthsites.io/map#!/locality/' + escapeHtml(p.id) +
                '" target="_blank" rel="noopener" data-umami-event="' +
                escapeHtml((country ? country + ' ' : '') + 'Map Highlight Facility Click') +
                '">View in healthsites.io</a>';
        }
        if (opts.link) {
            html += '<br><a href="' + escapeHtml(opts.link) + '" data-umami-event="' +
                escapeHtml((country ? country + ' ' : '') + 'Map Highlight Etape 2 Click') +
                '">Help confirm it in Étape 2 →</a>';
        }
        return html + '</div>';
    }

    function addHighlight(map, url, opts, country) {
        return fetch(url)
            .then(function (r) {
                if (!r.ok) throw new Error('HTTP ' + r.status);
                return r.json();
            })
            .then(function (gj) {
                var zoom = map.getZoom();
                var layer = L.geoJSON(gj, {
                    pointToLayer: function (f, latlng) {
                        return L.circleMarker(latlng, highlightStyle(f.properties || {}, opts, zoom));
                    }
                });
                layer.on('click', function (e) {
                    L.popup({ maxWidth: 280 })
                        .setLatLng(e.latlng)
                        .setContent(highlightPopup((e.propagatedFrom || e.layer).feature.properties || {}, opts, country))
                        .openOn(map);
                });
                map.on('zoomend', function () {
                    var z = map.getZoom();
                    layer.eachLayer(function (m) { m.setRadius(highlightStyle(m.feature.properties || {}, opts, z).radius); });
                });
                layer.addTo(map);
            })
            .catch(function (err) { console.error('Highlighted facilities not loaded:', err); });
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
        var focus = el.dataset.region || '';
        var links = parseLinks(el.dataset.regionLinks);
        var country = el.dataset.country || '';

        var regions = fetch(el.dataset.geojson)
            .then(function (r) { return r.json(); })
            .then(function (geojson) {
                var focusLayer = null;
                L.geoJSON(geojson, {
                    style: function (f) { return styleFor(f, focus, links); },
                    onEachFeature: function (feature, layer) {
                        var p = feature.properties || {};
                        layer.bindPopup(regionPopup(p, undefined, links, focus, country));
                        if (canHover) layer.bindTooltip(escapeHtml(regionName(p)), { sticky: true });
                        if (focus && regionName(p) === focus) focusLayer = layer;
                        regionLayers.push(layer);
                    }
                }).addTo(map);
                if (focusLayer) {
                    focusLayer.bringToFront();
                    map.fitBounds(focusLayer.getBounds(), { padding: [16, 16], animate: false });
                } else if (focus) {
                    console.warn('campaign-map: no region named "' + focus + '" in ' + el.dataset.geojson);
                }
            })
            .catch(function (err) { console.error('Error loading GeoJSON:', err); });

        // Facilities draw after the regions, and highlighted facilities last, so they sit on top.
        if (withFacilities || el.dataset.highlight) {
            whenVisible(el, function () {
                regions
                    .then(function () {
                        if (withFacilities) {
                            return addFacilities(map, el.dataset.facilities, country, regionLayers, links, focus);
                        }
                    })
                    .then(function () {
                        if (!el.dataset.highlight) return;
                        addHighlight(map, el.dataset.highlight, {
                            style: el.dataset.highlightStyle || 'red',
                            label: el.dataset.highlightLabel || '',
                            dates: el.dataset.highlightDates || '',
                            link: el.dataset.highlightLink || ''
                        }, country);
                    });
            });
        }
    }

    document.querySelectorAll('.campaign-map[data-geojson]').forEach(init);
})();
