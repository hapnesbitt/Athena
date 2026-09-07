#!/usr/bin/env python3
"""
polish2.py — metric-gated, second-round polish on the committed 24 ATHENA scenes.

Reads the RAW scene_bookN.md (NOT polish1's output — starts clean), applies one
smarter pass, and writes scene_bookN_polished2.md. Never overwrites the raw scene
or polish1's scene_bookN_polished.md (three-way compare). Never touches git.

Shelley-hardness: ONE constraint is hard, the rest are soft.
  - Plagiarism (voice-bible bleed) is a HARD gate at zero — looped up to 6 rounds.
  - Form (rhyme/meter/structure) is SOFT — a pass ships only if it measurably
    improves, never to force mechanical perfection. The form bends before it
    breaks the sense.
Every LLM pass computes a before/after metric and keeps its result only if the
metric improved (or held); otherwise it is discarded. No pass ships unjustified
by a number.

  python3 polish2.py 23            # one book   (Stages 1+2)
  python3 polish2.py all           # books 1-24 (Stages 1+2)
  python3 polish2.py 23 --rhyme    # add the opt-in Stage 3 (supervised experiments)

Stages per book:
  1. Deterministic artifact guard (no LLM): strip redundant labels, strip leaked
     scaffold tokens, fix doubled headings, fix wrong emoji, flag malformed staging
     and off-roster speakers.
  2. Multi-round bleed killer (HARD, LLM looped): per copied stanza, iteratively
     rewrite up to MAX_BLEED_ROUNDS times (refining the best-so-far, targeting the
     lines that still copy the bible), keeping the first attempt whose bible-overlap
     hits 0 (else the lowest-overlap attempt, flagged).
  3. Soft form pass — OFF by default, opt-in via --rhyme. Rhyme is entangled with
     meaning the metric can't measure (it can soften a plot-critical line), so the
     default pass ships only the unambiguous wins (Stages 1+2). When enabled it
     tightens the worst rhyme-breaking line per song stanza, keeping the rewrite only
     if rhyme_breaks drops and no new bleed appears.

Reuses polish.py's proven helpers; sources PERSONAS/BOOKS/SONG_SCAFFOLDS from the
YAML via scribe.py. Watch: tail -f polish2_run.log
"""

import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime

import polish                                   # reuse the proven helpers
from scribe import OLLAMA_URL, MODEL, PERSONAS, BOOKS   # config from athena.yaml via scribe

# ============================== CONFIG =======================================
MAX_BLEED_ROUNDS = 6      # the bleed killer's hard-gate loop
REWRITE_TEMP     = 0.7    # rewrite passes need invention
REQUEST_TIMEOUT  = 600    # whole-stanza/line calls; generous for a slow host

HERE     = polish.HERE
LOG_PATH = os.path.join(HERE, "polish2_run.log")

CANON_EMOJI = {name: p["emoji"] for name, p in PERSONAS.items()}   # the YAML emoji map
ROSTER      = set(PERSONAS)                                         # the 30 speaker names

# Heading: "### Turn N — NAME EMOJI" or "### NAME EMOJI" (emoji optional, defensive).
HEADING_RE = re.compile(r"^###\s+(?:Turn\s+(\d+)\s+—\s+)?(\S+)(?:\s+(.+?))?\s*$")
# Leaked scaffold structure as a standalone line: "Verse 1:", "Pre-hook", "Hook:", ...
SCAFFOLD_LABEL_RE = re.compile(
    r"^\s*(verse\s*\d+|pre-?hook|hook|bridge|outro|intro|chorus|refrain)\s*:?\s*$", re.I)
# Leaked scaffold annotation inline: "(Verse 1)", "(Pre-hook)", "(4 bars)", "(2 bars)".
SCAFFOLD_PAREN_RE = re.compile(
    r"\s*\((?:verse\s*\d+|pre-?hook|hook|bridge|outro|intro|chorus|\d+\s*bars?)\)", re.I)
# The literal "[STAGING lines ...]" placeholder (NOT a real "[STAGING: ...]" direction).
STAGING_PLACEHOLDER_RE = re.compile(r"^\s*\[staging lines\b[^\]]*\]?\s*$", re.I)
# A short header/label line ("New Rules:", "Verse 1:") — never a lyric to rhyme-rewrite.
LABEL_LINE_RE = re.compile(r"^[A-Za-z][\w' ]{0,24}:\s*$")

RHYME_SYSTEM = (
    "You are a lyric editor for a hip-hop piece. You rewrite a single line so its "
    "last word rhymes, keeping the same meaning and a similar length. You return "
    "ONLY the one rewritten line — no quotes, no label, no commentary."
)


# ============================== ENGINE =======================================

def log(msg=""):
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + "\n")


def call_ollama(system_prompt, user_prompt):
    """Same Ollama /api/chat pattern as polish.py, on polish2's temp/timeout."""
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
    with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return data["message"]["content"].strip()


def parse_heading(line):
    """(turn_no|None, name, emoji|None) for a '### ...' heading, else None."""
    m = HEADING_RE.match(line)
    if not m:
        return None
    tno = int(m.group(1)) if m.group(1) else None
    return tno, m.group(2), (m.group(3).strip() if m.group(3) else None)


def beat_type_for(book_id, turn_no):
    """beat_type of the Nth dialogue turn from the YAML turn order (Turn 0 = Muse)."""
    try:
        t = BOOKS[book_id]["turn_order"][turn_no - 1]
    except (KeyError, IndexError, TypeError):
        return "dialogue"
    return t[2] if len(t) > 2 else "dialogue"


# ---------- Stage 1: deterministic artifact guard (no LLM) ----------

def strip_scaffold_leaks(lines):
    """Remove leaked scaffold structure: standalone labels, inline annotations,
    and '[STAGING lines ...]' placeholders. Returns (lines, removed_count)."""
    out, removed = [], 0
    for ln in lines:
        if STAGING_PLACEHOLDER_RE.match(ln):
            removed += 1
            continue
        if SCAFFOLD_LABEL_RE.match(ln):
            removed += 1
            continue
        new, k = SCAFFOLD_PAREN_RE.subn("", ln)
        if k:
            removed += k
            new = re.sub(r"\s{2,}", " ", new).rstrip()
            if new.strip() == "":
                continue                    # line was only the annotation
            out.append(new)
            continue
        out.append(ln)
    return out, removed


def fix_duplicate_headings(lines):
    """Drop an empty '### Turn N' heading immediately followed (past blanks/'---')
    by another '### Turn N' with the same number. Returns (lines, fixed_count)."""
    out, fixed, i, n = [], 0, 0, len(lines)
    while i < n:
        h = parse_heading(lines[i])
        if h and h[0] is not None:
            j = i + 1
            while j < n and lines[j].strip() in ("", "---"):
                j += 1
            if j < n:
                h2 = parse_heading(lines[j])
                if h2 and h2[0] == h[0]:     # same Turn N, nothing between → first is empty
                    fixed += 1
                    i = j                    # skip the empty heading + separators
                    continue
        out.append(lines[i])
        i += 1
    return out, fixed


def fix_emojis(lines):
    """Fix a heading's emoji to the persona's canonical YAML emoji. Off-roster
    speakers are flagged, not touched. Returns (lines, emoji_fixed, unknown_flags)."""
    out, fixed, unknown = [], 0, []
    for ln in lines:
        h = parse_heading(ln)
        if h:
            tno, name, emoji = h
            if name not in ROSTER:
                unknown.append(f"off-roster speaker {name!r} in heading: {ln.strip()!r}")
                out.append(ln)
                continue
            canon = CANON_EMOJI[name]
            if emoji is not None and emoji != canon:
                fixed += 1
                out.append(f"### Turn {tno} — {name} {canon}" if tno is not None
                           else f"### {name} {canon}")
                continue
        out.append(ln)
    return out, fixed, unknown


def flag_malformed_staging(lines):
    """Flag '[STAGING' lines missing a ':' or ']' (placeholders already removed)."""
    flags = []
    for idx, ln in enumerate(lines):
        s = ln.strip()
        if s.startswith("[STAGING") and (":" not in s or "]" not in s):
            flags.append(f"malformed staging @line {idx + 1}: {s[:50]!r}")
    return flags


# ---------- Stage 2: multi-round bleed killer (HARD gate) ----------

def span_overlap(lines, frags):
    """The metric: how many lines still echo the voice bible."""
    return sum(1 for ln in lines if polish.line_is_bleed(ln, frags))


def build_bleed_prompt(stanza_lines, speaker, bible_text, bleeders):
    """A structure-breaking rewrite prompt: name the still-copying lines and forbid
    keeping the bible's images/skeleton (shallow synonym swaps keep tripping the gate)."""
    stanza = "\n".join(stanza_lines).strip()
    bleed_list = "\n".join(f"  - {b.strip()}" for b in bleeders) or "  - (the whole stanza)"
    return (
        f"In ATHENA (a hip-hop retelling of the Odyssey), the stanza below — spoken by "
        f"{speaker} — PLAGIARIZES the voice bible. Rewrite it as fully ORIGINAL lines in "
        f"{speaker}'s voice. Keep the same MEANING and emotion, but you MUST change the "
        f"images and the line structure — do NOT keep the source's pictures, phrases, or "
        f"rhyme words; invent fresh ones. Synonym-swapping is NOT enough.\n\n"
        f"These lines still copy the source and MUST be replaced wholesale (new imagery, "
        f"new wording):\n{bleed_list}\n\n"
        f"── VOICE BIBLE (never reuse any of its words, images, or rhymes) ──\n"
        f"{bible_text}\n\n"
        f"── STANZA TO REWRITE ({speaker}) ──\n{stanza}\n\n"
        f"Return ONLY the rewritten lines — no labels, no commentary."
    )


def kill_bleed(stanza, speaker, bible_text, frags):
    """Loop rewrites until bible-overlap hits 0 (HARD gate).

    Returns (lines, orig_overlap, final_overlap, rounds_used, flagged). ITERATIVE:
    each round refines the best-so-far and is told which lines still copy the source,
    so it attacks the residual instead of re-anchoring on the plagiarized original.
    Keep the lowest-overlap candidate; stop the moment one reaches 0.
    """
    orig = span_overlap(stanza, frags)
    speaker = speaker or "the speaker"
    best_lines, best_ov = list(stanza), orig
    base = list(stanza)
    for r in range(1, MAX_BLEED_ROUNDS + 1):
        bleeders = [ln for ln in base if polish.line_is_bleed(ln, frags)]
        try:
            raw = call_ollama(polish.REWRITE_SYSTEM,
                              build_bleed_prompt(base, speaker, bible_text, bleeders))
        except Exception:  # noqa: BLE001 — a round can fail; try the next
            continue
        cand = polish.clean_rewrite(raw)
        cand = [re.sub(r"^\s*[-*•]\s+", "", ln) for ln in cand]   # strip leaked list bullets
        if not cand:
            continue
        ov = span_overlap(cand, frags)
        if ov < best_ov:
            best_lines, best_ov = cand, ov
            base = cand                      # iterate on the improved version
        if ov == 0:
            return best_lines, orig, 0, r, False
    return best_lines, orig, best_ov, MAX_BLEED_ROUNDS, (best_ov > 0)


# ---------- Stage 3: soft form pass (song turns only, metric-gated) ----------

_VOWELS = "aeiou"


def _last_word(line):
    words = re.findall(r"[A-Za-z']+", line)
    return words[-1].lower() if words else ""


def _rhyme_key(word):
    """Crude rhyme key: from the last vowel onward (shore/more -> 'ore')."""
    if not word:
        return ""
    pos = max((i for i, ch in enumerate(word) if ch in _VOWELS), default=-1)
    return word[pos:] if pos >= 0 else word[-2:]


def _rhymes(a, b):
    ka, kb = _rhyme_key(_last_word(a)), _rhyme_key(_last_word(b))
    return ka != "" and ka == kb


def rhyme_breaks(stanza_lines):
    """Count lines that rhyme with NEITHER neighbour. Returns (breaks, break_indices)."""
    lyric = [ln for ln in stanza_lines if ln.strip()]
    if len(lyric) < 2:
        return 0, []
    breaks, idx = 0, []
    for i, ln in enumerate(lyric):
        prev = lyric[i - 1] if i > 0 else None
        nxt = lyric[i + 1] if i < len(lyric) - 1 else None
        if not ((prev and _rhymes(ln, prev)) or (nxt and _rhymes(ln, nxt))):
            breaks += 1
            idx.append(i)
    return breaks, idx


def build_line_rhyme_prompt(stanza_text, target_line, rhyme_with):
    return (
        f"Rewrite ONLY the marked line so its last word rhymes with '{rhyme_with}', "
        f"keeping the same meaning and a similar length.\n\n"
        f"Stanza (for context):\n{stanza_text}\n\n"
        f"Line to rewrite:\n{target_line}\n\n"
        f"Return ONLY the one rewritten line."
    )


def _clean_one_line(text):
    for ln in text.strip().splitlines():
        s = ln.strip().strip('"').strip()
        if not s:
            continue
        if re.match(r"^(sure|here|okay|certainly)\b", s, re.I):
            continue
        if s.rstrip(":").strip().upper() in ROSTER:
            continue
        return s
    return ""


def soft_rhyme_pass(lines, book_id, frags):
    """Tighten the worst rhyme-breaking line per song stanza, non-destructively.
    Returns (lines, breaks_before, breaks_after, lines_touched)."""
    before_total, after_total, touched = 0, 0, 0
    heads = [i for i, ln in enumerate(lines) if ln.startswith("### ")]
    for k, i in enumerate(heads):
        end = heads[k + 1] if k + 1 < len(heads) else len(lines)
        h = parse_heading(lines[i])
        if not h or h[0] is None or beat_type_for(book_id, h[0]) != "song":
            continue
        # split the turn body into stanzas (blank-separated runs of lyric lines)
        stanza, stanzas = [], []
        for idx in range(i + 1, end):
            s = lines[idx].strip()
            # blanks, staging, headings, and short header/label lines break a stanza
            # and are NEVER rewritten as lyric (e.g. "New Rules:").
            if (s == "" or s.startswith("[STAGING") or lines[idx].startswith("###")
                    or LABEL_LINE_RE.match(s)):
                if stanza:
                    stanzas.append(stanza)
                    stanza = []
                continue
            stanza.append(idx)
        if stanza:
            stanzas.append(stanza)

        for st in stanzas:
            if len(st) < 2:
                continue
            br_before, brk = rhyme_breaks([lines[a] for a in st])
            before_total += br_before
            if br_before == 0:
                continue
            ti = brk[0]                                  # first breaking line
            target_abs = st[ti]
            neigh = st[ti - 1] if ti > 0 else st[ti + 1]
            rhyme_with = _last_word(lines[neigh])
            stanza_text = "\n".join(lines[a] for a in st)
            try:
                cand = _clean_one_line(call_ollama(
                    RHYME_SYSTEM,
                    build_line_rhyme_prompt(stanza_text, lines[target_abs], rhyme_with)))
            except Exception:  # noqa: BLE001 — soft pass, ignore a failed call
                cand = ""
            applied = False
            if cand and not polish.line_is_bleed(cand, frags):   # HARD: no new bleed
                trial = [lines[a] for a in st]
                trial[ti] = cand
                br_after, _ = rhyme_breaks(trial)
                if br_after < br_before:                          # SOFT: only if better
                    lines[target_abs] = cand
                    after_total += br_after
                    touched += 1
                    applied = True
            if not applied:
                after_total += br_before                          # discarded — keep original
    return lines, before_total, after_total, touched


# ============================== PER-BOOK =====================================

def polish_book(book_id, bible_text, frags, rhyme=False):
    """Returns (status, artifacts, bleed_summary, rhyme_str, review_reasons)."""
    raw_path = os.path.join(HERE, f"scene_book{book_id}.md")
    out_path = os.path.join(HERE, f"scene_book{book_id}_polished2.md")
    if not os.path.isfile(raw_path):
        log(f"  · Book {book_id}: no scene_book{book_id}.md — skipped")
        return ("skipped", {}, "—", "off", [])

    lines = open(raw_path, encoding="utf-8").read().splitlines()

    # ---- Stage 1: deterministic artifact guard ----
    lines, lbl_stripped, lbl_flags = polish.strip_labels(lines)
    lines, scaf_removed            = strip_scaffold_leaks(lines)
    lines, head_fixed              = fix_duplicate_headings(lines)
    lines, emoji_fixed, unknown    = fix_emojis(lines)
    malformed                      = flag_malformed_staging(lines)
    artifacts = {"labels": lbl_stripped, "scaffold": scaf_removed,
                 "headings": head_fixed, "emoji": emoji_fixed}
    log(f"    · [Book {book_id}] stage1: {lbl_stripped} labels, {scaf_removed} scaffold-leaks, "
        f"{head_fixed} headings, {emoji_fixed} emoji")
    for fn in lbl_flags + unknown + malformed:
        log(f"    · [Book {book_id}] flag: {fn}")

    # ---- Stage 2: multi-round bleed killer (HARD gate) ----
    spans = polish.find_bleed_spans(lines, frags)
    bleed_bits, bleed_flag = [], False
    if spans:
        log(f"    · [Book {book_id}] bleed: {len(spans)} copied stanza(s) detected")
    for (start, end, speaker) in reversed(spans):
        stanza = lines[start:end + 1]
        new, orig, final, rounds, flagged = kill_bleed(stanza, speaker, bible_text, frags)
        if new != stanza:
            lines[start:end + 1] = new
        if flagged:
            bleed_flag = True
            log(f"    · [Book {book_id}] bleed: {speaker} @line {start + 1} — overlap "
                f"{orig}→{final} STILL echoes after {rounds} rounds — review")
        else:
            log(f"    · [Book {book_id}] bleed: {speaker} @line {start + 1} — overlap "
                f"{orig}→0 in {rounds} round(s)")
        bleed_bits.append(f"{orig}→{final}/{rounds}r" + ("⚠" if flagged else ""))
    bleed_summary = ", ".join(reversed(bleed_bits)) if bleed_bits else "no bleed"

    # ---- Stage 3: soft form pass — OFF by default (opt-in via --rhyme). Rhyme is
    #      entangled with meaning the gate can't measure, so the default keeps only
    #      the unambiguous wins (Stages 1+2). ----
    if rhyme:
        lines, rh_before, rh_after, rh_touched = soft_rhyme_pass(lines, book_id, frags)
        rhyme_str = f"{rh_before}→{rh_after}"
        if rh_touched:
            log(f"    · [Book {book_id}] rhyme: breaks {rh_before}→{rh_after} ({rh_touched} line(s) tightened)")
    else:
        rhyme_str = "off"

    # ---- write ----
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines).strip() + "\n")

    review = []
    if bleed_flag:
        review.append("bleed")
    if lbl_flags:
        review.append("labels")
    if unknown:
        review.append("off-roster")
    if malformed:
        review.append("staging")
    status = "review" if review else "done"
    mark = "⚠" if review else "✓"
    log(f"  {mark} Book {book_id}: "
        f"artifacts(labels {artifacts['labels']}, scaffold {artifacts['scaffold']}, "
        f"headings {artifacts['headings']}, emoji {artifacts['emoji']}), "
        f"bleed [{bleed_summary}], rhyme {rhyme_str}"
        + (f" — review: {', '.join(review)}" if review else ""))
    return (status, artifacts, bleed_summary, rhyme_str, review)


def main():
    args = sys.argv[1:]
    rhyme = "--rhyme" in args
    positional = [a for a in args if not a.startswith("--")]
    if len(positional) != 1:
        sys.stderr.write("usage: python3 polish2.py <book-number | all> [--rhyme]\n")
        sys.exit(2)
    arg = positional[0].strip().lower()

    open(LOG_PATH, "w", encoding="utf-8").close()
    log("=" * 64)
    log("✨  ATHENA polish2 — metric-gated second-round polish")
    log(f"   model   : {MODEL} @ {OLLAMA_URL}  (rewrite temp {REWRITE_TEMP}, "
        f"max bleed rounds {MAX_BLEED_ROUNDS})")
    log(f"   stages  : 1 (artifacts) + 2 (bleed→0)" + (" + 3 (rhyme, opt-in)" if rhyme
        else "   [rhyme OFF — pass --rhyme to enable]"))
    log(f"   started : {datetime.now():%Y-%m-%d %H:%M:%S}")
    log("=" * 64)

    bible_text = polish.read_voice_bible()
    frags = polish.bible_fragments(bible_text)
    if not frags:
        log("  !! no CADENCE SAMPLE fences in voice_bible.md — bleed detection off")

    book_ids = [str(n) for n in range(1, 25)] if arg == "all" else [arg]

    results = []
    for bid in book_ids:
        try:
            status, artifacts, bleed_summary, rhyme_str, review = polish_book(
                bid, bible_text, frags, rhyme=rhyme)
        except Exception as e:  # noqa: BLE001 — fail soft per book, keep going
            log(f"  !! Book {bid} FAILED: {e}")
            status, artifacts, bleed_summary, rhyme_str, review = ("failed", {}, "—", "—", ["error"])
        results.append((bid, status, artifacts, bleed_summary, rhyme_str, review))

    log("")
    log("  book | labels | scaf | head | emoji | bleed                 | rhyme | status")
    log("  -----+--------+------+------+-------+-----------------------+-------+--------")
    for bid, status, a, bleed_summary, rhyme_str, review in results:
        a = a or {}
        log(f"  {bid:>4} | {a.get('labels',0):>6} | {a.get('scaffold',0):>4} | "
            f"{a.get('headings',0):>4} | {a.get('emoji',0):>5} | {bleed_summary[:21]:<21} | "
            f"{rhyme_str:<5} | {status}")
    need = [r[0] for r in results if r[5]]
    skipped = sum(1 for r in results if r[1] == "skipped")
    failed = sum(1 for r in results if r[1] == "failed")
    log("")
    log(f"  {len(results) - skipped - failed} polished, {len(need)} need review, "
        f"{skipped} skipped, {failed} failed")
    if need:
        log(f"  → review these books: {', '.join(need)}")
    log(f"  log: {LOG_PATH}")


if __name__ == "__main__":
    main()
