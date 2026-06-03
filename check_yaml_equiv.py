#!/usr/bin/env python3
"""
check_yaml_equiv.py — prove athena.yaml reproduces the hardcoded engine EXACTLY.

The acceptance test for the YAML port. It imports scribe (whose module-level
PERSONAS / BOOKS / SONG_SCAFFOLDS are still the hardcoded reference at import time —
only main() swaps in the YAML), loads the YAML via scribe.load_config(), and asserts
structural equality field by field. Zero diffs = the port is faithful and safe.

  python3 check_yaml_equiv.py     # exits 0 on zero diffs, 1 otherwise
"""

import sys

import scribe

ref_personas  = scribe.PERSONAS          # hardcoded reference (from personas.py)
ref_books     = scribe.BOOKS             # hardcoded reference (literal in scribe.py)
ref_scaffolds = scribe.SONG_SCAFFOLDS    # hardcoded reference (literal in scribe.py)

personas, books, scaffolds, models = scribe.load_config()

diffs = []


def cmp_str_map(label, ref, got):
    if set(ref) != set(got):
        for k in sorted(set(ref) - set(got)):
            diffs.append(f"{label}: '{k}' in hardcoded but not YAML")
        for k in sorted(set(got) - set(ref)):
            diffs.append(f"{label}: '{k}' in YAML but not hardcoded")
    for k in sorted(set(ref) & set(got)):
        if ref[k] != got[k]:
            diffs.append(f"{label}['{k}']: value differs")


# ---------- personas ----------
if set(ref_personas) != set(personas):
    diffs.append("persona names differ: "
                 f"hardcoded-only={sorted(set(ref_personas) - set(personas))}, "
                 f"yaml-only={sorted(set(personas) - set(ref_personas))}")
for name in sorted(set(ref_personas) & set(personas)):
    rp, gp = ref_personas[name], personas[name]
    if set(rp) != set(gp):
        diffs.append(f"persona {name}: field keys differ — hardcoded={sorted(rp)} yaml={sorted(gp)}")
    for f in sorted(set(rp) & set(gp)):
        if rp[f] != gp[f]:
            diffs.append(f"persona {name}.{f}: value differs")
    if "model" in gp:
        diffs.append(f"persona {name}: loaded dict unexpectedly carries a 'model' key")

# ---------- scaffolds ----------
cmp_str_map("scaffold", ref_scaffolds, scaffolds)

# ---------- books ----------
if set(ref_books) != set(books):
    diffs.append("book ids differ: "
                 f"hardcoded-only={sorted(set(ref_books) - set(books))}, "
                 f"yaml-only={sorted(set(books) - set(ref_books))}")
nonstr = [k for k in books if not isinstance(k, str)]
if nonstr:
    diffs.append(f"book ids must be strings; got non-strings: {nonstr}")

for bid in sorted(set(ref_books) & set(books), key=int):
    rb, gb = ref_books[bid], books[bid]
    if set(rb) != set(gb):
        diffs.append(f"book {bid}: field keys differ — hardcoded={sorted(rb)} yaml={sorted(gb)}")
    for f in sorted(set(rb) & set(gb)):
        rv, gv = rb[f], gb[f]
        if f == "turn_order":
            if not all(isinstance(t, tuple) for t in gv):
                diffs.append(f"book {bid}.turn_order: entries must be tuples")
            if len(rv) != len(gv):
                diffs.append(f"book {bid}.turn_order: length {len(rv)} vs {len(gv)}")
            else:
                for i, (a, b) in enumerate(zip(rv, gv)):
                    if a != b:
                        diffs.append(f"book {bid}.turn_order[{i}] differs:\n      ref={a!r}\n      yaml={b!r}")
        elif f == "staging_clause":
            if rv is not gv:   # identity matters: build_muse_prompt uses `is`
                diffs.append(f"book {bid}.staging_clause: not the SAME constant object as hardcoded")
        else:
            if rv != gv:
                diffs.append(f"book {bid}.{f}: value differs")

# ---------- requirement #3: Book V -> NO_STAGING, everyone else -> STAGING ----------
for bid, b in books.items():
    expected = scribe.NO_STAGING_CLAUSE if bid == "5" else scribe.STAGING_CLAUSE
    if b.get("staging_clause") is not expected:
        want = "NO_STAGING" if bid == "5" else "STAGING"
        diffs.append(f"book {bid}: staging_clause is not the expected {want} constant")

# ---------- model overrides: capability wired, nobody uses it yet ----------
if models:
    diffs.append(f"persona_models should be empty in phase 1, got: {sorted(models)}")

# ---------- report ----------
print(f"loaded from athena.yaml: {len(personas)} personas, {len(books)} books, "
      f"{len(scaffolds)} scaffolds, {len(models)} model-overrides")
print(f"reference (hardcoded)  : {len(ref_personas)} personas, {len(ref_books)} books, "
      f"{len(ref_scaffolds)} scaffolds")

if diffs:
    print(f"\n✗ {len(diffs)} DIFF(S) — port is NOT faithful:")
    for d in diffs:
        print("  -", d)
    sys.exit(1)

print("\n✓ ZERO DIFFS — athena.yaml reproduces the hardcoded engine exactly.")
print("  (same persona/book/scaffold keys, same turn-order tuples, same field values,")
print("   same staging-clause constant per book, model capability wired but unused.)")
sys.exit(0)
