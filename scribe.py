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

Tweak the CONFIG block below; personas, books, and song scaffolds live in
athena.yaml and are reloaded fresh every run. Requires PyYAML. (The hardcoded
PERSONAS/BOOKS/SONG_SCAFFOLDS remain as the reference the equivalence check
compares the YAML against — see check_yaml_equiv.py.)
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

from personas import PERSONAS

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
        "title_md": "# ATHENA — Book V: Calypso's Island\n\n*Immersive dinner theater.*\n\n---\n",
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
        "title_md": "# ATHENA — Book X: Circe's Hall\n\n*Immersive dinner theater.*\n\n---\n",
    },

    "1": {
        "scene_file":    "scene_book1.md",
        "commit_prefix": "Book I",
        "banner":        "🎭  ATHENA writers' room — Book I: Deal With It",
        "scene_id":      "Book I — Deal With It",
        "song_scaffold_key": "TELEMACHUS_DEAL",
        "turn_order": [
            ("ANTINOUS",
             "OPEN THE FEAST. You own this hall — Odysseus has been gone twenty years "
             "and his palace is your personal banquet. Be loud, entitled, contemptuous. "
             "You genuinely believe the throne is available and you deserve it. Feast, "
             "boast, dismiss Telemachus as furniture. Include staging, e.g. [STAGING: "
             "Antinous sprawls at the head table, raising his cup to the room, ignoring "
             "Telemachus entirely].",
             "dialogue",
             "establish total ownership of the hall before the scene even starts — "
             "you are the force Telemachus has to push against",
             "Odysseus, fear, guilt, shame — you feel none of these yet"),
            ("EURYMACHUS",
             "WORK THE ROOM. While Antinous holds the head table, move among the diners "
             "— charming, reasonable, framing the whole situation as Penelope's fault for "
             "stringing everyone along with the weaving trick. You are the PR wing of the "
             "suitor operation. Include staging, e.g. [STAGING: Eurymachus moves table to "
             "table, leaning in, all charm and reasonableness].",
             "dialogue",
             "make the suitors' cause sound reasonable to the room — you are the most "
             "dangerous one because you are the most likeable",
             "aggressive, threatening — that's Antinous; you are the smile, not the fist"),
            ("ATHENA",
             "ARRIVE AS MENTES. Disguised as the old family friend, find Telemachus apart "
             "from the suitors and speak privately: who is he, what is this disgrace, his "
             "father is ALIVE and coming home. Plant the fire. Include staging, e.g. "
             "[STAGING: Athena as Mentes draws Telemachus to a quiet corner, away from "
             "the feast].",
             "dialogue",
             "light the fire in Telemachus — hand him his destiny without letting him "
             "know that's what you're doing",
             "obvious, divine, heavy-handed — you are Mentes the family friend; keep "
             "the disguise warm and human"),
            ("TELEMACHUS",
             "FIRST FIRE. You've heard from Mentes that your father may be alive and it's "
             "time to act. Twenty years of compressed rage starting to move. Not confident "
             "yet — a boy getting angry enough to become a man. Speak it: the suitors, the "
             "disgrace, the resolve beginning to form. Include staging, e.g. [STAGING: "
             "Telemachus stands and faces the suitors' tables for the first time without "
             "flinching].",
             "dialogue",
             "find the anger that's been buried under twenty years of powerlessness — "
             "raw, unformed, the first spark",
             "confident, heroic, resolved — not yet; this is the beginning; do NOT "
             "skip to the hero"),
            ("PENELOPE",
             "THE GRIEF THAT RUNS THE HOUSE. Appear briefly — regal, exhausted, still. "
             "You have been weaving and unweaving for years. Address the room, the absence, "
             "the twenty-year wait. One moment of sovereign grief then withdraw. Include "
             "staging, e.g. [STAGING: Penelope appears at the top of the stairs, surveys "
             "the ruined feast, says nothing for a long moment].",
             "dialogue",
             "hold the room with grief and sovereignty — you are the real power here "
             "and everyone knows it",
             "weak, begging, romantic — you are running a twenty-year strategy, "
             "not falling apart"),
            ("TELEMACHUS",
             "DEAL WITH IT — THE NUMBER. Ashnikko's 'Deal With It' as contrafact. Done "
             "being told to deal with it — the suitors eating your father's food, the hall "
             "in disgrace, your mother besieged. Full verse-and-hook: furious, young, raw. "
             "Hook built around refusing to deal with it anymore. Original lyrics, real "
             "rhythm, real rhyme. Include staging, e.g. [STAGING: Telemachus steps to the "
             "center of the hall; the suitors fall silent].",
             "song",
             "channel twenty years of swallowed rage into one number — this is the "
             "moment the boy stops absorbing it",
             "polished, heroic, resolved — this is rage not triumph; Calypso, Circe, "
             "sea-witch — wrong register"),
            ("ANTINOUS",
             "LAUGH IT OFF. Telemachus just stood up to you. You're amused, not threatened. "
             "Dismiss him, mock him lightly, return to the feast. You have no idea what's "
             "coming. Include staging, e.g. [STAGING: Antinous laughs and raises his cup; "
             "the other suitors follow suit, utterly unbothered].",
             "dialogue",
             "underestimate Telemachus completely — your contempt is your fatal flaw",
             "afraid, threatened — you are entitled and blind; that's worse"),
            ("NARRATOR",
             "CLOSE THE SCENE. One or two sentences of spare Homeric prose: the seed "
             "planted by Athena, the fire begun in Telemachus, the suitors feasting on "
             "oblivious. The poem is in motion.",
             "dialogue",
             "close with epic weight — the hinge of a coming-of-age story just turned",
             "warm, resolved — the danger is real; the suitors are still winning"),
        ],
        "brief": """\
BOOK I — DEAL WITH IT   (hidden brief)

Anchor song: Ashnikko — "Deal With It" → Telemachus's number. He is done being
told to deal with the suitors eating his father's food and besieging his mother.

Dramatic function: THE INCITING INCIDENT. Athena arrives disguised as Mentes and
plants the fire in Telemachus. The suitors feast, oblivious. Penelope endures.
Telemachus finds his first anger.

The reframe: Telemachus is not a passive boy — he's a boy sitting on twenty years
of compressed rage. This scene is the moment it starts to move.

Staging: the wealthy diners are the Ithacan court. Some of them are suitors.
Telemachus speaks to the room. Athena works a corner table.
""",
        "scene_context": """\
Book I is THE INCITING INCIDENT. The suitors feast in Odysseus's hall. Athena
arrives disguised as the family friend Mentes and privately tells Telemachus his
father may be alive — and that it's time to act. Telemachus finds his first fire.
Penelope appears briefly, sovereign and grieving. The suitors laugh it off.

Anchor song: Ashnikko "Deal With It" → Telemachus's number. The dialogue builds
toward that song.

Staging: the diners are the Ithacan court. Mark participatory beats with
[STAGING: ...] lines.""",
        "staging_clause": STAGING_CLAUSE,
        "muse_setup": "the palace of Ithaca, where the suitors have been feasting for twenty years and the boy of the house is about to find his spine.",
        "muse_extra": (
            "Hint that these very diners are the Ithacan court — they have been "
            "watching this disgrace. Some of them ARE the suitors. The boy is "
            "going to stand up tonight for the first time. Let them feel "
            "complicit in what's been happening and curious about what's coming."
        ),
        "title_md": "# ATHENA — Book I: Deal With It\n\n*Immersive dinner theater.*\n\n---\n",
    },

    "2": {
        "scene_file":    "scene_book2.md",
        "commit_prefix": "Book II",
        "banner":        "🎭  ATHENA writers' room — Book II: Fast",
        "scene_id":      "Book II — Fast",
        "song_scaffold_key": "TELEMACHUS_FAST",
        "turn_order": [
            ("TELEMACHUS",
             "CALL THE ASSEMBLY. Standing before the Ithacan court — these diners — for "
             "the first time as a man making demands. Call the assembly, name the disgrace, "
             "announce your intention: you will find your father. Hold the floor when the "
             "suitors try to shout you down. Include staging, e.g. [STAGING: Telemachus "
             "stands at the center of the room and calls the court to order for the first "
             "time in twenty years].",
             "dialogue",
             "hold the floor against the suitors — this is your first public act of "
             "defiance; make the room feel the shift",
             "timid, apologetic — you are not asking; you are declaring"),
            ("ANTINOUS",
             "PUSH BACK. Telemachus is making noise. Dismiss him, reframe it as Penelope's "
             "fault — she keeps stringing you along with the weaving trick. You're annoyed, "
             "not threatened. Include staging, e.g. [STAGING: Antinous rises, talking over "
             "Telemachus, gesturing at Penelope's absence].",
             "dialogue",
             "drown Telemachus out and reframe the whole situation as Penelope's "
             "manipulation — you genuinely believe this",
             "afraid, villainous — you are making a reasonable case by your own lights"),
            ("AMPHINOMUS",
             "THE QUIET DISSENT. While Antinous blusters, speak low — to a neighbor, to "
             "the room — your unease audible. This isn't right. You don't stop it but you "
             "name it. Include staging, e.g. [STAGING: Amphinomus sets down his cup and "
             "stares at the table, not laughing with the others].",
             "dialogue",
             "be the conscience of the room — quiet, uncomfortable, ineffective; you "
             "know this ends badly",
             "loud, heroic — you are not stopping anything; you are the one who knows"),
            ("ATHENA",
             "RECRUIT THE CREW. As Mentor, move among the tables while Telemachus holds "
             "the floor. Quietly assembling his crew — the young men who will sail with "
             "him. Speak to specific diners, pulling them in. Include staging, e.g. "
             "[STAGING: Athena as Mentor moves table to table, leaning in — three young "
             "men stand and nod].",
             "dialogue",
             "build the crew from the room itself — these diners are becoming "
             "Telemachus's fleet; make them feel chosen",
             "obvious, divine — you are Mentor the old family friend; "
             "conspiratorial and human"),
            ("TELEMACHUS",
             "FAST — THE NUMBER. Saweetie's 'Fast' as contrafact. Moving now — fast, "
             "forward, no more waiting. The crew assembling, the ship being readied, the "
             "journey beginning. Full verse-and-hook: urgent, hungry, young. Hook about "
             "moving fast toward your father and your destiny. Original lyrics, real "
             "rhythm, real rhyme. Include staging for the crew assembly, e.g. [STAGING: "
             "the recruited men rise from their tables and move toward Telemachus, forming "
             "up as his crew].",
             "song",
             "the energy of finally moving after twenty years of stillness — fast, "
             "forward, hungry",
             "angry, rageful — that was Book I; this is motion not rage; "
             "sea-witch, Calypso — wrong register"),
            ("NARRATOR",
             "CLOSE THE SCENE. One or two sentences of spare Homeric prose: the ship "
             "launched, Telemachus at the prow, the suitors not yet aware he is gone. "
             "The sea opens.",
             "dialogue",
             "close with the clean excitement of first departure — the journey has begun",
             "heavy, ominous — this is a beginning"),
        ],
        "brief": """\
BOOK II — FAST   (hidden brief)

Anchor song: Saweetie — "Fast" → Telemachus's number. He is moving fast now —
the assembly called, the crew recruited from the diners, the ship launched.

Dramatic function: THE DEPARTURE. Telemachus calls the assembly, faces down the
suitors publicly, and Athena (as Mentor) recruits his crew from among the diners.
The ship launches. He is gone before the suitors know it.

Staging: Athena moves table to table recruiting the crew — the diners become
Telemachus's fleet. This is the first participatory beat of the Telemachus arc.
""",
        "scene_context": """\
Book II is THE DEPARTURE. Telemachus calls the Ithacan assembly — the first in
twenty years — and publicly names the disgrace. The suitors push back. Athena
as Mentor moves among the tables recruiting his crew from the diners themselves.
The ship is provisioned and Telemachus launches before the suitors realize he's gone.

Anchor song: Saweetie "Fast" → Telemachus's number. The dialogue builds toward
that song and the crew assembly.

Staging: Athena recruits from the room — the diners become the crew. Mark
participatory beats with [STAGING: ...] lines.""",
        "staging_clause": STAGING_CLAUSE,
        "muse_setup": "the morning after — Telemachus calls the first assembly in twenty years and Athena starts quietly building him a crew from the room.",
        "muse_extra": (
            "Tell the room that Athena is in here tonight, disguised, and she is "
            "looking for volunteers. Some of these diners are about to become "
            "Telemachus's crew. Let that land."
        ),
        "title_md": "# ATHENA — Book II: Fast\n\n*Immersive dinner theater.*\n\n---\n",
    },

    "3": {
        "scene_file":    "scene_book3.md",
        "commit_prefix": "Book III",
        "banner":        "🎭  ATHENA writers' room — Book III: Freak",
        "scene_id":      "Book III — Freak",
        "song_scaffold_key": "TELEMACHUS_FREAK",
        "turn_order": [
            ("TELEMACHUS",
             "ARRIVE AT PYLOS. You and your crew approach Nestor's table — another part "
             "of the room. You are nervous: first time presenting yourself as Odysseus's "
             "son to a great king. Athena nudges you forward. Introduce yourself and ask "
             "for news of your father. Include staging, e.g. [STAGING: Telemachus "
             "hesitates at the edge of Nestor's table, then steps forward].",
             "dialogue",
             "present yourself with borrowed confidence — you don't feel ready but "
             "you do it anyway",
             "confident, polished — the hesitation is the point; this is growth "
             "in real time"),
            ("NESTOR",
             "THE OG HOLDS COURT. You love to talk and this is your moment. Tell "
             "Telemachus everything: the Greek returns from Troy, the deaths, the "
             "disasters, the gods' anger, his father's legend. You are genuinely fond "
             "of Odysseus and moved by this boy who looks like him. Include staging, "
             "e.g. [STAGING: Nestor gestures expansively, holding court, Telemachus's "
             "crew listening wide-eyed].",
             "dialogue",
             "open the world for Telemachus — give him the full scope of the heroic "
             "age and his father's place in it",
             "brief, modest — Nestor is famously long-winded; lean into it with warmth"),
            ("ATHENA",
             "THE FLASH. Briefly let the Mentor disguise slip — an eagle crosses the "
             "room, the air changes, Nestor feels it. Then Mentor stands there again, "
             "composed. Include staging, e.g. [STAGING: an eagle shadow crosses the "
             "ceiling; the room stills for one breath; then Mentor smiles and the "
             "moment passes].",
             "dialogue",
             "one electric moment of the divine showing through — remind the room "
             "who is really running this operation",
             "sustained — one flash only, then human again immediately"),
            ("TELEMACHUS",
             "FREAK — THE NUMBER. Pitbull's 'Freak' as contrafact. You have seen the "
             "wider world — kings, heroes, the scope of your father's legend. It is "
             "freaking you out in the best way. Full verse-and-hook: energetic, "
             "wide-eyed, newly confident. Hook about the world being bigger and wilder "
             "than Ithaca. Original lyrics, real rhythm, real rhyme. Include staging, "
             "e.g. [STAGING: Telemachus's crew dances; the whole room opens up around "
             "Nestor's table].",
             "song",
             "the intoxication of the wider world hitting you for the first time — "
             "overwhelming and thrilling; you are becoming someone",
             "angry, melancholy — this is joy and expansion; "
             "sea-witch, Calypso — wrong register"),
            ("NESTOR",
             "SEND HIM ON. You've told him what you know. Send Telemachus to Sparta, "
             "to Menelaus — who knows more. Give him your son Pisistratus as companion. "
             "Generous, kingly, brief. And pass the collection for his voyage. Include "
             "staging, e.g. [STAGING: Nestor gestures to a server who begins moving "
             "among the tables with the collection for Telemachus's voyage].",
             "dialogue",
             "equip him, send him forward, and invite the room to back him — "
             "you are a waypoint and a fundraiser",
             "lingering, sentimental — dispatch him with warmth and efficiency"),
            ("NARRATOR",
             "CLOSE THE SCENE. One or two sentences of spare Homeric prose: Telemachus "
             "received by Nestor, sent on toward Sparta, the boy's world expanding like "
             "a sea around him.",
             "dialogue",
             "close with the sense of expansion — his world is getting bigger",
             "heavy — this is growth, not danger"),
        ],
        "brief": """\
BOOK III — FREAK   (hidden brief)

Anchor song: Pitbull — "Freak" → Telemachus's number. He has sailed to Pylos,
met the great king Nestor, and the wider heroic world is freaking him out — in
the best way. He is becoming someone.

Dramatic function: THE WIDER WORLD. Telemachus arrives at Pylos, meets Nestor,
hears the scope of the Trojan war and its aftermath. Athena briefly drops her
disguise. Telemachus is sent on to Sparta. The collection is passed for his voyage.

Staging: Nestor is an older diner at another table — the voyage is a walk across
the room. The collection is passed during Nestor's send-off.
""",
        "scene_context": """\
Book III is THE WIDER WORLD. Telemachus and his crew sail to Pylos and present
themselves to the great king Nestor. Nestor tells the story of the Greek returns
from Troy. Athena briefly drops her Mentor disguise. Telemachus is sent on to
Sparta. The collection is passed among the diners for his voyage.

Anchor song: Pitbull "Freak" → Telemachus's number. The dialogue builds toward
that song.

Staging: Nestor is a diner at another table. Collection passed at send-off.
Mark beats with [STAGING: ...] lines.""",
        "staging_clause": STAGING_CLAUSE,
        "muse_setup": "Pylos — Telemachus has sailed to the court of the great king Nestor, and the wider world is about to hit him like a wave.",
        "muse_extra": (
            "Tell the room that Nestor is among them tonight — an older diner, "
            "the OG who has seen everything. Telemachus is coming to his table "
            "to ask for help finding his father. And that later, the collection "
            "will come around — this boy needs backing for his voyage. "
            "[STAGING: the Muse gestures to an older diner as Nestor]."
        ),
        "title_md": "# ATHENA — Book III: Freak\n\n*Immersive dinner theater.*\n\n---\n",
    },

    "4": {
        "scene_file":    "scene_book4.md",
        "commit_prefix": "Book IV",
        "banner":        "🎭  ATHENA writers' room — Book IV: Rude Boy",
        "scene_id":      "Book IV — Rude Boy",
        "song_scaffold_key": "TELEMACHUS_RUDE",
        "turn_order": [
            ("TELEMACHUS",
             "ARRIVE AT SPARTA. You and Pisistratus approach Menelaus and Helen's table "
             "— the most prestigious in the room. More confident than at Pylos — you've "
             "been received by a king, you've been on the road. Introduce yourself. "
             "Include staging, e.g. [STAGING: Telemachus approaches with the ease of "
             "a man who has done this before].",
             "dialogue",
             "arrive with the confidence of someone who has already done this once — "
             "Pylos cured the hesitation",
             "timid, over-awed — that was Pylos; you carry yourself differently now"),
            ("HELEN",
             "THE RECOGNITION. You see Telemachus across the table and you know "
             "immediately — his father's face, his father's bearing. Say so before "
             "anyone introduces him. You are Helen; you see clearly and you speak "
             "clearly. Include staging, e.g. [STAGING: Helen studies Telemachus's "
             "face, then smiles — she knows exactly who he is].",
             "dialogue",
             "give Telemachus the gift of being seen — your recognition is a "
             "benediction; you give it freely",
             "guilty, apologetic, diminished — you are HELEN; zero apology"),
            ("MENELAUS",
             "THE FATHER'S LEGEND. You were at Troy. You know Odysseus better than "
             "almost anyone alive. And you have news: Proteus told you Odysseus is "
             "alive, held by Calypso. Give the boy his father whole — the legend and "
             "the complexity both. Pass the collection for his voyage home. Include "
             "staging, e.g. [STAGING: Menelaus leans across the table, man to man; "
             "then gestures for the collection to go around].",
             "dialogue",
             "give Telemachus his father complete and back his voyage — "
             "man to man, king to prince",
             "brief, withholding — you have stories and you tell them straight"),
            ("TELEMACHUS",
             "RUDE BOY — THE NUMBER. Rihanna's 'Rude Boy' as contrafact. Your father "
             "is alive. You have been received by kings. You are going home and the "
             "suitors are going to find out what Odysseus's son has become. Full "
             "verse-and-hook: defiant, newly confident, dangerous. Hook about being "
             "the rude boy coming home to take back what's his. Original lyrics, real "
             "rhythm, real rhyme. Include staging, e.g. [STAGING: Telemachus stands "
             "and for the first time he looks exactly like his father].",
             "song",
             "claim your father's legacy and announce your return — you are the "
             "rude boy coming home",
             "timid, uncertain — that arc is over; sea-witch, Calypso — wrong register"),
            ("NARRATOR",
             "CLOSE THE TELEMACHUS ARC. Two sentences of spare Homeric prose: "
             "Telemachus received by Menelaus and Helen, his father confirmed alive, "
             "the boy turning toward home — and in Ithaca, the suitors plotting an "
             "ambush that will fail. The poem pivots now to Odysseus himself.",
             "dialogue",
             "close the whole Telemachus arc with structural weight — four books "
             "of coming-of-age landing on one pivot; signal the shift to Odysseus",
             "light, casual — this is a major hinge of the poem"),
        ],
        "brief": """\
BOOK IV — RUDE BOY   (hidden brief)

Anchor song: Rihanna — "Rude Boy" → Telemachus's number. He has been received
by Menelaus and Helen, heard that his father is alive, and is turning home —
the rude boy coming back to reclaim what's his.

Dramatic function: THE COMPLETION OF THE TELEMACHUS ARC. Helen recognizes him
by his father's face. Menelaus gives him the most complete picture of Odysseus.
Telemachus leaves Sparta a different man. The collection is passed. In Ithaca,
the suitors plot an ambush that will fail.

Staging: Menelaus and Helen at the most prestigious table. Collection passed
during Menelaus's speech.
""",
        "scene_context": """\
Book IV is THE COMPLETION OF THE TELEMACHUS ARC. Telemachus arrives at Sparta.
Helen recognizes him by his father's face. Menelaus confirms Odysseus is alive.
Telemachus turns for home a changed man. The collection is passed.

Anchor song: Rihanna "Rude Boy" → Telemachus's number. Dialogue builds toward
that song and the turn toward home.

Staging: Menelaus and Helen at a prestigious table. Collection at Menelaus's
speech. Mark beats with [STAGING: ...] lines.""",
        "staging_clause": STAGING_CLAUSE,
        "muse_setup": "Sparta — Telemachus arrives at the most legendary court in Greece, and Helen recognizes him before he says a word.",
        "muse_extra": (
            "Tell the room that Menelaus and Helen are among them — the king "
            "and queen of Sparta. Telemachus is coming to their table. "
            "And that the collection comes around again tonight — the boy "
            "still needs backing for the voyage home. "
            "[STAGING: the Muse gestures to a couple at a prominent table "
            "as Menelaus and Helen]."
        ),
        "title_md": "# ATHENA — Book IV: Rude Boy\n\n*Immersive dinner theater.*\n\n---\n",
    },

    "6": {
        "scene_file":    "scene_book6.md",
        "commit_prefix": "Book VI",
        "banner":        "🎭  ATHENA writers' room — Book VI: Rain On Me",
        "scene_id":      "Book VI — Rain On Me",
        "song_scaffold_key": "ODYSSEUS_RAIN",
        "turn_order": [
            ("POSEIDON",
             "THE STORM. You have found Odysseus at sea and you are ending him — or "
             "trying to. Describe what you do to his raft, the waves, the cold. You "
             "are vast and implacable — not angry the way a man is angry, but the way "
             "a storm is final. Brief, elemental. Include staging, e.g. [STAGING: the "
             "lights drop to blue; the dancers become the waves around Odysseus].",
             "dialogue",
             "be the storm itself — vast, cold, impersonal; this is not a tantrum, "
             "it is a force of nature expressing its will",
             "petty, emotional — you are the SEA; you don't need to raise your voice"),
            ("ODYSSEUS",
             "SURVIVAL. You are in the water for two days. The cold, the exhaustion, "
             "the stubbornness that keeps you swimming when any other man would let go. "
             "Ino gives you her veil. You swim. Include staging, e.g. [STAGING: "
             "Odysseus alone in blue light, swimming, the dancers as waves around him].",
             "dialogue",
             "show the endurance that defines you — not heroism, just the refusal "
             "to stop; this is what survival looks like after twenty years",
             "dramatic, speech-making — you are too tired for speeches; "
             "pure will"),
            ("NAUSICAA",
             "THE FINDING. You came to the beach to do laundry and found a wrecked man "
             "in the reeds. You are not afraid — you are curious and kind. Welcome him, "
             "give him clothes, tell him how to reach your father's court. Include "
             "staging, e.g. [STAGING: Nausicaa approaches the figure on the beach; "
             "her maids hang back; she does not].",
             "dialogue",
             "be genuinely brave and kind — and let the flicker of something more "
             "show without naming it; you are too wise for that",
             "fearful, romantic — you are a princess who knows what she's doing"),
            ("ODYSSEUS",
             "RAIN ON ME — THE NUMBER. Lady Gaga and Ariana Grande's 'Rain On Me' as "
             "contrafact. You have been drowning and you survived. The rain came down "
             "— Poseidon, the war, the years — and you are still here. Full "
             "verse-and-hook: defiant survival, the stubborn joy of still being alive. "
             "Hook built around 'rain on me — I survived it.' Original lyrics, real "
             "rhythm, real rhyme. Include staging, e.g. [STAGING: Odysseus stands; "
             "the blue light shifts to gold; the dancers as waves become celebration].",
             "song",
             "the defiant joy of survival — not triumph, just the fierce fact of "
             "still being alive after everything",
             "defeated, mournful — you survived; this is the song of someone "
             "who came through"),
            ("NAUSICAA",
             "SEND HIM TO THE COURT. Guide Odysseus toward your father's palace: go "
             "straight to Queen Arete, she is the real power. Then step aside — you "
             "will not be seen arriving with a strange man. Brief, practical, graceful. "
             "Include staging, e.g. [STAGING: Nausicaa points toward the palace lights "
             "and steps back into the shadows].",
             "dialogue",
             "give him everything he needs then remove yourself gracefully — "
             "your grace IS the romance",
             "lingering, romantic — this is a practical handoff"),
            ("NARRATOR",
             "CLOSE THE SCENE. One sentence of spare Homeric prose: Odysseus washed "
             "up, found, clothed, and pointed toward the last court before home.",
             "dialogue",
             "close cleanly — this is a transition; the Phaeacian drama is Book VII",
             "long — one sentence"),
        ],
        "brief": """\
BOOK VI — RAIN ON ME   (hidden brief)

Anchor song: Lady Gaga & Ariana Grande — "Rain On Me" → Odysseus's survival number.
He has been drowning for days, Poseidon destroyed his raft, and he is still here.

Dramatic function: THE SURVIVAL AND THE FINDING. Poseidon storms him; Odysseus
swims two days; Nausicaa finds him on the beach. The pivot from destruction to
hospitality — the last court before home.

Staging: blue storm-light for the drowning; gold light for the survival song;
dancers as waves. Nausicaa does not pull from the audience — she is a performer.
""",
        "scene_context": """\
Book VI is THE SURVIVAL AND THE FINDING. Poseidon destroys Odysseus's raft.
Odysseus swims two days. Nausicaa finds him on the beach of Scheria and points
him toward her father's court.

Anchor song: Lady Gaga & Ariana Grande "Rain On Me" → Odysseus's survival number.

Staging: dancers as waves in blue light; gold light for the song. Mark beats
with [STAGING: ...] lines.""",
        "staging_clause": STAGING_CLAUSE,
        "muse_setup": "the shore of Scheria — Odysseus has been drowning for days and a princess is about to find him on the beach.",
        "muse_extra": "",
        "title_md": "# ATHENA — Book VI: Rain On Me\n\n*Immersive dinner theater.*\n\n---\n",
    },

    "7": {
        "scene_file":    "scene_book7.md",
        "commit_prefix": "Book VII",
        "banner":        "🎭  ATHENA writers' room — Book VII: Mic Drop",
        "scene_id":      "Book VII — Mic Drop",
        "song_scaffold_key": "ODYSSEUS_MIC",
        "turn_order": [
            ("ALCINOUS",
             "WELCOME THE STRANGER. A man appeared in your court — ragged, clearly "
             "extraordinary. By Phaeacian law you don't ask his name until he has eaten. "
             "Welcome him with the full weight of your hospitality. The diners are your "
             "court. Include staging, e.g. [STAGING: Alcinous rises and gestures the "
             "stranger to the seat of honor; the court watches].",
             "dialogue",
             "establish your court as the finest in the world — your generosity "
             "is your glory",
             "stingy, suspicious — Phaeacian hospitality is legendary; perform it"),
            ("ODYSSEUS",
             "THE ARRIVAL. You are in the finest court you have seen since Troy. Still "
             "anonymous. Eat. Observe. Feel that this is the place that will get you "
             "home. Include staging, e.g. [STAGING: Odysseus eats in silence, watching "
             "the court, taking its measure].",
             "dialogue",
             "the cunning man reading the room — this court is your best chance "
             "and you know it",
             "boastful, revealing — not yet; eat first"),
            ("ALCINOUS",
             "THE QUESTION. After the games — when a young man insulted the stranger "
             "and the stranger silenced him with one throw — ask directly: who are you? "
             "Include staging, e.g. [STAGING: Alcinous leans forward, the court quiet, "
             "genuinely curious].",
             "dialogue",
             "ask the question the whole room is asking — your curiosity is "
             "kingly, not rude",
             "impatient — you waited through the feast; the question earns its weight"),
            ("ODYSSEUS",
             "MIC DROP — THE NUMBER. Steve Aoki's 'Mic Drop' as contrafact. You reveal "
             "yourself: I am Odysseus, son of Laertes, of Ithaca. The name lands. Full "
             "verse-and-hook: the legendary reveal, the weight of the name, the room "
             "going quiet. Original lyrics, real rhythm, real rhyme. Include staging, "
             "e.g. [STAGING: Odysseus rises; the court stills; he says his name].",
             "song",
             "the reveal of the most famous name in the world — the mic drop "
             "IS the name; let it land like a weapon",
             "humble, quiet — this is Odysseus announcing himself; own it"),
            ("ALCINOUS",
             "THE PROMISE. You will give him a ship. Whatever it takes — the Phaeacians "
             "will carry him home. Brief, kingly, final. Include staging, e.g. [STAGING: "
             "Alcinous stands and speaks to the whole court — we carry him home].",
             "dialogue",
             "make the promise with the full weight of a king's word",
             "hedging — the promise is absolute"),
            ("NARRATOR",
             "CLOSE THE SCENE. One or two sentences of spare Homeric prose: Odysseus "
             "revealed, the Phaeacians sworn to carry him home, the last court before "
             "Ithaca having heard his name.",
             "dialogue",
             "close with the weight of the reveal settling",
             "light — this is a major moment"),
        ],
        "brief": """\
BOOK VII — MIC DROP   (hidden brief)

Anchor song: Steve Aoki — "Mic Drop" → Odysseus's reveal number. He announces
his name to the Phaeacian court and the name lands like a weapon.

Dramatic function: THE REVEAL. Odysseus arrives anonymous at the finest court
before home. After the games, Alcinous asks who he is. Odysseus drops the name.
Alcinous promises a ship.

Staging: the diners are the Phaeacian court — they are the audience for the
reveal. No audience pull. The mic drop is purely performative.
""",
        "scene_context": """\
Book VII is THE REVEAL. Odysseus arrives anonymously at the Phaeacian court of
Alcinous. After the games, Alcinous asks who he is. Odysseus reveals his name.
Alcinous promises a ship home.

Anchor song: Steve Aoki "Mic Drop" → Odysseus's reveal number.

The diners are the Phaeacian court. Mark beats with [STAGING: ...] lines.""",
        "staging_clause": STAGING_CLAUSE,
        "muse_setup": "the Phaeacian court of Alcinous — the most hospitable kingdom in the world, and a wrecked legendary man is about to reveal his name.",
        "muse_extra": (
            "Tell the room that THEY are the Phaeacian court tonight — wealthy, "
            "cultivated, the best audience in the world. They are about to hear "
            "a name they know. Let them feel the privilege of that."
        ),
        "title_md": "# ATHENA — Book VII: Mic Drop\n\n*Immersive dinner theater.*\n\n---\n",
    },

    "8": {
        "scene_file":    "scene_book8.md",
        "commit_prefix": "Book VIII",
        "banner":        "🎭  ATHENA writers' room — Book VIII: Every Day",
        "scene_id":      "Book VIII — Every Day",
        "song_scaffold_key": "ODYSSEUS_EVERYDAY",
        "turn_order": [
            ("DEMODOCUS",
             "THE FIRST SONG. You are the blind bard. You sing of Troy — the quarrel "
             "between Odysseus and Achilles, the battles, the grinding years. You cannot "
             "see the faces of the men you sing about. You sing it beautifully and "
             "without mercy. Include staging, e.g. [STAGING: Demodocus sits at the "
             "center of the court; the room quiets; he begins].",
             "dialogue",
             "sing the truth without knowing who is listening — your blindness "
             "is your gift",
             "aware of Odysseus — you don't know he's there"),
            ("ODYSSEUS",
             "THE TEARS. You are listening to a blind man sing your own story and you "
             "cannot stop weeping. You hide it — pull your cloak over your face. The "
             "accumulated weight of everything. This is the most intimate moment you "
             "have had since leaving Ithaca. No staging — purely internal.",
             "dialogue",
             "let the weight of the years show — the tears are real and they "
             "matter; you have been holding this for a long time",
             "stoic, unmoved — the tears are the emotional core of this book"),
            ("ALCINOUS",
             "YOU SEE THE TEARS. You notice the stranger weeping and you stop the bard. "
             "You don't embarrass him — you redirect, with the grace of a great host. "
             "Include staging, e.g. [STAGING: Alcinous raises his hand gently; "
             "the music stops].",
             "dialogue",
             "see the stranger's pain and protect him — you don't expose him, "
             "you shield him",
             "oblivious — you saw; that's what makes you a great king"),
            ("DEMODOCUS",
             "THE TROJAN HORSE. They ask you to sing the Trojan Horse. You do. The "
             "stranger weeps again, louder. You still don't know why. Include staging, "
             "e.g. [STAGING: Demodocus begins again; Odysseus pulls his cloak "
             "over his face].",
             "dialogue",
             "sing the Trojan Horse with the pride of its cleverest invention — "
             "the horse was Odysseus's idea; sing it like the masterpiece it was",
             "aware, gentle — you are blind and singing; you don't know what "
             "you're doing to him"),
            ("ODYSSEUS",
             "EVERY DAY — THE NUMBER. A$AP Rocky's 'Every Day' as contrafact. Every "
             "day of the war, every day of the voyage, every day another thing lost — "
             "and every day you kept going. The grinding, relentless cost of being "
             "Odysseus. Full verse-and-hook. Original lyrics, real rhythm, real rhyme.",
             "song",
             "the weight of every day of twenty years — not one heroic moment "
             "but the grinding accumulation of all of them",
             "triumphant, boastful — this is the cost, not the glory; heavy "
             "and relentless"),
            ("ALCINOUS",
             "ASK HIM TO TELL HIS STORY. The weeping confirms it. Ask him directly — "
             "tell us everything. We will listen all night. Include staging, e.g. "
             "[STAGING: Alcinous speaks to the whole court; they lean forward as one].",
             "dialogue",
             "open the door to the retrospective — your invitation unlocks "
             "the next four books",
             "reluctant to ask — you have been wanting to ask since he arrived"),
            ("NARRATOR",
             "CLOSE THE SCENE AND OPEN THE RETROSPECTIVE. One sentence of spare Homeric "
             "prose: the court waiting, the bard silent, Odysseus lowering his cloak "
             "and beginning — I am Odysseus, and this is what happened to me.",
             "dialogue",
             "pivot to the retrospective — this sentence is the hinge between "
             "the wanderings and the great flashback",
             "long — one precise sentence opening the door"),
        ],
        "brief": """\
BOOK VIII — EVERY DAY   (hidden brief)

Anchor song: A$AP Rocky — "Every Day" → Odysseus's number. Every day of the war,
every day of the voyage, every day another thing lost — the grinding accumulation.

Dramatic function: THE TEARS AND THE OPENING. Demodocus sings Troy; Odysseus
weeps in secret. Alcinous sees it and asks him to tell his story. The hinge that
opens the retrospective.

Staging: diners as Phaeacian court. Demodocus at center. No audience pull.
""",
        "scene_context": """\
Book VIII is THE TEARS AND THE OPENING. Demodocus sings Troy; Odysseus weeps.
Alcinous notices and invites Odysseus to tell his whole story.

Anchor song: A$AP Rocky "Every Day" → Odysseus's number.

Diners are the Phaeacian court. Mark beats with [STAGING: ...] lines.""",
        "staging_clause": STAGING_CLAUSE,
        "muse_setup": "the Phaeacian court, the day after — the blind bard sings of Troy and one man in the room is going to weep because it is his story.",
        "muse_extra": (
            "Tell the room that tonight the blind bard sings — and that one man "
            "in this room is going to weep when he hears the song, because it "
            "is his story. Let them watch for it."
        ),
        "title_md": "# ATHENA — Book VIII: Every Day\n\n*Immersive dinner theater.*\n\n---\n",
    },

    "9": {
        "scene_file":    "scene_book9.md",
        "commit_prefix": "Book IX",
        "banner":        "🎭  ATHENA writers' room — Book IX: Bad Habits",
        "scene_id":      "Book IX — Bad Habits",
        "song_scaffold_key": "ODYSSEUS_BADHABITS",
        "turn_order": [
            ("ODYSSEUS",
             "BEGIN THE STORY. Narrating to the Phaeacian court — address them directly. "
             "Set the scene: after Troy you raided the Cicones (bad habit one — couldn't "
             "just go home), then the Lotus Eaters nearly took your crew, and then came "
             "the Cyclops. The bad habit that will haunt you forever is coming. Include "
             "staging, e.g. [STAGING: Odysseus speaks to the room directly, the court "
             "listening in silence].",
             "dialogue",
             "narrate with the authority of a man telling his own legend — you know "
             "how this story goes and exactly what it cost",
             "humble, uncertain — you are Odysseus performing his own epic; "
             "own the room"),
            ("POLYPHEMUS",
             "THE CAVE. You come home to find men in your cave. You are enormous, "
             "curious, hungry. You block the door with a boulder and begin eating them "
             "— methodically, without malice. A dancer performs your scale. Your lines "
             "are few and blunt. Include staging, e.g. [STAGING: Polyphemus — a dancer "
             "— fills the space, enormous; the others shrink back].",
             "dialogue",
             "be vast and simple and terrifying — not evil, a force of nature "
             "with an appetite",
             "sophisticated, scheming — you are a giant eating men; that's all"),
            ("ODYSSEUS",
             "THE TRICK. You tell him your name is Nobody. You get him drunk. You blind "
             "him with the sharpened stake. Narrate it to the court with the relish of "
             "the cleverest man in the room. Include staging, e.g. [STAGING: Odysseus "
             "mimes the blinding; Polyphemus the dancer reels; the court gasps].",
             "dialogue",
             "tell this with pride — this is your greatest trick; the Nobody "
             "gambit is the cleverest thing you ever did",
             "remorseful — you are proud of this; the remorse comes next"),
            ("POLYPHEMUS",
             "THE CRY TO POSEIDON. Blinded, you call out to your father — Nobody has "
             "blinded me. Then Odysseus names himself and the curse is set. Include "
             "staging, e.g. [STAGING: Polyphemus raises his arms blind; then "
             "Odysseus names himself and the curse lands].",
             "dialogue",
             "the pitiable moment — blinded, tricked, crying for a father who "
             "will answer; your curse is the engine of the whole poem",
             "merely monstrous — let the audience feel a flicker of pity"),
            ("ODYSSEUS",
             "BAD HABITS — THE NUMBER. Ed Sheeran's 'Bad Habits' as contrafact. You "
             "couldn't help it — when the ships were clear you shouted your real name "
             "back at him. You knew better. You did it anyway. The need to be known, "
             "to be credited, to have the last word. That is the bad habit that cost "
             "you ten years. Full verse-and-hook: honest, self-aware, the flaw named "
             "plain. Original lyrics, real rhythm, real rhyme.",
             "song",
             "be honest about the flaw — this is the bad habit that costs you "
             "ten years; name it with honest self-knowledge",
             "defensive, justifying — own it; the audience needs to feel you "
             "knew better and did it anyway"),
            ("NARRATOR",
             "CLOSE THE SCENE. One or two sentences of spare Homeric prose: the Cyclops "
             "blinded, the name given to Poseidon, the curse set in motion — ten years "
             "of wandering purchased by one moment of pride.",
             "dialogue",
             "land the weight of the mistake — this one beat is the engine of "
             "the rest of the poem",
             "light — this is the moment everything got harder"),
        ],
        "brief": """\
BOOK IX — BAD HABITS   (hidden brief)

Anchor song: Ed Sheeran — "Bad Habits" → Odysseus's number. The bad habit is
shouting his real name at the Cyclops when the ships were clear. He knew better.
He did it anyway. That is the moment that gave Poseidon his name.

Dramatic function: THE MISTAKE THAT COSTS EVERYTHING. The Cyclops scene is the
engine of the whole poem — Poseidon's wrath flows from this one moment of pride.

Staging: Polyphemus is a dancer, not an audience pull. The court are the audience
watching Odysseus tell his own story.
""",
        "scene_context": """\
Book IX is THE MISTAKE THAT COSTS EVERYTHING. Odysseus narrates to the Phaeacian
court: the Lotus Eaters, the Cyclops, the blinding, and the fatal moment he
shouted his name and gave Poseidon the target.

Anchor song: Ed Sheeran "Bad Habits" → Odysseus's number.

Polyphemus is a dancer. Diners are the Phaeacian court. Mark beats with
[STAGING: ...] lines.""",
        "staging_clause": STAGING_CLAUSE,
        "muse_setup": "Odysseus is telling his story to the Phaeacian court — and the first chapter is the Cyclops: the bad habit that cost him everything.",
        "muse_extra": "",
        "title_md": "# ATHENA — Book IX: Bad Habits\n\n*Immersive dinner theater.*\n\n---\n",
    },

    "11": {
        "scene_file":    "scene_book11.md",
        "commit_prefix": "Book XI",
        "banner":        "🎭  ATHENA writers' room — Book XI: Get Ugly",
        "scene_id":      "Book XI — Get Ugly",
        "song_scaffold_key": "ODYSSEUS_GETUGLY",
        "turn_order": [
            ("ODYSSEUS",
             "THE DESCENT. You have done what Circe told you: sailed to the edge of "
             "the world, dug the trench, poured the offerings. The dead come. Narrate "
             "it to the Phaeacian court — the cold, the dark, the crowd of shades. "
             "Include staging, e.g. [STAGING: the lights drop; the dancers as shades "
             "begin moving through the room among the tables, slow and silent].",
             "dialogue",
             "establish the horror and the cold courage it takes to be here — "
             "you are the only living man in this place",
             "numb, mechanical — you are frightened and doing it anyway; "
             "let both show"),
            ("TIRESIAS",
             "THE PROPHECY. You drink the blood and you speak once. Tell Odysseus "
             "everything: Poseidon's wrath, the cattle of the Sun, the suitors, "
             "the return alone, the journey after. Do not comfort him. Do not "
             "elaborate. Include staging, e.g. [STAGING: Tiresias stands utterly "
             "still amid the moving shades; Odysseus kneels].",
             "dialogue",
             "speak the spine of the rest of the poem in as few words as possible "
             "— every word is true and none of it is comforting",
             "gentle, warm — you are cold, precise, final"),
            ("ANTICLEA",
             "THE MOTHER. You are Odysseus's mother. You died waiting for him to come "
             "home. Tell him Penelope is faithful, Telemachus grown, Laertes grieving. "
             "And that you missed him. Speak briefly with terrible tenderness. Include "
             "staging, e.g. [STAGING: Anticlea reaches for Odysseus; her shade "
             "dissolves before he can hold her].",
             "dialogue",
             "the gut-punch — the mother who died of missing him; speak with "
             "the tenderness of someone who has waited a very long time",
             "dramatic, speech-making — this is quiet; the quiet is what "
             "destroys him"),
            ("ODYSSEUS",
             "GET UGLY — THE NUMBER. Jason Derulo's 'Get Ugly' as contrafact. You are "
             "in the Underworld. You have seen your dead mother, heard the cost ahead, "
             "stood in the ugliest place in the world. And you are going to keep going "
             "anyway. Full verse-and-hook: dark, defiant, the raw ugliness named and "
             "owned. Original lyrics, real rhythm, real rhyme. Include staging, e.g. "
             "[STAGING: Odysseus stands among the shades; the dancers close in; "
             "he does not flinch].",
             "song",
             "name the ugliness and own it — face it without flinching; the "
             "defiance earns its darkness",
             "triumphant, upbeat — this is the darkest place in the poem; "
             "earn the defiance"),
            ("NARRATOR",
             "CLOSE THE SCENE. One or two sentences of spare Homeric prose: the dead "
             "seen, the prophecy received, Odysseus turning back toward the light — "
             "carrying everything the dead have given him. The dancers return to "
             "stillness.",
             "dialogue",
             "close with the weight of what he carries back up",
             "light — this is the heaviest scene in the retrospective"),
        ],
        "brief": """\
BOOK XI — GET UGLY   (hidden brief)

Anchor song: Jason Derulo — "Get Ugly" → Odysseus's Underworld number. He faces
the ugliest place in the world — the dead mother, the cold prophecy — and keeps
going anyway.

Dramatic function: THE DESCENT. The Nekuia. Tiresias prophesies. Anticlea is the
gut-punch. The defiant return to the light.

Staging: dancers exclusively as the dead — they move through the room among the
tables, spooking the diners, but no audience pull. Spooky atmosphere, dark light.
""",
        "scene_context": """\
Book XI is THE DESCENT. Odysseus descends to the Underworld, consults Tiresias,
sees his dead mother Anticlea. He gets ugly — faces the cost — and returns.

Anchor song: Jason Derulo "Get Ugly" → Odysseus's number.

Dancers only as the dead — no audience pull. Dark atmosphere. Dancers move
among the tables. Mark beats with [STAGING: ...] lines.""",
        "staging_clause": STAGING_CLAUSE,
        "muse_setup": "the Underworld — Odysseus has descended to the land of the dead, and the dancers are waiting.",
        "muse_extra": (
            "Warn the room: this one gets dark. The dancers are the dead. "
            "They will move among you. Do not be afraid — or do."
        ),
        "title_md": "# ATHENA — Book XI: Get Ugly\n\n*Immersive dinner theater.*\n\n---\n",
    },

    "12": {
        "scene_file":    "scene_book12.md",
        "commit_prefix": "Book XII",
        "banner":        "🎭  ATHENA writers' room — Book XII: Outta Your Mind",
        "scene_id":      "Book XII — Outta Your Mind",
        "song_scaffold_key": "SIRENS_SONG",
        "turn_order": [
            ("SIRENS",
             "THE SONG. You sing to Odysseus — tied to his mast, the only man who will "
             "ever hear you and live. Offer him everything: all knowledge of Troy, the "
             "future, the most beautiful song in the world. Make it genuinely seductive. "
             "He is tied to a mast and straining at the ropes. Include staging, e.g. "
             "[STAGING: two dancers as the Sirens move toward Odysseus's ship; the crew "
             "rows with wax in their ears, seeing nothing].",
             "song",
             "make the song genuinely irresistible — the danger IS the beauty; "
             "this should be the most beautiful thing in the scene",
             "ugly, threatening — the Sirens are the most beautiful trap ever made"),
            ("ODYSSEUS",
             "PAST THE SIRENS. You heard it and survived. Narrate what it cost — "
             "straining at the ropes, begging the crew to free you, and they couldn't "
             "hear. That song will be in your head forever. Then: Scylla is ahead. "
             "You make the calculation: lose six men to Scylla or lose everything to "
             "Charybdis. You choose. Include staging, e.g. [STAGING: Odysseus narrates; "
             "the dancers as Scylla move through the ship; six dancers fall].",
             "dialogue",
             "narrate the calculation with honest coldness — you chose six men "
             "and you knew you were choosing them",
             "remorseful in the moment — you made the right call; own it"),
            ("SCYLLA",
             "THE TAKING. Six men. One per head. Brief, physical, final. Include "
             "staging, e.g. [STAGING: Scylla — dancers — move through the ship; "
             "six are taken, crying out, gone].",
             "dialogue",
             "be the hazard — physical, swift, impersonal; six men in six beats",
             "elaborate, explaining — you are a monster taking men; that's all"),
            ("ODYSSEUS",
             "THE CATTLE. You land on Thrinacia. You told the crew not to touch the "
             "cattle of the Sun. Tiresias told you. They are starving. You fell asleep. "
             "Narrate what happens with the weight of a man who knew it was coming and "
             "couldn't stop it. Include staging, e.g. [STAGING: Odysseus narrates, "
             "head bowed — he knew and he slept and they did it anyway].",
             "dialogue",
             "narrate the worst failure of the voyage — you warned them, you "
             "slept, they ate the cattle; carry it",
             "self-justifying — own the failure; you fell asleep"),
            ("NARRATOR",
             "CLOSE THE RETROSPECTIVE. Two sentences of spare Homeric prose: Zeus "
             "destroys the ship; the crew is lost, every last man; Odysseus alone "
             "drifts to Calypso's island — where Book V began. The retrospective "
             "closes; Odysseus has told his whole story.",
             "dialogue",
             "close the retrospective with the full weight of total loss — "
             "every man gone; the poem has come full circle",
             "brief — land the total cost; every man"),
        ],
        "brief": """\
BOOK XII — OUTTA YOUR MIND   (hidden brief)

Anchor song: Lil Jon — "Outta Your Mind" → the crew eating the sacred cattle.
They were warned by Tiresias, warned by Circe, warned by Odysseus. They ate
anyway. Outta their minds with hunger and desperation.

Dramatic function: THE TOTAL LOSS. The Sirens, Scylla, the sacred cattle, the
destruction of the ship. Every man lost. The retrospective ends.

Staging: Sirens and Scylla are dancers — no audience pull. Spooky/spectacular
choreography. The cattle scene is narrated, not staged.
""",
        "scene_context": """\
Book XII is THE TOTAL LOSS. The Sirens. Scylla takes six men. The crew eats the
sacred cattle against every warning. Zeus destroys the ship. Only Odysseus
survives. The retrospective ends here.

Anchor song: Lil Jon "Outta Your Mind" → the crew's fatal decision.

Sirens and Scylla are dancers. No audience pull. Mark beats with [STAGING: ...]
lines.""",
        "staging_clause": STAGING_CLAUSE,
        "muse_setup": "the final stretch of the wanderings — the Sirens, Scylla, and the cattle; the moment the crew goes outta their minds and Odysseus loses everyone.",
        "muse_extra": "",
        "title_md": "# ATHENA — Book XII: Outta Your Mind\n\n*Immersive dinner theater.*\n\n---\n",
    },

    "13": {
        "scene_file": "scene_book13.md",
        "commit_prefix": "Book XIII",
        "banner": "🎭  ATHENA writers' room — Book XIII: WOW",
        "scene_id": "Book XIII — WOW",
        "song_scaffold_key": "ODYSSEUS_WOW",
        "turn_order": [
            ("ODYSSEUS",
             "HOME AT LAST. The Phaeacians have set you sleeping on the shore of Ithaca. "
             "You wake and at first do not know it — a mist hides the land. Then you "
             "realize: you are HOME, after twenty years. Narrate the disbelief, the "
             "relief, the wariness. Include staging, e.g. [STAGING: Odysseus wakes "
             "alone on the shore; the mist lifts; he touches the ground of Ithaca].",
             "dialogue",
             "feel the ground of home under you after twenty years — disbelief and "
             "wariness both; you are not safe yet and you know it",
             "complacent, relieved — you are home but the work is just beginning"),
            ("ATHENA",
             "THE SCHEME. You appear — first as a young shepherd, then revealed as "
             "yourself, goddess to your favorite mortal. You and Odysseus are two of a "
             "kind: both cunning, both players. Lay out the plan: he must go disguised "
             "as a beggar, gather intelligence, find his allies, and strike when the "
             "moment is right. You disguise him. Include staging, e.g. [STAGING: Athena "
             "passes her hand over Odysseus; the king becomes a ragged old beggar].",
             "dialogue",
             "run the operation with your favorite mortal — you two are the smartest "
             "players in the poem and you enjoy each other; this is a partnership of equals",
             "subordinate, deferential — you are the goddess running this; he follows YOUR plan"),
            ("ODYSSEUS",
             "WOW — THE NUMBER. Post Malone's 'WOW' as contrafact. You are home and you "
             "are in rags and nobody knows the king just walked in. The low-key swagger "
             "of a man who has everything and is hiding all of it. Full verse-and-hook. "
             "Original lyrics, real rhythm, real rhyme. Include staging, e.g. [STAGING: "
             "Odysseus pulls the beggar's hood up; the disguise complete].",
             "song",
             "the quiet swagger of a king in disguise — you know who you are even if "
             "no one else does; wow, look what just walked in unrecognized",
             "boastful, loud — this is LOW-KEY swagger; the power is in the secret; "
             "Calypso, Circe, sea-witch — wrong register"),
            ("EUMAEUS",
             "FORESHADOW. As the scene closes, a brief beat: the loyal swineherd is "
             "mentioned or glimpsed — the first ally Odysseus will go to. Warm, loyal, "
             "grieving for a master he doesn't know is back. Brief. Include staging, "
             "e.g. [STAGING: in the distance, smoke rises from Eumaeus's hut — the "
             "first stop].",
             "dialogue",
             "establish the loyalty waiting for Odysseus — you are the first true "
             "ally, grieving and faithful",
             "aware that Odysseus is back — you have no idea; you are just keeping faith"),
            ("NARRATOR",
             "CLOSE THE SCENE. One or two sentences of spare Homeric prose: Odysseus "
             "home at last but hidden, the goddess his ally, the long game begun.",
             "dialogue",
             "close with the weight of the homecoming and the patience it will require",
             "triumphant — he's home but nothing is won yet"),
        ],
        "brief": """\
BOOK XIII — WOW   (hidden brief)

Anchor song: Post Malone — "WOW" → Odysseus's number. He is home after twenty
years — and immediately puts on rags. The low-key swagger of a king in disguise.

Dramatic function: THE RETURN. The Phaeacians deliver Odysseus to Ithaca. Athena
appears, they scheme as equals, and she disguises him as a beggar for the long
game ahead.

Staging: Athena and Odysseus as two cunning players enjoying each other. The
disguise goes on. No audience pull.
""",
        "scene_context": """\
Book XIII is THE RETURN. The Phaeacians deliver Odysseus sleeping to Ithaca. He
wakes home at last. Athena appears, schemes with him as an equal, and disguises
him as a beggar. The long game begins.

Anchor song: Post Malone "WOW" → Odysseus's number.

Athena runs the operation. Mark beats with [STAGING: ...] lines.""",
        "staging_clause": STAGING_CLAUSE,
        "muse_setup": "the shore of Ithaca — Odysseus is finally home after twenty years, and the goddess is about to turn the king into a beggar.",
        "muse_extra": "",
        "title_md": "# ATHENA — Book XIII: WOW\n\n*Immersive dinner theater.*\n\n---\n",
    },

    "14": {
        "scene_file": "scene_book14.md",
        "commit_prefix": "Book XIV",
        "banner": "🎭  ATHENA writers' room — Book XIV: Without Me",
        "scene_id": "Book XIV — Without Me",
        "song_scaffold_key": "ODYSSEUS_WITHOUT",
        "turn_order": [
            ("EUMAEUS",
             "WELCOME THE STRANGER. A ragged beggar comes to your hut. You don't know "
             "him — but you feed him, shelter him, treat him with dignity, because that "
             "is who you are. You speak of your lost master Odysseus with love and "
             "grief. Include staging, e.g. [STAGING: Eumaeus sets bread and wine before "
             "the beggar, his dogs settling at the stranger's feet].",
             "dialogue",
             "show hospitality without expecting anything — and grieve for your "
             "master openly; you are the most decent man in the poem and it costs "
             "you nothing to be kind",
             "suspicious, transactional — you give freely; that is your whole character"),
            ("ODYSSEUS",
             "THE TEST. You are the beggar. You test Eumaeus — spin a false tale of who "
             "you are, watch how he treats you, probe his loyalty. He passes every test "
             "without knowing it's a test. You feel the love this man has for you and "
             "you cannot yet reveal yourself. Include staging, e.g. [STAGING: Odysseus "
             "watches Eumaeus's face as he speaks of the lost king].",
             "dialogue",
             "test the loyalty while hiding the love — you are moved by this man's "
             "faith and you have to keep playing the beggar; that tension is the scene",
             "revealing, sentimental — you cannot reveal yourself yet; play the long game"),
            ("EUMAEUS",
             "THE FAITH. The beggar suggests Odysseus might still return. You have heard "
             "this too many times from too many liars looking for a meal. You refuse to "
             "hope — but the refusal is itself a kind of grief. Include staging, e.g. "
             "[STAGING: Eumaeus shakes his head, pours more wine, looks into the fire].",
             "dialogue",
             "refuse to hope because hope has hurt too much — your weariness is the "
             "measure of how long you've kept faith",
             "naively hopeful — you are guarding yourself against another disappointment"),
            ("ODYSSEUS",
             "WITHOUT ME — THE NUMBER. Halsey's 'Without Me' as contrafact. Everything "
             "fell apart without you — but this one man kept faith. The ache of the hole "
             "you left in this household, and the loyalty that survived it. Full "
             "verse-and-hook. Original lyrics, real rhythm, real rhyme. Sing it as the "
             "beggar but let the king's grief bleed through.",
             "song",
             "the ache of seeing what your absence cost and the loyalty that "
             "survived it — you are home and still hidden, watching a good man "
             "grieve for you",
             "self-pitying — this is about the loyalty, not just the loss; "
             "Calypso, Circe — wrong register"),
            ("NARRATOR",
             "CLOSE THE SCENE. One or two sentences of spare Homeric prose: the king "
             "fed by his own faithful servant, unrecognized, the reunion still to come.",
             "dialogue",
             "close with the quiet ache of the unrecognized homecoming",
             "triumphant — this is tender, not victorious"),
        ],
        "brief": """\
BOOK XIV — WITHOUT ME   (hidden brief)

Anchor song: Halsey — "Without Me" → Odysseus's number, sung as the beggar with
the king's grief bleeding through. Everything fell apart without him, but Eumaeus
kept faith.

Dramatic function: THE LOYAL SERVANT. Odysseus, disguised, shelters with Eumaeus
the swineherd, tests his loyalty, and finds it whole. The reunion held back.

Staging: Eumaeus's hut. Warm, intimate. No audience pull.
""",
        "scene_context": """\
Book XIV is THE LOYAL SERVANT. The disguised Odysseus comes to the hut of Eumaeus
the swineherd, who feeds and shelters him without knowing who he is. Odysseus
tests his loyalty and finds it true.

Anchor song: Halsey "Without Me" → Odysseus's number.

Eumaeus's hut, intimate. Mark beats with [STAGING: ...] lines.""",
        "staging_clause": STAGING_CLAUSE,
        "muse_setup": "the hut of the swineherd Eumaeus — where the disguised king finds the one servant who never stopped believing.",
        "muse_extra": "",
        "title_md": "# ATHENA — Book XIV: Without Me\n\n*Immersive dinner theater.*\n\n---\n",
    },

    "15": {
        "scene_file": "scene_book15.md",
        "commit_prefix": "Book XV",
        "banner": "🎭  ATHENA writers' room — Book XV: Bounce Back",
        "scene_id": "Book XV — Bounce Back",
        "song_scaffold_key": "ODYSSEUS_BOUNCE",
        "turn_order": [
            ("TELEMACHUS",
             "THE RETURN HOME. You have sailed back from Sparta, dodged the suitors' "
             "ambush (Athena warned you), and come to Eumaeus's hut. You are a different "
             "man than the boy who left — confident, road-tested. You don't yet know "
             "the beggar by the fire is your father. Include staging, e.g. [STAGING: "
             "Telemachus ducks into Eumaeus's hut, travel-worn and changed].",
             "dialogue",
             "arrive as the man you've become — and look right past the beggar who is "
             "your father; the dramatic irony is the whole scene",
             "boyish, uncertain — you have grown; carry it; the not-knowing is the point"),
            ("ATHENA",
             "PREPARE THE REVEAL. Unseen by Telemachus, you signal Odysseus — the moment "
             "is coming. You will lift the disguise. Brief, divine, stage-managing. "
             "Include staging, e.g. [STAGING: Athena appears at the door visible only "
             "to Odysseus; she beckons him outside].",
             "dialogue",
             "set up the most intimate recognition in the poem — you choose the "
             "moment; you are still running everything",
             "absent, passive — you are the director calling this scene"),
            ("EUMAEUS",
             "SENT TO THE PALACE. Telemachus sends you to tell Penelope he is home safe. "
             "You go — which clears the hut for the father-son reveal. Loyal, prompt, "
             "glad to carry good news to the queen. Include staging, e.g. [STAGING: "
             "Eumaeus sets out for the palace, leaving the beggar and the young master "
             "alone].",
             "dialogue",
             "carry the good news gladly — and unknowingly clear the room for the "
             "reunion; you are always doing the right thing",
             "reluctant — you are happy to serve; go"),
            ("TELEMACHUS",
             "ALONE WITH THE BEGGAR. Eumaeus gone, you and the beggar are alone. You "
             "treat him with courtesy — you are your father's son and Eumaeus's student "
             "in decency. You sense something but cannot name it. Include staging, e.g. "
             "[STAGING: Telemachus studies the beggar, troubled, not knowing why].",
             "dialogue",
             "extend courtesy to a stranger and feel something you can't explain — "
             "the blood pull you don't yet understand",
             "dismissive — you are decent to him; the unease is the recognition trying "
             "to surface"),
            ("ODYSSEUS",
             "BOUNCE BACK — THE NUMBER. Little Mix's 'Bounce Back' as contrafact. You "
             "are back on home soil, your son in front of you, and the disguise still "
             "holds. The bounce-back is bittersweet: so close, one lifted veil away. "
             "Full verse-and-hook. Original lyrics, real rhythm, real rhyme. Sing as "
             "the beggar with the father straining underneath.",
             "song",
             "the bittersweet bounce-back of being home with your son right there and "
             "still hidden — one disguise away from everything you lost",
             "triumphant — this is the ache of almost; the reveal hasn't happened yet; "
             "Calypso, Circe — wrong register"),
            ("NARRATOR",
             "CLOSE THE SCENE. One or two sentences of spare Homeric prose: father and "
             "son under one roof at last, unrecognized, the veil about to lift.",
             "dialogue",
             "close on the held breath before the recognition",
             "resolved — the reveal is Book XVI; hold the tension"),
        ],
        "brief": """\
BOOK XV — BOUNCE BACK   (hidden brief)

Anchor song: Little Mix — "Bounce Back" → Odysseus's number. Back on home soil,
his son in front of him, the disguise still holding. The bittersweet of almost.

Dramatic function: THE NON-RECOGNITION. Telemachus returns from Sparta, dodges
the ambush, comes to Eumaeus's hut — and does not recognize the beggar who is his
father. Athena prepares the reveal for Book XVI.

Staging: Eumaeus's hut. The dramatic irony of father and son unrecognized. No
audience pull.
""",
        "scene_context": """\
Book XV is THE NON-RECOGNITION. Telemachus returns from Sparta and comes to
Eumaeus's hut where his disguised father sits by the fire. He does not recognize
him. Athena sets up the reveal to come.

Anchor song: Little Mix "Bounce Back" → Odysseus's number.

The dramatic irony of the unrecognized father. Mark beats with [STAGING: ...] lines.""",
        "staging_clause": STAGING_CLAUSE,
        "muse_setup": "Eumaeus's hut — Telemachus comes home a changed man and sits down across from a beggar he does not know is his father.",
        "muse_extra": (
            "Set up the cruelest, sweetest irony of the night: a son and a father "
            "in the same small room, and the boy has no idea. Let the room ache "
            "for it."
        ),
        "title_md": "# ATHENA — Book XV: Bounce Back\n\n*Immersive dinner theater.*\n\n---\n",
    },

    "16": {
        "scene_file": "scene_book16.md",
        "commit_prefix": "Book XVI",
        "banner": "🎭  ATHENA writers' room — Book XVI: Lay",
        "scene_id": "Book XVI — Lay",
        "song_scaffold_key": "ODYSSEUS_LAY",
        "turn_order": [
            ("TELEMACHUS",
             "THE TRANSFORMATION. Athena draws the beggar outside and lifts the "
             "disguise — when the man returns he is changed, radiant, kingly. You think "
             "he is a god and you are afraid. Include staging, e.g. [STAGING: the beggar "
             "steps out, and the man who steps back in stands taller, transformed].",
             "dialogue",
             "react to the impossible — the beggar transformed into something "
             "godlike; fear before understanding",
             "calm, knowing — you don't understand yet; the fear is right"),
            ("ODYSSEUS",
             "THE REVEAL. You tell him: I am no god. I am your father. The man you have "
             "waited for your whole life. Lay it down — the disguise, the distance, the "
             "twenty years. This is the most intimate reunion in the poem. Include "
             "staging, e.g. [STAGING: Odysseus opens his arms; Telemachus, "
             "disbelieving, steps into them].",
             "dialogue",
             "reveal yourself to your son and let twenty years of held grief release "
             "— this is the reunion you crossed the world for",
             "guarded, cold — this is the one moment you let the armor all the way "
             "down; let it land"),
            ("TELEMACHUS",
             "THE EMBRACE. You cannot believe it and then you can. Twenty years without "
             "a father and he is here, holding you. Weep. Then: turn to business — you "
             "are your father's son, and there are suitors to deal with. Include "
             "staging, e.g. [STAGING: father and son weep; then Telemachus straightens, "
             "all business].",
             "dialogue",
             "break open and then pull together — the reunion and then the readiness; "
             "you are a man now and there is work",
             "purely emotional — feel it fully, then become the strategist your "
             "father needs"),
            ("ODYSSEUS",
             "LAY — THE NUMBER. Jason Derulo's 'Lay' as contrafact. Lay it all down — "
             "the years, the disguise, the distance between a father and a son who "
             "never knew each other. The plan forms as you sing: how the two of you "
             "will take back the house. Full verse-and-hook. Original lyrics, real "
             "rhythm, real rhyme. Include staging, e.g. [STAGING: father and son "
             "clasp hands; the plan begins].",
             "song",
             "the release of twenty years and the forging of a partnership with the "
             "son you finally have — intimacy turning into shared purpose",
             "boastful, distant — this is the most tender scene Odysseus gets; "
             "sea-witch, Calypso — wrong register entirely"),
            ("NARRATOR",
             "CLOSE THE SCENE. One or two sentences of spare Homeric prose: father and "
             "son reunited and allied, the plan set, the reckoning with the suitors "
             "now a matter of when.",
             "dialogue",
             "close on the alliance forged — the most important partnership in the "
             "back half of the poem",
             "ambiguous — this is a clear, earned moment of joy and resolve"),
        ],
        "brief": """\
BOOK XVI — LAY   (hidden brief)

Anchor song: Jason Derulo — "Lay" → Odysseus's number. Lay it all down — the
disguise, the distance, the twenty years between a father and son who never knew
each other.

Dramatic function: THE RECOGNITION. Athena lifts the disguise. Odysseus reveals
himself to Telemachus. The most intimate reunion in the poem, turning into the
alliance that will take back the house.

Staging: Eumaeus's hut. The reveal, the embrace, the plan. No audience pull.
""",
        "scene_context": """\
Book XVI is THE RECOGNITION. Athena lifts Odysseus's disguise and he reveals
himself to Telemachus. Father and son reunite, weep, and begin planning the
reckoning with the suitors.

Anchor song: Jason Derulo "Lay" → Odysseus's number.

The most intimate scene in the back half. Mark beats with [STAGING: ...] lines.""",
        "staging_clause": STAGING_CLAUSE,
        "muse_setup": "Eumaeus's hut — the disguise lifts, and a son meets his father for the first time as a man.",
        "muse_extra": "",
        "title_md": "# ATHENA — Book XVI: Lay\n\n*Immersive dinner theater.*\n\n---\n",
    },

    "17": {
        "scene_file": "scene_book17.md",
        "commit_prefix": "Book XVII",
        "banner": "🎭  ATHENA writers' room — Book XVII: Walk It Out",
        "scene_id": "Book XVII — Walk It Out",
        "song_scaffold_key": "ODYSSEUS_WALK",
        "turn_order": [
            ("ODYSSEUS",
             "BACK INTO THE PALACE. Disguised again as the beggar, you walk into your "
             "own hall for the first time in twenty years. You see the suitors at your "
             "tables, eating your house. You take it all in — cold, patient, cataloging. "
             "Include staging, e.g. [STAGING: the beggar shuffles into the great hall; "
             "the suitors barely glance at him].",
             "dialogue",
             "walk into your own stolen house and master your rage — every detail you "
             "catalog now is a debt you will collect; patience is the weapon",
             "explosive, impatient — the power is in the restraint; you wait"),
            ("NARRATOR",
             "ARGOS. The old dog Argos — Odysseus's own hound, now ancient and neglected "
             "on a dung heap — lifts his head. He alone knows his master through the "
             "disguise. He wags his tail once. And he dies. Spare Homeric prose; this "
             "is pure staging and the saddest beat in the poem. Include staging, e.g. "
             "[STAGING: a old dog on the dung heap lifts his head, knows the beggar, "
             "thumps his tail once, and dies; Odysseus wipes away a tear no one sees].",
             "dialogue",
             "land the Argos beat with total restraint — the dog who waited twenty "
             "years recognizes his master and lets go; do not overwrite it",
             "wordy, sentimental — this is spare and devastating; few words"),
            ("ANTINOUS",
             "ABUSE THE BEGGAR. The beggar asks for scraps. You — entitled, cruel — "
             "throw a footstool at him, hit him, mock him. You have no idea you are "
             "striking the king. Include staging, e.g. [STAGING: Antinous hurls a "
             "footstool; it strikes the beggar's shoulder; the beggar does not fall].",
             "dialogue",
             "abuse the helpless beggar for sport — this cruelty is the specific "
             "thing that will get you killed first; you are writing your own death",
             "restrained, decent — you are at your worst here; that's the point"),
            ("AMPHINOMUS",
             "THE DECENT ONE. You are uneasy at the abuse. You offer the beggar "
             "kindness — bread, a gentle word. Odysseus quietly warns you (in disguise) "
             "to leave before the reckoning comes. You feel the warning and you stay "
             "anyway. Include staging, e.g. [STAGING: Amphinomus presses bread into the "
             "beggar's hand, troubled].",
             "dialogue",
             "show the decency that won't save you — you sense the danger, you are "
             "warned, and you stay; that is the tragedy",
             "cruel, oblivious — you are the conscience who dies anyway"),
            ("ODYSSEUS",
             "WALK IT OUT — THE NUMBER. Usher's 'Walk It Out' as contrafact. You walk "
             "through your own hall, patient and watching, every insult a name on the "
             "list, the dog who knew you dead behind you. The slow walk of a man biding "
             "his time before the storm. Full verse-and-hook. Original lyrics, real "
             "rhythm, real rhyme.",
             "song",
             "the patient, watching walk through your stolen house — cold control, "
             "the list growing, the reckoning coming; you walk it out and you wait",
             "explosive — this is biding, not striking yet; the restraint is the power; "
             "Calypso, Circe — wrong register"),
            ("NARRATOR",
             "CLOSE THE SCENE. One or two sentences of spare Homeric prose: the beggar-"
             "king walking his own hall unknown, the dog dead, the suitors marked, the "
             "reckoning one day off.",
             "dialogue",
             "close with the patient menace of the disguised king in his own house",
             "light — the danger is coiling"),
        ],
        "brief": """\
BOOK XVII — WALK IT OUT   (hidden brief)

Anchor song: Usher — "Walk It Out" → Odysseus's number. The patient walk through
his own stolen hall, watching, cataloging, biding his time.

Dramatic function: THE RETURN TO THE PALACE. Odysseus, disguised, walks into his
own hall. Argos the old dog recognizes him and dies. The suitors abuse the beggar.
Amphinomus alone is kind — and is warned, and stays.

Staging: the great hall. Argos is pure staging — the saddest beat in the poem.
No audience pull. Dancers/cast only.
""",
        "scene_context": """\
Book XVII is THE RETURN TO THE PALACE. The disguised Odysseus walks into his own
hall. His old dog Argos recognizes him and dies. The suitors abuse the beggar;
Antinous throws a stool. Amphinomus is kind and is quietly warned to leave.

Anchor song: Usher "Walk It Out" → Odysseus's number.

Argos is a staging beat, no speaking. Mark beats with [STAGING: ...] lines.""",
        "staging_clause": STAGING_CLAUSE,
        "muse_setup": "the great hall of Ithaca — the king walks back into his own house in rags, and only his old dog knows him.",
        "muse_extra": (
            "Warn the room there's a heartbreak coming — an old dog who waited "
            "twenty years. And that the beggar taking abuse tonight is the king, "
            "keeping a list."
        ),
        "title_md": "# ATHENA — Book XVII: Walk It Out\n\n*Immersive dinner theater.*\n\n---\n",
    },

    "18": {
        "scene_file": "scene_book18.md",
        "commit_prefix": "Book XVIII",
        "banner": "🎭  ATHENA writers' room — Book XVIII: No Tears Left To Cry",
        "scene_id": "Book XVIII — No Tears Left To Cry",
        "song_scaffold_key": "PENELOPE_NOTEARS",
        "turn_order": [
            ("PENELOPE",
             "THE APPEARANCE. You come down into the hall — the first time the suitors "
             "have seen you in a while. Athena has made you radiant. You are not here "
             "to be admired; you are here to play them — to extract gifts, to keep them "
             "off balance, to remind them whose house this is. Include staging, e.g. "
             "[STAGING: Penelope descends the stairs; the hall goes quiet; every suitor "
             "turns].",
             "dialogue",
             "command the room you've been besieged in — you are not a prize, you are "
             "the player working every man here; let them think they're winning",
             "passive, victimized, dazzled — you are running this; they are your marks"),
            ("ANTINOUS",
             "THE SUITORS BITE. Penelope has them mesmerized. You promise gifts, you "
             "preen, you compete for her attention — exactly as she intended. Include "
             "staging, e.g. [STAGING: Antinous signals for gifts to be brought; the "
             "suitors scramble to outdo each other].",
             "dialogue",
             "be played without knowing it — you think you're courting; you're being "
             "milked for gifts by a smarter operator",
             "suspicious, wary — you are dazzled and manipulated; that's the joke"),
            ("EURYMACHUS",
             "THE SMOOTH PLAY. You lay on the charm, the flattery, the smooth talk — "
             "and Penelope takes your gifts and gives you nothing real. You congratulate "
             "yourself the whole time. Include staging, e.g. [STAGING: Eurymachus "
             "presents a golden necklace with a flourish; Penelope accepts it, "
             "unreadable].",
             "dialogue",
             "perform your charm and lose the exchange without realizing it — she "
             "out-games you completely",
             "aware you're being played — you think you're winning; you're not"),
            ("PENELOPE",
             "NO TEARS LEFT TO CRY — THE NUMBER. Ariana Grande's 'No Tears Left To Cry' "
             "as contrafact. Twenty years of grief have burned down to pure strategy. "
             "You're out of tears — what's left is the coldest, smartest game in the "
             "house. The suitors think they dazzle you; you're picking them clean. Full "
             "verse-and-hook. Original lyrics, real rhythm, real rhyme.",
             "song",
             "transform exhaustion into power — the tears are spent and what remains "
             "is a tactician who owns every man in this room while they think they "
             "own her",
             "weepy, fragile, victimized — this is strength forged from grief; "
             "she is the smartest player on the floor"),
            ("NARRATOR",
             "CLOSE THE SCENE. One or two sentences of spare Homeric prose: the queen "
             "having worked the room and walked out richer and untouched, the suitors "
             "preening over nothing, the disguised king watching his wife run the game.",
             "dialogue",
             "close on Penelope's mastery — and Odysseus watching, proud and unseen",
             "diminishing — let her win this scene outright"),
        ],
        "brief": """\
BOOK XVIII — NO TEARS LEFT TO CRY   (hidden brief)

Anchor song: Ariana Grande — "No Tears Left To Cry" → Penelope's number. Twenty
years of grief burned down to pure strategy. She's out of tears; what's left is
the smartest game in the house.

Dramatic function: PENELOPE'S MASTERY. She appears before the suitors and plays
them — extracting gifts, keeping them off balance — while the disguised Odysseus
watches his wife run the game. She is a tactician, not a victim.

Staging: the great hall. Penelope works the room. The disguised Odysseus watches.
No audience pull.
""",
        "scene_context": """\
Book XVIII is PENELOPE'S MASTERY. She appears before the suitors, radiant, and
plays them for gifts while keeping them off balance. The disguised Odysseus
watches his wife out-game a hall full of men.

Anchor song: Ariana Grande "No Tears Left To Cry" → Penelope's number.

Penelope is the smartest player in the room. Mark beats with [STAGING: ...] lines.""",
        "staging_clause": STAGING_CLAUSE,
        "muse_setup": "the great hall — the queen comes downstairs, and a room full of men who think they're hunting her are about to get played.",
        "muse_extra": (
            "Tell the room the queen is about to walk in, and every man here thinks "
            "he's got a shot — and not one of them realizes she's the smartest "
            "operator in the building."
        ),
        "title_md": "# ATHENA — Book XVIII: No Tears Left To Cry\n\n*Immersive dinner theater.*\n\n---\n",
    },

    "19": {
        "scene_file": "scene_book19.md",
        "commit_prefix": "Book XIX",
        "banner": "🎭  ATHENA writers' room — Book XIX: Savage Love",
        "scene_id": "Book XIX — Savage Love",
        "song_scaffold_key": "PENELOPE_SAVAGE",
        "turn_order": [
            ("ODYSSEUS",
             "THE INTERVIEW. Still the beggar, you are brought before Penelope. She "
             "questions you about the lost king. You spin a tale — you say you met "
             "Odysseus once, he is alive, he is near. You watch her face. You are "
             "talking to your wife and you cannot tell her. Include staging, e.g. "
             "[STAGING: the beggar sits across from Penelope in the firelight, the "
             "hall emptied for the interview].",
             "dialogue",
             "talk to your wife across a fire while hiding from her — the agony of "
             "near-recognition; you test her as you tested everyone",
             "revealing — you cannot reveal yourself yet; play it close"),
            ("PENELOPE",
             "THE NEAR-RECOGNITION. Something about this beggar. You almost know. You "
             "probe him — the details only Odysseus would know — and he answers them "
             "all. You are too smart not to suspect, and too careful to say. You hold "
             "it. Include staging, e.g. [STAGING: Penelope leans in, studying the "
             "beggar's face, a question forming she does not ask].",
             "dialogue",
             "almost know your husband and choose not to say it yet — you are testing "
             "HIM as much as he tests you; you hold the cards close because that's "
             "how you've survived",
             "naive, oblivious — you are the sharpest mind in the poem; you suspect "
             "and you wait"),
            ("EURYCLEIA",
             "THE SCAR. You are sent to wash the beggar's feet. Your hands find the scar "
             "on his thigh — the boar-hunt scar you have known since he was a boy. You "
             "KNOW. Your hand stops. Your heart stops. Include staging, e.g. [STAGING: "
             "Eurycleia's hand freezes on the scar; the basin tips; water spills].",
             "dialogue",
             "recognize your master in a single touch and nearly cry out — twenty "
             "years end in your hands in the dark",
             "calm, slow — this is a thunderbolt of recognition; let it land hard "
             "and fast"),
            ("ODYSSEUS",
             "THE SILENCING. You grip Eurycleia — by the throat, by the arm — and "
             "whisper: not yet, say nothing, or you doom us both. She obeys. The secret "
             "holds. Include staging, e.g. [STAGING: Odysseus seizes the old nurse; a "
             "whispered command; she nods, trembling, and keeps the secret].",
             "dialogue",
             "protect the whole plan in one swift silencing — gentle and absolute; "
             "she is loyal and she will hold",
             "violent, cruel — this is urgent, not brutal; she is your ally"),
            ("PENELOPE",
             "SAVAGE LOVE — THE NUMBER. Jason Derulo's 'Savage Love' as contrafact. "
             "Here is the savage thing: you've been faithful twenty years while he "
             "wandered, and now a stranger who knows too much sits at your fire and you "
             "have to play it cool. The double standard, the long game, the love that's "
             "survived as strategy. Full verse-and-hook. Original lyrics, real rhythm, "
             "real rhyme.",
             "song",
             "name the savage deal you've been handed — faithful while he roamed, and "
             "still you have to test and wait and hold your cards; the love is real "
             "and so is the grievance, and you play both",
             "purely romantic, purely sad — there's an edge here, a knowing about the "
             "double standard; she's a player too"),
            ("NARRATOR",
             "CLOSE THE SCENE. One or two sentences of spare Homeric prose: the scar "
             "known and the secret kept, husband and wife circling each other in the "
             "firelight, the recognition deferred to the queen's own chosen hour.",
             "dialogue",
             "close on the deferred recognition — Penelope will decide when, not him",
             "resolved — the recognition is hers to grant in Book XXIII"),
        ],
        "brief": """\
BOOK XIX — SAVAGE LOVE   (hidden brief)

Anchor song: Jason Derulo — "Savage Love" → Penelope's number. The savage deal:
faithful twenty years while he wandered, and now she has to play it cool with a
stranger who knows too much. The double standard named, the long game played.

Dramatic function: THE NEAR-RECOGNITION + THE SCAR. The disguised Odysseus is
interviewed by Penelope, who almost knows him. Eurycleia recognizes the scar and
is silenced. Penelope holds her cards — the recognition will be on her terms.

Staging: the hall by firelight. The scar scene. No audience pull.
""",
        "scene_context": """\
Book XIX is THE NEAR-RECOGNITION. Penelope interviews the disguised Odysseus and
almost knows him. The nurse Eurycleia recognizes the boar-hunt scar while washing
his feet; Odysseus silences her. Penelope holds her suspicion close.

Anchor song: Jason Derulo "Savage Love" → Penelope's number.

The scar recognition. Penelope as tactician. Mark beats with [STAGING: ...] lines.""",
        "staging_clause": STAGING_CLAUSE,
        "muse_setup": "the hall by firelight — a queen interrogates a beggar who knows too much, and an old nurse is about to feel a scar she has known for forty years.",
        "muse_extra": "",
        "title_md": "# ATHENA — Book XIX: Savage Love\n\n*Immersive dinner theater.*\n\n---\n",
    },

    "20": {
        "scene_file": "scene_book20.md",
        "commit_prefix": "Book XX",
        "banner": "🎭  ATHENA writers' room — Book XX: Up",
        "scene_id": "Book XX — Up",
        "song_scaffold_key": "ODYSSEUS_UP",
        "turn_order": [
            ("ODYSSEUS",
             "THE SLEEPLESS NIGHT. The eve of the reckoning. You lie awake in your own "
             "hall, disguised, rage and readiness coiling. You see the disloyal "
             "servants, you hear the suitors' confidence. Tomorrow it all goes up. "
             "Include staging, e.g. [STAGING: the beggar lies sleepless in the hall, "
             "eyes open in the dark, the house breathing around him].",
             "dialogue",
             "hold the coiled tension of the night before — everything you've waited "
             "twenty years for is one sunrise away; master the rage one more night",
             "calm, resolved — the tension is everything; you barely sleep"),
            ("ATHENA",
             "STEADY HIM. You appear to Odysseus in the night. Steady him — the plan is "
             "sound, the moment near, the gods are with him. Brief, divine, the "
             "commander's reassurance before the battle. Include staging, e.g. [STAGING: "
             "Athena appears in the dark above the sleepless king; a word, and she "
             "is gone].",
             "dialogue",
             "reassure your favorite before the storm — you've engineered this moment "
             "and you know it will hold",
             "uncertain, absent — you are the architect; tell him it's time"),
            ("ANTINOUS",
             "THE OMENS IGNORED. Morning. Strange omens fill the hall — a prophet sees "
             "blood, the suitors laugh uneasily. You dismiss it all, lead the others in "
             "mockery, double down on the feast. Include staging, e.g. [STAGING: "
             "Antinous laughs off a dark omen; the suitors follow, a little too loud].",
             "dialogue",
             "dismiss the warning and lead the others to their doom — your "
             "fearlessness is fatal blindness now",
             "afraid, heeding — you ignore every sign; that's why you die"),
            ("AMPHINOMUS",
             "THE LAST WARNING. You feel the dread in the room. The omens, the strange "
             "beggar, the queen's calm — something is coming. You almost leave. You "
             "don't. This is your last chance and you let it pass. Include staging, "
             "e.g. [STAGING: Amphinomus rises as if to go, hesitates at the door, and "
             "sits back down].",
             "dialogue",
             "feel the doom and fail to act on it one final time — the conscience who "
             "knows and stays; this is the last exit and you miss it",
             "oblivious, comfortable — you sense everything and stay anyway; tragedy"),
            ("ODYSSEUS",
             "UP — THE NUMBER. Cardi B's 'Up' as contrafact. Everything is about to go "
             "up. The trap is set, the bow is waiting, the suitors are blind, the dawn "
             "has come. The coiled, electric energy of the moment before the storm "
             "breaks. Full verse-and-hook. Original lyrics, real rhythm, real rhyme.",
             "song",
             "the electric readiness of the moment before everything blows — up, it's "
             "all about to go up; twenty years coiled into one held breath",
             "mournful, hesitant — this is Cardi B 'Up' energy: hard, ready, "
             "unstoppable; the storm one beat away"),
            ("NARRATOR",
             "CLOSE THE SCENE. One or two sentences of spare Homeric prose: the omens "
             "ignored, the trap set, the queen about to bring out the bow, the whole "
             "house one breath from the reckoning.",
             "dialogue",
             "close on the held breath — the next scene is the bow and the blood",
             "relaxed — the tension should be unbearable"),
        ],
        "brief": """\
BOOK XX — UP   (hidden brief)

Anchor song: Cardi B — "Up" → Odysseus's number. Everything about to go up. The
trap set, the bow waiting, the suitors blind, the dawn arrived.

Dramatic function: THE EVE OF THE RECKONING. The sleepless night, Athena's
reassurance, the ignored omens, Amphinomus's last missed chance to leave. The
coiled tension before the storm.

Staging: the hall at night and dawn. No audience pull. The tension is the scene.
""",
        "scene_context": """\
Book XX is THE EVE OF THE RECKONING. Odysseus lies sleepless; Athena steadies
him. Morning brings omens the suitors ignore. Amphinomus feels the doom and fails
to leave. Everything is one breath from the storm.

Anchor song: Cardi B "Up" → Odysseus's number.

The coiled tension before the slaughter. Mark beats with [STAGING: ...] lines.""",
        "staging_clause": STAGING_CLAUSE,
        "muse_setup": "the last night before the reckoning — the trap is set, the bow is waiting, and everything is about to go up.",
        "muse_extra": "",
        "title_md": "# ATHENA — Book XX: Up\n\n*Immersive dinner theater.*\n\n---\n",
    },

    "21": {
        "scene_file": "scene_book21.md",
        "commit_prefix": "Book XXI",
        "banner": "🎭  ATHENA writers' room — Book XXI: Black Widow",
        "scene_id": "Book XXI — Black Widow",
        "song_scaffold_key": "PENELOPE_BLACKWIDOW",
        "turn_order": [
            ("PENELOPE",
             "BRING OUT THE BOW. You announce the contest: string Odysseus's great bow "
             "and shoot an arrow through twelve axe-heads, and you will marry the winner. "
             "The suitors think it's a prize. It's a trap you've spun for years — only "
             "one man alive can string that bow. Include staging, e.g. [STAGING: "
             "Penelope brings out the great bow and sets up the twelve axes in a row].",
             "dialogue",
             "spring the trap you've been weaving for years — they think you're "
             "finally surrendering; you're setting the killing floor; you are the "
             "black widow and this is your web",
             "resigned, defeated, giving up — this is your masterstroke; you engineered "
             "this exact moment"),
            ("ANTINOUS",
             "THE FAILURE BEGINS. You take the bow confident and you cannot even bend "
             "it. You make excuses — the wood is cold, you'll try later — and pass it "
             "on. The mighty suitors humiliated by a bow. Include staging, e.g. "
             "[STAGING: Antinous strains at the bow, fails, covers with bluster, "
             "passes it down].",
             "dialogue",
             "fail at the bow and cover with excuses — your weakness exposed in front "
             "of everyone; the throne you claimed you can't even draw the bow for",
             "graceful, humble — you bluster and blame the bow; that's who you are"),
            ("EURYMACHUS",
             "THE SMOOTH FAILURE. You try the bow with all your charm and you fail too "
             "— and unlike Antinous, the failure frightens you. You see what it means: "
             "you are lesser men than the king whose house you've eaten. Include "
             "staging, e.g. [STAGING: Eurymachus fails at the bow, and for the first "
             "time real fear crosses his face].",
             "dialogue",
             "fail and feel the fear behind it — you're the smart one and you "
             "suddenly understand exactly what this means",
             "confident, untroubled — the fear is the recognition of doom; let it show"),
            ("PENELOPE",
             "BLACK WIDOW — THE NUMBER. Iggy Azalea's 'Black Widow' as contrafact. "
             "You've spun this web for twenty years — the weaving, the waiting, the "
             "contest none of them can win. The trap is closing and they don't even "
             "see it. The cold satisfaction of the long game paying off. Full "
             "verse-and-hook. Original lyrics, real rhythm, real rhyme.",
             "song",
             "savor the web closing — every thread you wove for twenty years pulling "
             "tight at once; you are the predator here and they walked right in",
             "passive, mournful, fragile — this is the black widow's triumph; she "
             "set this whole thing and it's working perfectly"),
            ("ODYSSEUS",
             "THE BEGGAR ASKS FOR THE BOW. Still disguised, you ask to try the bow. The "
             "suitors mock you — a beggar? But Penelope (who may now suspect) and "
             "Telemachus insist he be allowed. You take the bow. Include staging, e.g. "
             "[STAGING: the beggar takes up the great bow; the hall laughs; then he "
             "strings it in one smooth motion and the laughter stops].",
             "dialogue",
             "reveal your strength in one impossible motion — the beggar strings the "
             "bow no suitor could bend; the room realizes too late what just happened",
             "boastful, slow — let the action speak; the strung bow IS the reveal"),
            ("NARRATOR",
             "CLOSE THE SCENE. One or two sentences of spare Homeric prose: the bow "
             "strung in the beggar's hands, the arrow nocked, the suitors' laughter "
             "curdling to dread, the trap sprung and the storm about to break.",
             "dialogue",
             "close on the strung bow — the next scene is the slaughter",
             "relaxed — this is the trap snapping shut"),
        ],
        "brief": """\
BOOK XXI — BLACK WIDOW   (hidden brief)

Anchor song: Iggy Azalea — "Black Widow" → Penelope's number. She's spun this web
for twenty years; the bow contest is the trap closing. Only one man alive can
string that bow.

Dramatic function: THE TRAP SPRUNG. Penelope announces the bow contest. The
suitors fail one by one. The disguised Odysseus asks for the bow and strings it
in one motion. The reveal is one beat away.

Staging: the great hall, the bow, the twelve axes. No audience pull. Penelope's
long game pays off.
""",
        "scene_context": """\
Book XXI is THE TRAP SPRUNG. Penelope brings out Odysseus's bow and announces the
contest — string it and shoot through twelve axes. The suitors fail. The disguised
Odysseus strings it effortlessly. The reckoning is one beat away.

Anchor song: Iggy Azalea "Black Widow" → Penelope's number.

Penelope's twenty-year trap closes. Mark beats with [STAGING: ...] lines.""",
        "staging_clause": STAGING_CLAUSE,
        "muse_setup": "the great hall — the queen brings out the great bow and announces a contest none of these men can win. The web is closing.",
        "muse_extra": (
            "Tell the room the queen has spun a trap twenty years in the weaving, "
            "and the suitors are about to walk right into it — they think it's a "
            "wedding contest; it's a killing floor."
        ),
        "title_md": "# ATHENA — Book XXI: Black Widow\n\n*Immersive dinner theater.*\n\n---\n",
    },

    "22": {
        "scene_file": "scene_book22.md",
        "commit_prefix": "Book XXII",
        "banner": "🎭  ATHENA writers' room — Book XXII: All About That Bass",
        "scene_id": "Book XXII — All About That Bass",
        "song_scaffold_key": "ODYSSEUS_BASS",
        "turn_order": [
            ("ODYSSEUS",
             "THE REVEAL AND THE FIRST SHOT. You throw off the rags. You are Odysseus, "
             "and the bow is in your hands. Your first arrow takes Antinous in the "
             "throat as he drinks. The hall erupts. Include staging, e.g. [STAGING: "
             "Odysseus throws off the beggar's rags; the first arrow flies; Antinous "
             "falls. The dancers freeze, then scatter].",
             "dialogue",
             "drop the disguise and open the reckoning — twenty years of patience "
             "released in one shot; you are the king again and the floor is yours",
             "hesitant, merciful — this is the moment of no return; cold and total"),
            ("ANTINOUS",
             "THE FIRST TO FALL. You are mid-boast, mid-drink, when the arrow takes "
             "you. You never saw it coming — your contempt blinded you to the end. A "
             "few last shocked words, if any. Include staging, e.g. [STAGING: Antinous "
             "clutches at the arrow, the cup falling from his hand].",
             "dialogue",
             "die first and stunned — the ringleader who never believed this could "
             "happen; your blindness was total to the last second",
             "wise, prepared — you die shocked and uncomprehending; that's the justice"),
            ("EURYMACHUS",
             "THE LAST BARGAIN. You try what you do best — you talk. Blame it all on "
             "the dead Antinous, offer payment, beg for terms. Odysseus is not buying. "
             "Then you rally the suitors to fight. Include staging, e.g. [STAGING: "
             "Eurymachus pleads, then draws a sword and charges; an arrow takes him "
             "mid-stride].",
             "dialogue",
             "make your final smooth play and have it fail — the talker who can't "
             "talk his way out of this one; then die fighting",
             "silent, accepting — you bargain to the last; it's who you are"),
            ("LEODES",
             "THE PROPHET BEGS. You are the suitor who warned them, the seer they "
             "ignored. You go to Odysseus and beg: I never wronged your wife, I tried "
             "to stop them, I only read the omens. It is true. Odysseus kills you "
             "anyway. Include staging, e.g. [STAGING: Leodes kneels and clasps "
             "Odysseus's knees; Odysseus's blade does not pause].",
             "dialogue",
             "beg with the truth and die anyway — you were right about everything "
             "and it saves no one, least of all you; the tragedy of the unheeded "
             "conscience",
             "defiant, proud — you plead the truth; it doesn't matter; that's the "
             "horror of it"),
            ("ODYSSEUS",
             "ALL ABOUT THAT BASS — THE NUMBER. Meghan Trainor's 'All About That Bass' "
             "as contrafact, flipped hard: it's all about that bass now — loud, "
             "physical, final, the floor murdered, the reckoning total. Twenty years "
             "of patience paying out in one storm of justice. Full verse-and-hook. "
             "Original lyrics, real rhythm, real rhyme. Include staging, e.g. [STAGING: "
             "the dancers perform the slaughter as choreography — the floor is murdered, "
             "not the audience].",
             "song",
             "release twenty years of held rage as total reckoning — it's all about "
             "that bass now, the floor murdered, the house reclaimed; loud and final "
             "and earned",
             "playful, light — this is the slaughter; it's heavy and final; the "
             "dancers murder the FLOOR not the audience; keep it choreographic, "
             "not gratuitous"),
            ("NARRATOR",
             "CLOSE THE SCENE. One or two sentences of spare Homeric prose: the suitors "
             "dead to the last man, the hall cleansed, the disloyal servants judged, "
             "Odysseus standing in his reclaimed house with the bow still warm.",
             "dialogue",
             "close on the reckoning complete — the house reclaimed in blood",
             "light — this is the climax of the whole poem"),
        ],
        "brief": """\
BOOK XXII — ALL ABOUT THAT BASS   (hidden brief)

Anchor song: Meghan Trainor — "All About That Bass" → Odysseus's number, flipped
hard. It's all about that bass now: loud, physical, final. The floor murdered,
the house reclaimed.

Dramatic function: THE SLAUGHTER. Odysseus throws off the disguise and kills the
suitors. Antinous first, Eurymachus bargaining and dying, Leodes begging the truth
and dying anyway. Twenty years of patience paid in one storm.

Staging: the great hall. The slaughter is DANCERS ONLY, performed as choreography
— murdering the dance floor, NOT the audience. No audience pull. Keep it
choreographic, not gratuitous.
""",
        "scene_context": """\
Book XXII is THE SLAUGHTER. Odysseus reveals himself and kills the suitors —
Antinous first, then Eurymachus who bargains and dies, then Leodes who begs the
truth and dies anyway. The house is reclaimed in blood.

Anchor song: Meghan Trainor "All About That Bass" → Odysseus's number, flipped.

The slaughter is dancers only — murdering the dance floor, not the audience.
Choreographic, not gratuitous. Mark beats with [STAGING: ...] lines.""",
        "staging_clause": STAGING_CLAUSE,
        "muse_setup": "the great hall — the beggar is the king, the bow is strung, and the suitors are about to find out. Tonight we murder the dance floor.",
        "muse_extra": (
            "Tell the room: tonight the dancers murder the DANCE FLOOR — nobody's "
            "touching the diners. But the suitors? Their reckoning has come. "
            "Twenty years in the making."
        ),
        "title_md": "# ATHENA — Book XXII: All About That Bass\n\n*Immersive dinner theater.*\n\n---\n",
    },

    "23": {
        "scene_file": "scene_book23.md",
        "commit_prefix": "Book XXIII",
        "banner": "🎭  ATHENA writers' room — Book XXIII: New Rules",
        "scene_id": "Book XXIII — New Rules",
        "song_scaffold_key": "PENELOPE_NEWRULES",
        "turn_order": [
            ("EURYCLEIA",
             "THE NEWS. You rush to Penelope — it's over, the suitors are dead, the "
             "beggar was Odysseus all along, your husband is home. You are overjoyed "
             "and certain. Include staging, e.g. [STAGING: Eurycleia hurries up the "
             "stairs to wake the queen with the impossible news].",
             "dialogue",
             "bring the impossible news with total joy and certainty — you knew, you "
             "kept the secret, and now you get to tell her",
             "doubtful, restrained — you are certain and overjoyed; you felt the scar"),
            ("PENELOPE",
             "THE REFUSAL TO BELIEVE. You do not run downstairs weeping with joy. You "
             "are too smart for that — twenty years of liars and tricks. You will not "
             "accept this man as your husband until HE proves it on YOUR terms. You set "
             "the test. Include staging, e.g. [STAGING: Penelope descends slowly, "
             "studying the man who claims to be her husband, giving nothing away].",
             "dialogue",
             "refuse to be told who your husband is — you decide, you test, you "
             "control the terms of this reunion; you've earned the right to be sure",
             "swept away, instantly believing — you are the most careful mind in the "
             "poem; make him prove it"),
            ("ODYSSEUS",
             "THE TEST PASSED. Penelope orders the marriage bed moved from their chamber "
             "— and you react with anger, because you KNOW that bed cannot be moved: you "
             "built it yourself around a living olive tree rooted in the ground. Only "
             "the real Odysseus knows this. The secret sign. Include staging, e.g. "
             "[STAGING: Odysseus describes the bed built from the olive tree; Penelope's "
             "composure finally breaks].",
             "dialogue",
             "prove yourself with the one secret only you could know — the bed you "
             "built; let the indignation be real, because the bed is your marriage",
             "uncertain, pleading — you KNOW this secret; assert it with the "
             "confidence of the man who built the bed"),
            ("PENELOPE",
             "NEW RULES — THE NUMBER. Dua Lipa's 'New Rules' as contrafact. You don't "
             "just fall back into his arms — you have rules, and he just passed the only "
             "test that mattered. The bed test was YOURS. The recognition happens on "
             "YOUR terms, in YOUR time. Now — only now — you let him home. Full "
             "verse-and-hook. Original lyrics, real rhythm, real rhyme.",
             "song",
             "claim the reunion on your own terms — you set the rules, he passed the "
             "test, and only now do you choose to let him back in; the agency is "
             "entirely yours and you've earned it",
             "passive, swept-away, helpless — this is Penelope in full command of her "
             "own reunion; she decides; new rules, her rules"),
            ("NARRATOR",
             "CLOSE THE SCENE. One or two sentences of spare Homeric prose: husband and "
             "wife reunited at last on the queen's own terms, the secret of the bed the "
             "key that fit, twenty years ending not in surrender but in recognition "
             "freely granted.",
             "dialogue",
             "close on the reunion as Penelope's choice — not surrender, recognition "
             "granted on her terms",
             "diminishing her — center her agency in the close"),
        ],
        "brief": """\
BOOK XXIII — NEW RULES   (hidden brief)

Anchor song: Dua Lipa — "New Rules" → Penelope's number. She doesn't just fall
back into his arms — she has rules, and the bed test is hers. The recognition
happens on HER terms.

Dramatic function: THE REUNION ON HER TERMS. Eurycleia brings the news; Penelope
refuses to believe until Odysseus passes her test — the secret of the immovable
bed. Only then does she let him home. Her agency is the point.

Staging: the palace. The bed test. No audience pull. Penelope decides.
""",
        "scene_context": """\
Book XXIII is THE REUNION ON HER TERMS. Eurycleia tells Penelope the beggar was
Odysseus. Penelope refuses to believe until she tests him with the secret of
their immovable marriage bed. He passes. She chooses to accept him — on her terms.

Anchor song: Dua Lipa "New Rules" → Penelope's number.

Penelope controls the recognition. Mark beats with [STAGING: ...] lines.""",
        "staging_clause": STAGING_CLAUSE,
        "muse_setup": "the palace, after the storm — the suitors are dead, the king is home, and the queen is not about to just take anyone's word for it.",
        "muse_extra": (
            "Tell the room the queen has one last test — and that she'll decide "
            "when this reunion happens, not him. Twenty years; she's earned the "
            "right to be sure."
        ),
        "title_md": "# ATHENA — Book XXIII: New Rules\n\n*Immersive dinner theater.*\n\n---\n",
    },

    "24": {
        "scene_file": "scene_book24.md",
        "commit_prefix": "Book XXIV",
        "banner": "🎭  ATHENA writers' room — Book XXIV: Work",
        "scene_id": "Book XXIV — Work",
        "song_scaffold_key": "ODYSSEUS_WORK",
        "turn_order": [
            ("HERMES",
             "ESCORT THE DEAD. You lead the shades of the slaughtered suitors down to "
             "the underworld — gibbering, bewildered, stripped of all their swagger. In "
             "Hades they meet the great dead of Troy, who marvel that they died for a "
             "queen's hand and a king's vengeance. Brisk, wry, final — you open and "
             "close this poem. Include staging, e.g. [STAGING: Hermes leads a line of "
             "pale shades down into shadow; the dancers as the dead of Troy watch them "
             "pass].",
             "dialogue",
             "escort the suitors to their end with cold ceremony — you are the "
             "psychopomp closing the ledger; their swagger means nothing now",
             "warm, sentimental — you are the messenger of death; brisk and final"),
            ("LAERTES",
             "THE FATHER. On your farm, old and worn, you have nearly given up. Then "
             "Odysseus comes to you. At first you cannot believe — you've been fooled "
             "by grief too long. He proves it: the trees, the orchard you planted for "
             "him as a boy, named one by one. You break. Your son is home. Include "
             "staging, e.g. [STAGING: Laertes drops his spade among the trees; the old "
             "man and his son hold each other].",
             "dialogue",
             "come back to life at the return of your son — the father who retreated "
             "to the farm to grieve, restored in one impossible moment",
             "youthful, energetic — you are old and nearly broken; the joy reanimates you"),
            ("ODYSSEUS",
             "THREE GENERATIONS. You stand with your father Laertes and your son "
             "Telemachus — three generations of the line, armed together for the first "
             "and only time, as the suitors' families come for revenge. The house "
             "restored is a thing that must still be defended. Include staging, e.g. "
             "[STAGING: Odysseus, Telemachus, and Laertes stand together, armed, as the "
             "angry families approach].",
             "dialogue",
             "stand with your father and son and feel the line restored — but the "
             "work isn't done; the kingdom still has to be held",
             "finished, resting — the kingdom isn't won until peace is made; "
             "there's work yet"),
            ("ATHENA",
             "THE PEACE. The families of the suitors come for vengeance — the cycle "
             "could go on forever. You intervene: STOP. Enough blood. You broker the "
             "peace, restore order, and end the cycle by divine command. You have run "
             "this whole poem and now you close it. Include staging, e.g. [STAGING: "
             "Athena rises between the two sides; a thunderclap; the weapons fall].",
             "dialogue",
             "end the cycle of vengeance by command — you've stage-managed the entire "
             "epic and now you close it with peace; the goddess has the last word",
             "subordinate, minor — you are the architect of the whole poem; "
             "the resolution is yours to grant"),
            ("ODYSSEUS",
             "WORK — THE NUMBER. Britney Spears's 'Work' as contrafact. You wanted your "
             "kingdom back and you worked twenty years for it — the war, the wandering, "
             "the disguise, the slaughter, and even now the work of making peace. The "
             "restoration of everything takes work, and you did it. Full verse-and-hook. "
             "Original lyrics, real rhythm, real rhyme. The triumphant close of the "
             "whole epic.",
             "song",
             "claim the restoration as twenty years of work paid in full — the "
             "kingdom reclaimed, the line restored, the peace made; you wanted it, "
             "you worked, and now it's yours",
             "exhausted, bitter — this is the triumphant close of the whole poem; "
             "earned, not weary; the work paid off"),
            ("NARRATOR",
             "CLOSE THE POEM. Two or three sentences of spare Homeric prose closing the "
             "entire epic: the suitors dead and judged, the kingdom restored, the line "
             "of Laertes secure across three generations, Odysseus home and king again, "
             "the goddess's peace settling over Ithaca. The Odyssey ends. Then — a final "
             "word to the house from the world of the poem, the long song finally sung.",
             "dialogue",
             "close the ENTIRE epic with full weight — this is the last sentence of "
             "all twenty-four books; make it land like a benediction",
             "abrupt, small — this is the end of the whole Odyssey; give it gravity"),
        ],
        "brief": """\
BOOK XXIV — WORK   (hidden brief)

Anchor song: Britney Spears — "Work" → Odysseus's number, the triumphant close of
the whole epic. He wanted his kingdom back and worked twenty years for it — and
even the peace takes work.

Dramatic function: THE RESTORATION — the close of the entire poem. Hermes escorts
the suitors' shades to Hades. Odysseus reunites with his father Laertes. Three
generations stand armed together. The suitors' families come for revenge; Athena
intervenes and ends the cycle with peace.

Staging: the farm and the final confrontation. Athena closes the poem. No
audience pull. This is the finale of all 24 books.
""",
        "scene_context": """\
Book XXIV is THE RESTORATION and the close of the whole epic. Hermes leads the
suitors' shades to Hades. Odysseus reunites with Laertes. Three generations stand
together against the suitors' vengeful families. Athena intervenes, brokers peace,
and ends the cycle. The kingdom is restored.

Anchor song: Britney Spears "Work" → Odysseus's number — the triumphant finale.

This is the last book. Athena closes the poem. Mark beats with [STAGING: ...] lines.""",
        "staging_clause": STAGING_CLAUSE,
        "muse_setup": "the end of the journey — the suitors judged, the king reunited with his aged father, and a goddess about to bring twenty years of war to peace.",
        "muse_extra": (
            "This is the last book — the close of the whole long song. Tell the "
            "room what it took: twenty years, an ocean, an underworld, a slaughter "
            "— and that it all comes down to this. Send them out remembering they "
            "were part of it."
        ),
        "title_md": "# ATHENA — Book XXIV: Work\n\n*Immersive dinner theater.*\n\n---\n",
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
    "TELEMACHUS_DEAL": textwrap.dedent("""\
        ── SONG STRUCTURE TARGET ───────────────────────────────────────────
        Verse 1  (4 bars): the suitors, the feast, the twenty-year disgrace
        Pre-hook (2 bars): everyone keeps saying deal with it — you're done
        Hook     (4 bars): "Deal with it / [rhyme]" — the refusal, the rage
        Verse 2  (4 bars): Athena's spark, the father coming home, the choice
        Bridge   (2 bars): direct address to the suitors — this ends now
        [STAGING lines at the confrontation moment]
    """),
    "TELEMACHUS_FAST": textwrap.dedent("""\
        ── SONG STRUCTURE TARGET ───────────────────────────────────────────
        Verse 1  (4 bars): the assembly, the suitors shouted down, the decision made
        Pre-hook (2 bars): the crew assembling, the ship ready
        Hook     (4 bars): "Fast / [rhyme]" — moving, finally moving
        Verse 2  (4 bars): the journey ahead, the father to find, the man becoming
        Bridge   (2 bars): direct address to the crew rising from the tables
        [STAGING lines at the crew-assembly moment]
    """),
    "TELEMACHUS_FREAK": textwrap.dedent("""\
        ── SONG STRUCTURE TARGET ───────────────────────────────────────────
        Verse 1  (4 bars): arriving at Pylos, the great king, the heroes of Troy
        Pre-hook (2 bars): the world is bigger than Ithaca ever was
        Hook     (4 bars): "Freak / [rhyme]" — the intoxication of the wider world
        Verse 2  (4 bars): Nestor's stories, the father's legend, becoming
        Bridge   (2 bars): direct address — I'm not the boy from Ithaca anymore
        [STAGING lines at the court celebration moment]
    """),
    "TELEMACHUS_RUDE": textwrap.dedent("""\
        ── SONG STRUCTURE TARGET ───────────────────────────────────────────
        Verse 1  (4 bars): Sparta, Helen's recognition, Menelaus's confirmation
        Pre-hook (2 bars): father alive — the whole journey justified
        Hook     (4 bars): "Rude boy / [rhyme]" — coming home, coming for what's his
        Verse 2  (4 bars): the suitors won't know what hit them; the man he's become
        Bridge   (2 bars): direct address to Ithaca — I'm on my way
        [STAGING lines at the moment Telemachus looks like his father]
    """),
    "ODYSSEUS_RAIN": textwrap.dedent("""\
        ── SONG STRUCTURE TARGET ───────────────────────────────────────────
        Verse 1  (4 bars): the storm, the raft destroyed, the days in the water
        Pre-hook (2 bars): everything came down — and you're still here
        Hook     (4 bars): "Rain on me / [rhyme]" — defiant survival
        Verse 2  (4 bars): Nausicaa, the shore, the first kindness in years
        Bridge   (2 bars): the stubborn fact of still being alive
        [STAGING lines at the shift from blue storm-light to gold]
    """),
    "ODYSSEUS_MIC": textwrap.dedent("""\
        ── SONG STRUCTURE TARGET ───────────────────────────────────────────
        Verse 1  (4 bars): the court, the anonymity, the weight of the name unsaid
        Pre-hook (2 bars): they want to know — you're about to tell them
        Hook     (4 bars): "Mic drop / [rhyme]" — the name, the legend, the silence after
        Verse 2  (4 bars): Troy, the wanderings, the man standing in front of them
        Bridge   (2 bars): the name is the weapon; drop it
        [STAGING lines at the moment the court goes silent]
    """),
    "ODYSSEUS_EVERYDAY": textwrap.dedent("""\
        ── SONG STRUCTURE TARGET ───────────────────────────────────────────
        Verse 1  (4 bars): every day of the war — the grinding accumulation
        Pre-hook (2 bars): every day another thing lost
        Hook     (4 bars): "Every day / [rhyme]" — relentless, heavy, alive
        Verse 2  (4 bars): every day of the voyage — the cost named one by one
        Bridge   (2 bars): every day you kept going anyway
        [STAGING lines as the shades of the dead move through the court]
    """),
    "ODYSSEUS_GETUGLY": textwrap.dedent("""\
        ── SONG STRUCTURE TARGET ───────────────────────────────────────────
        Verse 1  (4 bars): the Underworld, the cold, the dead pressing in
        Pre-hook (2 bars): the mother, the prophecy, the cost named plain
        Hook     (4 bars): "Get ugly / [rhyme]" — face it, name it, own it
        Verse 2  (4 bars): everything the journey has taken; what's still ahead
        Bridge   (2 bars): you are going back up into the light anyway
        [STAGING lines as the dancers as shades close in around Odysseus]
    """),
    "ODYSSEUS_BADHABITS": textwrap.dedent("""\
        ── SONG STRUCTURE TARGET ───────────────────────────────────────────
        Verse 1  (4 bars): the bad habits — raiding the Cicones, the Lotus Eaters
        Pre-hook (2 bars): you knew better; you never learn
        Hook     (4 bars): "Bad habits / [rhyme]" — the flaw named plain
        Verse 2  (4 bars): the Cyclops, the trick, the ships clear — and then
        Bridge   (2 bars): you shouted your name; you knew what it would cost
        [STAGING lines at the moment the name is shouted]
    """),
    "SIRENS_SONG": textwrap.dedent("""\
        ── SONG STRUCTURE TARGET ───────────────────────────────────────────
        Verse 1  (4 bars): we know everything — Troy, the dead, what's coming
        Pre-hook (2 bars): we will tell you; just come a little closer
        Hook     (4 bars): the offer — all knowledge, total beauty, just stop
        Verse 2  (4 bars): we know what you want most; we have it; come
        Bridge   (2 bars): the ropes are the only thing between you and us
        [STAGING lines showing Odysseus straining at the mast]
    """),
    "ODYSSEUS_WOW": textwrap.dedent("""\
        ── SONG STRUCTURE TARGET ───────────────────────────────────────────
        Verse 1  (4 bars): home at last — and immediately putting on rags
        Pre-hook (2 bars): twenty years to get here and you can't even show your face
        Hook     (4 bars): "Wow / [rhyme]" — the low-key swagger of a king in disguise
        Verse 2  (4 bars): the long game ahead; the patience it will take
        Bridge   (2 bars): nobody knows who just walked in — wow
        [STAGING lines as the disguise goes on]
    """),
    "ODYSSEUS_WITHOUT": textwrap.dedent("""\
        ── SONG STRUCTURE TARGET ───────────────────────────────────────────
        Verse 1  (4 bars): the faithful servant grieving a master who isn't gone
        Pre-hook (2 bars): everything fell apart without me — but someone kept faith
        Hook     (4 bars): "Without me / [rhyme]" — the ache of the hole you left
        Verse 2  (4 bars): testing the loyalty, the disguise holding, the love underneath
        Bridge   (2 bars): you don't know it yet, but I'm already home
        [STAGING lines at Eumaeus's hut]
    """),
    "ODYSSEUS_BOUNCE": textwrap.dedent("""\
        ── SONG STRUCTURE TARGET ───────────────────────────────────────────
        Verse 1  (4 bars): the son returns, the father a beggar in front of him
        Pre-hook (2 bars): so close, and the disguise still holds between you
        Hook     (4 bars): "Bounce back / [rhyme]" — back on home soil, still hidden
        Verse 2  (4 bars): the recognition coming, the years almost over
        Bridge   (2 bars): one lifted disguise away from everything
        [STAGING lines as father and son stand unrecognized]
    """),
    "ODYSSEUS_LAY": textwrap.dedent("""\
        ── SONG STRUCTURE TARGET ───────────────────────────────────────────
        Verse 1  (4 bars): Athena lifts the disguise; the father revealed
        Pre-hook (2 bars): lay it all down — the rags, the distance, the years
        Hook     (4 bars): "Lay / [rhyme]" — the most intimate reunion in the poem
        Verse 2  (4 bars): father and son, the plan forming, the tears
        Bridge   (2 bars): no more hiding between us now
        [STAGING lines at the embrace]
    """),
    "ODYSSEUS_WALK": textwrap.dedent("""\
        ── SONG STRUCTURE TARGET ───────────────────────────────────────────
        Verse 1  (4 bars): walking back into your own palace in rags
        Pre-hook (2 bars): the dog who waited knows you — and lets go
        Hook     (4 bars): "Walk it out / [rhyme]" — patient, watching, biding
        Verse 2  (4 bars): the suitors abuse the beggar; you take it; you wait
        Bridge   (2 bars): every insult is a name on the list
        [STAGING lines — Argos, the walk through the hall]
    """),
    "PENELOPE_NOTEARS": textwrap.dedent("""\
        ── SONG STRUCTURE TARGET ───────────────────────────────────────────
        Verse 1  (4 bars): twenty years of crying — you're out of tears
        Pre-hook (2 bars): the suitors think they dazzle you; you're playing them
        Hook     (4 bars): "No tears left / [rhyme]" — exhausted strength, pure strategy
        Verse 2  (4 bars): the long game you've run; the throne you've held
        Bridge   (2 bars): you don't break — you calculate
        [STAGING lines as Penelope works the room]
    """),
    "PENELOPE_SAVAGE": textwrap.dedent("""\
        ── SONG STRUCTURE TARGET ───────────────────────────────────────────
        Verse 1  (4 bars): a stranger at your hearth who knows too much
        Pre-hook (2 bars): twenty years faithful — and you get interrogated?
        Hook     (4 bars): "Savage / [rhyme]" — the double standard named, the game played
        Verse 2  (4 bars): the almost-recognition; you test him as he tested everyone
        Bridge   (2 bars): you've been the smartest one in the room the whole time
        [STAGING lines — the interview, the firelight]
    """),
    "ODYSSEUS_UP": textwrap.dedent("""\
        ── SONG STRUCTURE TARGET ───────────────────────────────────────────
        Verse 1  (4 bars): the night before; the omens; the coiled readiness
        Pre-hook (2 bars): everything you've waited for is one day away
        Hook     (4 bars): "Up / [rhyme]" — it's about to go up; the calm before
        Verse 2  (4 bars): the suitors oblivious; the trap set; the bow waiting
        Bridge   (2 bars): tomorrow the whole thing blows
        [STAGING lines — the restless hall at night]
    """),
    "PENELOPE_BLACKWIDOW": textwrap.dedent("""\
        ── SONG STRUCTURE TARGET ───────────────────────────────────────────
        Verse 1  (4 bars): you bring out the bow — the contest is your move
        Pre-hook (2 bars): they think it's a prize; it's a trap you've spun for years
        Hook     (4 bars): "Black widow / [rhyme]" — the web closing, the kill set up
        Verse 2  (4 bars): string the bow, win the queen — none of them can
        Bridge   (2 bars): you've been weaving this exact moment the whole time
        [STAGING lines — the bow, the axes, the suitors lining up to fail]
    """),
    "ODYSSEUS_BASS": textwrap.dedent("""\
        ── SONG STRUCTURE TARGET ───────────────────────────────────────────
        Verse 1  (4 bars): the bow strung, the arrow through the axes, the reveal
        Pre-hook (2 bars): the suitors realize who just stood up
        Hook     (4 bars): "All about that bass / [rhyme]" — it's about to get loud and final
        Verse 2  (4 bars): the slaughter; the floor murdered; the reckoning
        Bridge   (2 bars): twenty years of patience paid in one storm
        [STAGING lines — dancers as the slaughter; murdering the dance floor, NOT the audience]
    """),
    "PENELOPE_NEWRULES": textwrap.dedent("""\
        ── SONG STRUCTURE TARGET ───────────────────────────────────────────
        Verse 1  (4 bars): the slaughter's over and you STILL don't just take him back
        Pre-hook (2 bars): you have rules; he passes them or he doesn't
        Hook     (4 bars): "New rules / [rhyme]" — the bed test, the reunion on your terms
        Verse 2  (4 bars): the secret only he knows; the proof you demand
        Bridge   (2 bars): you decide when this is over — and now it is
        [STAGING lines — the bed test, the recognition]
    """),
    "ODYSSEUS_WORK": textwrap.dedent("""\
        ── SONG STRUCTURE TARGET ───────────────────────────────────────────
        Verse 1  (4 bars): the kingdom's not restored just because the suitors are dead
        Pre-hook (2 bars): the families want revenge; the work isn't done
        Hook     (4 bars): "Work / [rhyme]" — twenty years of work, and still more
        Verse 2  (4 bars): Laertes armored, Athena intervening, peace brokered
        Bridge   (2 bars): you wanted your kingdom back — you worked for it
        [STAGING lines — Laertes rises; Athena calls the halt; restoration]
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
