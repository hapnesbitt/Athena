#!/usr/bin/env python3
"""
scribe.py — the ATHENA collaborative-writing engine ("clb").

A writers' room of AI character-agents takes turns writing their OWN lines for ONE
scene — each committing to git AS THEMSELVES, in a contained run you can watch with
`tail -f clb_run.log`.

  - One shared Ollama model, re-prompted per character (each character = a persona).
  - The MUSE / EMCEE opens the house first (Turn 0): a generated, Cabaret-style card
    that welcomes the audience and sets up the number. It IS the visible top of the
    scene; the old production memo is now a HIDDEN brief the agents read.
  - Fixed turn order per scene IS the dramatic arc.
  - Every turn: read scene-so-far -> prompt the active character -> append their
    lines -> commit as that character -> log it.

Two scenes ship today, selected on the command line (defaults to Book V):

    python3 scribe.py        # Book V — Calypso's Island (the two-hander, the RELEASE)
    python3 scribe.py 5      #   "  (same as above)
    python3 scribe.py 10     # Book X — Circe's Hall (ensemble spectacle, power-flip, rescue)

Watch: tail -f clb_run.log   (in another terminal)

Tweak the CONFIG block below; personas, books, and song scaffolds are the sole
source of truth in athena.yaml, loaded fresh every run. Requires PyYAML.
"""

import json
import os
import re
import subprocess
import sys
import textwrap
import time
import urllib.request
from datetime import datetime

import yaml


# ============================== CONFIG (Ross's knobs) ==========================
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")  # set OLLAMA_URL to your inference host
MODEL      = "mistral:7b"                    # `ollama list` to see options; swap freely
TEMPERATURE = 0.9                            # higher = wilder; lower = tighter
MAX_TURNS  = int(os.environ.get("MAX_TURNS", "12"))   # hard safety cap; env-overridable for smoke tests
REQUEST_TIMEOUT = 300                        # seconds to wait on the model per turn

# Editor pass: a second model call that re-drafts the strongest beats (tighter,
# more on-voice). Only fires on the beat_types in EDITOR_TURNS, at a cooler temp.
EDITOR_PASS  = os.environ.get("EDITOR_PASS", "True").lower() not in ("false", "0", "no")
EDITOR_TURNS = {"song", "flip", "demand"}
EDITOR_TEMP  = 0.7
EDITOR_SYSTEM = (
    "You are a script editor for a hip-hop dinner-theater piece. "
    "You receive a draft and return only an improved version — tighter, "
    "more on-voice, better rhythm. No commentary."
)

HERE       = os.path.dirname(os.path.abspath(__file__))
LOG_PATH   = os.path.join(HERE, "clb_run.log")
VOICE_BIBLE_PATH = os.path.join(HERE, "voice_bible.md")
# ^ Excerpted from the Athena repo README. Point this at the full repo
#   README if you want the agents to chew on all of Books I–IV.

YAML_PATH = os.path.join(HERE, "athena.yaml")   # personas/books/scaffolds, reloaded per run

# Per-persona model overrides, filled by load_config() from each persona's optional
# `model:` field in athena.yaml. Empty unless a persona sets one; falls back to MODEL.
PERSONA_MODELS = {}

# SCENE_PATH is set per-run from the selected book (see run()).
SCENE_PATH = None


# Per-book staging clause spliced into the per-turn prompt rules. Book V forbids
# stage directions (Narrator only); Book X invites [STAGING: ...] lines from everyone.
NO_STAGING_CLAUSE = "Do NOT write stage directions unless you are the NARRATOR."
STAGING_CLAUSE = (
    "When the action calls for it — the audience-pull, a transformation, the rescue — "
    "you MAY include one or more clearly marked staging directions, each on its own "
    "line and prefixed EXACTLY like [STAGING: dancers bring three men up from the "
    "tables as the crew]. Use them for what the BODIES do on the floor; keep your "
    "spoken/sung lines separate."
)


# ============================== ENGINE =======================================

def log(msg=""):
    """Print to stdout AND append to the logfile (so `tail -f` sees everything)."""
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def banner(text):
    line = "=" * 70
    log("\n" + line)
    log(text)
    log(line)


def read_voice_bible():
    try:
        with open(VOICE_BIBLE_PATH, "r", encoding="utf-8") as f:
            return f.read().strip()
    except FileNotFoundError:
        return "(voice bible not found — agents fly blind)"


def build_user_prompt(book, character, beat, voice_bible, scene_so_far,
                      want="", forbidden="", beat_type=""):
    """Assemble the per-turn prompt: scene context + voice bible + scene-so-far + beat.

    want/forbidden/beat_type are optional (Book V passes none → identical prompt).
    """
    prompt = textwrap.dedent(f"""\
        You are writing ONE contribution to a collaborative scene: ATHENA, {book['scene_id']}.
        This is a hip-hop-inflected retelling of the Odyssey.

        ── THE SCENE ──────────────────────────────────────────────
        {book['scene_context']}

        ── VOICE BIBLE (study the CADENCE and TONE only — never copy its words) ──
        {voice_bible}

        The voice bible is a STYLE REFERENCE ONLY. Any lyrics or lines in it are
        examples of the FEEL to emulate, NOT material to reuse. Write entirely
        original words. Never repeat a phrase, line, or rhyme from the voice bible.

        ── THE SCENE SO FAR ───────────────────────────────────────
        {scene_so_far}

        ── YOUR TASK THIS TURN ({character}) ──────────────────────
        {beat}

        Write ONLY {character}'s next lines — this single beat, in voice. Do NOT write
        any other character's lines. {book['staging_clause']} Do NOT preface, explain,
        or restate the instructions. No "Sure" or "Here is". Just the lines themselves.""")

    if want:
        prompt += f"\nWhat you WANT this turn: {want}"
    if forbidden:
        prompt += f"\nDo NOT use or echo: {forbidden}"
    if beat_type == "song":
        scaffold_key = book.get("song_scaffold_key", character)
        if scaffold_key in SONG_SCAFFOLDS:
            prompt += "\n\n" + SONG_SCAFFOLDS[scaffold_key]
        prompt += (
            "\nWrite 100% ORIGINAL lyrics. Do not reuse any line, phrase, or rhyme from the\n"
            "voice bible or from any earlier turn in this scene. The contrafact should\n"
            "echo the SONG'S rhythm and spirit, never its actual words, and never the\n"
            "voice bible's words."
        )

    prompt += "\n        Keep it to roughly 4–12 lines (the song may run longer).\n"
    return prompt


def build_editor_prompt(character, beat, draft, want, voice_bible):
    return textwrap.dedent(f"""\
        You are a script editor for ATHENA, a hip-hop Odyssey dinner-theater piece.
        A character-agent just wrote a draft for one beat. Your job: identify what's
        weak and rewrite it — sharper, more on-voice, truer to the character's want.

        ── VOICE BIBLE ────────────────────────────────────────────
        {voice_bible}

        ── THE BEAT (what this turn was supposed to accomplish) ────
        {beat}

        ── WHAT {character} WANTS THIS TURN ───────────────────────
        {want}

        ── THE DRAFT ──────────────────────────────────────────────
        {draft}

        ── YOUR TASK ───────────────────────────────────────────────
        Rewrite this as {character}. Fix: flat rhymes, off-voice lines, missed staging
        marks, any echoes of Book V (Calypso partnership beats). Keep what works.
        Return ONLY the improved lines — no commentary, no "Here is", no headers.
        If the draft is already strong, return it unchanged.
    """)


def build_muse_prompt(book, voice_bible):
    """Assemble the MUSE's Turn 0 prompt: open the house and read the card for THIS book."""
    staging_note = (
        "no stage directions" if book["staging_clause"] is NO_STAGING_CLAUSE
        else "only the staging line invited above, if you use it"
    )
    extra = ("\n\n        " + book["muse_extra"]) if book["muse_extra"] else ""
    return textwrap.dedent(f"""\
        You are opening tonight's chapter of ATHENA — an immersive dinner-theater
        retelling of the Odyssey, performed for a room of wealthy diners who are part
        of the show. You are the MUSE / EMCEE: you host the house. Right now you walk
        out FIRST, before any performer, and read your card — welcome the room and set
        up tonight's number, then hand off.

        ── THE BOOK YOU'RE INTRODUCING (your brief — the audience never sees this) ──
        {book['brief']}

        ── VOICE BIBLE (study the CADENCE and TONE only — never copy its words) ──
        {voice_bible}

        The voice bible is a STYLE REFERENCE ONLY. Any lyrics or lines in it are
        examples of the FEEL to emulate, NOT material to reuse. Write entirely
        original words. Never repeat a phrase, line, or rhyme from the voice bible.

        ── YOUR TASK RIGHT NOW (THE MUSE) ─────────────────────────
        Welcome the audience to THIS book and set up the number that follows: {book['muse_setup']}
        Speak DIRECTLY to the room (fourth wall) — you are not in the story, you present
        it. Work the house, frame the stakes, make them lean in, let the knowing edge
        show beneath the charm, then hand off to the performers. Keep it punchy and
        performable — roughly 8–16 lines, an MC's card read before a number.{extra}

        Write ONLY the Muse's spoken card. No headers, no speaker label, {staging_note},
        no "Here is" — just the words you say to the room.
    """)


def call_ollama(system_prompt, user_prompt, temp_override=None, model=None):
    """Call the shared model on the M1 via Ollama's /api/chat. Pure stdlib.

    `model` lets a persona override the global MODEL for its own turns; falls back
    to MODEL when None (the case for everyone until a persona sets `model:`).
    """
    temp = temp_override if temp_override is not None else TEMPERATURE
    payload = {
        "model": model or MODEL,
        "stream": False,
        "options": {"temperature": temp},
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    }
    req = urllib.request.Request(
        f"{OLLAMA_URL}/api/chat",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["message"]["content"].strip()


def clean_output(text, label):
    """Trim common model tics: a leading 'CALYPSO:' label, wrapping quotes, headers."""
    text = text.strip()
    # Drop a leading "NAME:" / "NAME —" if the model restated the speaker.
    text = re.sub(rf"^\s*{re.escape(label)}\s*[:\-—]\s*", "", text, flags=re.IGNORECASE)
    # Drop leading markdown header hashes if any slipped in.
    text = re.sub(r"^\s*#+\s*", "", text)
    # Strip a single layer of wrapping quotes around the whole block.
    if len(text) >= 2 and text[0] in "\"'" and text[-1] == text[0]:
        text = text[1:-1].strip()
    return text.strip()


def git(*args, check=True):
    return subprocess.run(["git", "-C", HERE, *args],
                          capture_output=True, text=True, check=check)


def ensure_repo():
    if not os.path.isdir(os.path.join(HERE, ".git")):
        git("init")
        git("config", "user.name", "Athena clb scribe")
        git("config", "user.email", "scribe@athena")
        log("• git repo initialized")


def commit_as(character_label, email, message):
    """Stage the scene file and commit it AUTHORED by the character."""
    git("add", os.path.basename(SCENE_PATH))
    author = f"{character_label} <{email}>"
    result = git("commit", "--author", author, "-m", message, check=False)
    if result.returncode != 0:
        log(f"  ! git commit issue:\n{result.stdout}\n{result.stderr}")
    return author


def append_to_scene(turn_no, persona, lines):
    block = f"\n### Turn {turn_no} — {persona['label']} {persona['emoji']}\n\n{lines}\n"
    with open(SCENE_PATH, "a", encoding="utf-8") as f:
        f.write(block)


def run_muse_turn(book, voice_bible):
    """TURN 0: the MUSE/EMCEE reads the opening card that OPENS the performed scene."""
    persona = PERSONAS["MUSE"]
    banner(f"=== Turn 0: {persona['label']} {persona['emoji']} — the Muse opens the house ===")

    user_prompt = build_muse_prompt(book, voice_bible)

    t0 = time.time()
    try:
        raw = call_ollama(persona["system"], user_prompt, model=PERSONA_MODELS.get("MUSE"))
    except Exception as e:  # noqa: BLE001 — keep the run observable, fail soft
        log(f"  !! Ollama call failed: {e}")
        log("  !! Is the M1 reachable? Check OLLAMA_URL / that the model is pulled.")
        sys.exit(1)
    dt = time.time() - t0

    card = clean_output(raw, persona["label"])
    log(f"  (generated in {dt:.1f}s)\n")
    for line in card.splitlines():
        log(f"  | {line}")
    log("")

    # The Muse's card is the audience-facing opening: no turn number, then a rule.
    block = f"### {persona['label']} {persona['emoji']}\n\n{card}\n\n---\n"
    with open(SCENE_PATH, "a", encoding="utf-8") as f:
        f.write(block)

    author = commit_as(persona.get("author", persona["label"]), persona["email"],
                       f"{book['commit_prefix']}: the Muse opens the house")
    log(f"  ✎ committed as {author}")


def run(book):
    global SCENE_PATH
    SCENE_PATH = os.path.join(HERE, book["scene_file"])

    # Fresh log each run.
    open(LOG_PATH, "w", encoding="utf-8").close()

    turns = book["turn_order"][:MAX_TURNS]

    banner(book["banner"])
    log(f"   model        : {MODEL} @ {OLLAMA_URL}")
    log(f"   turns        : the Muse (Turn 0) + {len(turns)} dialogue turns")
    log(f"   scene file   : {SCENE_PATH}")
    log(f"   started      : {datetime.now():%Y-%m-%d %H:%M:%S}")

    ensure_repo()

    voice_bible = read_voice_bible()

    # 1. Initialize the performed file with a SLIM TITLE only — the dry production
    #    memo now lives in the book's hidden brief and is NOT the visible top.
    with open(SCENE_PATH, "w", encoding="utf-8") as f:
        f.write(book["title_md"])
    log(f"\n• {book['scene_file']} initialized with the slim title (memo hidden in the brief)\n")

    # 2. TURN 0 — THE MUSE opens the house. Its generated card is the real opening
    #    of the scene. It reads the book's brief + voice_bible and commits as The Muse.
    run_muse_turn(book, voice_bible)

    # 3. Run the dialogue turns.
    for i, turn in enumerate(turns, start=1):
        # Turns are 2-tuples (Book V) or 5-tuples (Book X): unpack safely.
        character, beat = turn[0], turn[1]
        beat_type = turn[2] if len(turn) > 2 else "dialogue"
        want      = turn[3] if len(turn) > 3 else ""
        forbidden = turn[4] if len(turn) > 4 else ""

        persona = PERSONAS[character]
        banner(f"=== Turn {i}/{len(turns)}: {persona['label']} {persona['emoji']} ===")

        with open(SCENE_PATH, "r", encoding="utf-8") as f:
            scene_so_far = f.read()

        user_prompt = build_user_prompt(book, character, beat, voice_bible, scene_so_far,
                                        want=want, forbidden=forbidden, beat_type=beat_type)

        t0 = time.time()
        try:
            raw = call_ollama(persona["system"], user_prompt, model=PERSONA_MODELS.get(character))
        except Exception as e:  # noqa: BLE001 — keep the run observable, fail soft
            log(f"  !! Ollama call failed: {e}")
            log("  !! Is the M1 reachable? Check OLLAMA_URL / that the model is pulled.")
            sys.exit(1)
        dt = time.time() - t0

        lines = clean_output(raw, persona["label"])
        log(f"  (generated in {dt:.1f}s)\n")
        for line in lines.splitlines():
            log(f"  | {line}")
        log("")

        # Editor pass: re-draft the strongest beats at a cooler temp (Book X only,
        # via beat_type; Book V's "dialogue" beats never qualify).
        if EDITOR_PASS and beat_type in EDITOR_TURNS:
            log("  → editor pass...")
            editor_prompt = build_editor_prompt(character, beat, lines, want, voice_bible)
            t1 = time.time()
            try:
                raw2 = call_ollama(EDITOR_SYSTEM, editor_prompt, temp_override=EDITOR_TEMP)
            except Exception as e:  # noqa: BLE001 — fail soft; keep the draft if editor errors
                log(f"  !! editor pass failed, keeping draft: {e}")
            else:
                dt2 = time.time() - t1
                lines = clean_output(raw2, character)
                log(f"  (editor pass in {dt2:.1f}s)\n")
                for line in lines.splitlines():
                    log(f"  | {line}")
                log("")

        append_to_scene(i, persona, lines)
        author = commit_as(persona["label"], persona["email"],
                           f"{book['commit_prefix']}: {persona['label']}'s turn {i}")
        log(f"  ✎ committed as {author}")

    # 4. Done.
    banner(f"✅  scene complete — the Muse + {len(turns)} turns")
    log(f"   scene  : {SCENE_PATH}")
    log(f"   log    : {LOG_PATH}")
    log("   git log:")
    out = git("log", "--pretty=format:     %an — %s").stdout
    for line in out.splitlines():
        log(line)
    log("")


def load_config(path=None):
    """Load personas, books, and scaffolds from athena.yaml.

    Returns (personas, books, scaffolds, persona_models), structurally identical to
    the hardcoded reference dicts:
      - a persona's optional `model:` is split into persona_models (empty unless set)
        so the persona dict itself matches the hardcoded shape exactly;
      - `author` is included only when present (the Muse);
      - each book's `staging_clause` key maps back to the SAME constant object
        (NO_STAGING_CLAUSE / STAGING_CLAUSE) so identity checks still hold;
      - `turn_order` lists become tuples; absent keys (e.g. song_scaffold_key on
        Books V/X) stay absent.
    """
    with open(path or YAML_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)

    personas, persona_models = {}, {}
    for name, p in data["personas"].items():
        entry = {"label": p["label"], "emoji": p["emoji"], "email": p["email"]}
        if p.get("author"):
            entry["author"] = p["author"]
        entry["system"] = p["system"]
        personas[name] = entry
        if p.get("model"):
            persona_models[name] = p["model"]

    scaffolds = dict(data["scaffolds"])

    clause_for = {"NO_STAGING": NO_STAGING_CLAUSE, "STAGING": STAGING_CLAUSE}
    books = {}
    for bid, b in data["books"].items():
        book = {}
        for k, v in b.items():
            if k == "staging_clause":
                book[k] = clause_for[v]
            elif k == "turn_order":
                book[k] = [tuple(t) for t in v]
            else:
                book[k] = v
        books[bid] = book

    return personas, books, scaffolds, persona_models


# Load config once at import so PERSONAS / BOOKS / SONG_SCAFFOLDS / PERSONA_MODELS
# exist for importers (assemble.py, polish.py) and the engine. athena.yaml is the
# sole source of truth; main() reloads it per run so live edits take effect.
PERSONAS, BOOKS, SONG_SCAFFOLDS, PERSONA_MODELS = load_config()


def main():
    book_id = sys.argv[1] if len(sys.argv) > 1 else "5"
    # Reload config from athena.yaml every run so live YAML edits take effect.
    global PERSONAS, BOOKS, SONG_SCAFFOLDS, PERSONA_MODELS
    PERSONAS, BOOKS, SONG_SCAFFOLDS, PERSONA_MODELS = load_config()
    if book_id not in BOOKS:
        sys.stderr.write(
            f"unknown book '{book_id}'. choose one of: {', '.join(BOOKS)}\n"
            f"usage: python3 scribe.py [{ '|'.join(BOOKS) }]   (default 5)\n"
        )
        sys.exit(2)
    run(BOOKS[book_id])


if __name__ == "__main__":
    main()
