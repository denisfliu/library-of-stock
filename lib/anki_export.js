/**
 * anki_export.js — Generate .apkg files in the browser.
 *
 * Uses sql.js (SQLite WASM) and JSZip to create Anki-compatible packages.
 * Loaded via CDN in the card editor page.
 *
 * Usage:
 *   const blob = await exportApkg(cards, deckName);
 *   // cards: [{front, back, tags[], images?: [{url, side}], type}]
 *   // returns a Blob you can download
 */

async function exportApkg(cards, deckName) {
    // Load dependencies from CDN
    const [SQL, JSZip] = await Promise.all([
        loadSqlJs(),
        loadJSZip(),
    ]);

    const db = new SQL.Database();
    const now = Math.floor(Date.now() / 1000);
    const modelId = stableHash(deckName + '_basic');
    const imageModelId = stableHash(deckName + '_image');
    const deckId = stableHash(deckName + '_deck');

    // Create Anki schema
    db.run(`
        CREATE TABLE col (id INTEGER PRIMARY KEY, crt INTEGER, mod INTEGER,
            scm INTEGER, ver INTEGER, dty INTEGER, usn INTEGER, ls INTEGER,
            conf TEXT, models TEXT, decks TEXT, dconf TEXT, tags TEXT);
        CREATE TABLE notes (id INTEGER PRIMARY KEY, guid TEXT, mid INTEGER,
            mod INTEGER, usn INTEGER, tags TEXT, flds TEXT, sfld TEXT,
            csum INTEGER, flags INTEGER, data TEXT);
        CREATE TABLE cards (id INTEGER PRIMARY KEY, nid INTEGER, did INTEGER,
            ord INTEGER, mod INTEGER, usn INTEGER, type INTEGER, queue INTEGER,
            due INTEGER, ivl INTEGER, factor INTEGER, reps INTEGER,
            lapses INTEGER, left INTEGER, odue INTEGER, odid INTEGER,
            flags INTEGER, data TEXT);
        CREATE TABLE revlog (id INTEGER PRIMARY KEY, cid INTEGER, usn INTEGER,
            ease INTEGER, ivl INTEGER, lastIvl INTEGER, factor INTEGER,
            time INTEGER, type INTEGER);
        CREATE TABLE graves (usn INTEGER, oid INTEGER, type INTEGER);
    `);

    // Models (note types)
    const models = {};
    models[modelId] = {
        css: `.card { font-family: -apple-system, 'Segoe UI', Roboto, sans-serif; font-size: 18px; text-align: center; color: #202122; background: #fff; padding: 20px; } img { max-width: 400px; max-height: 400px; }`,
        did: deckId,
        flds: [
            { name: "Front", ord: 0, font: "Arial", media: [], rtl: false, size: 20, sticky: false },
            { name: "Back", ord: 1, font: "Arial", media: [], rtl: false, size: 20, sticky: false },
            { name: "Image", ord: 2, font: "Arial", media: [], rtl: false, size: 20, sticky: false },
        ],
        id: modelId,
        mod: now,
        name: "StockQB Basic",
        req: [[0, "any", [0]]],
        sortf: 0,
        tags: [],
        tmpls: [{
            afmt: '{{FrontSide}}<hr id="answer">{{Back}}{{#Image}}<br>{{Image}}{{/Image}}',
            bafmt: "",
            bqfmt: "",
            did: null,
            name: "Card 1",
            ord: 0,
            qfmt: "{{Front}}",
        }],
        type: 0,
        usn: -1,
        vers: [],
    };
    models[imageModelId] = {
        css: `.card { font-family: -apple-system, 'Segoe UI', Roboto, sans-serif; font-size: 18px; text-align: center; color: #202122; background: #fff; padding: 20px; } img { max-width: 500px; max-height: 500px; }`,
        did: deckId,
        flds: [
            { name: "Image", ord: 0, font: "Arial", media: [], rtl: false, size: 20, sticky: false },
            { name: "Back", ord: 1, font: "Arial", media: [], rtl: false, size: 20, sticky: false },
        ],
        id: imageModelId,
        mod: now,
        name: "StockQB Image",
        req: [[0, "any", [0]]],
        sortf: 0,
        tags: [],
        tmpls: [{
            afmt: '{{Image}}<hr id="answer">{{Back}}',
            bafmt: "",
            bqfmt: "",
            did: null,
            name: "Card 1",
            ord: 0,
            qfmt: '{{Image}}',
        }],
        type: 0,
        usn: -1,
        vers: [],
    };

    // Deck
    const decks = {
        "1": { collapsed: false, conf: 1, desc: "", dyn: 0, extendNew: 10, extendRev: 50, id: 1, lrnToday: [0,0], mod: now, name: "Default", newToday: [0,0], revToday: [0,0], timeToday: [0,0], usn: 0 },
    };
    decks[deckId] = {
        collapsed: false, conf: 1, desc: "", dyn: 0, extendNew: 0, extendRev: 50, id: deckId, lrnToday: [0,0], mod: now, name: deckName, newToday: [0,0], revToday: [0,0], timeToday: [0,0], usn: -1,
    };

    const conf = { activeDecks: [1], addToCur: true, collapseTime: 1200, curDeck: 1, curModel: String(modelId), dueCounts: true, estTimes: true, newBury: true, newSpread: 0, nextPos: 1, sortBackwards: false, sortType: "noteFld", timeLim: 0 };
    const dconf = { "1": { autoplay: true, id: 1, lapse: { delays: [10], leechAction: 0, leechFails: 8, minInt: 1, mult: 0 }, maxTaken: 60, mod: 0, name: "Default", new: { bury: true, delays: [1, 10], initialFactor: 2500, ints: [1, 4, 7], order: 1, perDay: 20, separate: true }, replayq: true, rev: { bury: true, ease4: 1.3, fuzz: 0.05, ivlFct: 1, maxIvl: 36500, minSpace: 1, perDay: 100 }, timer: 0, usn: 0 } };

    db.run(`INSERT INTO col VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
        [1, now, now * 1000, now * 1000, 11, 0, 0, 0, JSON.stringify(conf), JSON.stringify(models), JSON.stringify(decks), JSON.stringify(dconf), "{}"]);

    // Normalize card images: support both old image_url and new images array
    function getCardImages(card) {
        if (card.images && card.images.length) return card.images;
        if (card.image_url) return [{ url: card.image_url, side: card.image_side || (card.type === 'image' ? 'front' : 'back') }];
        return [];
    }

    // Download images and track media files
    const mediaMap = {};  // url -> filename
    let mediaIdx = 0;
    const mediaFiles = {}; // "0" -> {name, blob}

    // Collect unique image URLs to download
    const imageUrls = [];
    for (const card of cards) {
        for (const img of getCardImages(card)) {
            if (img.url && !img.url.startsWith('data:') && !imageUrls.includes(img.url)) {
                imageUrls.push(img.url);
            }
        }
    }

    // Download images sequentially with delay and retry
    async function fetchWithRetry(url, retries = 2) {
        for (let attempt = 0; attempt <= retries; attempt++) {
            try {
                const resp = await fetch(url);
                if (resp.ok) return resp;
                if (resp.status === 429 || resp.status === 503) {
                    const wait = attempt === 0 ? 2000 : 5000;
                    console.warn(`Rate limited (${resp.status}) on ${url.substring(0, 60)}..., retrying in ${wait}ms`);
                    await new Promise(r => setTimeout(r, wait));
                    continue;
                }
                console.warn(`HTTP ${resp.status} for ${url.substring(0, 60)}...`);
                return null;
            } catch (e) {
                if (attempt < retries) {
                    await new Promise(r => setTimeout(r, 2000));
                    continue;
                }
                throw e;
            }
        }
        return null;
    }

    for (const card of cards) {
        for (const img of getCardImages(card)) {
            const imageUrl = img.url;
            if (!imageUrl || mediaMap[imageUrl]) continue;
            try {
                if (imageUrl.startsWith('data:')) {
                    const match = imageUrl.match(/^data:image\/(\w+);base64,(.+)$/);
                    if (match) {
                        const ext = match[1] === 'jpeg' ? 'jpg' : match[1];
                        const binary = atob(match[2]);
                        const bytes = new Uint8Array(binary.length);
                        for (let j = 0; j < binary.length; j++) bytes[j] = binary.charCodeAt(j);
                        const fname = `pasted_${mediaIdx}.${ext}`;
                        mediaMap[imageUrl] = fname;
                        mediaFiles[String(mediaIdx)] = { name: fname, blob: bytes };
                        mediaIdx++;
                        console.log(`Embedded pasted image ${mediaIdx}: ${fname} (${bytes.length} bytes)`);
                    }
                } else {
                    // Delay between remote fetches to avoid rate limiting
                    if (mediaIdx > 0) await new Promise(r => setTimeout(r, 500));
                    const resp = await fetchWithRetry(imageUrl);
                    if (resp) {
                        const blob = await resp.blob();
                        if (blob.size > 0) {
                            const contentType = resp.headers.get('content-type') || '';
                            let ext = 'jpg';
                            if (contentType.includes('png')) ext = 'png';
                            else if (contentType.includes('gif')) ext = 'gif';
                            else if (contentType.includes('webp')) ext = 'webp';
                            else {
                                const urlExt = imageUrl.split('.').pop().split('?')[0].substring(0, 4).toLowerCase();
                                if (['jpg','jpeg','png','gif','webp'].includes(urlExt)) ext = urlExt;
                            }
                            const urlParts = imageUrl.split('/');
                            let fname = urlParts[urlParts.length - 1].split('?')[0];
                            fname = fname.replace(/^\d+px-/, '');
                            try { fname = decodeURIComponent(fname); } catch(e) {}
                            if (Object.values(mediaMap).includes(fname)) {
                                fname = `${mediaIdx}_${fname}`;
                            }
                            mediaMap[imageUrl] = fname;
                            mediaFiles[String(mediaIdx)] = { name: fname, blob: new Uint8Array(await blob.arrayBuffer()) };
                            mediaIdx++;
                            console.log(`Downloaded image ${mediaIdx}: ${fname} (${blob.size} bytes)`);
                        }
                    } else {
                        console.warn(`Failed to download: ${imageUrl.substring(0, 80)}...`);
                    }
                }
            } catch (e) {
                console.warn('Failed to process image:', imageUrl?.substring(0, 50), e);
            }
        }
    }
    console.log(`Processed ${mediaIdx} images, ${imageUrls.length - mediaIdx} failed`);

    // Insert notes and cards
    let cardId = now * 1000;
    let noteId = now * 1000;

    for (let i = 0; i < cards.length; i++) {
        const card = cards[i];
        const tags = (card.tags || []).map(t => t.replace(/ /g, '_')).join(' ');
        const guid = generateGuid();
        noteId++;
        cardId++;

        const images = getCardImages(card);
        const frontImgTags = images.filter(img => img.side === 'front')
            .map(img => mediaMap[img.url] ? `<img src="${mediaMap[img.url]}">` : '').filter(Boolean).join(' ');
        const backImgTags = images.filter(img => img.side === 'back')
            .map(img => mediaMap[img.url] ? `<img src="${mediaMap[img.url]}">` : '').filter(Boolean).join(' ');

        const hasFrontImg = frontImgTags.length > 0;
        const hasBackImg = backImgTags.length > 0;

        if (hasFrontImg && !hasBackImg) {
            // Images only on front: use image model
            const frontContent = frontImgTags + (card.front ? ' ' + card.front : '');
            const flds = frontContent + '\x1f' + (card.back || '');
            db.run(`INSERT INTO notes VALUES (?,?,?,?,?,?,?,?,?,?,?)`,
                [noteId, guid, imageModelId, now, -1, ' ' + tags + ' ', flds, frontContent, 0, 0, '']);
        } else {
            // Basic model: Front=text, Back=text, Image=combined img tags
            const frontContent = hasFrontImg ? frontImgTags + ' ' + (card.front || '') : (card.front || '');
            const flds = frontContent + '\x1f' + (card.back || '') + '\x1f' + (hasBackImg ? backImgTags : '');
            db.run(`INSERT INTO notes VALUES (?,?,?,?,?,?,?,?,?,?,?)`,
                [noteId, guid, modelId, now, -1, ' ' + tags + ' ', flds, frontContent, 0, 0, '']);
        }

        db.run(`INSERT INTO cards VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)`,
            [cardId, noteId, deckId, 0, now, -1, 0, 0, i, 0, 0, 0, 0, 0, 0, 0, 0, '']);
    }

    // Export to binary
    const dbBinary = db.export(); // Uint8Array
    db.close();

    // Build the zip
    const zip = new JSZip();
    zip.file('collection.anki2', new Uint8Array(dbBinary), { compression: 'STORE' });

    // Media manifest and files — Anki expects STORE (no compression)
    const manifest = {};
    for (const [idx, file] of Object.entries(mediaFiles)) {
        manifest[idx] = file.name;
        zip.file(idx, file.blob, { compression: 'STORE' });
    }
    zip.file('media', JSON.stringify(manifest), { compression: 'STORE' });

    return await zip.generateAsync({ type: 'blob', compression: 'STORE' });
}

// --- Helpers ---

function stableHash(str) {
    let hash = 0;
    for (let i = 0; i < str.length; i++) {
        hash = ((hash << 5) - hash) + str.charCodeAt(i);
        hash = hash & 0x7FFFFFFF; // keep positive 31-bit
    }
    return hash || 1;
}

function generateGuid() {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!#$%&()*+,-./:;<=>?@[]^_`{|}~';
    let result = '';
    for (let i = 0; i < 10; i++) {
        result += chars[Math.floor(Math.random() * chars.length)];
    }
    return result;
}

// --- CDN loaders ---

let _sqlPromise = null;
function loadSqlJs() {
    if (_sqlPromise) return _sqlPromise;
    _sqlPromise = new Promise((resolve, reject) => {
        if (window.initSqlJs) { window.initSqlJs().then(resolve); return; }
        const s = document.createElement('script');
        s.src = 'https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.3/sql-wasm.js';
        s.onload = () => {
            window.initSqlJs({ locateFile: f => `https://cdnjs.cloudflare.com/ajax/libs/sql.js/1.10.3/${f}` })
                .then(resolve).catch(reject);
        };
        s.onerror = reject;
        document.head.appendChild(s);
    });
    return _sqlPromise;
}

let _zipPromise = null;
function loadJSZip() {
    if (_zipPromise) return _zipPromise;
    _zipPromise = new Promise((resolve, reject) => {
        if (window.JSZip) { resolve(window.JSZip); return; }
        const s = document.createElement('script');
        s.src = 'https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js';
        s.onload = () => resolve(window.JSZip);
        s.onerror = reject;
        document.head.appendChild(s);
    });
    return _zipPromise;
}
