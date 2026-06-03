# ATHENA — The HipHop Odyssey

*An immersive dinner-theater retelling of Homer's* Odyssey *— 24 books, 24 songs, one writers' room of gods.*

---

## What this is

ATHENA is a full retelling of the *Odyssey* built for immersive dinner theater, where each of the 24 books is danced and rapped to a contemporary song the performers already know in their bodies. The Muse hosts the house like a Cabaret emcee. The wealthy diners become the Ithacan court — recruited as Telemachus's crew, pulled onto the floor as Circe's bewitched sailors, toasted and played and, in the end, sent home as witnesses. The women who get used and sidelined in Homer get the mic, the floor, and the bars: Calypso is a partner, not a prison; Circe is overpowered, not in love; and Penelope runs the entire back half of the poem on her own terms.

It is also an experiment in **collaborative AI** — not "AI wrote a book," but a human author conducting an ensemble of machines, each doing what it does best, with every creative decision made by a person.

## How it was made

The scripts in this repo are a writers'-room engine. Each character is an AI persona — a distinct system prompt — that takes its turn writing its own lines for a scene, in voice, and commits them to git *as itself*. The Muse opens each book; the characters speak, argue, and rap their numbers in a fixed turn order that *is* the dramatic arc; the Narrator closes. Run `git log` and you'll see the gods as authors: Calypso, Circe, Hermes, Penelope, Athena, each committing their own lines.

The pipeline that produced the manuscript:

- **`scribe.py`** — the generation engine. A book-parameterized writers' room. Reads a per-book registry (brief, turn order, staging mode, song scaffold) and re-prompts one shared local model per character. Includes an editor pass that revises the high-stakes turns (the songs, the power-flips) for quality.
- **`personas.py`** — the cast. 30 character-agents, each a system prompt encoding voice, identity, and dramatic function.
- **`voice_bible.md`** — the house style: Homeric cadence braided with hip-hop voice, drawn from the author's own Books I–IV.
- **`polish.py`** — a standalone editorial pass. Deterministically strips redundant labels, detects when a song accidentally echoes the style reference, and does targeted rewrites — flagging anything it can't fully resolve rather than shipping it silently.
- **`assemble.py`** — stitches the 24 polished scenes into one manuscript with a title page and table of contents.

Generation runs on a local model (Ollama). Nothing about the engine is tied to a specific host — set `OLLAMA_URL` to point it wherever your model lives.

The division of labor: a human held the vision and made every creative call. A reasoning model handled architecture and direction. A coding agent did the implementation. A local model generated the lines. And the author's own news-analysis framework (the A.R.C. Counter-Analyst) red-teamed the finished result. The human stayed the author and the conductor throughout. The machines were instruments.

## The song map

Each book is a contrafact — a real song's rhythm and spirit bent onto the Homeric beat, with entirely original lyrics. The songs were chosen to match choreography the performers already know.

### I — Adventures of Telemachus
1. **Deal With It** — Ashnikko · *the boy's first rage*
2. **Fast** — Saweetie · *the assembly, the crew, the departure*
3. **Freak** — Pitbull · *Pylos, Nestor, the wider world*
4. **Rude Boy** — Rihanna · *Sparta, Helen's recognition, turning home*

### II — Wanderings of Odysseus
5. **My Type** — Saweetie · *Calypso's island; predator meets predator; the release*
6. **Rain On Me** — Lady Gaga & Ariana Grande · *the storm, the survival, Nausicaa*
7. **Mic Drop** — Steve Aoki · *the reveal of the name at the Phaeacian court*
8. **Every Day** — A$AP Rocky · *the bard sings Troy; the cost of every day*

### III — Retrospective
9. **Bad Habits** — Ed Sheeran · *the Cyclops; the name shouted into the dark*
10. **Don't Stop** — Megan Thee Stallion · *Circe's hall; the power-flip; the rescue*
11. **Get Ugly** — Jason Derulo · *the Underworld; the dead mother; the prophecy*
12. **Outta Your Mind** — Lil Jon · *the Sirens, Scylla, the cattle; total loss*

### IV — Main Narrative Resumes
13. **WOW** — Post Malone · *home at last, in disguise*
14. **Without Me** — Halsey · *the loyal swineherd who kept faith*
15. **Bounce Back** — Little Mix · *the son who doesn't recognize his father*
16. **Lay** — Jason Derulo · *the reveal to Telemachus; the alliance*

### V — Return to the Palace
17. **Walk It Out** — Usher · *the walk through the stolen hall; the dog who waited*
18. **No Tears Left To Cry** — Ariana Grande · *Penelope plays the suitors*
19. **Savage Love** — Jason Derulo · *the near-recognition; the scar; the double standard*
20. **Up** — Cardi B · *the eve of the reckoning*

### VI — The Denouement
21. **Black Widow** — Iggy Azalea · *the bow contest; the trap closes*
22. **All About That Bass** — Meghan Trainor · *the slaughter; murdering the dance floor*
23. **New Rules** — Dua Lipa · *the bed test; the reunion on her terms*
24. **Work** — Britney Spears · *the restoration; the goddess ends the cycle*

## A note on the frame

A fair critique — raised, fittingly, by the author's own analysis framework when this manuscript was run through it — is whether mapping an ancient epic onto contemporary, often hedonistic, party tracks risks flattening the *Odyssey*'s themes of duty, endurance, and homecoming into mere entertainment.

The answer the production stakes itself on: the *Odyssey* was always performed. It was an oral tradition, sung live by a bard who generated the connective narration in the moment, for a feasting hall. ATHENA's Muse restores exactly that mode — the live host who works the room, the audience who are part of the show, the story sung rather than read. Hip-hop, an art form born of resistance and built on the contrafact, on flipping a known beat into new meaning, is not a betrayal of that tradition. It is a continuation of it. The weight of Penelope's twenty years and Odysseus's longing is meant to land *harder* for being carried on a beat the room already knows in its body.

Whether it succeeds is for the house to decide. That has always been the bard's wager.

## Status

The complete 24-book manuscript is assembled (`ATHENA_manuscript.md`). It is a strong draft, not a press-ready final pass — a small number of stanzas are flagged for a final editorial rewrite. The engine, the cast, and the song map are complete.

## License

The code is the author's. The songs referenced are the property of their respective artists and rights-holders; ATHENA's lyrics are original contrafacts written in their spirit, not reproductions. Performance and publication rights for any contrafact built on a copyrighted song are subject to the rights-holders' terms.
