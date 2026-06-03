#!/usr/bin/env python3
"""
polish.py — standalone editorial polish pass for ATHENA scenes.

The raw scenes (scene_bookN.md, written by scribe.py) carry a few quality bugs:
on song turns the small model copies lyrics nearly verbatim from voice_bible.md
instead of writing original lines; it leaves bare speaker-name labels in the body;
and it occasionally mis-attributes lines to the wrong character.

A whole-scene "rewrite everything" call to mistral:7b just echoes the scene back, so
this tool fixes the reliable things DETERMINISTICALLY and uses the model only where
it can actually help — a small, focused rewrite of each copied stanza:

  1. STRIP LABELS (deterministic, speaker-aware): drop redundant in-body speaker
     labels ("Penelope:" inside a PENELOPE turn). A label naming a DIFFERENT
     character than the turn heading is a mis-attribution signal, so it is LEFT in
     place and logged for Ross instead of being silently merged.
  2. DETECT BLEED (deterministic): line-match each line against the fenced cadence
     sample in voice_bible.md to find copied lyric stanzas.
  3. REWRITE BLEED (targeted LLM call): rewrite only the flagged stanza into
     original lines in the same speaker's voice — small enough that 7B succeeds.

It writes scene_bookN_polished.md (NEVER the raw file) and NEVER touches git.

  python3 polish.py 23     # polish one book
  python3 polish.py all    # polish every book 1-24 that has a scene file

Watch: tail -f polish_run.log
Pure stdlib + the same Ollama call pattern as scribe.py.
"""

import difflib
import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime

from scribe import OLLAMA_URL, MODEL   # single source of truth for the M1 host/model
from personas import PERSONAS

# ============================== CONFIG =======================================
REWRITE_TEMP   = 0.7    # targeted stanza rewrite needs invention (vs verbatim echo)
POLISH_TIMEOUT = 600    # generous; stanza calls are small but the host can be slow
BLEED_RATIO    = 0.6    # similarity at/above this vs a bible line = copied

HERE             = os.path.dirname(os.path.abspath(__file__))
LOG_PATH         = os.path.join(HERE, "polish_run.log")
VOICE_BIBLE_PATH = os.path.join(HERE, "voice_bible.md")

# Speaker names that may show up as in-body labels (case-insensitive match).
LABELS = {lab.upper() for lab in PERSONAS}

REWRITE_SYSTEM = (
    "You are a script editor for ATHENA, a hip-hop dinner-theater retelling of the "
    "Odyssey. You rewrite a copied stanza into fully original lines in the same "
    "character's voice. You return ONLY the rewritten lines — no commentary, no "
    "speaker labels, no headings."
)

# Scene-structure patterns.
HEADING_TURN_RE  = re.compile(r"^###\s+Turn\s+\d+\s+—\s+(\S+)")
HEADING_PLAIN_RE = re.compile(r"^###\s+([A-Za-z][A-Za-z']*)")
RAPS_RE          = re.compile(r"^\s*[A-Za-z][\w']*(?:'s)?\s+RAPS?:?\s*$", re.IGNORECASE)
INLINE_LABEL_RE  = re.compile(r"^\s*([A-Za-z][A-Za-z']*)\s*[:\-—]\s*(.*)$")


# ============================== ENGINE =======================================

def log(msg=""):
    """Print to stdout AND append to polish_run.log (so `tail -f` sees everything)."""
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def read_voice_bible():
    try:
        with open(VOICE_BIBLE_PATH, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return ""


def normalize(s):
    """Lowercase, drop the '/' lyric separators and punctuation, collapse spaces."""
    s = s.lower().replace("/", " ")
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


# ---------- 1. deterministic label strip (speaker-aware) ----------

def heading_speaker(line):
    """Return the UPPER speaker name if `line` is a turn heading, else None."""
    if not line.startswith("###"):
        return None
    m = HEADING_TURN_RE.match(line) or HEADING_PLAIN_RE.match(line)
    return m.group(1).upper() if m else None


def strip_labels(lines):
    """Drop redundant in-body speaker labels. Returns (new_lines, warnings)."""
    out, warnings = [], []
    current = None
    for ln in lines:
        sp = heading_speaker(ln)
        if sp is not None:
            current = sp
            out.append(ln)
            continue
        if ln.strip().startswith("[STAGING"):
            out.append(ln)
            continue
        # A "Name's RAPS:" header is a bleed mislabel, never a real speaker line.
        if RAPS_RE.match(ln):
            warnings.append(f"dropped stray header: {ln.strip()!r}")
            continue
        # Standalone bare label line ("Penelope:" / "ODYSSEUS").
        bare = ln.strip().rstrip(":").strip()
        if bare.upper() in LABELS:
            if current and bare.upper() == current:
                continue  # redundant — drop it
            warnings.append(f"kept mismatched label {ln.strip()!r} inside {current} turn "
                            f"(possible mis-attribution — review)")
            out.append(ln)
            continue
        # Inline "Name: rest" prefix.
        m = INLINE_LABEL_RE.match(ln)
        if m and m.group(1).upper() in LABELS:
            name, rest = m.group(1).upper(), m.group(2)
            if current and name == current:
                if rest.strip():
                    out.append(rest)        # strip the redundant prefix, keep the words
                continue
            warnings.append(f"kept mismatched inline label {ln.strip()[:40]!r} inside "
                            f"{current} turn (possible mis-attribution — review)")
            out.append(ln)
            continue
        out.append(ln)
    return out, warnings


# ---------- 2. deterministic bleed detection ----------

def bible_fragments(bible_text):
    """Normalized lyric fragments from the fenced CADENCE SAMPLE in the voice bible."""
    frags, inside = [], False
    for ln in bible_text.splitlines():
        if "BEGIN CADENCE SAMPLE" in ln:
            inside = True
            continue
        if "END CADENCE SAMPLE" in ln:
            inside = False
            continue
        if inside:
            whole = normalize(ln)
            if len(whole.split()) >= 4:
                frags.append(whole)
            for part in ln.split("/"):
                p = normalize(part)
                if len(p.split()) >= 4:
                    frags.append(p)
    return frags


def line_is_bleed(line, frags):
    if line.startswith("###") or line.strip().startswith("[STAGING"):
        return False
    candidates = [normalize(line)] + [normalize(p) for p in line.split("/")]
    best = 0.0
    for c in candidates:
        if len(c.split()) < 4:
            continue
        for f in frags:
            best = max(best, difflib.SequenceMatcher(None, c, f).ratio())
    return best >= BLEED_RATIO


def find_bleed_spans(lines, frags):
    """Contiguous runs of bleeding lines (merging interior blanks). Returns
    list of (start, end, speaker)."""
    speakers, cur = [], None
    for ln in lines:
        sp = heading_speaker(ln)
        if sp is not None:
            cur = sp
        speakers.append(cur)
    bleed = [line_is_bleed(ln, frags) for ln in lines]

    spans, i, n = [], 0, len(lines)
    while i < n:
        if not bleed[i]:
            i += 1
            continue
        last = i
        k = i
        while k + 1 < n:
            if bleed[k + 1]:
                k += 1
                last = k
            elif lines[k + 1].strip() == "" and not lines[k + 1].startswith("###"):
                m = k + 1
                while m < n and lines[m].strip() == "":
                    m += 1
                if m < n and bleed[m]:
                    k, last = m, m
                else:
                    break
            else:
                break
        spans.append((i, last, speakers[i]))
        i = last + 1
    return spans


# ---------- 3. targeted LLM rewrite of a flagged stanza ----------

def call_ollama(system_prompt, user_prompt):
    payload = {
        "model": MODEL,
        "stream": False,
        "options": {"temperature": REWRITE_TEMP},
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
    with urllib.request.urlopen(req, timeout=POLISH_TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["message"]["content"].strip()


def build_rewrite_prompt(stanza_lines, speaker, bible_text, n):
    stanza = "\n".join(stanza_lines).strip()
    return (
        f"In ATHENA (a hip-hop retelling of the Odyssey), the stanza below — spoken by "
        f"{speaker} — copies the voice bible almost verbatim. Rewrite it as ~{n} fully "
        f"ORIGINAL lines in {speaker}'s voice: keep the same intent, emotion, and "
        f"rhythm, but share NO wording, phrases, or rhymes with the voice bible.\n"
        f"\n"
        f"── VOICE BIBLE (never reuse its words) ──\n"
        f"{bible_text}\n"
        f"\n"
        f"── STANZA TO REWRITE ({speaker}) ──\n"
        f"{stanza}\n"
        f"\n"
        f"Return ONLY the rewritten lines — no labels, no commentary."
    )


def clean_rewrite(text):
    """Trim a stanza rewrite: drop fences, 'Here is...', and any bare labels."""
    lines = []
    for ln in text.strip().splitlines():
        s = ln.strip()
        if s.startswith("```"):
            continue
        if re.match(r"^(sure|here(’s| is| are)|okay|certainly)\b", s, re.IGNORECASE):
            continue
        if s.rstrip(":").strip().upper() in LABELS:
            continue
        if RAPS_RE.match(ln):
            continue
        lines.append(ln.rstrip())
    while lines and lines[0].strip() == "":
        lines.pop(0)
    while lines and lines[-1].strip() == "":
        lines.pop()
    return lines


def rewrite_span(stanza_lines, speaker, bible_text, frags):
    """Rewrite a bleeding stanza; retry once if it still bleeds. Returns (lines, note)."""
    content = [ln for ln in stanza_lines if ln.strip()]
    n = len(content)
    speaker = speaker or "the speaker"
    for attempt in (1, 2):
        raw = call_ollama(REWRITE_SYSTEM, build_rewrite_prompt(stanza_lines, speaker, bible_text, n))
        new = clean_rewrite(raw)
        if new and not any(line_is_bleed(ln, frags) for ln in new):
            return new, f"rewritten ({n}->{len(new)} lines, attempt {attempt})"
    # Still bleeding (or empty) after retries — keep the best attempt but flag it.
    if new:
        return new, "rewritten but STILL echoes bible — review"
    return stanza_lines, "rewrite failed/empty — left as-is, review"


# ============================== PER-BOOK =====================================

def scene_paths(book_id):
    return (os.path.join(HERE, f"scene_book{book_id}.md"),
            os.path.join(HERE, f"scene_book{book_id}_polished.md"))


def polish_book(book_id, bible_text, frags):
    """Polish one book. Returns (status, raw_chars, polished_chars)."""
    raw_path, polished_path = scene_paths(book_id)
    if not os.path.isfile(raw_path):
        log(f"  · Book {book_id}: no {os.path.basename(raw_path)} — skipped")
        return ("skipped", 0, 0)

    with open(raw_path, "r", encoding="utf-8") as f:
        raw = f.read()
    lines = raw.splitlines()

    # 1. deterministic label strip.
    lines, warnings = strip_labels(lines)
    for w in warnings:
        log(f"    · label: {w}")

    # 2 + 3. detect bleed spans, rewrite each (last-to-first to keep indices valid).
    spans = find_bleed_spans(lines, frags)
    if spans:
        log(f"    · bleed: {len(spans)} copied stanza(s) detected")
    failures = 0
    for (start, end, speaker) in reversed(spans):
        stanza = lines[start:end + 1]
        try:
            new, note = rewrite_span(stanza, speaker, bible_text, frags)
        except Exception as e:  # noqa: BLE001 — fail soft on a single stanza
            log(f"    !! Book {book_id}: stanza rewrite errored ({speaker}): {e}")
            failures += 1
            continue
        lines[start:end + 1] = new
        log(f"    · bleed: {speaker} stanza @line {start + 1} — {note}")

    polished = "\n".join(lines).strip() + "\n"
    with open(polished_path, "w", encoding="utf-8") as f:
        f.write(polished)

    if failures:
        log(f"  ~ Book {book_id}: wrote {os.path.basename(polished_path)} "
            f"with {failures} stanza error(s) — review")
        return ("partial", len(raw), len(polished))
    log(f"  ✓ Book {book_id}: wrote {os.path.basename(polished_path)} "
        f"({len(spans)} stanza(s) rewritten, {len(warnings)} label note(s))")
    return ("done", len(raw), len(polished))


def main():
    if len(sys.argv) != 2:
        sys.stderr.write("usage: python3 polish.py <book-number | all>\n")
        sys.exit(2)
    arg = sys.argv[1].strip().lower()

    open(LOG_PATH, "w", encoding="utf-8").close()  # fresh log each run

    log("=" * 60)
    log("✨  ATHENA polish pass (deterministic strip + targeted bleed rewrite)")
    log(f"   model   : {MODEL} @ {OLLAMA_URL}  (rewrite temp {REWRITE_TEMP})")
    log(f"   started : {datetime.now():%Y-%m-%d %H:%M:%S}")
    log("=" * 60)

    bible_text = read_voice_bible()
    frags = bible_fragments(bible_text)
    if not frags:
        log("  !! no CADENCE SAMPLE fences found in voice_bible.md — bleed detection off")

    book_ids = [str(n) for n in range(1, 25)] if arg == "all" else [arg]

    results = []
    for book_id in book_ids:
        try:
            status, raw_c, pol_c = polish_book(book_id, bible_text, frags)
        except Exception as e:  # noqa: BLE001 — fail soft per book, continue
            log(f"  !! Book {book_id} FAILED: {e}")
            status, raw_c, pol_c = ("failed", 0, 0)
        results.append((book_id, status, raw_c, pol_c))

    log("")
    log("  book | raw chars | polished chars | status")
    log("  -----+-----------+----------------+---------")
    for book_id, status, raw_c, pol_c in results:
        log(f"  {book_id:>4} | {raw_c:>9} | {pol_c:>14} | {status}")
    done = sum(1 for _, s, _, _ in results if s in ("done", "partial"))
    skipped = sum(1 for _, s, _, _ in results if s == "skipped")
    failed = sum(1 for _, s, _, _ in results if s == "failed")
    log("")
    log(f"  {done} polished, {skipped} skipped, {failed} failed")
    log(f"  log: {LOG_PATH}")


if __name__ == "__main__":
    main()
