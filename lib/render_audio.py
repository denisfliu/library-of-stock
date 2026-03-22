"""
render_audio.py — Convert ABC notation from score_clues to MP3 audio files.

For each score_clue with an `abc` field in any analysis JSON, generates:
    output/audio/{topic_key}/{index}.mp3

Writes the resolved `mp3` path back into each score_clue so render_cards.py
and anki_export.js can reference the file without recomputing paths.

Requires (pip):
    music21    — ABC → MIDI conversion (pip install music21)

Requires (system, broadly available):
    fluidsynth — MIDI → WAV  (apt/dnf/brew install fluidsynth)
    ffmpeg     — WAV → MP3   (apt/dnf/brew install ffmpeg)

A General MIDI soundfont is also needed for fluidsynth. Common locations
are checked automatically; install one if missing:
    Linux:  sudo apt install fluid-soundfont-gm
            sudo dnf install fluid-soundfont-gm
    macOS:  brew install fluid-synth  (bundles a soundfont)

Usage:
    python lib/render_audio.py           # incremental
    python lib/render_audio.py --force   # re-render everything
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

OUTPUT_DIR = Path("output")
AUDIO_DIR = OUTPUT_DIR / "audio"

# Common soundfont search paths across distros / macOS
_SOUNDFONT_CANDIDATES = [
    Path("/usr/share/soundfonts/FluidR3_GM.sf2"),
    Path("/usr/share/soundfonts/default.sf2"),
    Path("/usr/share/sounds/sf2/FluidR3_GM.sf2"),
    Path("/usr/share/sounds/sf2/default.sf2"),
    Path("/usr/local/share/fluidsynth/generaluser.sf2"),
    Path("/opt/homebrew/share/fluidsynth/generaluser.sf2"),
]


def _find_soundfont() -> Path | None:
    for p in _SOUNDFONT_CANDIDATES:
        if p.exists():
            return p
    return None


def _abc_to_midi(abc_text: str, midi_path: Path) -> bool:
    """Convert ABC notation to MIDI using music21. Returns True on success.

    Honors the %%MIDI program N directive that music21's ABC parser ignores,
    by extracting the program number and applying it as a music21 instrument.
    """
    import re
    try:
        from music21 import converter, instrument
    except ImportError:
        print("    music21 not installed — run: pip install music21")
        return False
    try:
        score = converter.parse(abc_text, format="abc")

        # Apply %%MIDI program directive (ignored by music21's ABC reader)
        m = re.search(r'%%MIDI program (\d+)', abc_text)
        if m:
            program = int(m.group(1))
            inst = instrument.Instrument()
            inst.midiProgram = program
            for part in score.parts:
                # Remove any existing instrument at offset 0 before inserting
                for existing in part.getElementsByClass(instrument.Instrument):
                    part.remove(existing)
                part.insert(0, inst)

        score.write("midi", fp=str(midi_path))
        return midi_path.exists()
    except Exception as e:
        print(f"    music21 parse error: {e}")
        return False


def abc_to_mp3(abc_text: str, output_path: Path, soundfont: Path) -> bool:
    """Convert an ABC notation string to MP3. Returns True on success."""
    with tempfile.TemporaryDirectory() as _tmpdir:
        tmpdir = Path(_tmpdir)
        midi_file = tmpdir / "score.mid"
        wav_file = tmpdir / "score.wav"

        # Step 1: ABC → MIDI (pure Python via music21)
        if not _abc_to_midi(abc_text, midi_file):
            return False

        # Step 2: MIDI → WAV
        r = subprocess.run([
            "fluidsynth", "-ni", str(soundfont),
            str(midi_file), "-F", str(wav_file), "-r", "44100",
        ], capture_output=True, text=True)
        if r.returncode != 0 or not wav_file.exists():
            msg = (r.stderr or r.stdout).strip().splitlines()
            print(f"    fluidsynth: {msg[-1] if msg else 'unknown error'}")
            return False

        # Step 3: WAV → MP3
        output_path.parent.mkdir(parents=True, exist_ok=True)
        r = subprocess.run([
            "ffmpeg", "-i", str(wav_file),
            "-codec:a", "libmp3lame", "-qscale:a", "4",
            "-y", str(output_path),
        ], capture_output=True, text=True)
        if r.returncode != 0:
            msg = r.stderr.strip().splitlines()
            print(f"    ffmpeg: {msg[-1] if msg else 'unknown error'}")
            return False

        return True


def build_all(force: bool = False) -> None:
    soundfont = _find_soundfont()
    if not soundfont:
        print("ERROR: No GM soundfont found. Install fluid-soundfont-gm (apt/dnf) or fluidsynth (brew).")
        return

    count = 0
    skipped = 0
    errors = 0

    for analysis_file in sorted(OUTPUT_DIR.glob("*_analysis.json")):
        topic_key = analysis_file.stem.replace("_analysis", "")

        with open(analysis_file) as f:
            analysis = json.load(f)

        score_clues = analysis.get("score_clues", [])
        if not score_clues:
            continue

        topic_name = analysis.get("topic", topic_key)
        changed = False

        for i, clue in enumerate(score_clues):
            abc = clue.get("abc")
            if not abc:
                continue

            mp3_rel = f"audio/{topic_key}/{i}.mp3"
            mp3_path = OUTPUT_DIR / mp3_rel

            # Incremental: skip if MP3 is newer than the analysis JSON
            if not force and mp3_path.exists():
                if mp3_path.stat().st_mtime >= analysis_file.stat().st_mtime:
                    skipped += 1
                    # Ensure mp3 path is written even if we skip conversion
                    if clue.get("mp3") != mp3_rel:
                        clue["mp3"] = mp3_rel
                        changed = True
                    continue

            work = clue.get("work", "?")
            print(f"  {topic_name} / {work}")
            if abc_to_mp3(abc, mp3_path, soundfont):
                clue["mp3"] = mp3_rel
                changed = True
                count += 1
            else:
                errors += 1

        if changed:
            with open(analysis_file, "w") as f:
                json.dump(analysis, f, indent=2, ensure_ascii=False)

    parts = [f"Built {count} audio clips"]
    if skipped:
        parts.append(f"{skipped} up-to-date")
    if errors:
        parts.append(f"{errors} errors")
    print(", ".join(parts))


if __name__ == "__main__":
    force = "--force" in sys.argv
    build_all(force=force)
