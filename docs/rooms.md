# Online rooms — design notes (July 2026)

Status: **promoted into qb-moderator v1** (July 18, 2026 — see
`docs/moderator.md`, which supersedes this doc's framing but keeps its
architecture verbatim: DO-per-room on the existing Worker, clock protocol,
server-side checker). Kept as the detailed reference for the room-server
internals. Nothing here is built yet.

## Why the pieces already line up

- The Cloudflare stack is deployed (`sync/` Worker + D1) and the reader's
  auth is a stateless HMAC session token — verifiable inside any Worker or
  Durable Object with the same `SESSION_SECRET`, so signed-in users carry
  identity into rooms for free.
- qbreader's answer checker is vendored client-side
  (`lib/js/answer_checker.js`, plain JS) — it runs unchanged server-side,
  making verdicts server-authoritative.
- The reveal engine is a **deterministic function of elapsed time**: given
  the question text, `buildUnits` + `slowSpans` + a wpm rate, the current
  word index is computable from a start timestamp. That makes the clock
  protocol cheap (no per-word streaming).

## Architecture: one Durable Object per room

Extend the existing `los-sync` Worker rather than deploying something new.
SQLite-backed Durable Objects are on the Workers **Free** plan; the
WebSocket Hibernation API keeps idle rooms free.

- **Lobby routes** in `sync/worker.js`: `POST /rooms` (create → short room
  code), `GET /rooms/:code/ws` (WebSocket upgrade, routed to that room's
  DO). Guests get ephemeral names; signed-in users present their existing
  bearer token.
- **Room DO** owns: player roster, host-controlled filters, the question
  queue, the reading clock, buzz arbitration, lockouts, scores,
  end-of-question flow. It draws questions the same way the client does —
  bind the R2 bucket and read `catalog.json` + set shards directly.
- **Server-side grading** with the vendored checker; the reader's
  self-grade override becomes a host override.

## Clock + buzz protocol

- DO broadcasts `{doc, startedAt, msPerWord}`; every client runs its
  existing local reveal loop anchored to that timestamp. Late join /
  reconnect = recompute the index from the clock.
- Buzz: client sends `{buzz, myWordIdx}`. DO takes first arrival, clamps
  the claimed index against its own clock (anti-cheat), broadcasts "X
  buzzed at word N, clock paused", locks others out. Standard rules:
  wrong answer → that player locked for the question, reading resumes;
  all buzzers exhausted or time up → dead.
- First-arrival arbitration slightly favors low ping — same as qbreader,
  fine at friends scale.
- Caveat: clients hold the full doc from question start, so devtools can
  read ahead. Hardening = DO streams sentence-by-sentence. Skip for v1.

## Client work (largest chunk)

`lib/js/reader.js` is a single-player state machine (`phase` driven by
local events). Room mode = same phases driven by DO messages. Rendering
(`renderQText`, sentence splitting, score-clue pacing, judge panel) is
reusable. New UI: create/join with room code, player list + live
scoreboard, "X buzzed" state, host controls (skip/pause/filters), maybe
chat. Each player's own results still append to the normal attempts log,
so personal stats + sync keep working.

## Work breakdown

1. **Protocol doc first** — message types + state diagram; pins down both
   the DO and the client refactor.
2. **Room DO + lobby routes** — game-logic core, ~500-800 lines incl.
   buzz/lockout/scoring rules; R2 binding + `wrangler.toml` DO migration.
3. **Client room mode** — state machine refactor + room UI.
4. **Edge cases** — reconnects, host disconnect/migration, mid-question
   joins, clock resume after wrong buzzes. This is where the time goes;
   qbreader's multiplayer (open source) is the reference for the rules
   matrix.

Cost: effectively $0 at friends scale (free-plan DOs + hibernation);
$5/mo Workers Paid is the escape hatch.
