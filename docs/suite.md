# qbsuite — open-source suite plan (July 2026)

Status: **org created** (`github.com/qbsuite`, renamed from qbkit), extraction
not started. The intent: a suite of quizbowl tools, each organized around a
**user-facing surface** (the database, the audio, search, the moderator, the
wiki) rather than internal plumbing. `library-of-stock` moves into the org,
goes fully public, and becomes the reference consumer of the extracted
packages — code moves out and is imported back, one source of truth, no copy
drift.

## Decisions (settled)

- **Org: `qbsuite`** (July 18, 2026 — after `openqb` taken, `qbkit` "sounds
  weird", `qbtools` squatted + qBittorrent collision). Free across GitHub /
  npm / PyPI / HF at decision time. Site at **`https://qbsuite.github.io/`**
  (org root Pages — no custom domain; Denis doesn't want to buy one).
- **Organize by user value, not shared contracts.** The earlier `qb-core`
  repo (answer checker + reveal engine + normalizers) is dropped: nobody
  installs a contracts library, and the checker is qbreader's code — already
  public upstream. Each contract lives in the repo that owns its domain
  (below).
- **Upstream-first**: anything vendored from qbreader stays credited-vendored
  or gets contributed back upstream; we never republish their code as ours.
- **Target consumer: qbreader itself.** Success looks like qbreader.org
  adopting the audio dataset for read-aloud. Everything must be consumable
  with zero knowledge of this repo.
- **Registries on demand, specs up front** (decided July 18, 2026). The
  suite's real interfaces are **data contracts** — dataset layouts, manifest
  and sidecar schemas, the mirror's SQLite schema, taxonomy ordinals —
  documented in each repo, not code packages on registries. Consumers reach
  code via git tags: pip installs `git+https://...@tag` natively, and
  jsDelivr serves browser JS straight from a GitHub tag
  (`cdn.jsdelivr.net/gh/qbsuite/<repo>@<tag>/...`). PyPI/npm publishing
  happens only when a real external consumer asks for it — it's a
  20-minute step later vs. release ceremony now. The `@qbsuite` npm org
  stays claimed as squat protection.
- **The pipeline is open.** All of `library-of-stock` (generators, skills,
  renderers) goes public in the org — not just the rendered site.
- **Dev flow parity**: multi-repo must feel like today's monorepo locally
  (see "Development flow" below). This constraint shapes every extraction.

## Repo map

| Repo | What a user gets | Extracted from |
|---|---|---|
| `qb-mirror` | *The database interface.* Python package + CLI: build a full local qbreader SQLite from official backups, sync new sets from the live API, clean query layer (category/set/difficulty/answerline). Owns the **taxonomy ordinals** contract. | `lib/mirror/` (importer, sync, query engine; R2 publisher stays site-side) |
| `qb-audio` | **The dataset + its SPEC.md are the product.** HF dataset (stays `uild42/qb-audio` — Denis decided against an HF org, July 18) + a versioned SPEC.md: layout + path scheme (`tossups\|bonuses/{qid[-2:]}/{qid}.opus`), `audio_index.json` manifest schema, chunk-offset sidecar schema (v1 chunks, v2 word-level post-alignment), and the **text-cleaning contract** ("exactly the text the audio speaks"). Everything a consumer needs is plain HTTP — no install. Supporting code: generation pipeline (any TTS backend; qb-mirror as input adapter) + a reference JS playback client as a plain copyable/CDN-loadable file (manifest gate, LRU prefetch, audio-clock→text-position via sidecars). **First public deliverable.** | `dev/tts/`, audio parts of `lib/js/reader.js` |
| `qb-search` | Self-hostable semantic search: embedder, IVF-binary index builder, Cloudflare Worker, minimal search UI. | `lib/embed/`, `sync/worker.js` `/search`, `lib/js/semsearch.js` |
| `qb-moderator` | The moderator app (PWA) — **full plan: `docs/moderator.md`** (July 18; supersedes the hotkeys-first sketch). Two buzz modes: (1) temporary self-hosted **rooms** (DO-per-room per docs/rooms.md, promoted into v1; phones as buzzers, mobile-critical, host console, past-questions log, in-person read-aloud or remote text-reveal) and (2) **voice** (calibrated physical-buzzer sound detection + STT answer, optional local Whisper download). Optional scoring layer (15/10/-5, negs only during reading) with a human-manned adjudication mode. Engine = pure state machine module inside this repo. | new + docs/rooms.md + docs/moderator.md |
| `qb-td` | Tournament hub for TDs (**shipped July 20, 2026**; plan + status: `docs/tournament_hub.md`): per-room upload buckets for ModaQ game files, packet distribution + live round, live public stats, YellowFruit `.yft` + qbj-bundle export. Cloudflare Worker (D1+R2, OAuth from sync/) + static pages + dependency-free qbj/stats/yft engine. | new + `sync/worker.js` auth |
| `qbsuite.github.io` | The wiki/site itself — study guides, overviews, reader, search pages — **plus the whole generation pipeline** (this repo, transferred + renamed; org root Pages requires that exact repo name). | `library-of-stock` |

Old qb-core pieces, new homes:
- Answer checker → stays qbreader's; reader + moderator keep thin vendored
  copies with attribution; fixes go upstream.
- TTS text cleaning (`ttsclean`) → `qb-audio` (part of the dataset spec:
  "this is exactly the text the audio says").
- Taxonomy ordinals → `qb-mirror`; `qb-search` imports them.
- Answerline normalization + reveal/pacing engine → site-internal; the
  normAns-×3 unification survives as a site cleanup (CLAUDE.md roadmap),
  not a public package.
- **Golden test vectors** survive as data: the owning repo ships its vectors
  *inside the published package* (e.g. cleaning vectors in `qb-audio`), so
  consumers' test suites import them at their pinned version — no hand-copied
  fixtures, no drift.

## Development flow (the parity requirement)

Local layout: sibling checkouts under `~/code/` (`qb-mirror`, `qb-audio`,
`qb-search`, `qb-moderator`, `qb-td`, `qbsuite.github.io`).

- **Python**: every package is `pip install -e ../qb-mirror` into the shared
  env — edit in the package repo, effects are live in the site immediately,
  exactly like editing `lib/` today. `requirements.txt` in each consumer pins
  *released* versions; editable installs shadow them locally. CI installs the
  pins, so what ships is always a published version.
- **JS**: shipped as plain files in the owning repo. The site stays
  no-build vanilla JS, so `build.py` gains a vendor step that copies the
  pinned file into the deploy artifact; a dev flag/env var points it at the
  sibling checkout instead for live iteration. External consumers copy the
  file or load it from a git tag via jsDelivr. npm only on demand.
- **Release**: push a git tag. Python consumers pin
  `git+https://github.com/qbsuite/<repo>@<tag>` (pip-native); JS consumers
  pin the tag in their jsDelivr URL or vendor the file. The site upgrades by
  bumping a pin — a normal, reviewable commit. Registry publishing (PyPI
  trusted publisher / npm) is added per-repo only when an external consumer
  asks.
- **Rule of thumb**: a cross-repo change = one PR in the owning package + one
  pin-bump PR in consumers. If some change routinely needs coordinated PRs in
  three repos, the boundary is wrong — move the code.

## Chunk-offset sidecars — DONE in gen_tts.py (July 18, 2026)

Synthesis is per-*chunk* (`chunk_text` merges tiny fragments, splits long
sentences at clauses), so cumulative per-chunk durations are exact and free
to record at generation time. Load-bearing for the moderator (audio time T →
text position → powers/negs) and part of the qb-audio dataset spec.

- `gen_tts.py` emits a per-question sidecar `{qid}.json` next to each
  `.opus`: `{"v": 1, "chunks": [[start_s, end_s], ...], "texts": [...]}`.
  Chunk *texts* are included because chunk boundaries aren't reproducible
  client-side. Sidecar written before the `.opus` lands so skip-existing
  resume can never produce audio without offsets. `upload_hf.py` ships them.
- **Deploy**: copy updated `gen_tts.py` + `upload_hf.py` to MSL, bounce the
  tmux sessions (skip-existing makes restarts free). Reader keeps its
  proportional `currentTime/duration` approximation until taught to fetch
  sidecars.
- **Post-run batch alignment (decided July 18)**: after generation completes,
  force-align the ENTIRE dataset in one 4090 batch — alignment-only against
  the known clean+chunk transcript (whisperX align / wav2vec2 CTC), ~1 GPU-day
  for ~900 h. Yields (a) word-level sidecar v2 everywhere, (b) coverage of
  pre-sidecar files (nothing regenerated for offsets' sake), (c) a QA sweep:
  badly-aligning files are the runaway/babble glitches → regen worklist.
  Gen-time chunk sidecars are the alignment anchors.

## Site migration (independent of extraction; can happen any time)

Cloudflare (Worker/D1/R2) is keyed to the Cloudflare account and does not
move. GitHub is the whole migration:

1. Org Settings → Actions → allow all actions; verify Pages creation allowed.
2. Transfer `denisfliu/library-of-stock` → `qbsuite`, rename to
   `qbsuite.github.io` (required name for the root-URL site). NOTE (July 20,
   2026): `qbsuite/qbsuite.github.io` now exists as the interim landing/link
   page — fold its `index.html` sections into the site homepage and
   delete/replace that repo as part of this step.
3. Verify repo Settings → Pages → Source = GitHub Actions after transfer.
4. `sync/wrangler.toml` `ALLOWED_ORIGIN` → `https://qbsuite.github.io` +
   `npx wrangler deploy` (CORS + login-redirect validation).
5. OAuth app: callback URL points at the Worker (unchanged); update cosmetic
   homepage URL; optionally transfer the app to the org.
6. Old `denisfliu.github.io/library-of-stock` links die (github.io never
   redirects). Optional: stub repo with meta-refresh redirects.

## Sequencing

1. **qb-audio run finishes** (in flight on MSL; sidecar deploy CONFIRMED live
   July 18 — MSL scripts match the repo): post-run batch alignment + QA sweep
   → split `dev/tts/` + playback client into `qbsuite/qb-audio` (dataset
   stays `uild42/qb-audio`). Ship with **SPEC.md as the headline deliverable**
   (see repo map) plus a README qbreader could follow cold over plain HTTP.
   **Fleet constraint while the run is live (~11 days)**: the Windows workers
   execute `dev/tts/*.py` straight from their repo checkouts (worker_ctl.ps1),
   so `dev/tts/` must not be moved/deleted until the run ends — extraction is
   copy-first, removal after. GitHub transfer/rename is safe mid-run (local
   paths unchanged; git redirects old remotes — but do NOT create a stub repo
   at the old name until every machine's remote is updated, a stub kills the
   redirect).
2. **qb-mirror** — ~~cleanest extraction~~ **DONE July 18, 2026**:
   `github.com/qbsuite/qb-mirror` (public, v0.1.0 tag, CI). Package
   `qbmirror` = db/query/sync/api/import_backup + `qbmirror` CLI;
   query semantics verified **byte-identical** against the old site
   implementation on the full real mirror. Site refactored:
   `lib/common.py` exports `QBMIRROR_DB`/`QBMIRROR_CACHE`, `lib/mirror/`
   keeps only `publish.py`, `lib/pipeline/fetch.py` dropped its live-API
   section, `requirements.txt` pins the git tag (editable sibling
   checkout shadows it locally). The git pin IS the supported install
   (registries-on-demand); no PyPI step planned.
3. **Site migration** to `qbsuite.github.io` (any time; independent).
4. **qb-search**.
5. **qb-moderator** — build order in `docs/moderator.md`: ~~protocol+engine
   spec → engine + solo mode~~ **v0 shipped July 18**
   (github.com/qbsuite/qb-moderator; app at
   qbsuite.github.io/qb-moderator/app/) → rooms (DO + player PWA + host
   console) → voice mode → local STT download.

Manual (Denis) checklist remaining: ~~`@qbsuite` npm org~~ (done July 18,
kept as squat protection — no publishing planned); HF org — decided **not**
creating one, dataset stays under `uild42`; repo transfer (step 2 above).
PyPI/npm publishing: dropped from the plan (registries on demand).

## Data / licensing note

The mirror and audio dataset derive from qbreader-hosted, tournament-authored
question content. qbreader distributes official backups, so community norms
appear fine, but keep the deliberate stance: tools *build from* qbreader
backups (the user runs the import); we don't redistribute the raw DB. The
audio dataset README credits qbreader + tournament authors. Code license:
MIT across the org (matches qbreader and Chatterbox).

Status (done July 20, 2026): every repo carries a MIT `LICENSE`; this repo,
qb-td, and qb-moderator also carry `THIRD_PARTY_NOTICES.md` with full
license texts for vendored code (qb-answer-checker + inlined deps,
qb-packet-parser + its LICENSE.txt sidecar, MODAQ) and interop notes
(YellowFruit is AGPL-3.0 — qb-td implements the .yft *format* only, no YF
code). The HF dataset card (source: `dev/tts/DATASET_CARD.md`, uploaded as
the dataset README from MSL where the token lives) documents the
layout contract + credits + community-norms licensing stance.
