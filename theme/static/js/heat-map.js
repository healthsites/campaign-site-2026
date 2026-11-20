/* heat-map.js: health facilities in Senegal coloured by heat over one week.
 *
 * Reads one static GeoJSON built by scripts/senegal_heat.py, so no API key
 * ever reaches the browser. Usage:
 *   <div id="heat-map" class="heat-map"
 *        data-heat="…/theme/geojson/sen_facility_heat.geojson"
 *        data-boundaries="…/theme/geojson/sen_admin1.geojson"></div>
 * Requires Leaflet (L) loaded before this script.
 *
 * Four views (buttons in #heat-views): daytime high (tmax), night-time low
 * (tmin), heat stress (wbgt) and above normal (anom). Each view colours the
 * facilities by quintiles of its own measure, worked out here in the browser.
 */
(function () {
    'use strict';

    // Five-step ordinal ramp, lowest to highest (one hue, validated light to dark).
    var COLORS = ['#ef9a5e', '#e57536', '#cc521b', '#a33b10', '#6b2408'];
    var NO_DATA = '#9e9e9e';
    var HOT_LABELS = ['Coolest 20%', 'Cooler', 'Middle', 'Hotter', 'Hottest 20%'];
    var ANOM_LABELS = ['Lowest 20%', 'Lower', 'Middle', 'Higher', 'Highest 20%'];
    var GRID = 'era5_land_grid';

    var VIEWS = {
        day: {
            key: 'tmax', name: 'Daytime high', labels: HOT_LABELS,
            legend: 'Daytime high', top: 'The 10 hottest facilities',
            rank: 'Hotter by day than {p}% of facilities in Senegal'
        },
        night: {
            key: 'tmin', name: 'Night-time low', labels: HOT_LABELS,
            legend: 'Night-time low', top: 'The 10 facilities with the warmest nights',
            rank: 'Warmer at night than {p}% of facilities in Senegal'
        },
        wbgt: {
            key: 'wbgt', name: 'Heat stress (WBGT)', labels: HOT_LABELS,
            legend: 'Heat stress (WBGT), daily maximum', top: 'The 10 facilities with the highest heat stress',
            rank: 'Higher heat stress than {p}% of facilities in Senegal'
        },
        anom: {
            // The only view measured on the 9 km grid: HeatReady has no downscaled baseline.
            key: 'anom', name: 'Above normal', labels: ANOM_LABELS, signed: true, grid: true,
            legend: 'Daytime high compared with the 9 km grid\'s 2016–2025 average for the same days',
            top: 'The 10 facilities furthest above normal',
            rank: 'Further above normal than {p}% of facilities in Senegal'
        }
    };

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

    function num(v, signed) {
        var s = Math.abs(v) < 0.05 ? '0.0' : Math.abs(v).toFixed(1);
        if (!signed) return v.toFixed(1);
        return (v < 0 && s !== '0.0' ? '−' : '+') + s;
    }

    function deg(v, signed) { return v == null ? 'no data' : num(v, signed) + ' °C'; }

    function fmtDate(iso) {
        var d = new Date(iso + 'T00:00:00Z');
        return d.toLocaleDateString('en-GB', { day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC' });
    }

    // "7 to 13 November 2026", "28 October to 3 November 2026", or one date.
    function fmtRange(a, b, noYear) {
        var A = fmtDate(a).split(' '), B = fmtDate(b).split(' ');
        var end = noYear ? B[0] + ' ' + B[1] : fmtDate(b);
        if (a === b) return end;
        if (A[2] !== B[2]) return (noYear ? A[0] + ' ' + A[1] : fmtDate(a)) + ' to ' + end;
        if (A[1] !== B[1]) return A[0] + ' ' + A[1] + ' to ' + end;
        return A[0] + ' to ' + end;
    }

    // Provisional dates as a range when they run on, otherwise a list.
    function fmtDates(list) {
        if (!list.length) return '';
        var run = list.every(function (d, i) {
            return i === 0 || (Date.parse(d) - Date.parse(list[i - 1])) === 864e5;
        });
        if (run) return fmtRange(list[0], list[list.length - 1], true);
        return list.map(function (d) { return fmtRange(d, d, true); }).join(', ');
    }

    function setText(id, text) {
        var el = document.getElementById(id);
        if (el) el.textContent = text;
        return el;
    }

    function mean(values) {
        values = values.filter(function (v) { return v != null; });
        if (!values.length) return null;
        return values.reduce(function (a, b) { return a + b; }, 0) / values.length;
    }

    // Leftmost index at which v could be inserted into the sorted list.
    function bisectLeft(list, v) {
        var lo = 0, hi = list.length;
        while (lo < hi) {
            var mid = (lo + hi) >> 1;
            if (list[mid] < v) lo = mid + 1; else hi = mid;
        }
        return lo;
    }

    // Quintile classes and percentiles of one measure, the same method as the build script.
    function rank(features, key) {
        var vals = features.map(function (f) { return f.properties[key]; })
            .filter(function (v) { return v != null; })
            .sort(function (a, b) { return a - b; });
        var n = vals.length;
        var breaks = [0.2, 0.4, 0.6, 0.8].map(function (q) { return vals[Math.min(n - 1, Math.floor(q * n))]; });
        var cls = new Map(), ranges = {};
        features.forEach(function (f) {
            var v = f.properties[key];
            if (v == null || !n) return;
            var c = bisectLeft(breaks, v) + 1;
            cls.set(f, { c: c, p: Math.round(100 * bisectLeft(vals, v) / n) });
            var r = ranges[c] || (ranges[c] = { min: v, max: v });
            r.min = Math.min(r.min, v);
            r.max = Math.max(r.max, v);
        });
        return { cls: cls, ranges: ranges };
    }

    function trustLine(p) {
        var text;
        var conf = p.conf ? ' (confidence: ' + p.conf + ').' : '.';
        if (p.src === GRID) text = 'From the 9 km grid, likely below the real daytime high.';
        else if (p.src === 'metar_station') text = 'From a weather station in the same 9 km square.';
        else if (p.src === 'era5_land_station_blended') text = 'Corrected with nearby weather station data' + conf;
        else text = 'Corrected for local conditions' + conf;
        if (p.ood > 0) {
            text += ' On ' + p.ood + (p.ood === 1 ? ' day' : ' days') +
                ', outside the conditions the model was tested on.';
        }
        return '<p class="heat-popup__trust">' + esc(text) + '</p>';
    }

    function popupHtml(p, view, r) {
        var html = '<div class="heat-popup"><strong>' + esc(nameOf(p)) + '</strong>' +
            '<div class="heat-popup__sub">' + esc(typeLabel(p.t)) + (p.r ? ' · ' + esc(p.r) : '') + '</div>';
        if (p.tmax == null) {
            html += '<p>No heat data for this location.</p>';
        } else {
            html += '<dl>' +
                '<dt>Daytime high</dt><dd>' + deg(p.tmax) + '</dd>' +
                '<dt>Night-time low</dt><dd>' + deg(p.tmin) + '</dd>' +
                '<dt>Heat stress (WBGT)</dt><dd>' + deg(p.wbgt) + '</dd>' +
                '<dt>Above normal (9 km grid)</dt><dd>' + deg(p.anom, true) + '</dd>' +
                '</dl>';
            if (r) html += '<p class="heat-popup__rank">' + esc(view.rank.replace('{p}', r.p)) + '</p>';
            html += trustLine(p);
        }
        if (p.id && /^(node|way|relation)\/\d+$/.test(p.id)) {
            html += '<a href="https://healthsites.io/map#!/locality/' + esc(p.id) + '" target="_blank" rel="noopener" data-umami-event="Senegal Heat Facility Click">View in healthsites.io</a>';
        }
        return html + '</div>';
    }

    function showDates(meta) {
        if (!meta.date_from || !meta.date_to) return '';
        var range = fmtRange(meta.date_from, meta.date_to);
        setText('heat-lede-dates', meta.days === 1 ? 'on ' + range : 'from ' + range);
        var prov = meta.provisional_dates || [];
        var el = document.getElementById('heat-provisional');
        if (el && prov.length) {
            el.textContent = 'Values for ' + fmtDates(prov) + ' are provisional and will be updated.';
            el.hidden = false;
        }
        if (meta.attribution && meta.attribution.copernicus) setText('heat-copernicus', meta.attribution.copernicus);
        return range;
    }

    function showMeta(meta, view, range) {
        var n = (meta.with_heat || 0).toLocaleString('en-GB');
        setText('heat-meta', view.name + (range ? ', averaged over ' + range : '') + '. ' + n +
            ' facilities. Updated ' + fmtDate(meta.generated) + '.');
    }

    // The grid view says what it compares with; the others compare facilities.
    function legendTitle(view, range) {
        var dates = range ? ', ' + range : '';
        if (view.grid) return view.legend + dates;
        return view.legend + dates + ', compared with other facilities in Senegal';
    }

    function showLegend(view, ranks, hasNoData, range) {
        var box = document.getElementById('heat-legend');
        var list = document.getElementById('heat-legend-items');
        if (!box || !list) return;
        setText('heat-legend-title', legendTitle(view, range));
        var items = [1, 2, 3, 4, 5].filter(function (c) { return ranks.ranges[c]; }).map(function (c) {
            var k = ranks.ranges[c];
            var text = k.min === k.max ? deg(k.min, view.signed)
                : num(k.min, view.signed) + ' to ' + deg(k.max, view.signed);
            return '<li><span class="heat-swatch" style="background:' + COLORS[c - 1] + '"></span>' +
                '<span class="heat-legend__label">' + view.labels[c - 1] + '</span>' +
                '<span class="heat-legend__range">' + text + '</span></li>';
        });
        if (hasNoData) {
            items.push('<li><span class="heat-swatch heat-swatch--none"></span>' +
                '<span class="heat-legend__label">No data</span><span class="heat-legend__range"></span></li>');
        }
        list.innerHTML = items.join('');
        box.hidden = false;
    }

    function showTop(features, view, range) {
        var body = document.getElementById('heat-top');
        var section = document.getElementById('heat-top-section');
        if (!body || !section) return;
        var key = view.key;
        var top = features.filter(function (f) { return f.properties[key] != null; })
            .sort(function (a, b) { return b.properties[key] - a.properties[key]; })
            .slice(0, 10);
        if (!top.length) return;
        setText('heat-top-title', view.top + (range ? ', ' + range : ''));
        setText('heat-top-measure', view.name);
        setText('heat-top-note', view.name + ', averaged over the same days as the map.');
        body.innerHTML = top.map(function (f) {
            var p = f.properties;
            return '<tr><td>' + esc(nameOf(p)) + '</td><td>' + esc(typeLabel(p.t)) + '</td><td>' +
                esc(p.r || '') + '</td><td>' + deg(p[key], view.signed) + '</td></tr>';
        }).join('');
        section.hidden = false;
    }

    function regionStats(features) {
        var groups = {};
        features.forEach(function (f) {
            var p = f.properties;
            if (p.tmax == null || !p.r) return;
            (groups[p.r] = groups[p.r] || []).push(p);
        });
        return Object.keys(groups).map(function (r) {
            var ps = groups[r];
            function m(k) { return mean(ps.map(function (p) { return p[k]; })); }
            return { region: r, n: ps.length, tmax: m('tmax'), tmin: m('tmin'), wbgt: m('wbgt'), anom: m('anom') };
        }).sort(function (a, b) { return b.tmax - a.tmax; });
    }

    function showRegions(stats, range) {
        var body = document.getElementById('heat-regions');
        var section = document.getElementById('heat-region-section');
        if (!body || !section || !stats.length) return;
        setText('heat-region-title', 'Heat by region' + (range ? ', ' + range : ''));
        if (stats.length > 1) {
            setText('heat-region-lead', 'On average, the hottest regions were ' +
                stats[0].region + ' (' + deg(stats[0].tmax) + ') and ' +
                stats[1].region + ' (' + deg(stats[1].tmax) + '). Daytime high, averaged over facilities.');
        }
        body.innerHTML = stats.map(function (s) {
            return '<tr><th scope="row">' + esc(s.region) + '</th><td>' + s.n.toLocaleString('en-GB') +
                '</td><td>' + deg(s.tmax) + '</td><td>' + deg(s.tmin) + '</td><td>' + deg(s.wbgt) +
                '</td><td>' + deg(s.anom, true) + '</td></tr>';
        }).join('');
        section.hidden = false;
    }

    // "From 7 to 13 November, nights at Saint-Louis facilities averaged a low of 24.5 °C, …"
    // "From 7 to 13 November, days at Saint-Louis facilities ran 1.6 °C above normal."
    // No night-time figure until HeatReady confirms its night-time refit.
    function closingText(meta, stats) {
        var sl = stats.filter(function (s) { return s.region === 'Saint-Louis'; })[0];
        if (!sl || sl.anom == null || !meta.date_from) return null;
        var a = Math.abs(sl.anom).toFixed(1);
        var days = a === '0.0' ? 'close to normal' : a + ' °C ' + (sl.anom > 0 ? 'above' : 'below') + ' normal';
        return 'From ' + fmtRange(meta.date_from, meta.date_to, true) +
            ', days at Saint-Louis facilities ran ' + days + '.';
    }

    function showClosing(meta, stats) {
        var el = document.getElementById('heat-closing-figures');
        var text = closingText(meta, stats);
        if (!el || !text) return;
        el.textContent = text;
        el.hidden = false;
    }

    function showMissing() {
        setText('heat-meta', 'The heat data is not available right now.');
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
                var features = gj.features || [];
                var range = showDates(meta);
                var current = null;
                var markers = [];

                var layer = L.geoJSON({ type: 'FeatureCollection', features: features }, {
                    attribution: 'healthsites.io / © OpenStreetMap contributors (ODbL) · ' +
                        'HeatReady, CrisisReady (CC BY 4.0) · ERA5-Land, Copernicus',
                    pointToLayer: function (f, latlng) {
                        return L.circleMarker(latlng, {
                            renderer: renderer, radius: radius, color: '#ffffff', weight: 1,
                            fillColor: NO_DATA, fillOpacity: 0.7
                        });
                    },
                    onEachFeature: function (f, l) {
                        markers.push(l);
                        l.bindPopup(function () {
                            return popupHtml(f.properties, VIEWS[current.name], current.ranks.cls.get(f));
                        });
                        if (canHover) l.bindTooltip(esc(nameOf(f.properties)), { direction: 'top', offset: [0, -4] });
                    }
                }).addTo(map);

                function show(name) {
                    var view = VIEWS[name];
                    var ranks = rank(features, view.key);
                    current = { name: name, ranks: ranks };
                    var hasNoData = false;
                    // Lowest first, so the highest end up drawn on top.
                    markers.slice().sort(function (a, b) {
                        var ca = ranks.cls.get(a.feature), cb = ranks.cls.get(b.feature);
                        return (ca ? ca.c : 0) - (cb ? cb.c : 0);
                    }).forEach(function (m) {
                        var r = ranks.cls.get(m.feature);
                        if (!r) hasNoData = true;
                        m.setStyle({ fillColor: r ? COLORS[r.c - 1] : NO_DATA, fillOpacity: r ? 0.95 : 0.7 });
                        m.bringToFront();
                    });
                    map.closePopup();
                    showMeta(meta, view, range);
                    showLegend(view, ranks, hasNoData, range);
                    showTop(features, view, range);
                    document.querySelectorAll('#heat-views .heat-view').forEach(function (b) {
                        b.setAttribute('aria-pressed', b.dataset.view === name ? 'true' : 'false');
                    });
                }

                var views = document.getElementById('heat-views');
                if (views) {
                    views.addEventListener('click', function (e) {
                        var b = e.target.closest('.heat-view');
                        if (b && VIEWS[b.dataset.view] && b.dataset.view !== current.name) show(b.dataset.view);
                    });
                    views.hidden = false;
                }

                show('day');
                if (layer.getBounds().isValid()) map.fitBounds(layer.getBounds(), { padding: [12, 12] });
                var stats = regionStats(features);
                showRegions(stats, range);
                showClosing(meta, stats);
            })
            .catch(function (err) {
                console.error('Heat data not loaded:', err);
                showMissing();
            });
    }

    // For tests/test_senegal_heat.py, which loads this file in Node.
    if (typeof module !== 'undefined' && module.exports) {
        module.exports = {
            VIEWS: VIEWS, trustLine: trustLine, popupHtml: popupHtml, legendTitle: legendTitle,
            closingText: closingText
        };
    }
    if (typeof document === 'undefined') return;

    var el = document.getElementById('heat-map');
    if (el) init(el);
})();
