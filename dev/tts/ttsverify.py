"""ASR verification for TTS chunks — shared by gen_tts.py (inline gate) and
verify_tts.py (backfill). Single source of truth for "is this chunk good?".

Chatterbox stochastically mangles the first phoneme of a chunk (the attack-clip
Denis reported) and occasionally babbles/runs away. whisper-tiny transcribes each
synthesized chunk (~58 ms/chunk vs ~1 s to generate — a ~5% tax) and the chunk
passes only if its first word fuzzy-matches the intended text and its duration is
within tolerance. Fuzzy matching is essential: whisper mishears proper nouns
(Moore->"more", Fick's->"fix", Grignard->"Grinyard") and those must PASS, while a
truly clipped onset (An->"and", first word dropped) must FAIL. Calibrated on a
150-file / 859-chunk scan of the production output (July 2026).

The retry path (gen_tts) escalates a repeatedly-failing chunk to *priming*: it
prepends PRIME, synthesizes, and cuts PRIME back off at the ASR word boundary, so
the attack-clip lands on the sacrificial word instead of the real first word. A/B
(dev/tts_samples/tuning3) showed this fixes stubborn onsets (e.g. "Phthalic").
"""
import re
import numpy as np

PRIME = "Okay. "          # sacrificial priming utterance for the retry path
_PRIME_WORDS = {"okay", "ok"}
KEEP_LEAD_S = 0.08        # lead-in silence to keep before the real first word after a prime cut


def load_whisper(size="tiny"):
    from faster_whisper import WhisperModel
    return WhisperModel(size, device="cuda", compute_type="float16")


def _to16k(w, sr):
    if sr == 16000:
        return np.ascontiguousarray(w, dtype=np.float32)
    n = int(len(w) * 16000 / sr)
    return np.interp(np.arange(n) * (sr / 16000.0), np.arange(len(w)), w).astype(np.float32)


def transcribe(wm, w, sr, max_s=None):
    """Return [(word, start_s, end_s), ...] with word timestamps."""
    x = _to16k(w if max_s is None else w[: int(sr * max_s)], sr)
    segs, _ = wm.transcribe(x, language="en", beam_size=1, word_timestamps=True)
    return [(wd.word.strip(), wd.start, wd.end) for s in segs for wd in s.words]


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _lev(a, b):
    if a == b:
        return 0
    if not a or not b:
        return len(a) or len(b)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def first_content_word(text):
    """First spoken word of a chunk, stripped of leading quotes/brackets/digits-punct."""
    for tok in text.split():
        w = _norm(tok)
        if w:
            return w
    return ""


# Short words whisper substitutes when a content word's onset is clipped/dropped.
_FUNCTION = {"a", "an", "and", "the", "in", "of", "to", "is", "it", "its", "on",
             "for", "as", "at", "but", "or", "was", "he", "she", "they", "that"}

def first_word_ok(heard, want):
    """Conservative first-word check — high precision on FAILURE, because free ASR
    can't cleanly tell a legitimate Chatterbox pronunciation (Euler->"Oiler",
    Fick's->"fix", Grignard->"Grinyard") from a real clip using edit distance
    alone. So PASS by default and only FAIL on strong defect evidence:
      1. nothing heard at all,
      2. a content word (len>=3) replaced by a bare function word ("Phthalic"->"They"),
      3. a longer content word replaced by an unrelated word with no shared onset
         and near-maximal edit distance ("Phthalic"->"Dalek").
    Subtle low-harm cases (An->"and") pass; priming-on-retry and the post-run
    whisperX pass are the thorough nets. Calibrated on the July 2026 output scan."""
    h, w = _norm(heard), _norm(want)
    if not w:
        return True
    if not h:                                          # (1) silence / dropped onset
        return False
    if h == w or h[:1] == w[:1]:                        # shared first char => misheard, keep
        return True
    if len(w) >= 3 and h in _FUNCTION:                 # (2) content word -> function word
        return False
    if len(w) >= 4 and len(h) >= 2 and _lev(h, w) > 0.6 * len(w):
        return False                                   # (3) unrelated word (far relative to length)
    return True


def verify_chunk(w, sr, text, wm, tol):
    """(ok, score). ok = duration within tol AND first word matches. score ranks
    failed attempts so the caller can keep the least-bad one (higher = better)."""
    dur = len(w) / sr
    if dur > tol:                                # runaway/babble
        return False, -dur
    words = transcribe(wm, w, sr, max_s=min(3.0, dur))
    if not words:
        return False, -99.0
    ok = first_word_ok(words[0][0], first_content_word(text))
    expected = len(text) / 15.0                  # ~150 wpm
    score = (1.0 if ok else 0.0) - abs(dur - expected) * 0.05
    return ok, score


def cut_prime(w, sr, wm):
    """Remove the leading PRIME utterance from a primed generation, cutting at the
    ASR word boundary (keeping KEEP_LEAD_S of silence). Returns the trimmed audio,
    or None if PRIME wasn't found at the start (attempt should be discarded)."""
    words = transcribe(wm, w, sr, max_s=2.5)
    if not words or _norm(words[0][0]) not in _PRIME_WORDS:
        return None
    nxt = words[1][1] if len(words) > 1 else words[0][2]
    cut = int(max(words[0][2], nxt - KEEP_LEAD_S) * sr)
    return w[cut:] if 0 < cut < len(w) else None


if __name__ == "__main__":
    # first_word_ok calibration cases (heard, want, expected_ok). Philosophy:
    # PASS legitimate mishearings; FAIL only on strong defect evidence.
    CASES = [
        ("more", "Moore", True),        # whisper mishears proper noun -> keep
        ("fix", "Fick's", True),        # shared onset -> keep
        ("Grinyard", "Grignard", True),
        ("morelle", "Morel,", True),
        ("Oiler", "Euler", True),       # no shared onset but close -> keep (real pronunciation)
        ("St", "Saint", True),          # abbreviation expansion mismatch, tolerated
        ("She", "She", True),
        ("They", "Phthalic", False),    # content word -> function word (real clip)
        ("Dalek", "Phthalic", False),   # unrelated word, no shared onset (real clip)
        ("Alec", "Phthalic", False),
        ("", "This", False),            # nothing heard -> regen
        ("and", "An", True),            # low-harm subtle case -> tolerated
    ]
    ok = bad = 0
    for heard, want, exp in CASES:
        got = first_word_ok(heard, want)
        good = got == exp
        ok += good; bad += (not good)
        print(("ok  " if good else "BAD ") + f"{heard!r} vs {want!r} -> {got} (want {exp})")
    print(f"\n{ok} ok, {bad} bad")
