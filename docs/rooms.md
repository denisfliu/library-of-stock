# Online rooms — design notes (July 2026)

Status: **promoted into qb-scorekeeper v1** (July 18, 2026 — see
`docs/scorekeeper.md`, which supersedes this doc's framing but keeps its
architecture verbatim: DO-per-room on the existing Worker, clock protocol,
server-side checker). Kept as the detailed reference for the room-server
internals.

**Reader rooms v1 BUILT (Nov 2026)** — the reader's Multiplayer pill. It
reuses the qb-scorekeeper room server rather than building the DO below:
the relay is payload-blind, so the reader is its third consumer (after
qb-scorekeeper and consensus-scorekeeper). Like scorekeeper v1 it is
host-authoritative: the hosting reader picks questions from its own queue,
runs the checker, keeps scores and broadcasts snapshots; every client
renders from snapshots and derives the reveal from `{t0, u0, wpm}` on a
synced server clock (the clock protocol below, as designed). The host also
plays: it holds a player socket and buzzes through the same arbitration.
The one server change was additive — a buzz may carry the buzzer's
reveal-unit position `u`, relayed on `buzz_pending`/`buzz` so a power is
credited where the buzzer saw the text (the host clamps it to a window
behind its own clock). Client: `lib/js/reader_room.js` + the "multiplayer
rooms" block of `lib/js/reader.js`; tests `tests/reader_rooms/`. Still
open from this doc: server-authoritative grading / host migration (closing
the host tab ends the room) and sentence-streamed text (anti-cheat).

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

## Responsiveness + buzz flow (Nov 5, 2026)

Measured against the live room server in a two-browser Playwright run;
the simulated-server harness (`tests/reader_rooms/`) pins each down.

- **Start of a question**: the host used to wait a fixed 1.2 s
  (`ROOM_LEAD_MS`) so guests could fetch the shard, then started the
  reveal a fixed 300 ms ahead. Now each guest, once it has prefetched the
  snapshot's `next` question, tells the host
  (`{t:'request', data:{op:'preloaded', id, rtt}}`), so a Next press
  starts reading at once; a question nobody preloaded waits for
  `op:'ready'` acks instead, with 1.2 s as the cap (`roomHostMaybeStart`).
  The reveal's t0 lead is sized from the clock-sync round trips the
  players report: host one-way + slowest player one-way + 60 ms
  (`roomStartLead`, 300 ms cap when a latency is unknown). Live server,
  two browsers: Next/skip → first word 1.75 s → ~0.33 s (first question
  of a session ~0.7 s: nothing preloaded yet). What's left is the press
  reaching the host and the snapshot coming back (two relay hops), the
  jitter allowance, and the first word's own duration (same as solo).
- **Word timing**: the reveal followed a 50 ms polling frame, so each
  word showed up to 50 ms late by a varying amount (stutter next to solo
  play's exact per-word timer). `roomArmStep` now also wakes exactly
  when the next unit is due on the room clock.
- **Answer → verdict** is two relay hops (buzzer → host → everyone),
  inherent to host-authoritative grading; ~0.25 s at 60 ms one-way.
- **Buzz list**: the buzz lines stay under the question until the next
  one (judged lines included), so nothing jumps when a buzz is judged.
- **Time-out** judges what the buzzer had typed (their live typing
  text; a flush just before the deadline), as qbreader does, not a blank.
- **Skip** is disabled while someone is answering (button, guest
  request, and host-side guard).
