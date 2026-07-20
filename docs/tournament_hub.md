# Tournament-director hub (`qb-td`)

Status: **built + deployed July 20, 2026** — repo
[qbsuite/qb-td](https://github.com/qbsuite/qb-td) (dev checkout `../qb-td/`),
Worker live at `qb-td.denisliu10.workers.dev` (D1 + R2 provisioned, schema
applied, SESSION_SECRET set), pages at `qbsuite.github.io/qb-td/app/`, linked
from the qbsuite landing page. Tests: 18 engine unit tests + 25-check Worker
E2E (`qb-td/tests/`). Remaining manual steps:
1. **GitHub OAuth app** (Denis): create at Settings → Developer settings →
   OAuth Apps, callback `https://qb-td.denisliu10.workers.dev/auth/callback`;
   put the client id in `worker/wrangler.toml`, run
   `npx wrangler secret put GITHUB_CLIENT_SECRET`, `npx wrangler deploy`.
   (A placeholder secret is set so the Worker runs; sign-in fails until this.)
2. **YellowFruit round-trip** (Denis): generate a `.yft` from real ModaQ
   games, open in YF >= 4.0.18, confirm stats match the public page.

The two "Open items" (YellowFruit's exact `YfData` contract, ModaQ's native
game-file format) were re-verified against source on build day — findings
folded into "Format findings" below, and the architecture was simplified
accordingly (single Worker, client-side engine). The three key design
decisions were confirmed with Denis in the original planning session.

**Capacity + security hardening (July 20, follow-up session):** sized against
Cloudflare free-tier caps (Workers 100K req/day, D1 5M row reads/day). The
Worker maintains a materialized `t/<tid>/combined.json` stats bundle on qbj
upload/delete (R2 conditional writes; TO dashboard has a rebuild button), so
the public stats page is ~2 requests and refetches only when the `/pub`
`version` stamp moves (mods on laptops; stats change only on upload — no
blind polling). Bucket pages poll 60s visible-only with the upload list
trimmed to 20. **Bucket links expire 48h after creation** (410 "room closed"
on state/upload/packet; close time shown on bucket page + dashboard; TO
access unaffected) — a leaked link stops serving packets shortly after the
tournament. Secrets are ~99-bit; packets are current-round-only via bucket
links and never on public routes; bucket/admin pages are noindex +
no-referrer. E2E: 41 checks.

## Original request (verbatim)

> after you deploy, i'd like to develop a new tool. this one is for tournament
> organizers to handle modaq files in one place. in tournaments, moderators
> typically have to upload modaq files somewhere (usually, the game file and the
> qbj file). this makes things annoying because then the to or whoever is doing
> the stats has to download the files one by one and then upload them to
> yellowfruit (on github) and then generate the stats report. i want this to be
> a hub for the to have "buckets" where moderators will upload qbj files. in
> here, the to can also upload the packets for the moderators to download from
> and label which round they are currently on. also they can include the roster
> qbj of the tournament. then, we will make the yft file for the organizer and
> also have stats be shown (in public facing page, important to decouple these
> so that players can't see the website) without actually having to open yft.
> the to should also be able to download any of the files that get uploaded.
> please plan first after deploying.

## Problem / intended outcome

A TO running a tournament currently chases down each moderator's game files (the
`.qbj` match file + the ModaQ native game file), downloads them one by one,
imports them into YellowFruit, and generates stats by hand. This tool
centralizes that: TOs create a tournament, hand each room a private upload
"bucket," distribute packets, track the live round, collect the roster, and get
back a ready-to-open **`.yft`** plus a **live public stats page** — without ever
opening YellowFruit.

## Name / home

- Proposed repo: **`qbsuite/qb-td`** (tournament director). Alternatives:
  `qb-desk`, `qb-control`, `qb-hub`. Not created yet — easy to rename.
- New sibling checkout `../qb-td/`, following suite dev-flow parity
  (`docs/suite.md`). Adds a row to the qbsuite landing page when ready.

## Format findings (verified against source, July 20, 2026)

Verified against MODAQ master (`src/qbj/QBJ.ts`,
`src/components/dialogs/ExportToJsonDialog.tsx`) and YellowFruit master at
v4.0.18 (`src/renderer/DataModel/FileParsing.ts`, `Tournament.ts`,
`TournamentManager.ts`, `Match.ts`).

- **ModaQ exports three files** from its Export-to-JSON dialog:
  - `Round_{N}_{TeamA}_{TeamB}.qbj` — a **bare match object** (snake_case match
    schema, NOT wrapped in `{version, objects}`): `{tossups_read, match_teams:
    [{team:{name, players}, bonus_points, match_players:[{player:{name},
    tossups_heard, answer_counts:[{number, answer:{value}}]}], lineups}],
    match_questions:[…buzzes with word_index…], packets, _round}`. `_round` is
    a nonstandard field carrying the user-entered round number.
  - `Round_{N}_{TeamA}_{TeamB}_Game.json` — the full ModaQ GameState (packet +
    players + cycles). **This is "the game file"** — extension `.json`, treated
    by us as an opaque blob.
  - `Round_{N}_{TeamA}_{TeamB}_Events.json` — cycles only (some TDs collect it;
    also an opaque blob).
- **YellowFruit natively imports raw ModaQ `.qbj` files** ("import game files"):
  `TournamentManager.importMatchesFromWholeQbj` → uses `_round` to place each
  match (`IModaqMatch` in `Match.ts`). So the **qbj-bundle fallback needs zero
  transformation** — it's just the collected files + roster in a zip.
- **`.yft` contract**: top level `{version: '2.1.1', objects: [Tournament]}`.
  The Tournament object is a QBJ tournament (`type:'Tournament'`, `name`,
  `startDate`/`endDate`, `questionSet`, `registrations`, `phases`,
  `rankings`, `tournamentSite`, `scoringRules`) with a **`YfData` block spread
  in**: `{YfVersion, standardRuleSet, seeds, trackPlayerYear, trackSmallSchool,
  trackJV, trackUG, trackDiv2, finalRankingsReady, usingScheduleTemplate}`.
  Sub-objects (Registration, Team, Player, Phase, Pool, Round, Match,
  MatchTeam, ScoringRules) each *may* carry their own `YfData`; **on parse all
  of these are optional** (`if (yfExtraData)` guards) — the only hard
  requirements are:
  - top-level `YfData.YfVersion` present, and ≤ the reader's app version
    (`parseYftTournament` throws "upgrade to open" otherwise) — **we stamp
    `4.0.18`**, the current release; generated files need YF ≥ 4.0.18;
  - `scoringRules.answerTypes` non-empty with ≥ 1 positive value;
  - every Match has exactly 2 `matchTeams`;
  - every Phase has a `name`; phase type falls back to an assumed value when
    `YfData.phaseType` is absent (fine for a single "All games" prelim phase).
  - **YF ignores question-level data** (`Tournament.useQuestionLevelData` is
    hard-coded `false`), so the `.yft` needs only per-team/per-player
    aggregates (`answer_counts`, `bonus_points`, `tossupsRead`) — buzz-point
    detail stays in the raw qbj bundle for tools that want it.
  - Case note: YF reads both snake_case qbj and camelCase yft spellings
    (`CaseConversion.ts`); YF's own writer emits camelCase — we match that.
- **QBJ tournament schema** (schema.quizbowl.technology): Tournament →
  Registration → Team → Player; Match → MatchTeam → MatchPlayer. A
  **roster/registration qbj** carries Registrations/Teams/Players and no
  matches. **All standings + individual stats are computable from match qbj +
  roster** — no YellowFruit required.
- YF is GUI-only Electron, so we cannot invoke it programmatically — we
  replicate its `.yft` serialization and verify by round-trip.

## Confirmed design decisions (from Denis)

1. **Moderator access = unguessable bucket link.** No login, mobile-first. TO
   hands each room a secret link/code; the mod uploads qbj + game file and
   downloads that round's packet with no account.
2. **YFT output = both** a native `.yft` and a **qbj bundle** (zip of raw match
   qbj + roster) as an import fallback.
3. **Public stats = TO publish-toggle + separate slug.** Public stats live at a
   distinct URL (e.g. `/t/<slug>`) computed live from qbj; admin is behind OAuth
   on a different route, never linked from the public page; TO flips "publish"
   when ready and controls whether in-progress rounds show.

## Architecture (re-evaluated July 20, 2026 — one Worker, client-side engine)

- **One Worker: `qb-td`** — clone of `library-of-stock/sync/worker.js`'s
  skeleton. Reuse the **stateless HMAC session + GitHub OAuth verbatim**
  (`worker.js:22-155`: `/auth/login`, `/auth/callback`, token in URL fragment,
  `requireUser` bearer gate, `corsHeaders` echoing `ALLOWED_ORIGIN` not `*`).
  Same single-`fetch` manual path dispatch. Bindings: D1 `DB`, R2 `DATA` (own
  bucket `qb-td-data`). New OAuth app (`GITHUB_CLIENT_ID`), secrets
  `GITHUB_CLIENT_SECRET`/`SESSION_SECRET` via `wrangler secret put`. TO
  identity = `gh:<id>`, exactly like `sync/schema.sql` `users.uid`.
  The Worker is a **pure auth/metadata/blob API** — no stats or yft code
  server-side.
- **R2 write path is NEW** (today every site R2 write goes through the wrangler
  CLI in `lib/mirror/publish.py`; moderators can't use that): Worker upload
  endpoints write via the binding (`env.DATA.put`), authorized by the bucket
  secret (not OAuth) for moderator uploads and by OAuth for TO uploads. All
  reads stream through the Worker (no public r2.dev exposure — publish gating
  stays in one place). Key scheme: `t/<tid>/packet/<r>/<name>`,
  `t/<tid>/bucket/<bid>/<fileid>-<name>`, `t/<tid>/roster.qbj`.
- **No DO / no second Worker in v1.** Live current-round on the bucket page is
  a poll of the bucket-state endpoint (~30 s). The `qb-moderator` `RoomDO`
  WebSocket relay remains a drop-in upgrade if polling ever feels laggy —
  explicitly deferred, as the original plan allowed.
- **The stats + `.yft` engine runs client-side** as a dependency-free shared JS
  module (`app/engine/`). The TO dashboard fetches the collected qbj + roster
  through the authed API, computes standings, and generates the `.yft` and the
  qbj-bundle zip **in the browser** (store-only zip, hand-rolled CRC32 — no
  library). The public stats page uses the *same module* over the public
  endpoints. Rationale: YF import needs no server transformation (see Format
  findings), browsers handle these file sizes trivially, and it keeps the
  Worker at sync/worker.js's proven complexity level. Also mirrors the suite's
  static-app pattern (qb-moderator).
- **Frontend = static pages** in the `qb-td` repo, served at
  `qbsuite.github.io/qb-td/` via Pages. Routing is query-param based, matching
  qb-moderator's `player.html?room=X` convention: bucket link
  `bucket.html?b=<secret>`, public stats `stats.html?t=<slug>`, admin
  `admin.html`. (The original plan's `/b/<code>` path style assumed
  Worker-served HTML; query params keep the API/page split clean.)

## Data model (D1)

Follow the patterns from `sync/schema.sql` (`users` table identical).

- `tournaments(id, slug UNIQUE, name, owner_uid, current_round, published,
  settings TEXT, roster_r2_key, created)` — `settings` is a JSON blob for
  YfData tracking flags + scoring-rule choices; single roster per tournament is
  a column, not a table.
- `buckets(id, tournament_id, room_name, secret UNIQUE, created)`
- `rounds(tournament_id, number, packet_r2_key, packet_name, PRIMARY KEY
  (tournament_id, number))` — a round row exists iff a packet was uploaded;
  `current_round` lives on the tournament.
- `files(id, tournament_id, bucket_id, round, kind, r2_key, filename, size,
  created)` — `kind ∈ {qbj, game, other}` (mod uploads only; packets and
  roster live in their own homes above).

## Pages / flows

1. **TO admin dashboard** (OAuth-gated, `admin.html`): create tournament (slug +
   YfData settings: ruleset, powers, tracking flags); create buckets (one per
   room) and copy each bucket's private link; upload packets per round and set
   the **current round** (pushed live to mods); upload the **roster qbj** once;
   see all uploads and **download any file**; validate each game qbj (parse +
   surface schema errors, like YF's import error reporting); **generate `.yft`**
   and **download qbj bundle**; toggle **publish**.
2. **Moderator bucket page** (`bucket.html?b=<secret>`, no login, mobile-first): shows
   the tournament + this room + the live current round; download the current
   round's packet; upload this game's `.qbj` + ModaQ native game file (drag/drop
   or file pick); confirm + list this room's prior uploads.
3. **Public stats page** (`stats.html?t=<slug>`, only when published): standings (W/L,
   PPG, PPB, PP20TUH) + individual leaderboard (TUH, 15/10/−5, P/N, bonus
   conversion), computed live in-browser from the collected qbj + roster.
   Decoupled: no link to admin, nothing about the upload side.

## Reusable engine: `qbj → stats` + `qbj → .yft`

A pure JS module (`qb-td/src/stats/`) that:
- **merges** N match qbj + roster into one QBJ tournament object,
- **computes** standings + individual stats (the aggregation YellowFruit/SQBS
  do — well specified by the schema),
- **serializes** `.yft` (QBJ tournament + `YfData`).

`consensus-scorekeeper` `src/util/tournament-aggregate.js` is a good *shape*
reference (pure `aggregate → {standings, leaderboard, ...}`) but is flat-CSV,
not qbj, and has no tossup/bonus granularity — this engine is new. The moderator
scoring-rule table (`docs/moderator.md:161-186`, 15/10/−5/0 + 10/part bonuses) is
the closest existing per-question spec. Extract to its own package if a second
suite consumer appears (suite rule).

## Build phases (revised)

1. Engine first (pure JS, offline-testable): qbj parse → merge with roster →
   standings/leaderboard → `.yft` serialization → store-only zip. Node test
   suite with ModaQ-shaped fixtures.
2. Worker: OAuth (copy from `sync/`), D1 schema, tournament/bucket/round/file
   API, R2 blob endpoints, public endpoints behind the publish gate.
3. Frontends: TO admin dashboard; moderator bucket page (poll current round);
   public stats page — all on the shared engine module.
4. **Round-trip a generated `.yft` through real YellowFruit** (manual, Denis)
   to confirm it opens with no version/schema errors and stats match; verify
   the qbj bundle imports via YF's ModaQ import path.
5. Deploy (D1 create + schema, OAuth app, secrets, `wrangler deploy`), add
   `qb-td` to the qbsuite landing page.

## Verification

- **`.yft` round-trip**: generate from real ModaQ qbj matches + roster, open in
  YellowFruit v4, confirm it loads with no version/schema errors and its report
  matches our public page's numbers.
- **Stats parity**: cross-check the aggregator against YellowFruit's HTML report
  on the same inputs.
- **Upload E2E**: from a phone-sized viewport, open a bucket link, download the
  current packet, upload a qbj + game file, see it in the TO dashboard and
  downloadable.
- **Decoupling**: public slug exposes no admin route and no upload affordance;
  publish toggle hides in-progress data.
- **Auth**: only the owning TO's OAuth session can touch a tournament's admin
  API; a bucket code grants upload only to its own bucket.

## Open items — resolved July 20, 2026

- ~~Exact `YfVersion` / `YfData` field set~~ — verified against YF 4.0.18
  source; see Format findings. We stamp `YfVersion: '4.0.18'`.
- ~~ModaQ's native "game file" format/extension~~ — `Round_N_A_B_Game.json`,
  a full GameState dump; stored + served as an opaque blob. Only the `.qbj`
  is parsed for stats.
