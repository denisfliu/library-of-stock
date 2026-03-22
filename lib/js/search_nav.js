/**
 * search_nav.js — Shared search + random navigation for stock guide pages.
 *
 * Expects GUIDES_DATA to be defined (loaded from guides_data.js).
 * Call initSearchNav(containerSelector, options) to set up.
 *
 * Options:
 *   prefix: path prefix for links (e.g., "" for index, "../" for stock pages in output/)
 *   showRandom: whether to show the random button (default: true)
 *   currentSlug: if set, shows a "next" button linking to next topic in same subcategory
 */

function initSearchNav(containerSelector, options = {}) {
    const container = document.querySelector(containerSelector);
    if (!container || typeof GUIDES_DATA === 'undefined') return;

    const prefix = options.prefix || '';
    const showRandom = options.showRandom !== false;
    const currentSlug = options.currentSlug || null;

    // Compute prev/next links if currentSlug is provided
    // Group by subcategory for categories that have them (Literature, Fine Arts,
    // Science, History), by category for the rest (Philosophy, Religion, etc.)
    const CATEGORIES_WITH_SUBS = ['Literature', 'Fine Arts', 'Science', 'History'];

    let prevGuide = null;
    let nextGuide = null;
    if (currentSlug) {
        const currentPath = 'output/' + currentSlug + '_stock.html';
        const current = GUIDES_DATA.find(g => g.path === currentPath);
        if (current) {
            const useGenre = CATEGORIES_WITH_SUBS.includes(current.category) && current.genre;
            const useSubcat = CATEGORIES_WITH_SUBS.includes(current.category) && current.subcategory;
            const siblings = GUIDES_DATA
                .filter(g => useGenre
                    ? g.genre === current.genre
                    : useSubcat
                        ? g.subcategory === current.subcategory
                        : g.category === current.category)
                .sort((a, b) => {
                    const aYear = a.year ?? Infinity;
                    const bYear = b.year ?? Infinity;
                    if (aYear !== bYear) return aYear - bYear;
                    return a.name.localeCompare(b.name);
                });
            const idx = siblings.findIndex(g => g.path === currentPath);
            if (idx !== -1 && siblings.length > 1) {
                prevGuide = siblings[(idx - 1 + siblings.length) % siblings.length];
                nextGuide = siblings[(idx + 1) % siblings.length];
            }
        }
    }

    // Build the UI
    const prevBtn = prevGuide
        ? `<a href="${prefix}${prevGuide.path}" class="search-nav-prev" title="Previous: ${prevGuide.name}">&larr;</a>`
        : '';
    const nextBtn = nextGuide
        ? `<a href="${prefix}${nextGuide.path}" class="search-nav-next" title="Next: ${nextGuide.name}">&rarr;</a>`
        : '';

    const wrap = document.createElement('div');
    wrap.className = 'search-nav';
    wrap.innerHTML = `
        <div class="search-nav-row">
            <div class="search-nav-input-wrap">
                <input class="search-nav-input" type="text" placeholder="Search guides..." autocomplete="off">
                <div class="search-nav-dropdown"></div>
            </div>
            ${prevBtn}
            ${showRandom ? '<button class="search-nav-random" title="Random guide">&#x1f3b2;</button>' : ''}
            ${nextBtn}
        </div>
    `;
    container.appendChild(wrap);

    const input = wrap.querySelector('.search-nav-input');
    const dropdown = wrap.querySelector('.search-nav-dropdown');
    const randomBtn = wrap.querySelector('.search-nav-random');

    // Normalize for accent-insensitive matching
    function normalize(s) {
        return s.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase();
    }

    function renderDropdown() {
        const q = normalize(input.value || '');
        if (q.length < 1) {
            dropdown.classList.remove('open');
            return;
        }

        const matches = GUIDES_DATA
            .filter(g => normalize(g.name).includes(q))
            .sort((a, b) => {
                // Prefer starts-with matches
                const aStarts = normalize(a.name).startsWith(q) ? 0 : 1;
                const bStarts = normalize(b.name).startsWith(q) ? 0 : 1;
                if (aStarts !== bStarts) return aStarts - bStarts;
                return a.name.localeCompare(b.name);
            })
            .slice(0, 12);

        if (matches.length === 0) {
            dropdown.innerHTML = '<div class="search-nav-empty">No guides found</div>';
        } else {
            dropdown.innerHTML = matches.map((g, i) => {
                const cat = g.subcategory || g.category || '';
                return `<a href="${prefix}${g.path}" class="search-nav-result${i === 0 ? ' active' : ''}" data-index="${i}">
                    <span class="search-nav-result-name">${g.name}</span>
                    <span class="search-nav-result-cat">${cat}</span>
                </a>`;
            }).join('');
        }
        dropdown.classList.add('open');
    }

    input.addEventListener('input', renderDropdown);

    // Keyboard navigation
    input.addEventListener('keydown', (e) => {
        const results = dropdown.querySelectorAll('.search-nav-result');
        if (!results.length) {
            if (e.key === 'Escape') {
                dropdown.classList.remove('open');
                input.blur();
            }
            return;
        }

        const active = dropdown.querySelector('.search-nav-result.active');
        let idx = active ? parseInt(active.dataset.index) : -1;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            idx = Math.min(idx + 1, results.length - 1);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            idx = Math.max(idx - 1, 0);
        } else if (e.key === 'Enter') {
            e.preventDefault();
            if (active) window.location.href = active.href;
            return;
        } else if (e.key === 'Escape') {
            dropdown.classList.remove('open');
            input.blur();
            return;
        } else {
            return;
        }

        results.forEach(r => r.classList.remove('active'));
        if (results[idx]) {
            results[idx].classList.add('active');
            results[idx].scrollIntoView({ block: 'nearest' });
        }
    });

    // Close on outside click
    document.addEventListener('click', (e) => {
        if (!wrap.contains(e.target)) {
            dropdown.classList.remove('open');
        }
    });

    // Focus on slash key
    document.addEventListener('keydown', (e) => {
        if (e.key === '/' && document.activeElement !== input && !e.ctrlKey && !e.metaKey) {
            const tag = document.activeElement?.tagName;
            if (tag === 'INPUT' || tag === 'TEXTAREA' || document.activeElement?.isContentEditable) return;
            e.preventDefault();
            input.focus();
            input.select();
        }
    });

    // Random button
    if (randomBtn) {
        randomBtn.addEventListener('click', () => {
            const g = GUIDES_DATA[Math.floor(Math.random() * GUIDES_DATA.length)];
            if (g) window.location.href = prefix + g.path;
        });
    }
}
