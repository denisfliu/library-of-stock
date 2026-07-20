# qb-moderator — design plan (July 2026)

Status: **v0 BUILT July 18, 2026** — `github.com/qbsuite/qb-moderator`
(public, CI, app live at https://qbsuite.github.io/qb-moderator/app/).
Build-order steps 1–2 are done: SPEC.md (engine events, scoring rule
table, room protocol sketch), the pure event-sourced engine (22 test
vectors incl. host point-pad verdict overrides — Denis July 18: in
voice/manual mode the host assigns points via +15/+10/−5/+20-if-enabled
pad; implemented as `verdict{points}` override so the pad drives flow,
not just totals), and the solo host console (R2 set/packet browsing,
qb-audio read-aloud with the **first sidecar-based audio-clock→position
mapper** — reader should adopt it later, checker-assisted adjudication,
bonus cycle, scoreboard/history). **v0.5 July 19**: three reading modes
(TTS audio with text+answer hidden until done so the host can play /
reader-contract word-by-word reveal with wpm + slow note-run pacing /
full-text moderator read; audio falls back to reveal, never full text),
teams in the engine (team-wide lockouts, teamScores, 25 vectors), roster
bar with add/rename teams + pointer-drag players + per-player
+15/+10/−5/0 boxes (buzz+verdict in one tap during reading, plain score
adjustment otherwise), bonus on/off toggle. **v0.6 July 19 (Denis's
no-two-copies + UX pass)**: `reveal_units.js` is now THE canonical
classic-script copy in qb-moderator — `lib/js/reader.js` dropped its
inline splitter and loads the shared file (script tag in
build_reader.py; `build.py sync_vendored_js()` copies from the sibling
checkout so local builds can't drift; all reader node suites + golden
green). Setup homepage removed — set/packet picker + settings are
collapsible panels on the one game screen, live-changeable mid-game
(engine `configure` event; scores carry across packets); player rows
one-line (name+score+pad); drag also reorders within teams (positional
`player_move`). **v0.7 July 19 — layout settled via mockup iteration
with Denis** (4 rounds, SendUserFile render): full-width question text
(no boxes/panels), top bar = set sheet + reading-mode select + bulk
roster editor (👥, teams as blocks w/ one-name-per-line textareas) + ⚙;
consensus-scorekeeper-style team panels underneath (big team totals,
player rows name·score·pad); **chronological history sidebar** on the
right grouped by tossup (engine logs `dead` now); **click-the-buzzed-
word** in full-text mode (exact positions with no clock — MODAQ-
inspired); bonus leadin/parts at full question type size, parts
revealed one at a time as scored, tossup stays on screen; no
instruction strings. **v0.8 July 19 — ROOMS v1 SHIPPED**: phones as
buzzers. `rooms/` = self-hostable Cloudflare Worker (SQLite DO per
room, WebSocket Hibernation, free plan), default instance
`qb-rooms.denisliu10.workers.dev`. Deliberate v1 simplification of the
rooms.md design (documented in the repo SPEC.md): **host-authoritative
relay** — engine stays in the host app; the DO does atomic first-buzz
arbitration + fan-out + late-join snapshots only. `app/player.html` =
join-by-code full-screen buzz button + live scoreboard + vibration.
Host: 🌐 Room button (creates code; click again copies the player
link); remote buzz pauses reading and preselects the buzzer at the
host's clock position; player joins auto-enter the roster; locked-out
buzzes re-arm. Live protocol test `tests/rooms.e2e.mjs` (8 checks).
**v0.9 July 19**: players get a browsable Past Questions list
(host broadcasts a completed-question log — text/answer/result — DO
stores it for late joiners); quick +player/+team buttons top-right of
the scoring section; room mode marks host-added players not connected
via the code with a ○. Rooms cost note (Denis asked): all Cloudflare
free plan — Workers free tier + SQLite DOs + WebSocket Hibernation;
$0 at any realistic scale. **v0.9.1**: room lifecycle — POST /rooms
claims a fresh DO (collision → re-roll; ~923k codes) and a DO alarm
self-destructs every room 12h after last activity (sockets closed,
storage wiped) so codes recycle with no stale state; host mobile CSS
pass (compact header, fitted point buttons, bottom-sheet dialogs).
**v0.10**: upload-your-own-packets (.docx/.txt, each file = one
packet, synthetic `up-*` qids, no TTS audio → auto-fallback);
reading-mode select on its own set-sheet row. **v0.10.2 July 19**: in
TTS-audio mode the set picker lists only sets whose tossups ALL have
audio (client-side pass over catalog tossup ids × audio_index qids;
mode change re-renders the list; index fetch failure disables the
filter and the per-question reveal fallback still covers gaps).
**v0.10.1**: parsing is
fully CLIENT-SIDE — Denis rejected the hosted-YAPP dependency; the
vendored `app/vendor/qb_packet_parser.mjs` (qbreader's JS packet
parser v1.2.2, ISC, ~2 MB lazy-loaded, mammoth bundled) parses in the
browser, auto-detecting the hasQuestionNumbers×hasCategoryTags combo
by keeping the parse that finds the most questions; output is the
native qbreader doc shape incl. auto-classified categories. Remaining build order: voice mode → local STT;
server-authoritative grading + remote text reveal stay the v2 room
path. **July 19: consensus-scorekeeper became a second consumer of the
shared qb-rooms instance** (vendors `app/room.js` byte-identical with a
drift test, own snapshot/qlog payload shapes, spectator links via a
`~watch` name sentinel; worker unchanged — the relay never inspects
payloads, so both apps share one deployment; protocol freeze noted in
qb-moderator SPEC.md). Same day, for remote US-wide consensus play:
**latency-equalized buzz arbitration** in the DO (ping/pong RTT
sampling, buzzes compete within an RTT-sized window on estimated press
time = arrival − RTT/2, caps 100/200ms bound lag-faking and announce
delay; 0-window/0-comp fallback keeps old clients and LAN rooms on
plain first-arrival), plus player-page pass: buzz on pointerdown with
a press/release toggle, Space-bar buzzing on desktop, screen wake
lock.

This doc supersedes the "living-room, hotkeys-first" sketch in
`docs/suite.md` and **promotes the tabled rooms design**
(`docs/rooms.md`) into moderator v1 — Denis decided July 18 that buzz
mode 1 *is* a temporary self-hosted room with phones as buzzers.

## The two buzz modes (Denis, July 18)

1. **Room mode** — someone sets up a *temporary, self-hosted* room; people
   join on their phones and buzz via a button. Mobile-friendliness is a
   hard requirement. Players can also help operate the room and browse
   past questions. Most of the infrastructure is shared with the reader.
2. **Voice mode** — one device reads aloud and *listens*: it detects the
   sound of a physical buzzer system, pauses, then captures the spoken
   answer. Hosts can optionally download a better local voice processor.

Both modes feed the same engine; they differ only in input adapter and
presentation. Scoring is optional in both, and can be **manned by a
human** instead of (or overriding) the automatic judge.

## Architecture: engine ≠ transport ≠ input (unchanged)

- **Engine** (pure state machine, no I/O): set/packet iteration from the
  mirror data, reading clock, buzz arbitration + lockouts, scoring, bonus
  flow, question log. Runs identically in a browser tab (solo/voice mode)
  and inside the room server. One implementation, driven by events:
  `buzz(player?, position)`, `verdict(correct|wrong|manual)`, `resume`,
  `skip`, `override(...)`.
- **Transport**: local (same tab) or WebSocket room. The client never
  knows which — it sends events and renders state snapshots.
- **Input adapters**: touch button / hotkeys / buzzer-sound detector all
  emit the same `buzz` event.

## Scoring rules (Denis's spec, July 18 — the engine's rule table)

| Event | Points |
|---|---|
| Correct buzz **before the power mark** `(*)` | **15** |
| Correct buzz after the power mark (or unpowered set) | **10** |
| Wrong buzz **while the question is still being read** | **-5** (neg) + lockout |
| Wrong buzz **after reading finished** | **0** + lockout |
| Bonuses (room play, standard) | 10/part, no negs |

- Powers exist only when the text contains a power mark; position comes
  from the reveal clock (room mode: word index; read-aloud: audio clock →
  word via the qb-audio chunk/word sidecars — this is why the sidecars
  are load-bearing).
- A buzz **pauses reading immediately** (decided earlier: the buzz
  timestamp is detection time, not when the answer finishes); wrong →
  lockout, resume from the pause point; all locked out or time up → dead,
  reveal.
- **Scoring is a layer, not a requirement**: rooms can run scoreless
  (buzz order + reveal only). Point values are config with these
  defaults.
- **Human-manned option**: a "moderator judges" toggle. Verdicts come
  from a host tap (correct / wrong / no penalty) instead of the answer
  checker; even with auto-judging on, the host can override any verdict
  and edit any score line after the fact (the reader's self-grade
  override generalizes to this).

## Mode 1: rooms (promotes docs/rooms.md — that design stands)

Everything in rooms.md carries over: one **SQLite-backed Durable Object
per room** on the existing Worker stack (free plan + WebSocket
Hibernation ≈ $0 at friends scale), lobby routes (`POST /rooms` → short
code, `GET /rooms/:code/ws`), server-authoritative grading with the
vendored qbreader checker, the deterministic reveal clock broadcast as
`{doc, startedAt, msPerWord}`, buzz as `{buzz, myWordIdx}` clamped
server-side, guests with ephemeral names + signed-in identity via the
existing HMAC session token.

**"Temporary self-hosted"** means two things, both supported:
- *Temporary*: rooms are ephemeral — in-DO state only, short code,
  garbage-collected after inactivity. No accounts required to join.
- *Self-hosted*: the room server ships in the qb-moderator repo with a
  `wrangler.toml`; anyone can deploy it to their own free Cloudflare
  account and point the client at their URL (same self-hosting stance as
  qb-search). We also run a default instance on `los-sync`. The client
  is server-URL-agnostic.

**In-person vs remote presentation** (same room, host's choice):
- *Remote*: every phone reveals text via the clock — the online-rooms
  picture from rooms.md.
- *In-person (living room / practice)*: the host device reads **aloud**
  (qb-audio TTS through the speaker); player phones show only the buzz
  button + scoreboard. The audio clock maps to text position through the
  sidecars, so powers still adjudicate exactly.

**Roles & operation**: host console (start/pause/skip, filters — reuse
the reader's facet system, adjudication buttons, score editing, transfer
host); players (buzz + answer); spectators. **Past questions**: the DO
keeps the room's question log; any participant can browse it mid-game
(the reader's History tab pattern), and late joiners get it on connect.

**Mobile-friendly buzzing** (the player page is the make-or-break UI):
- PWA with the site's existing `data-layout` mobile system: one giant
  full-screen buzz button, wake lock so the screen never sleeps,
  vibration on buzz-accepted/locked-out, huge latency-honest visual state
  (armed / buzzed / locked out).
- **Volume-button buzzing — honest feasibility note**: mobile browsers do
  not deliver hardware volume-key events to pages, so pure-web
  volume-buzz is not reliably possible. Paths if we want physical
  buttons: (a) cheap Bluetooth camera-shutter clickers paired as HID
  keyboards — where they emit a mappable key event this works in the
  browser today, and it's the closest thing to handing everyone a $2
  buzzer; (b) a thin TWA/native wrapper later, which CAN capture volume
  keys. Investigate (a) during v1; neither blocks the touch button.

## Mode 2: voice (the listening moderator)

For rooms with a **real buzzer system**: the host device reads aloud,
mic open (`getUserMedia` with `echoCancellation: true` so it doesn't
hear its own TTS output).

1. **Buzzer-sound detection**: a calibration step records the buzzer's
   sound once ("press a buzzer now"); at runtime a WebAudio analyser does
   onset detection + spectral match against the template, debounced.
   Detection timestamp = buzz position (audio clock → word via sidecars).
   Reading pauses instantly. The buzzer system itself arbitrates *who*
   buzzed (its lights) — attribution in the app is a host tap on the
   player name, or skipped entirely in scoreless mode.
2. **Spoken answer → STT**: Web Speech API by default (zero install).
   **Optional "better voice processor" download**: a local Whisper build
   (WASM/WebGPU, model fetched on demand, ~40-150 MB) for hosts who want
   offline/accurate recognition — same progressive-upgrade pattern as the
   reader's voice features.
3. **Verdict**: transcript → the vendored answer checker → engine. Low
   confidence or "prompt" → host adjudicates (the human-manned path is
   the fallback everywhere, so STT failures degrade to a tap).

## Reuse map (from the reader / site)

| Piece | Source | Reuse |
|---|---|---|
| Question data | R2 data plane (`catalog.json`, set shards) | DO + client read it directly |
| Reveal/pacing engine | `reader.js` (deterministic fn of elapsed time) | clock protocol + power position |
| Answer checker | `lib/js/answer_checker.js` (vendored qbreader) | server-side verdicts |
| Audio + sidecars | qb-audio dataset | read-aloud + audio-clock buzz position |
| Facet filters | reader subsubcategory facets | host's question filters |
| History UI | reader History tab | past-questions panel |
| Auth (optional) | sync Worker HMAC session | identity in rooms; guests fine |
| Mobile layout | `theme.MOBILE_MQ` + `lib/js/mobile.js` | player + host pages |

## Build order

1. **Protocol + engine spec** (first artifact in the qb-moderator repo):
   message types, state diagram, the scoring rule table above as data,
   engine test vectors (buzz-at-word × verdict × timing → score deltas).
2. **Engine + solo mode**: engine as a plain JS module driven by hotkeys
   + human adjudication in one browser tab (host reads aloud to the
   room, keeps score). Already useful; proves the engine with zero
   server.
3. **Room mode**: DO + lobby routes, player buzz PWA, host console,
   past-questions log. (rooms.md work breakdown applies; edge cases —
   reconnects, host migration, clock resume — are where the time goes.)
4. **Voice mode**: calibrated buzzer detection → pause → Web Speech →
   checker; host-tap fallback throughout.
5. **Local STT upgrade** download path.

Deferred/parked: streaming text sentence-by-sentence for anti-cheat
(rooms.md caveat), TWA wrapper for volume-key buzzing, per-player voice
attribution.
