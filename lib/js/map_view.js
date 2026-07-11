/**
 * map_view.js — Shared map component for stock guide pages.
 *
 * Modular: any page (overview, sweep set, index) can mount it. Expects
 * Leaflet to be loaded first (theme.LEAFLET_TAGS) and, for topic
 * lookups, GUIDES_DATA (output/guides_data.js).
 *
 * API:
 *   initMapView(containerEl, items, opts) -> { map, refresh(items) }
 *
 * items: [{
 *   name:    display name (required)
 *   country: country string; resolved via COUNTRY_COORDS (aliases OK)
 *   coords:  optional [lat, lon] — overrides country centroid
 *   group:   optional facet string (category, section, ...) — used to
 *            organize the location panel and the filter chips
 *   year:    optional int (negative = BCE) — era chips + panel sorting
 *   href:    optional link for the panel entry
 *   anchor:  optional element id — panel entry scrolls to it on click
 *   meta:    optional small grey text after the name
 * }]
 *
 * ONE pin per location (no concentric stacking). Hovering shows
 * "Country — N". Clicking opens a detail panel below the map with
 * everything at that location, grouped by `group` and sorted by year.
 * Pin hitboxes grow as you zoom in. Facet chips (groups + eras) filter
 * the pins live. Unlocatable items go to opts.onUnlocated(list).
 *
 * opts: { height: '420px', onUnlocated: fn, panelEl: element }
 *   panelEl: where the location panel renders; by default the
 *   component creates a div right after containerEl.
 *
 * Helpers: guideCountry(slug), guideYear(slug) — from GUIDES_DATA.
 */

const COUNTRY_COORDS = {
    'United States': [39.8, -98.6], 'England': [52.6, -1.5],
    'United Kingdom': [52.6, -1.5], 'Scotland': [56.8, -4.2],
    'Wales': [52.3, -3.7], 'Ireland': [53.3, -8.0],
    'France': [46.6, 2.5], 'Italy': [42.8, 12.8], 'Rome': [41.9, 12.5],
    'Germany': [51.1, 10.4], 'Greece': [39.3, 22.4],
    'Russia': [55.9, 37.9], 'Japan': [36.5, 138.4],
    'Spain': [40.2, -3.6], 'Mexico': [23.9, -102.5],
    'Austria': [47.6, 14.1], 'China': [35.0, 104.0],
    'India': [22.9, 79.6], 'Canada': [56.1, -106.3],
    'Netherlands': [52.2, 5.5], 'Belgium': [50.6, 4.6],
    'Nigeria': [9.6, 8.1], 'Czech Republic': [49.8, 15.5],
    'Czechia': [49.8, 15.5], 'Brazil': [-10.8, -52.9],
    'Poland': [52.1, 19.4], 'Sweden': [62.0, 15.0],
    'Hungary': [47.2, 19.4], 'Chile': [-33.5, -70.7],
    'South Africa': [-29.0, 25.1], 'Denmark': [56.0, 9.9],
    'Argentina': [-34.6, -64.4], 'Norway': [61.2, 8.8],
    'Switzerland': [46.8, 8.2], 'Iran': [32.6, 54.3],
    'Egypt': [26.6, 29.8], 'Colombia': [4.6, -74.1],
    'Portugal': [39.6, -8.0], 'Cuba': [21.5, -79.5],
    'New Zealand': [-41.8, 172.8], 'Australia': [-25.3, 133.8],
    'Syria': [35.0, 38.5], 'Martinique': [14.6, -61.0],
    'Finland': [61.9, 25.7], 'Taiwan': [23.7, 121.0],
    'Romania': [45.9, 24.9], 'Armenia': [40.3, 44.9],
    'South Korea': [36.5, 127.9], 'Bulgaria': [42.7, 25.5],
    'Turkey': [39.0, 35.2], 'Ukraine': [49.0, 31.4],
    'Israel': [31.4, 35.0], 'Iraq': [33.2, 43.7],
    'Peru': [-9.2, -75.0], 'Nicaragua': [12.9, -85.2],
    'Guatemala': [15.8, -90.2], 'Iceland': [64.9, -19.0],
    'Croatia': [45.1, 15.2], 'Serbia': [44.0, 20.9],
    'Vienna': [48.2, 16.4],
};

const MAP_GROUP_COLORS = [
    '#6b9eff', '#e0b860', '#6bcf8e', '#f08080', '#c792ea',
    '#7fdbca', '#f78c6c', '#89ddff', '#d4a5a5', '#b5cea8',
];

// Era buckets for the time filter (label, minYear inclusive, maxYear exclusive).
const MAP_ERAS = [
    ['pre-1600', -Infinity, 1600],
    ['1600–1750', 1600, 1750],
    ['1750–1850', 1750, 1850],
    ['1850–1900', 1850, 1900],
    ['1900–1950', 1900, 1950],
    ['1950+', 1950, Infinity],
];

function _resolveCountry(country) {
    if (!country) return null;
    if (COUNTRY_COORDS[country]) return COUNTRY_COORDS[country];
    for (const part of String(country).split('/')) {
        if (COUNTRY_COORDS[part.trim()]) return COUNTRY_COORDS[part.trim()];
    }
    return null;
}

function _guide(slug) {
    if (typeof GUIDES_DATA === 'undefined') return null;
    const path = 'output/' + slug + '/stock.html';
    return GUIDES_DATA.find(g => g.path === path) || null;
}

function guideCountry(slug) {
    const g = _guide(slug);
    return g ? g.country : null;
}

function guideYear(slug) {
    const g = _guide(slug);
    return g && typeof g.year === 'number' ? g.year : null;
}

function initMapView(containerEl, items, opts = {}) {
    if (typeof L === 'undefined') {
        containerEl.textContent = 'Map unavailable (Leaflet failed to load).';
        return null;
    }
    containerEl.style.height = opts.height || '420px';

    const map = L.map(containerEl, { worldCopyJump: true })
        .setView([30, 10], 2);
    L.tileLayer(
        'https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/attributions">CARTO</a>',
            subdomains: 'abcd', maxZoom: 12,
        }).addTo(map);

    const layer = L.layerGroup().addTo(map);

    // Detail panel (click a pin → everything at that location).
    let panelEl = opts.panelEl;
    if (!panelEl) {
        panelEl = document.createElement('div');
        panelEl.className = 'map-location-panel';
        panelEl.style.cssText = 'display:none;border:1px solid #3a3f47;'
            + 'border-top:none;background:#15191e;padding:0.6rem 0.9rem;'
            + 'max-height:340px;overflow-y:auto;font-size:0.85rem;';
        containerEl.after(panelEl);
    }

    let allItems = [];
    const offGroups = new Set();
    const offEras = new Set();
    let groupColor = new Map();
    let markers = [];   // [{marker, base}] for zoom-scaled radii
    let openLocation = null;   // location label of the open panel

    function esc(s) {
        return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
            .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
    }

    function eraOf(year) {
        if (typeof year !== 'number') return null;
        for (const [label, lo, hi] of MAP_ERAS) {
            if (year >= lo && year < hi) return label;
        }
        return null;
    }

    function yearLabel(year) {
        if (typeof year !== 'number') return '';
        return year < 0 ? (-year) + ' BCE' : String(year);
    }

    const chipBase = 'display:inline-block;margin:2px;padding:1px 8px;'
        + 'border-radius:10px;font-size:11px;cursor:pointer;user-select:none;'
        + 'background:#1a1f25;border:1px solid #3a3f47;';

    // --- Facet chips (groups + eras) as a Leaflet control ---
    const facetCtl = L.control({ position: 'bottomleft' });
    facetCtl.onAdd = () => {
        const div = L.DomUtil.create('div');
        div.className = 'map-facets';
        div.style.cssText = 'background:rgba(16,20,24,0.88);border:1px solid #3a3f47;'
            + 'border-radius:4px;padding:4px 6px;max-width:340px;';
        L.DomEvent.disableClickPropagation(div);
        return div;
    };
    facetCtl.addTo(map);

    function renderFacets() {
        const div = containerEl.querySelector('.map-facets');
        if (!div) return;
        let html = '';
        const groups = [...groupColor.keys()];
        if (groups.length > 1) {
            html += groups.map(g => {
                const off = offGroups.has(g);
                const color = groupColor.get(g);
                return `<span class="map-group-chip" data-g="${esc(g)}" style="${chipBase}`
                    + `color:${off ? '#555' : color};`
                    + (off ? 'text-decoration:line-through;' : `border-color:${color};`)
                    + `">${esc(g)}</span>`;
            }).join('');
        }
        const erasPresent = MAP_ERAS.map(e => e[0])
            .filter(label => allItems.some(it => eraOf(it.year) === label));
        if (erasPresent.length > 1) {
            html += '<div style="margin-top:2px">' + erasPresent.map(label => {
                const off = offEras.has(label);
                return `<span class="map-era-chip" data-e="${esc(label)}" style="${chipBase}`
                    + `color:${off ? '#555' : '#9aa0a7'};`
                    + (off ? 'text-decoration:line-through;' : '')
                    + `">${esc(label)}</span>`;
            }).join('') + '</div>';
        }
        div.innerHTML = html;
        div.style.display = html ? '' : 'none';
        div.querySelectorAll('.map-group-chip').forEach(chip =>
            chip.addEventListener('click', () => {
                const g = chip.dataset.g;
                offGroups.has(g) ? offGroups.delete(g) : offGroups.add(g);
                render();
            }));
        div.querySelectorAll('.map-era-chip').forEach(chip =>
            chip.addEventListener('click', () => {
                const e = chip.dataset.e;
                offEras.has(e) ? offEras.delete(e) : offEras.add(e);
                render();
            }));
    }

    function activeItems() {
        return allItems.filter(it => {
            if (it.group && offGroups.has(it.group)) return false;
            const era = eraOf(it.year);
            if (era && offEras.has(era)) return false;
            return true;
        });
    }

    // Zoom-scaled pin radius: fixed-pixel circles are hard to hit when
    // zoomed in, so scale with zoom level.
    function zoomFactor() {
        return Math.max(1, 1 + (map.getZoom() - 2) * 0.35);
    }

    function itemRowHtml(it) {
        const yr = it.year != null
            ? `<span style="color:#555;font-size:0.72rem;margin-right:0.4rem;`
              + `display:inline-block;min-width:3.2rem">${yearLabel(it.year)}</span>`
            : `<span style="display:inline-block;min-width:3.2rem"></span>`;
        const meta = it.meta
            ? ` <span style="color:#808790;font-size:0.72rem">${esc(it.meta)}</span>` : '';
        let name;
        if (it.href) {
            name = `<a href="${esc(it.href)}" style="color:#6b9eff;text-decoration:none">${esc(it.name)}</a>`;
        } else if (it.anchor) {
            name = `<a href="#${esc(it.anchor)}" class="map-anchor-link" data-anchor="${esc(it.anchor)}"`
                + ` style="color:#6b9eff;text-decoration:none">${esc(it.name)}</a>`;
        } else {
            name = esc(it.name);
        }
        return `<div style="padding:0.1rem 0">${yr}${name}${meta}</div>`;
    }

    function showLocationPanel(label, locItems) {
        openLocation = label;
        // Group by `group`, sort groups by name; items by year (unknown last).
        const byGroup = new Map();
        for (const it of locItems) {
            const g = it.group || '';
            if (!byGroup.has(g)) byGroup.set(g, []);
            byGroup.get(g).push(it);
        }
        const groups = [...byGroup.keys()].sort();
        let html = `<div style="display:flex;justify-content:space-between;align-items:baseline;margin-bottom:0.3rem">`
            + `<b style="color:#e0e0e0">${esc(label)}</b>`
            + `<span style="color:#808790;font-size:0.78rem">${locItems.length} · `
            + `<a href="#" class="map-panel-close" style="color:#808790">close</a></span></div>`;
        for (const g of groups) {
            const rows = byGroup.get(g).sort((a, b) => {
                const ay = a.year ?? Infinity, by = b.year ?? Infinity;
                if (ay !== by) return ay - by;
                return a.name.localeCompare(b.name);
            });
            if (g) {
                const color = groupColor.get(g) || '#9aa0a7';
                html += `<div style="color:${color};font-size:0.75rem;font-weight:bold;`
                    + `margin:0.4rem 0 0.1rem;text-transform:uppercase;letter-spacing:0.03em">${esc(g)}</div>`;
            }
            html += rows.map(itemRowHtml).join('');
        }
        panelEl.innerHTML = html;
        panelEl.style.display = '';
    }

    function hidePanel() {
        openLocation = null;
        panelEl.style.display = 'none';
        panelEl.innerHTML = '';
    }

    function render() {
        layer.clearLayers();
        markers = [];
        const locs = new Map();   // "lat,lon" -> {coords, label, items}
        const unlocated = [];
        for (const it of activeItems()) {
            const coords = it.coords || _resolveCountry(it.country);
            if (!coords) { unlocated.push(it); continue; }
            const key = coords.join(',');
            if (!locs.has(key)) {
                locs.set(key, { coords, label: it.country || '', items: [] });
            }
            locs.get(key).items.push(it);
        }
        for (const { coords, label, items: locItems } of locs.values()) {
            const total = locItems.length;
            const baseR = Math.min(5 + Math.sqrt(total) * 2, 16);

            // Concentric group rings (visual only — a single transparent
            // hit circle on top handles hover/click for the location).
            const counts = new Map();
            for (const it of locItems) {
                const g = it.group || '';
                counts.set(g, (counts.get(g) || 0) + 1);
            }
            const groupsHere = [...counts.entries()].sort((a, b) => b[1] - a[1]);
            const rings = [];
            let cum = 0;
            for (const [g, n] of groupsHere) {
                cum += n;
                rings.push({
                    color: groupColor.get(g) || MAP_GROUP_COLORS[0],
                    base: baseR * Math.sqrt(cum / total),   // area-proportional
                });
            }
            // Draw outermost first so inner rings sit on top.
            for (const ring of rings.reverse()) {
                const circle = L.circleMarker(coords, {
                    radius: ring.base * zoomFactor(),
                    stroke: true, color: '#101418', weight: 1,
                    fillColor: ring.color, fillOpacity: 0.6,
                    interactive: false,
                });
                circle.addTo(layer);
                markers.push({ marker: circle, base: ring.base });
            }

            const hit = L.circleMarker(coords, {
                radius: baseR * zoomFactor(),
                stroke: false, fill: true, fillOpacity: 0,
            });
            hit.bindTooltip(`${label} — ${total}`, { direction: 'top' });
            hit.on('click', () => showLocationPanel(label, locItems));
            hit.addTo(layer);
            markers.push({ marker: hit, base: baseR });
        }
        renderFacets();
        // Keep the open panel in sync with active filters.
        if (openLocation) {
            const loc = [...locs.values()].find(l => l.label === openLocation);
            loc ? showLocationPanel(loc.label, loc.items) : hidePanel();
        }
        if (opts.onUnlocated) opts.onUnlocated(unlocated);
    }

    map.on('zoomend', () => {
        const f = zoomFactor();
        for (const { marker, base } of markers) marker.setRadius(base * f);
    });

    function refresh(newItems) {
        allItems = newItems;
        const groups = [...new Set(newItems.map(it => it.group).filter(Boolean))];
        groupColor = new Map(groups.map((g, i) =>
            [g, MAP_GROUP_COLORS[i % MAP_GROUP_COLORS.length]]));
        render();
    }

    // Panel interactions: close link, anchor scroll-and-highlight.
    panelEl.addEventListener('click', e => {
        if (e.target.closest('.map-panel-close')) {
            e.preventDefault();
            hidePanel();
            return;
        }
        const a = e.target.closest('.map-anchor-link');
        if (!a) return;
        e.preventDefault();
        const el = document.getElementById(a.dataset.anchor);
        if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            el.style.transition = 'background 0.3s';
            el.style.background = '#1a2535';
            setTimeout(() => { el.style.background = ''; }, 1600);
        }
    });

    refresh(items);
    return { map, refresh };
}
