# Ceci Spec — Athena clb Prototype (Book V, Calypso's Island)

## Goal
Build a SMALL, WATCHABLE prototype of the Athena collaborative writing engine ("clb").
Multiple AI character-agents (via local Ollama) take turns writing their OWN lines for
ONE scene, each committing as themselves to git, in a CONTAINED run (fixed number of turns)
that Ross can watch with `tail -f` on a log. This is a proof-of-concept, not the full 24-scene
engine. Prioritize: working, observable, easy to tweak. Not: scale, polish, the other 23 scenes.

## Where to build
- Build in a NEW directory: /home/www/Athena_clb  (do NOT touch the existing /home/www/Athena_repo
  source-of-truth, but DO read from it — see Voice Bible below).
- Git-init /home/www/Athena_clb. The generated scene will be committed here, scene-as-file.

## Ollama
- Ollama is available on the M1 Mac at http://192.168.1.185:11434 (Ross's existing inference host).
- Use a capable local model — start with mistral or gemma (whatever's pulled on the M1).
  Make the model name a config constant at the top so Ross can swap it.
- One model, re-prompted per character (simplest). Each "character" = a distinct system prompt /
  persona, not a separate model. (Future: per-character models. Not now.)

## The scene to write: BOOK V — Calypso's Island
- DRAMATIC FUNCTION: the turning point. Odysseus is RELEASED; the journey home begins.
- REFRAME: not a prison, a morally murky PARTNERSHIP. Odysseus (a city-sacker) is Calypso's
  "type" because she's a sea-witch — predator meets predator. He's spent most of his ten missing
  years here, likely sacking cities from the sea FOR her, hoping to go home rich.
- ANCHOR SONG: Saweetie "My Type" -> Calypso's number (she sings WHY he's her type / why he should
  stay). The dialogue should BUILD TOWARD this song.
- SCENE ARC: Hermes arrives with Zeus's order to release Odysseus -> Calypso resists (her "My Type"
  song) -> Odysseus is torn (the appetite that kept him vs. the home that calls) -> RELEASE.

## The character-agents (each writes ONLY their own character's lines, in voice)
- HERMES — messenger of Zeus; arrives to deliver the release order. Brisk, official, a little wry.
- CALYPSO — sea-witch; sovereign, alluring, possessive; NOT a simple villain. She has a point.
  (She gets the song.)
- ODYSSEUS — city-sacker; first appearance; torn between appetite/plunder and longing for home.
  Cunning, weathered, morally grey.
- (Optional framing agent: a NARRATOR/scribe voice for stage directions — keep minimal.)

## Voice Bible (CRITICAL — agents must match Ross's established style)
- READ /home/www/Athena_repo/README.md — this is the existing Books I-IV, written by Ross.
  It mixes HOMERIC CADENCE with HIP-HOP voice (e.g. Athena raps; gods speak with grandeur + swagger).
- Pass relevant excerpts of that README into each agent's prompt as the style reference.
- Each agent prompt = [character identity] + [the Book V scene context + arc] + [the anchor song's
  role] + [voice bible excerpt] + [the scene-so-far] + "write your character's NEXT contribution only."

## The scribe loop (the engine)
1. Initialize: write a scene header file (scene_book5.md) with the scene/song/arc context.
2. Define a TURN ORDER (e.g. Hermes -> Calypso -> Odysseus -> Calypso -> Odysseus -> Calypso[song] ...),
   OR a simple scribe rule that rotates and lets each character respond to the latest lines.
   Start with a FIXED turn order for predictability; making it smart is a later step.
3. For each turn (cap at ~8-10 turns total, a CONFIG constant):
   a. Read the current scene_book5.md (the scene-so-far).
   b. Build the active character's prompt (identity + context + voice bible + scene-so-far).
   c. Call Ollama on the M1, get the character's lines.
   d. Append the lines to scene_book5.md, labeled with the character.
   e. git commit --author="<Character> <character@athena>" -m "Book V: <Character>'s turn N"
      (so `git log` shows the gods/characters authoring the scene — this is the magic Ross wants to see)
   f. Log progress to a logfile Ross can `tail -f` (e.g. clb_run.log) — print whose turn, the lines,
      and the commit.
4. After the turn cap, stop. Print "scene complete — N turns" and the path to scene_book5.md.

## Observability (Ross will WATCH this)
- Everything streams to /home/www/Athena_clb/clb_run.log so `tail -f` shows the writers' room working:
  "=== Turn 3: CALYPSO ===", the generated lines, "committed as Calypso <...>". Make it readable/fun.

## Config constants at top (so Ross can fine-tune without digging)
- OLLAMA_URL, MODEL, MAX_TURNS, TURN_ORDER, paths. Easy knobs.

## What to deliver
- /home/www/Athena_clb/ with: the scribe script (python), the character persona definitions,
  the scene header, a README explaining how to run it and tweak it.
- A single command to run the prototype (e.g. `python3 scribe.py`) that does a contained run.
- Do NOT push anything. Show Ross the files and how to run + tail it.

## Explicitly OUT of scope for this prototype
- The other 23 scenes. Songs beyond Book V. Per-character models. Smart/dynamic turn logic.
- Web UI. Audio. Anything beyond "watch character-agents write Book V dialogue-into-song in the log."

## After Ceci builds it — Ross fine-tunes
- Run it, `tail -f clb_run.log`, read what the agents wrote.
- Tweak: character prompts, voice-bible excerpts, turn order, MAX_TURNS, the model.
- Iterate until Calypso's island sounds like ATHENA. Then generalize the engine to other scenes.
