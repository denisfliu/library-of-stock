// qdata.js — runtime loader for the question data plane on R2.
//
// Question text is no longer embedded in pages at build time: pages ship
// with id refs only and fetch resolved text from the public bucket (see
// docs/mirror.md). This module is the single source of truth for the
// base URL. Artifacts are gzip-encoded JSON; fetch() decompresses
// transparently.
const QDATA_BASE = 'https://pub-b5f94e8d4cc648abb0e35b7ca4444c65.r2.dev';

const _qdataInflight = new Map();

// Fetch + parse a bucket path (e.g. 'topic_questions/foo.json') with
// in-flight/promise dedupe. Rejects with err.status set for HTTP errors.
function qdataFetch(path) {
    if (!_qdataInflight.has(path)) {
        const p = fetch(QDATA_BASE + '/' + path).then(r => {
            if (!r.ok) {
                const err = new Error('HTTP ' + r.status);
                err.status = r.status;
                throw err;
            }
            return r.json();
        }).catch(err => {
            _qdataInflight.delete(path); // allow retry
            throw err;
        });
        _qdataInflight.set(path, p);
    }
    return _qdataInflight.get(path);
}

// Standard error panel: 404 means the content exists in the repo but
// hasn't been published yet (publish is a manual local step).
function qdataErrorHtml(err) {
    const msg = (err && err.status === 404)
        ? 'Questions not yet published for this page.'
        : 'Questions couldn’t load.';
    return '<div class="qdata-error">' + msg +
           ' <a href="#" onclick="location.reload();return false;">Retry</a></div>';
}
