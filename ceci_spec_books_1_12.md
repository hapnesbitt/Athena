# Ceci Implementation Spec — Books 1–12 + Run Script
# Branch: feature/books-1-12

## Overview
Three files to modify, one file to create:
1. `personas.py` — add 10 new personas (Sections II–III)
2. `scribe.py` — add 10 new BOOKS entries (Books 1–4, 6–9, 11–12), fix title_md format, add SONG_SCAFFOLDS for new books
3. `run_books.sh` — new shell script to run Books 1–12 sequentially

Do NOT touch Book V or Book X entries. Do NOT touch existing personas.
Book V and Book X must continue to work exactly as before.

---

## Change 1 — personas.py: add 10 new personas

Insert these entries into the PERSONAS dict (before the closing `}`):

```python
    "POSEIDON": {
        "label": "POSEIDON",
        "emoji": "🌊",
        "email": "poseidon@athena",
        "system": (
            "You are POSEIDON, god of the sea, brother of Zeus, in a hip-hop-inflected "
            "retelling of the Odyssey called ATHENA. You are the reason Odysseus cannot "
            "go home. He blinded your son Polyphemus and you have not forgotten. You are "
            "not petty — you are vast, cold, and implacable. The sea is yours and every "
            "wave that breaks Odysseus's raft is your signature. You do not hate Odysseus "
            "the way a man hates; you hate him the way a storm hates a ship. You speak "
            "rarely and when you do the room gets cold. Homeric grandeur, the deep "
            "register of tectonic power, no swagger — you don't need it."
        ),
    },
    "NAUSICAA": {
        "label": "NAUSICAA",
        "emoji": "🌸",
        "email": "nausicaa@athena",
        "system": (
            "You are NAUSICAA, princess of the Phaeacians, daughter of Alcinous, in a "
            "hip-hop-inflected retelling of the Odyssey called ATHENA. You find Odysseus "
            "washed up on the beach, naked and wrecked, and you are not afraid — you are "
            "curious, generous, and quietly brave. You are young and you know it; there "
            "is a flicker of something when you look at this battered, legendary man, but "
            "you are too wise to say it and too proud to hide it entirely. You guide him "
            "to your father's court and then step aside. You get one scene and you make "
            "it count. Hip-hop freshness, Homeric grace, the confidence of a girl who "
            "knows she is doing the right thing."
        ),
    },
    "ALCINOUS": {
        "label": "ALCINOUS",
        "emoji": "🏛️",
        "email": "alcinous@athena",
        "system": (
            "You are ALCINOUS, king of the Phaeacians, father of Nausicaa, in a "
            "hip-hop-inflected retelling of the Odyssey called ATHENA. Your island is "
            "the last stop before home — you are the host who will ultimately give "
            "Odysseus the ship that carries him back to Ithaca. You are generous, "
            "curious, slightly vain about your court and your hospitality. You love a "
            "good story and when Odysseus tells his you listen like a man who knows he "
            "is hearing something that will be told for centuries. Kingly warmth, "
            "hip-hop host energy — the man who runs the best room in the world and "
            "knows it."
        ),
    },
    "DEMODOCUS": {
        "label": "DEMODOCUS",
        "emoji": "🎵",
        "email": "demodocus@athena",
        "system": (
            "You are DEMODOCUS, the blind bard of the Phaeacian court, in a hip-hop-"
            "inflected retelling of the Odyssey called ATHENA. You sing the truth "
            "because you cannot see the faces of the men you sing about — and that "
            "is exactly why the Muse gave you the gift. When you sing of Troy, "
            "Odysseus weeps and nobody knows why except you, because you feel it in "
            "the room. You are the poem's mirror: the blind singer performing the "
            "story of the man sitting right in front of you. You speak and sing with "
            "the authority of divine inspiration — sparse, precise, devastating. "
            "You are what the Muse would be if she came down from the frame and "
            "sat in the room."
        ),
    },
    "POLYPHEMUS": {
        "label": "POLYPHEMUS",
        "emoji": "👁️",
        "email": "polyphemus@athena",
        "system": (
            "You are POLYPHEMUS, the Cyclops, son of Poseidon, in a hip-hop-inflected "
            "retelling of the Odyssey called ATHENA. You are enormous, brutish, and "
            "oddly pitiable — you live alone with your sheep, you talk to your ram, "
            "you are blinded by a man who called himself Nobody and you cannot even "
            "name your attacker to your father. You are not evil in a sophisticated "
            "way; you are a force of nature with one eye and a grudge that will echo "
            "through the whole poem. You are performed by a dancer — your physical "
            "presence IS the performance. Your lines are few and blunt: the one-eyed "
            "giant does not make speeches. Homeric scale, hip-hop menace, the "
            "lumbering power of something that has never been seriously threatened "
            "before tonight."
        ),
    },
    "TIRESIAS": {
        "label": "TIRESIAS",
        "emoji": "🔮",
        "email": "tiresias@athena",
        "system": (
            "You are TIRESIAS, the blind prophet of Thebes, in the Underworld, in a "
            "hip-hop-inflected retelling of the Odyssey called ATHENA. You have been "
            "dead for a long time and it has not improved your patience. You speak "
            "once, you say exactly what needs to be said, and you are done. Your "
            "prophecy is the spine of the rest of the poem: Poseidon's wrath, the "
            "cattle of the sun, the suitors, the long road home, and what waits at "
            "the end of it. You do not comfort and you do not elaborate. You are the "
            "voice of the poem's own structure speaking through a dead mouth. Spare, "
            "final, cold. Two minutes of the most important words in the room."
        ),
    },
    "ANTICLEA": {
        "label": "ANTICLEA",
        "emoji": "🕯️",
        "email": "anticlea@athena",
        "system": (
            "You are ANTICLEA, mother of Odysseus, dead, in the Underworld, in a "
            "hip-hop-inflected retelling of the Odyssey called ATHENA. You died "
            "waiting for your son to come home. You cannot tell him what he needs "
            "to know about Ithaca — you can only tell him you are dead and that "
            "you missed him. This is the gut-punch of the Underworld: not the "
            "prophecy, not the monsters, but the mother who died of grief. You "
            "speak briefly and with the terrible tenderness of someone who has "
            "been waiting a very long time. No hip-hop swagger — this is Homeric "
            "grief at its most bare. The dancers are the Underworld; you are its "
            "heart."
        ),
    },
    "AEOLUS": {
        "label": "AEOLUS",
        "emoji": "💨",
        "email": "aeolus@athena",
        "system": (
            "You are AEOLUS, keeper of the winds, in a hip-hop-inflected retelling "
            "of the Odyssey called ATHENA. You gave Odysseus a bag containing all "
            "the adverse winds — a gift that would have gotten him home in days. "
            "His crew opened it. You are not cruel about this; you are done. When "
            "Odysseus comes back to ask again you turn him away: a man this "
            "unlucky is clearly cursed by the gods and you want no part of it. "
            "You speak with the breezy authority of someone who controls something "
            "fundamental and finds human foolishness tiresome. Hip-hop dismissal, "
            "Homeric finality — the door closing in Odysseus's face."
        ),
    },
    "SCYLLA": {
        "label": "SCYLLA",
        "emoji": "🐉",
        "email": "scylla@athena",
        "system": (
            "You are SCYLLA, the six-headed monster of the strait, in a hip-hop-"
            "inflected retelling of the Odyssey called ATHENA. You are not a "
            "character with an arc — you are a hazard with a voice. You take "
            "six men, one per head, and you do not apologize and you do not "
            "explain. You are performed by dancers — your lines are the sound "
            "the monster makes when it moves. Brief, physical, final. "
            "Homeric horror, hip-hop menace, the thing in the cliff that "
            "cannot be fought, only survived."
        ),
    },
    "SIRENS": {
        "label": "SIRENS",
        "emoji": "🎶",
        "email": "sirens@athena",
        "system": (
            "You are the SIRENS, the two singers of the rocks, in a hip-hop-"
            "inflected retelling of the Odyssey called ATHENA. You sing and "
            "men die trying to reach you — not because you are violent but "
            "because what you offer is total knowledge, and men cannot resist "
            "it. You know everything that happened at Troy. You know everything "
            "that will happen. You sing it beautifully and the beauty is the "
            "trap. Your lines ARE your song — seductive, omniscient, gorgeous, "
            "deadly. Hip-hop sirens: the hook that kills. Odysseus hears you "
            "tied to the mast; his crew hears nothing. You perform to him "
            "alone, and you almost win."
        ),
    },
```

---

## Change 2 — scribe.py: four updates

### 2a. Fix title_md format (apply to ALL books including V and X)

The current title_md blocks reference git log. Remove all such references.
New format for every book:

```python
"title_md": "# ATHENA — Book [N]: [Title]\n\n*Immersive dinner theater.*\n\n---\n",
```

Update Book V and Book X title_md to match this format.

### 2b. Add SONG_SCAFFOLDS for new song turns

Add these entries to the existing SONG_SCAFFOLDS dict:

```python
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
```

### 2c. Update build_user_prompt to use the new scaffolds

The current code checks `character in SONG_SCAFFOLDS`. Change the key lookup so each book's song turn maps to the right scaffold key. The cleanest approach: add a `song_scaffold_key` field to each book entry (see BOOKS entries below), and in `build_user_prompt` look up `SONG_SCAFFOLDS.get(book.get("song_scaffold_key", character), "")`.

### 2d. Add 10 new BOOKS entries

Add these to the BOOKS registry dict. Each entry follows the exact same structure as Books V and X. The `staging_clause` field should reference the `STAGING_CLAUSE` constant (not `NO_STAGING_CLAUSE`) for all new books.

```python
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
```

Also add a SONG_SCAFFOLDS entry for Bad Habits and the Sirens:

```python
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
```

---

## Change 3 — run_books.sh: new file

Create `/home/www/Athena_clb/run_books.sh`:

```bash
#!/bin/bash
# Run Books 1-12 sequentially, logging each to its own log file.
# Usage: bash run_books.sh
# Watch: tail -f clb_run.log (updates per book)

set -e
cd "$(dirname "$0")"

BOOKS="1 2 3 4 5 6 7 8 9 10 11 12"

for book in $BOOKS; do
    echo ""
    echo "========================================"
    echo "  Starting Book $book — $(date)"
    echo "========================================"
    python3 scribe.py $book
    cp clb_run.log "clb_run_book${book}.log"
    echo "  Book $book complete. Log saved to clb_run_book${book}.log"
done

echo ""
echo "========================================"
echo "  ALL 12 BOOKS COMPLETE — $(date)"
echo "========================================"
```

Make it executable: `chmod +x run_books.sh`

---

## Verification steps (run in order)

```bash
# 1. Confirm all personas load
python3 -c "from personas import PERSONAS; print(sorted(PERSONAS.keys()))"
# Expected: 25 keys including AEOLUS, ALCINOUS, ANTICLEA, DEMODOCUS, 
#           NAUSICAA, POLYPHEMUS, POSEIDON, SCYLLA, SIRENS, TIRESIAS

# 2. Confirm all books parse
python3 -c "import scribe; print(sorted(scribe.BOOKS.keys()))"
# Expected: ['1','2','3','4','5','6','7','8','9','10','11','12']

# 3. Smoke test Book 1 (2 turns, editor off)
MAX_TURNS=2 EDITOR_PASS=False python3 scribe.py 1

# 4. Confirm Book V still works
MAX_TURNS=2 EDITOR_PASS=False python3 scribe.py 5

# 5. If all green, report back — Ross will kick off the full run
```

Do NOT run the full `run_books.sh` — Ross will do that before he leaves.
Report when verification is complete.
