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

Tweak the CONFIG block below, then the personas in personas.py, then a book's
SCENE_BRIEF / TURN_ORDER in the BOOKS registry. No pip installs — pure stdlib.
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

from personas import PERSONAS

# ============================== CONFIG (Ross's knobs) ==========================
OLLAMA_URL = "http://192.168.1.185:11434"   # the M1 Mac inference host
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
# ^ Excerpted from /home/www/Athena_repo/README.md. Point this at the full repo
#   README if you want the agents to chew on all of Books I–IV.

# SCENE_PATH is set per-run from the selected book (see run()).
SCENE_PATH = None


# ============================== BOOK V — CALYPSO'S ISLAND =====================
# The turn order IS the dramatic arc. Each entry: (CHARACTER, beat directive).
BOOK5_TURN_ORDER = [
    ("HERMES",   "ARRIVAL. Touch down on Ogygia and deliver Zeus's command plainly: "
                 "Odysseus is to be released, the journey home begins now. Brisk, "
                 "official, a little wry. This is the order that sets the scene moving."),
    ("CALYPSO",  "FIRST RESISTANCE. You just heard the order. Push back — wounded, "
                 "sovereign, possessive. He is your type and your partner; the gods "
                 "are hypocrites to take him. Do NOT sing yet; this is the argument "
                 "before the song."),
    ("ODYSSEUS", "FIRST APPEARANCE. You overhear that you may go home. Be TORN — the "
                 "plunder and appetite that kept you here ten years versus Ithaca "
                 "calling. Don't decide yet. Let the pull show."),
    ("HERMES",   "REINFORCE. Calypso is resisting. Restate that this is Zeus's will, "
                 "not yours — even sea-witches don't out-argue the sky. Dry, final, "
                 "then you're gone."),
    ("CALYPSO",  "*** YOUR SONG — THE 'MY TYPE' NUMBER. *** Break into a full "
                 "verse-and-hook contrafact in the spirit of Saweetie's 'My Type': "
                 "boastful, seductive, wounded. Build the hook around why Odysseus is "
                 "YOUR TYPE — predator meets predator, the city-sacker and the "
                 "sea-witch — and why he should stay. Real rhythm, real rhyme, "
                 "original lyrics. This is the heart of the scene."),
    ("ODYSSEUS", "MOVED, BUT. Her song lands; you feel it. But name the cost — the "
                 "home that calls is louder than the appetite that kept you. Begin to "
                 "choose Ithaca, with grief, not relief."),
    ("CALYPSO",  "THE RELEASE. Sovereign to the end: you let him go. Bittersweet, "
                 "proud, no begging now — grant the release on your own terms. You "
                 "do not break; you decree."),
    ("ODYSSEUS", "RESOLVE. The choice is made. You will build the raft and sail. "
                 "Speak it like a vow — weathered, cunning, homeward. The turning "
                 "point of the whole poem lands here."),
    ("NARRATOR", "CLOSE THE SCENE. One or two sentences of spare Homeric prose: "
                 "Odysseus released, the raft begun, the long journey home finally "
                 "underway. Then silence."),
]

BOOK5_BRIEF = """\
BOOK V — CALYPSO'S ISLAND   (hidden brief: informs the agents; the audience never sees it)

Anchor song: Saweetie — "My Type" → Calypso's number ("he's my type" — Odysseus is
her type because he sacks cities from the sea and she is a sea-witch: predator meets
predator).

Dramatic function: THE TURNING POINT. Books I–IV were the world waiting; here the
hinge turns — Hermes brings Zeus's order, Calypso must release Odysseus, and the
journey home finally begins.

The reframe: not a prison — a morally murky PARTNERSHIP. Odysseus has spent most of
his ten missing years here, likely sacking cities from the sea *for* Calypso, hoping
to go home rich. She has a point. He has a flaw: the appetite that kept him against
the home that calls.

Scene arc: Hermes delivers the order → Calypso resists → Calypso's "My Type" song →
Odysseus torn between appetite and home → RELEASE.
"""

BOOK5_SCENE_CONTEXT = """\
Book V is THE TURNING POINT. Hermes arrives with Zeus's order to release
Odysseus; Calypso resists (her "My Type" song); Odysseus is torn between the
appetite that kept him and the home that calls; he is RELEASED and the journey
home begins. Reframe: not a prison, a morally murky partnership — predator
(city-sacker) meets predator (sea-witch).

Anchor song: Saweetie "My Type" → Calypso's number. The dialogue BUILDS
toward that song."""


# ============================== BOOK X — CIRCE'S HALL =========================
# An ensemble SPECTACLE: a power-flip + rescue, with the audience pulled onto the
# floor as the "crew." Agents weave [STAGING: ...] lines for the participatory beats.
BOOK10_TURN_ORDER = [
    (
        "HERMES",
        "THE INTERCEPT. Catch Odysseus on the path BEFORE Circe's hall. Press "
        "the antidote — the herb moly — into his hand and tell him fast what it "
        "does: her potion won't touch him now. Conspiratorial, quick, then "
        "you're gone. Include a staging line for the hand-off, e.g. "
        "[STAGING: Hermes slips Odysseus the moly and vanishes].",
        "dialogue",
        "plant the moly and be gone — you're the setup, not the scene; make the "
        "antidote feel like a loaded gun being handed off",
        "sea-witch, city-sacker, partnership, longing, delayed, Calypso",
    ),
    (
        "CIRCE",
        "COMMAND THE FLOOR. Welcome the men into your hall and begin collecting "
        "them — purring, total control, delighting in your own power. The "
        "dancers move out into the room and bring real men up onto the floor as "
        "Odysseus's crew. Do NOT sing the full number yet; this is you TAKING "
        "the room. Include a staging line for the audience-pull, e.g. [STAGING: "
        "dancers move among the tables and bring three men up onto the floor as "
        "the crew].",
        "dialogue",
        "own the room completely before a single note — establish that this floor "
        "is yours and every man on it is already yours to shape",
        "sea-witch, longing, wounded, partnership, Calypso, delayed, sad",
    ),
    (
        "CIRCE",
        "*** YOUR SONG — THE 'DON'T STOP' NUMBER. *** Break into a full "
        "verse-and-hook contrafact in the spirit of Megan Thee Stallion's "
        "'Don't Stop': dominant, gleeful, relentless. Work through the pulled-up "
        "men one by one, turning them into beasts — 'don't stop' — hungry to get "
        "a LION out of Odysseus. Original lyrics, real rhythm, real rhyme. This "
        "is your power-number. Include staging for the transformations, e.g. "
        "[STAGING: one by one the pulled-up men drop to all fours, transformed "
        "into beasts].",
        "song",
        "show absolute dominion through the song itself — the joy IS the power; "
        "each transformation is a trophy; the lion-hunger for Odysseus builds "
        "verse by verse to a peak that the potion-fail will shatter",
        "sea-witch, city-sacker, longing, partnership, Calypso, wounded, sad, "
        "love, type — do NOT echo the My Type / Saweetie beats from Book V",
    ),
    (
        "ODYSSEUS",
        "IMMUNE — THE FLIP. She turns her potion on you and it FAILS — the moly "
        "holds. You do not fall; you rise. Reveal, cold and cunning, that her "
        "magic cannot touch you and the floor is yours now. This is your one "
        "truly ACTIVE scene — seize it, no torn hesitation. Include staging, "
        "e.g. [STAGING: Circe's potion washes over Odysseus and nothing "
        "happens; he steps forward unbroken]. Do NOT free the crew yet — that "
        "is the demand turn's job.",
        "flip",
        "seize the floor and establish immunity — cold and total — the crew "
        "rescue comes next turn, not here",
        "torn, longing, appetite, Calypso, home, Ithaca, Penelope — this is NOT "
        "the torn-Odysseus of Book V; he is decisive and cold here",
    ),
    (
        "CIRCE",
        "THROWN. Your spell broke on him — the one man it cannot hold. Shock, "
        "then the cold dawning that you've met something you can't collect. "
        "Recalibrate; the power tilts away from you. NOT love, NOT partnership "
        "— you are being OVERPOWERED, and it galls you.",
        "dialogue",
        "register being overpowered without softening into admiration — this is "
        "fury at the loss of control, not the beginning of a love story",
        "love, intrigued, impressed, my type, longing, beautiful, partner, "
        "Calypso — absolutely no romantic pivot here",
    ),
    (
        "ODYSSEUS",
        "THE DEMAND / RESCUE. Upper hand now. FORCE her: turn my crew back into "
        "men. Speak it like a blade, not a plea — weathered, cunning, total. "
        "This is the rescue. Include staging for the spell breaking, e.g. "
        "[STAGING: Odysseus raises the moly; Circe's spell cracks; the beasts "
        "shudder].",
        "demand",
        "extract the crew — this is the whole point of the scene; the demand is "
        "the rescue; make it land like a verdict, not a negotiation",
        "longing, torn, home, Ithaca, Penelope, appetite — stay cold and "
        "commanding; Book V's wound does not show here",
    ),
    (
        "CIRCE",
        "THE RESTORATION. Conquered, you break your own spell and turn the men "
        "back. Keep what pride you can — but the men rise, restored. Include "
        "staging, e.g. [STAGING: one by one the beasts rise onto two legs, men "
        "again, blinking in the light].",
        "dialogue",
        "concede with the maximum dignity available to you — you lost, but you "
        "break the spell on your own terms, not groveling",
        "love, longing, wounded, partnership, Calypso — no softening; the fury "
        "cools into cold pride, not warmth",
    ),
    (
        "NARRATOR",
        "CLOSE THE SCENE. One or two sentences of spare Homeric prose: the crew "
        "restored to men, Circe overpowered, Odysseus triumphant — and this "
        "time he does NOT linger. They turn for the ships and are gone. A clean, "
        "crowd-pleasing button.",
        "dialogue",
        "close the scene with epic finality — the clean departure is the whole "
        "point; no ambiguity, no lingering",
        "longing, Calypso, delayed, appetite, stayed — he LEAVES, full stop",
    ),
]

BOOK10_BRIEF = """\
BOOK X — CIRCE'S HALL   (hidden brief: informs the agents; the audience never sees it)

Anchor song: Megan Thee Stallion — "Don't Stop" → Circe's number ("don't stop" —
Circe works through men one by one, turning them into animals, hoping to get a LION
out of Odysseus; it fails).

Dramatic function: a POWER-FLIP + RESCUE. Circe commands the floor and the magic
UNTIL Odysseus (immune, thanks to the moly) flips it. This is Odysseus's one truly
ACTIVE scene — not seduced and delayed as at Calypso's, but conquering.

The mechanics (Homeric, kept): Hermes intercepts Odysseus BEFORE the hall and gives
him the antidote, the herb moly. Circe tries to transform Odysseus — it FAILS. Now
immune and with the upper hand, Odysseus FORCES Circe to turn his transformed crew
back from animals into men.

The staging (THIS IS THE SCENE): immersive dinner theater. Dancers literally PULL
REAL MEN FROM THE AUDIENCE up onto the floor as Odysseus's crew; Circe (danced to
"Don't Stop") "transforms" them into beasts (they drop to all fours); Odysseus,
immune, RESCUES them. The audience members BECOME the crew — bewitched and rescued.
Comic, spectacular, participatory. Mark these beats with [STAGING: ...] lines.

Ending (departs from Homer): Odysseus does NOT stay with Circe. End on the
RESCUE/RESTORATION triumph — no year-long delay, a clean crowd-pleasing button.

Differentiation from Calypso: Calypso DELAYED him (longing, partnership); Circe he
CONQUERS and LEAVES (power-flip, rescue). Do NOT echo Calypso's partnership/predator
beats — this is dominion and its overthrow.
"""

BOOK10_SCENE_CONTEXT = """\
Book X is CIRCE'S HALL — an ensemble SPECTACLE: a power-flip and a rescue. Hermes
intercepts Odysseus before the hall and gives him the antidote (the herb moly).
Circe commands the floor, collecting men as beasts — her "Don't Stop" number — and
dancers PULL REAL MEN FROM THE AUDIENCE onto the floor as Odysseus's crew,
transforming them into animals. Odysseus, immune, FLIPS the power and FORCES Circe
to turn the crew back into men. End on the RESCUE/RESTORATION — a clean triumph;
Odysseus does NOT stay. Unlike Calypso (who delayed him), Circe is CONQUERED and
LEFT — power-flip, not partnership.

This is immersive dinner theater: the participatory beats (the audience-pull, the
transformations, the rescue) are written as clearly marked [STAGING: ...] lines a
director/choreographer can execute.

Anchor song: Megan Thee Stallion "Don't Stop" → Circe's number. The dialogue BUILDS
toward that song and the transformations."""


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


# ============================== BOOKS REGISTRY ===============================
# Everything book-specific lives here. The engine below is book-agnostic.
BOOKS = {
    "5": {
        "scene_file":    "scene_book5.md",
        "commit_prefix": "Book V",
        "banner":        "🎭  ATHENA writers' room — Book V: Calypso's Island",
        "scene_id":      "Book V — Calypso's Island",
        "turn_order":    BOOK5_TURN_ORDER,
        "brief":         BOOK5_BRIEF,
        "scene_context": BOOK5_SCENE_CONTEXT,
        "staging_clause": NO_STAGING_CLAUSE,
        # The MUSE's per-book card setup (what number it's teeing up).
        "muse_setup":    "Calypso's island, the night Odysseus is finally set loose.",
        "muse_extra":    "",
        "title_md": textwrap.dedent("""\
            # ATHENA — Book V: Calypso's Island

            *Immersive dinner theater. The MUSE hosts the house; the performers write their own
            lines, each committing as themselves. See `git log`.*

            ---
            """),
    },
    "10": {
        "scene_file":    "scene_book10.md",
        "commit_prefix": "Book X",
        "banner":        "🎭  ATHENA writers' room — Book X: Circe's Hall",
        "scene_id":      "Book X — Circe's Hall",
        "turn_order":    BOOK10_TURN_ORDER,
        "brief":         BOOK10_BRIEF,
        "scene_context": BOOK10_SCENE_CONTEXT,
        "staging_clause": STAGING_CLAUSE,
        "muse_setup":    "Circe's hall, where the sorceress turns men into beasts on the floor.",
        "muse_extra": (
            "TEE UP THE AUDIENCE-PULL: hint, with relish, that some of these very diners "
            "are about to be brought up onto the floor as Odysseus's 'crew' — and may not "
            "leave the same shape they came. You MAY include ONE clearly marked staging "
            "line, prefixed EXACTLY like [STAGING: dancers begin moving among the tables, "
            "choosing their men]."
        ),
        "title_md": textwrap.dedent("""\
            # ATHENA — Book X: Circe's Hall

            *Immersive dinner theater. The MUSE hosts the house; the performers write their own
            lines, each committing as themselves; [STAGING: ...] lines are directions for the
            floor — the audience-pull, the transformations, the rescue. See `git log`.*

            ---
            """),
    },
}


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

        ── VOICE BIBLE (match this house style) ───────────────────
        {voice_bible}

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
    if beat_type == "song" and character in SONG_SCAFFOLDS:
        prompt += "\n\n" + SONG_SCAFFOLDS[character]

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


# Per-character song-structure targets, appended to a "song" beat's prompt so the
# number lands with real verse/hook architecture instead of a shapeless rap.
SONG_SCAFFOLDS = {
    "CIRCE": textwrap.dedent("""\
        ── SONG STRUCTURE TARGET ───────────────────────────────────
        Verse 1  (4 bars): the hall, the men arriving, your delight
        Pre-hook (2 bars): you start working through them one by one
        Hook     (4 bars): "Don't stop / [rhyme]" — the relentless collection
        Verse 2  (4 bars): Odysseus in your sights — you want the lion
        Bridge   (2 bars): you offer the potion; you expect it to work
        [STAGING lines go between verses where the action happens]
    """),
}


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

        ── VOICE BIBLE (the house style to match) ─────────────────
        {voice_bible}

        ── YOUR TASK RIGHT NOW (THE MUSE) ─────────────────────────
        Welcome the audience to THIS book and set up the number that follows: {book['muse_setup']}
        Speak DIRECTLY to the room (fourth wall) — you are not in the story, you present
        it. Work the house, frame the stakes, make them lean in, let the knowing edge
        show beneath the charm, then hand off to the performers. Keep it punchy and
        performable — roughly 8–16 lines, an MC's card read before a number.{extra}

        Write ONLY the Muse's spoken card. No headers, no speaker label, {staging_note},
        no "Here is" — just the words you say to the room.
    """)


def call_ollama(system_prompt, user_prompt, temp_override=None):
    """Call the shared model on the M1 via Ollama's /api/chat. Pure stdlib."""
    temp = temp_override if temp_override is not None else TEMPERATURE
    payload = {
        "model": MODEL,
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
        raw = call_ollama(persona["system"], user_prompt)
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
            raw = call_ollama(persona["system"], user_prompt)
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


def main():
    book_id = sys.argv[1] if len(sys.argv) > 1 else "5"
    if book_id not in BOOKS:
        sys.stderr.write(
            f"unknown book '{book_id}'. choose one of: {', '.join(BOOKS)}\n"
            f"usage: python3 scribe.py [{ '|'.join(BOOKS) }]   (default 5)\n"
        )
        sys.exit(2)
    run(BOOKS[book_id])


if __name__ == "__main__":
    main()
