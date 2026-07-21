# The qbreader mirror

**Status: LIVE (July 2026).** The pipeline no longer depends on the
qbreader API for queries. Every question in the qbreader database lives
in a local SQLite mirror, and `lib/pipeline/fetch.py` answers all reads
(topic fetches, text mentions, frequency lists, unit sweeps, set/packet
reads) from it — offline, no rate limits. This is also the data
foundation for the planned custom question reader (specs TBD; Denis
decisions July 12, 2026: SQLite mirror, local-first reader v1, hosting
deferred — R2 the leading candidate if/when the online half is built).

## Layout

- `mirror/qbreader.sqlite` — the mirror (~860 MB, gitignored). Tables
  `sets` / `packets` / `tossups` / `bonuses`: indexed columns for
  everything the pipeline filters by, plus an `extra` JSON column that
  preserves any qbreader field we don't map (schema drift never loses
  data). `meta` records provenance (`seeded_from_backup`, `last_sync`).
- `mirror/raw/` — the backup dumps used for seeding (safe to delete
  after import; re-downloadable).
- **The engine is the extracted `qb-mirror` package** (July 2026,
  github.com/qbsuite/qb-mirror; dev checkout `../qb-mirror`,
  editable-installed — the first qbsuite extraction, see
  `docs/suite.md`): `qbmirror.db` (schema, extended-JSON decoding, doc
  flattening — shared by importer and sync, since the live API and the
  backup dumps have the same doc shape once decoded), `qbmirror.query`
  (local reimplementation of `/api/query`, `/api/frequency-list`,
  `/api/set-list`, `/api/packet`; semantics transliterated from
  qbreader/website's server source, quirks included — verified at
  cutover against the live API and re-verified byte-identical at
  extraction), `qbmirror.sync` + `qbmirror.api` (live-API pull), and
  `qbmirror.import_backup`. `lib/common.py` exports `QBMIRROR_DB` /
  `QBMIRROR_CACHE` so in-pipeline opens hit `mirror/qbreader.sqlite`.
- `lib/mirror/publish.py` — site-side only: R2 export of reader/site
  artifacts (stays in this repo).

## Operations

```bash
qbmirror sync --db mirror/qbreader.sqlite            # pull sets qbreader added (the ONLY live-API use)
qbmirror sync --db mirror/qbreader.sqlite --dry-run  # list what a sync would fetch
qbmirror sync --db mirror/qbreader.sqlite --refresh "SET"  # force-refetch one set (question edits)
qbmirror import-backup --db mirror/qbreader.sqlite   # full re-seed from mirror/raw/ dumps
qbmirror stats --db mirror/qbreader.sqlite           # row counts + provenance
python lib/mirror/publish.py --upload                # export + upload website artifacts to R2
```

Seeding: qbreader publishes full database backups (Google Drive folder
linked from https://www.qbreader.org/db/backups; the latest backup has
mongoexport JSON alongside BSON). Download `sets/packets/tossups/bonuses
.json` into `mirror/raw/`, run the importer (~30 s), then `sync` to top
up sets added since the backup date.

## Freshness model

- **New sets**: `sync` diffs the live set list and pulls whole missing
  sets via the packet endpoint (rate-limited, ~1 request/packet). Run it
  whenever new tournaments should appear.
- **Question edits inside mirrored sets** are NOT auto-detected (the API
  has no changed-since endpoint). They surface as small drift — e.g. at
  cutover, one tossup had been re-categorized two days after the backup.
  Remedies: `--refresh "Set Name"` for targeted fixes, or re-seed from
  the next published backup (qbreader posts one every month or two).
- The committed store (`output/_questions/`) is RETIRED (July 2026):
  renderers ship id refs only and pages fetch text at view time from
  the R2 artifacts, so nothing in CI needs question text anymore.
  Committed refs are validated against the mirror at publish time
  (publish aborts on a dangling id). After content work, run
  `publish --upload` or new pages' panels stay "not yet published".

## Published website artifacts (the reader's data plane)

`lib/mirror/publish.py` exports static artifacts to `mirror/publish/`
and uploads them (hash-diffed against the remote manifest, changed files
only) to the Cloudflare R2 bucket `library-of-stock-data` via wrangler
(`npx wrangler login`, Denis's account). Public base URL:

    https://pub-b5f94e8d4cc648abb0e35b7ca4444c65.r2.dev

e.g. `<base>/manifest.json`, `<base>/sets/2023_acf_nationals.json`.
CORS allows GET/HEAD from any origin. Objects are stored pre-gzipped
with `Content-Encoding: gzip` (browser fetch() decompresses
transparently) because r2.dev applies no edge compression of its own;
`curl` needs `--compressed`. A custom-domain alias can be added later
without changing the artifacts. First published July 12, 2026 (~200 MB
stored; manifest hashes are of the *uncompressed* JSON).
Decided July 2026: static-first, no server — reading, random mode,
answerline search, and offline all work from these files; a Worker API
would only ever be added for full-text search.

| artifact | size (gz) | purpose |
|---|---|---|
| `sets/{slug}.json` (704) | ~250 KB each | unit of fetch for reading a set; slugs assigned by `_unique_slugs` (collisions like "2023 CREEK+" get a numeric suffix) and published in the catalog — clients must not derive them |
| `catalog.json` | 1.5 MB | columnar index of all 347k questions: id, set, packet, number, taxonomy enums, difficulty → set browser, filters, random mode |
| `answerlines.json` | 12 MB | answer text aligned index-for-index with catalog rows → client-side answerline search |
| `topics.json` | 0.2 MB | our study-guide overlay: per-topic metadata (year, country, coordinates, tags, group, unit, ...) + the question ids backing its pages |
| `manifest.json` | — | hashes, counts, mirror provenance; clients cache-bust with it, the uploader diffs against it (uploaded last, so readers never see a half-updated bucket) |

Publish after every sync/re-seed (`sync` → `publish --upload`). The
run is idempotent: staging rewrites nothing when content is unchanged,
and unchanged files are never re-uploaded.

## Copyright note

Questions are copyright their writers/tournaments; qbreader's own
disclaimer permits non-commercial use. Fine for this personal study
tool; revisit before any public reader URL ships question text at scale.
