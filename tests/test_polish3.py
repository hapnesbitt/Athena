"""polish3.py with a fake cloud: the budget holds, each round builds on the best version, the keep rule and the hard gates hold, and no earlier file changes."""
import hashlib
import json
import os
import shutil
import urllib.error
from pathlib import Path

import pytest

import assemble
import polish
import polish3

ROOT = Path(__file__).resolve().parent.parent
COPIED = ["voice_bible.md", "ATHENA_song_map.md", "ATHENA_manuscript.md", "assemble.py"]
FAKE_HOMER = "Now the Dawn arose from her couch. And the lady nymph abode with him. Many words of the book."


class FakeCloud:
    """Answers /api/chat like Ollama. A writer call changes the first word of each line to a numbered FRESH tag, which keeps the
    stanza's length, hook and canon words, unless `rewriter(old_lines, tag)` says otherwise. A judge call scores everything 6 and
    answers any comparison from `compare(old_label, new_label)`."""

    def __init__(self, rewriter=None, compare=None):
        self.calls, self.prompts = [], []
        self.rewriter = rewriter or (lambda old, tag: [" ".join([tag] + ln.split()[1:]) for ln in old])
        self.compare = compare or (lambda old, new: ([5, 5], [7, 7], new))
        self.fail_with = None
        self.rewrites = 0

    def __call__(self, payload):
        self.calls.append(payload)
        user = payload["messages"][1]["content"]
        self.prompts.append(user)
        if self.fail_with:
            raise self.fail_with
        if payload.get("format") == "json":
            return self.judge(user)
        self.rewrites += 1
        old = user.split("── THE STANZA TO REWRITE ──\n")[1].split("\n\n── WHAT THE EDITOR")[0].split("\n")
        lines = self.rewriter(old, f"FRESH{self.rewrites}")
        return {"message": {"content": "\n".join(lines)}, "prompt_eval_count": 300, "eval_count": 40, "done_reason": "stop"}

    def judge(self, user):
        ids = [i for i in dict.fromkeys(_ids(user))]
        reply = {"scores": {i: [6, 6] for i in ids}, "weakest": [{"id": i, "problem": f"{i} is weak", "homer": ""} for i in ids[:3]]}
        if "VERSION A:" in user:
            sid = user.split("Stanza ")[1].split(" ")[0]
            reply["scores"].pop(sid, None)
            reply["weakest"] = [w for w in reply["weakest"] if w["id"] != sid]
            b = user.split("VERSION B:\n")[1].split("\n\n── REPLY")[0]
            new_is_b = f"FRESH{self.rewrites}" in b
            new_label = "B" if new_is_b else "A"
            old_label = "A" if new_is_b else "B"
            old_scores, new_scores, pick = self.compare(old_label, new_label)
            reply["compare"] = {old_label: old_scores, new_label: new_scores, "better": pick, "why": "because", "lyrics_A": [], "lyrics_B": []}
        return {"message": {"content": json.dumps(reply)}, "prompt_eval_count": 3000, "eval_count": 300, "done_reason": "stop"}


def _ids(user):
    import re
    return re.findall(r"^<(S\d+)>", user.split("── THE SCENE ──")[1], re.M)


@pytest.fixture
def repo(tmp_path, monkeypatch):
    for name in COPIED:
        shutil.copy(ROOT / name, tmp_path / name)
    for path in ROOT.glob("scene_book*.md"):
        if "polished3" not in path.name:            # a run's output in this checkout must not leak into the tests
            shutil.copy(path, tmp_path / path.name)
    monkeypatch.setattr(polish3, "HERE", str(tmp_path))
    monkeypatch.setattr(polish, "VOICE_BIBLE_PATH", str(tmp_path / "voice_bible.md"))
    monkeypatch.setattr(assemble, "HERE", str(tmp_path))
    monkeypatch.setattr(polish3, "homer_book", lambda book: FAKE_HOMER)
    return tmp_path


def run(fake, *args):
    """No referee unless a test asks for one, so most budgets below are simply 1 + 2 a round."""
    args = [str(a) for a in args]
    return polish3.main(args if "--referee" in args else args + ["--referee", "none"], post=fake)


def fingerprints(folder):
    keep = list(folder.glob("scene_book*.md")) + [folder / "ATHENA_manuscript.md", folder / "assemble.py"]
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in keep if "polished3" not in p.name}


def rounds_log(repo, book=5):
    rows = [json.loads(x) for x in (repo / "polish3_logs" / f"book{book}_rounds.jsonl").read_text().splitlines()]
    return [r for r in rows if r["event"] == "round"]


def writer_prompts(fake):
    return [u for u, c in zip(fake.prompts, fake.calls) if c.get("format") != "json"]


# ---------- budget ----------

@pytest.mark.parametrize("budget", [4, 5, 6, 7, 11])
def test_budget_is_never_exceeded_and_is_printed(repo, capsys, budget):
    fake = FakeCloud()
    assert run(fake, "--books", "all", "--rounds", 5, "--budget", budget) == 0
    assert len(fake.calls) <= budget
    assert f"requests used: {len(fake.calls)} of {budget}" in capsys.readouterr().out


def test_a_round_that_cant_finish_is_not_started(repo, capsys):
    fake = FakeCloud()
    run(fake, "--books", 5, "--rounds", 5, "--budget", 5)      # open, rewrite, judge, close = 4; a fifth alone would be a rewrite nobody judges
    assert len(fake.calls) == 4
    assert "budget reached" in capsys.readouterr().out


def test_budget_required_and_estimate_sends_nothing(repo, capsys):
    fake = FakeCloud()
    with pytest.raises(SystemExit):
        run(fake, "--books", 5, "--rounds", 1)
    with pytest.raises(SystemExit):
        run(fake, "--books", 5, "--rounds", 1, "--budget", 3)
    assert run(fake, "--estimate", "--books", "5", "--rounds", 2) == 0
    assert run(fake, "--spent") == 0
    assert fake.calls == []
    out = capsys.readouterr().out
    assert "to open and close 1 book(s): 2 requests" in out and "each round, at most: 2 requests" in out and "--budget 6 requests" in out


def test_local_models_are_refused(repo):
    fake = FakeCloud()
    with pytest.raises(SystemExit):
        run(fake, "--books", 5, "--budget", 5, "--judge", "gemma4:e4b")
    assert fake.calls == []


def test_quota_refusal_stops_at_once_and_is_counted(repo, capsys):
    fake = FakeCloud()
    fake.fail_with = urllib.error.HTTPError("u", 429, "quota", {}, None)
    assert run(fake, "--books", "all", "--rounds", 3, "--budget", 50) == 3
    assert len(fake.calls) == 1
    out = capsys.readouterr().out
    assert "cloud refused" in out and "requests used: 1 of 50" in out
    assert json.loads((repo / "polish3_logs" / "spend.jsonl").read_text().splitlines()[0])["status"] == "http 429"


def test_cloud_down_stops_after_two_errors(repo, capsys):
    fake = FakeCloud()
    fake.fail_with = TimeoutError("timed out")
    run(fake, "--books", "all", "--rounds", 3, "--budget", 50)
    assert len(fake.calls) == 2
    assert "errors in a row" in capsys.readouterr().out


def test_spend_ledger_records_every_call(repo, capsys):
    fake = FakeCloud()
    run(fake, "--books", 5, "--rounds", 2, "--budget", 6)
    rows = [json.loads(x) for x in (repo / "polish3_logs" / "spend.jsonl").read_text().splitlines()]
    assert len(rows) == len(fake.calls)
    assert {r["kind"] for r in rows} == {"judge", "rewrite"}
    assert rows[0]["tokens_in"] == 3000
    run(fake, "--spent")
    assert f"all: {len(rows)} requests" in capsys.readouterr().out


# ---------- rounds and the keep rule ----------

def test_a_kept_rewrite_is_what_the_next_round_starts_from(repo):
    fake = FakeCloud()
    run(fake, "--books", 5, "--rounds", 2, "--budget", 6)
    prompts = writer_prompts(fake)
    assert "FRESH1" not in prompts[0] and "FRESH1" in prompts[1]
    final = (repo / "scene_book5_polished3.md").read_text()
    assert "FRESH1" in final and "FRESH2" in final
    rows = rounds_log(repo)
    assert [r["decision"] for r in rows] == ["kept", "kept"]
    assert rows[0]["stanza"] != rows[1]["stanza"]


@pytest.mark.parametrize("old,new,pick_is_new", [
    ([5, 5], [5, 5], True),      # a tie is not better
    ([6, 6], [6, 7], True),      # one point is within the judge's noise
    ([6, 6], [7, 5], True),      # one score fell
    ([6, 6], [5, 9], True),      # story fell, though the sum rose
    ([5, 5], [8, 8], False),     # the numbers say yes, the judge's own pick says no
])
def test_a_rewrite_that_does_not_score_better_is_discarded(repo, old, new, pick_is_new):
    fake = FakeCloud(compare=lambda old_label, new_label: (old, new, new_label if pick_is_new else old_label))
    run(fake, "--books", 5, "--rounds", 1, "--budget", 4)
    assert rounds_log(repo)[0]["decision"] == "discarded"
    assert (repo / "scene_book5_polished3.md").read_text().strip() == (repo / "scene_book5_polished2.md").read_text().strip()


def test_after_a_discard_the_next_round_tries_another_stanza(repo):
    fake = FakeCloud(compare=lambda old_label, new_label: ([6, 6], [5, 5], old_label))
    run(fake, "--books", 5, "--rounds", 3, "--budget", 8)
    picked = [r["stanza"] for r in rounds_log(repo)]
    assert len(picked) == 3 and len(set(picked)) == 3
    assert all(r["decision"] == "discarded" for r in rounds_log(repo))


def test_the_judge_sees_the_two_versions_blind_and_in_both_orders(repo):
    fake = FakeCloud()
    run(fake, "--books", "1-6", "--rounds", 2, "--budget", 40)
    labels = {r["label"] for b in range(1, 7) for r in rounds_log(repo, b) if "label" in r}
    assert labels == {"A", "B"}
    compares = [u for u in fake.prompts if "VERSION A:" in u]
    assert compares
    for user in compares:
        assert "old version" not in user.lower() and "new version" not in user.lower() and "rewrite" not in user.lower().split("── compare ──")[1]


def verdicts(*answers):
    """A compare() for FakeCloud that gives each answer in turn: (old scores, new scores, whether the pick is the new version)."""
    answers = iter(answers)

    def compare(old_label, new_label):
        old, new, yes = next(answers)
        return old, new, new_label if yes else old_label
    return compare


def test_the_referee_is_a_different_model_asked_with_the_order_swapped_and_must_agree(repo):
    fake = FakeCloud(compare=verdicts(([5, 5], [7, 7], True), ([6, 6], [6, 6], True)))
    run(fake, "--books", 5, "--rounds", 1, "--budget", 5, "--referee", "gpt-oss:120b-cloud")
    assert [c["model"] for c in fake.calls] == ["gemma4:31b-cloud", "gemma4:31b-cloud", "gemma4:31b-cloud", "gpt-oss:120b-cloud"]
    row = rounds_log(repo)[0]
    assert row["decision"] == "discarded" and row["old"] == [5, 5] and row["new"] == [7, 7] and row["ref_new"] == [6, 6] and row["ref_better"] == "new"
    judge_b, referee_b = (u.split("VERSION B:\n")[1].split("\n\n── REPLY")[0] for u in (fake.prompts[2], fake.prompts[3]))
    assert ("FRESH1" in judge_b) != ("FRESH1" in referee_b)      # the new version changed sides
    referee = fake.prompts[3]
    assert FAKE_HOMER in referee and "morally murky PARTNERSHIP" in referee and "BEGIN CADENCE SAMPLE" in referee
    assert '"scores"' not in referee and "weakest" not in referee


def test_a_rewrite_ships_when_judge_and_referee_both_prefer_it(repo):
    fake = FakeCloud(compare=verdicts(([5, 5], [7, 7], True), ([6, 6], [8, 6], True)))
    run(fake, "--books", 5, "--rounds", 1, "--budget", 5, "--referee", "gpt-oss:120b-cloud")
    row = rounds_log(repo)[0]
    assert row["decision"] == "kept"
    assert "FRESH1" in (repo / "scene_book5_polished3.md").read_text()
    log = (repo / "polish3_logs" / "book5_rounds.md").read_text()
    assert "Referee (gpt-oss:120b-cloud), order swapped: old [6, 6], new [8, 6]" in log


def test_the_referee_only_runs_after_the_judge_passes_a_rewrite(repo):
    fake = FakeCloud(compare=verdicts(([6, 6], [5, 5], False)))
    run(fake, "--books", 5, "--rounds", 1, "--budget", 5, "--referee", "gpt-oss:120b-cloud")
    assert [c["model"] for c in fake.calls].count("gpt-oss:120b-cloud") == 0 and len(fake.calls) == 3


def test_a_round_is_not_started_without_a_request_for_the_referee(repo, capsys):
    fake = FakeCloud()
    run(fake, "--books", 5, "--rounds", 2, "--budget", 7, "--referee", "gpt-oss:120b-cloud")    # 4 for the first round leaves 3, and a round needs 3 + 1 to close
    assert len(fake.calls) == 5
    assert "budget reached" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        run(FakeCloud(), "--books", 5, "--budget", 4, "--referee", "gpt-oss:120b-cloud")


def test_a_referee_that_cant_be_read_is_a_no(repo, monkeypatch):
    fake = FakeCloud(compare=verdicts(([5, 5], [7, 7], True)))
    good = fake.judge
    monkeypatch.setattr(fake, "judge", lambda user: good(user) if "weakest" in user else {"message": {"content": "no json here"}, "done_reason": "stop"})
    run(fake, "--books", 5, "--rounds", 1, "--budget", 6, "--referee", "gpt-oss:120b-cloud")
    assert len(fake.calls) == 5
    row = rounds_log(repo)[0]
    assert row["decision"] == "discarded" and "referee" in row["gates"][0]


def test_a_rewrite_the_referee_cant_finish_checking_does_not_ship(repo, monkeypatch):
    """A judge retry and a referee retry can together outrun the budget. The rewrite must then be discarded, not shipped unchecked."""
    fake = FakeCloud(compare=verdicts(([5, 5], [7, 7], True)))
    good = fake.judge
    judge_bad_once = iter([True])

    def replies(user):
        if "weakest" not in user or ("VERSION A:" in user and next(judge_bad_once, False)):
            return {"message": {"content": "oops"}, "done_reason": "stop"}
        return good(user)

    monkeypatch.setattr(fake, "judge", replies)
    run(fake, "--books", 5, "--rounds", 1, "--budget", 5, "--referee", "gpt-oss:120b-cloud")
    assert len(fake.calls) == 5 and fake.calls[-1]["model"] == "gpt-oss:120b-cloud"
    row = rounds_log(repo)[0]
    assert row["decision"] == "discarded" and "referee" in row["gates"][0]
    assert "FRESH1" not in (repo / "scene_book5_polished3.md").read_text()


def test_a_local_referee_is_refused_and_none_turns_it_off(repo):
    with pytest.raises(SystemExit):
        run(FakeCloud(), "--books", 5, "--budget", 5, "--referee", "gemma4:e4b")
    fake = FakeCloud()
    run(fake, "--books", 5, "--rounds", 1, "--budget", 4, "--referee", "none")
    assert len(fake.calls) == 4


def test_small_budget_is_spread_across_books_one_round_at_a_time(repo):
    fake = FakeCloud()
    run(fake, "--books", "5,9,23", "--rounds", 3, "--budget", 12)   # 3 x (open + round + close), not 3 rounds of Book V
    assert [len(rounds_log(repo, b)) for b in (5, 9, 23)] == [1, 1, 1]


def test_unreadable_judge_gets_one_retry_then_the_round_is_lost(repo, monkeypatch):
    fake = FakeCloud()
    good = fake.judge
    replies = iter([{"message": {"content": "not json"}, "done_reason": "stop"}, {"message": {"content": "{\"scores\": 3}"}, "done_reason": "stop"}])
    monkeypatch.setattr(fake, "judge", lambda user: next(replies, None) or good(user))
    assert run(fake, "--books", 5, "--rounds", 1, "--budget", 4) == 0
    assert len(fake.calls) == 2
    assert not (repo / "scene_book5_polished3.md").exists()


# ---------- hard gates ----------

def scene5(repo):
    return polish3.parse_scene((repo / "scene_book5_polished2.md").read_text())


def stanza_with(scene, words):
    return next(st for st in scene.stanzas if words in "\n".join(polish3.stanza_lines(scene, st)))


def gates(repo, book, scene, st, new_lines):
    frags = polish.bible_fragments((repo / "voice_bible.md").read_text())
    return polish3.gate_failures(book, scene, st, new_lines, frags, polish3.title_phrases())


def plain_rewrite(lines):
    return [f"This plain new line number {i} runs along with easy words" for i, _ in enumerate(lines)]


def test_a_copied_voice_bible_line_goes_nowhere_near_the_judge(repo):
    scene = scene5(repo)
    st = stanza_with(scene, "Sea's edge whispers")
    bad = plain_rewrite(polish3.stanza_lines(scene, st))
    bad[0] = "So sick of your games, Calypso I'll set your truck to flames"
    fails = gates(repo, 5, scene, st, bad)
    assert any("voice bible" in f for f in fails)

    fake = FakeCloud(rewriter=lambda old, tag: old + ["So sick of your games, Calypso I'll set your truck to flames"])
    run(fake, "--books", 5, "--rounds", 1, "--budget", 4)
    assert len(fake.calls) == 2                                       # opening judge + writer; no judge for the failed rewrite, nothing to close
    row = rounds_log(repo)[0]
    assert row["decision"] == "discarded" and "voice bible" in row["gates"][0]


def test_new_song_words_are_rejected_but_this_books_own_title_is_the_hook(repo):
    scene = scene5(repo)
    st = stanza_with(scene, "My type's a predator")
    lines = polish3.stanza_lines(scene, st)
    assert any("song words" in f for f in gates(repo, 5, scene, st, plain_rewrite(lines[:-1]) + ["I hate you so much right now, my type"]))
    assert any("song words" in f for f in gates(repo, 5, scene, st, plain_rewrite(lines[:-1]) + ["You sacked the place with all about that bass, my type"]))
    keep_hook = plain_rewrite(lines[:-1]) + ["My type's a predator who never had enough, a partner sacking towns"]
    assert not [f for f in gates(repo, 5, scene, st, keep_hook) if "song words" in f]
    chorus = stanza_with(scene, "Sea's edge whispers")
    adds_hook = plain_rewrite(polish3.stanza_lines(scene, chorus)[:-1]) + ["And that is exactly my type for the rest of the night"]
    assert not [f for f in gates(repo, 5, scene, chorus, adds_hook) if "song words" in f]
    nine = polish3.parse_scene((repo / "scene_book9_polished2.md").read_text())
    other = next(s for s in nine.stanzas if s.kind == "verse" and len(polish3.stanza_lines(nine, s)) >= 3)
    borrowed = plain_rewrite(polish3.stanza_lines(nine, other)[:-1]) + ["And that is exactly my type for the rest of the night"]
    assert any("song words" in f for f in gates(repo, 9, nine, other, borrowed))


def test_the_judge_naming_a_real_lyric_kills_a_rewrite(repo, monkeypatch):
    fake = FakeCloud()
    good = fake.judge

    def flags_lyric(user):
        reply = good(user)
        body = json.loads(reply["message"]["content"])
        if "compare" in body:
            new = next(label for label in "AB" if body["compare"][label] == [7, 7])
            body["compare"][f"lyrics_{new}"] = ["a line the judge says is a real lyric"]
            reply["message"]["content"] = json.dumps(body)
        return reply

    monkeypatch.setattr(fake, "judge", flags_lyric)
    run(fake, "--books", 5, "--rounds", 1, "--budget", 4)
    row = rounds_log(repo)[0]
    assert row["decision"] == "discarded" and "real lyric" in row["gates"][0]


@pytest.mark.parametrize("old_words,new_line", [
    ("Ten years on this island", "Seven years on this island, feasting, and the spoils"),
    ("Odysseus has spent years sacking cities", "Calypso kept a captive man, a prisoner in her caves, and the goddess holds him fast there"),
])
def test_book_five_canon_cannot_be_fixed_toward_homer(repo, old_words, new_line):
    scene = scene5(repo)
    st = stanza_with(scene, old_words)
    lines = polish3.stanza_lines(scene, st)
    fails = gates(repo, 5, scene, st, plain_rewrite(lines[:-1]) + [new_line])
    assert any("canon" in f for f in fails), fails


def test_a_stanza_may_drop_a_canon_word_but_the_scene_must_keep_saying_it(repo):
    scene = scene5(repo)
    captive = stanza_with(scene, "I've been held captive")
    better = ["No cage, no chains, just a taste for the gold,", "A partnership written in blood and in bold.",
              "But the hunger for home hits harder than the greed,", "And Ithaca's the only ghost I still need."]
    assert not [f for f in gates(repo, 5, scene, captive, better) if "canon" in f]
    lone = polish3.parse_scene("\n".join(["# T", "", "### MUSE 🎩", "", "Tonight the sea-witch keeps her man, her partner in the raid, and ten long years go by."]) + "\n")
    fails = gates(repo, 5, lone, lone.stanzas[0], ["Tonight the woman keeps her man, a friend upon the raid, and many years go by there."])
    assert any("sea" in f for f in fails) and any("ten" in f for f in fails) and any("partner" in f for f in fails)


def test_book_five_brief_and_canon_reach_the_judge_and_the_writer(repo):
    fake = FakeCloud()
    run(fake, "--books", 5, "--rounds", 1, "--budget", 4)
    for user in (fake.prompts[0], writer_prompts(fake)[0]):
        assert "morally murky PARTNERSHIP" in user and "ten missing years" in user and "the brief" in user.lower()
        assert "Calypso is a partner, not a prison" in user
    assert FAKE_HOMER in fake.prompts[0] and "BEGIN CADENCE SAMPLE" in fake.prompts[0]


def test_framing_and_song_hook_are_kept(repo):
    scene = scene5(repo)
    muse = stanza_with(scene, "Ladies and Gentlemen")
    assert any("room" in f for f in gates(repo, 5, scene, muse, plain_rewrite(polish3.stanza_lines(scene, muse))))
    hook = stanza_with(scene, "My type's a predator")
    no_hook = plain_rewrite(polish3.stanza_lines(scene, hook))
    assert any("hook" in f for f in gates(repo, 5, scene, hook, no_hook))


def test_structure_and_length_gates(repo):
    scene = scene5(repo)
    st = stanza_with(scene, "Sea's edge whispers")
    lines = polish3.stanza_lines(scene, st)
    base = plain_rewrite(lines)
    assert any("structure" in f for f in gates(repo, 5, scene, st, base[:-1] + ["### Turn 9 — HERMES 🪽"]))
    assert any("structure" in f for f in gates(repo, 5, scene, st, base[:-1] + ["[STAGING: she dances]"]))
    assert any("speaker label" in f for f in gates(repo, 5, scene, st, base[:-1] + ["Hermes: this line belongs to someone else entirely"]))
    assert any("length" in f for f in gates(repo, 5, scene, st, ["Too short."]))
    assert any("runs over" in f for f in gates(repo, 5, scene, st, base[:-1] + [" ".join(["word"] * 30)]))
    assert gates(repo, 5, scene, st, lines) == ["same as the old stanza"]
    assert gates(repo, 5, scene, st, []) == ["empty rewrite"]


def test_short_lines_have_room_to_grow_but_a_stanza_cant_balloon(repo):
    """About 25 to 40 words was the trial's canon fix for "I've been held captive". It failed a flat limit of half again."""
    scene = scene5(repo)
    st = stanza_with(scene, "I've been held captive")
    grows = ["No cage held me here, just a hunger for the gold,", "A partnership of predators, a story left untold.",
             "But the appetite is fading, and the home-fire starts to burn,", "Calypso, I'm a ghost now, it's my time to return."]
    assert len(" ".join(polish3.stanza_lines(scene, st)).split()) == 25 and len(" ".join(grows).split()) == 40
    assert not [f for f in gates(repo, 5, scene, st, grows) if "length" in f]
    assert any("length" in f for f in gates(repo, 5, scene, st, grows + ["And on it goes with many other words"]))
    assert any("length" in f for f in gates(repo, 5, scene, st, ["Far too short now."]))


def test_a_stage_direction_stays_one_stage_direction(repo):
    scene = polish3.parse_scene((repo / "scene_book10_polished2.md").read_text())
    st = next(s for s in scene.stanzas if s.kind == "staging")
    assert not gates(repo, 10, scene, st, ["[STAGING: the dancers cross the floor and choose among the tables]"])
    assert gates(repo, 10, scene, st, ["The dancers cross the floor."])


# ---------- files ----------

def test_earlier_files_stay_byte_identical_and_assemble_keeps_its_source(repo):
    before = fingerprints(repo)
    fake = FakeCloud()
    run(fake, "--books", "5,9", "--rounds", 2, "--budget", 12)
    assert fingerprints(repo) == before
    assert (repo / "scene_book5_polished3.md").exists() and (repo / "polish3_logs" / "book5_rounds.md").exists()
    text, source = assemble.scene_text("5")
    assert source == "polished2" and text == (repo / "scene_book5_polished2.md").read_text().strip()


def test_assemble_does_not_read_polished3():
    assert "polished3" not in (ROOT / "assemble.py").read_text()


def test_a_second_run_starts_from_polished3_and_keeps_a_copy_of_it(repo):
    run(FakeCloud(), "--books", 5, "--rounds", 1, "--budget", 4)
    first = (repo / "scene_book5_polished3.md").read_text()
    hand_edited = first.replace("### MUSE 🎩\n\n", "### MUSE 🎩\n\nA HAND EDIT by a person.\n\n", 1)
    (repo / "scene_book5_polished3.md").write_text(hand_edited)
    fake = FakeCloud()
    run(fake, "--books", 5, "--rounds", 1, "--budget", 4)
    assert "A HAND EDIT by a person." in fake.prompts[0]
    saved = list((repo / "polish3_logs" / "history").glob("scene_book5_polished3.*.md"))
    assert saved and any(p.read_text() == hand_edited for p in saved)
    log = (repo / "polish3_logs" / "book5_rounds.md").read_text()
    assert log.count("## Run ") == 2 and "started from scene_book5_polished3.md" in log


def test_round_log_shows_before_after_scores_and_the_closing_reading(repo, capsys):
    fake = FakeCloud()
    run(fake, "--books", 5, "--rounds", 1, "--budget", 4)
    log = (repo / "polish3_logs" / "book5_rounds.md").read_text()
    for needle in ("Opening scores", "Before:", "After:", "Scores [story, speak]: old", "KEPT", "Requests used so far: 3 of 4", "Closing reading, the opening's exact question", "Untouched stanzas that moved anyway", "do not measure progress"):
        assert needle in log, needle
    assert "VERSION A:" not in fake.prompts[3] and fake.prompts[3].split("── THE SCENE ──")[0] == fake.prompts[0].split("── THE SCENE ──")[0]
    assert "FRESH1" in fake.prompts[3] and fake.calls[3]["options"]["seed"] == fake.calls[0]["options"]["seed"]
    assert "closing reading" in capsys.readouterr().out


def test_nothing_kept_means_no_closing_call_and_a_closing_is_kept_back_from_the_rounds(repo):
    fake = FakeCloud(compare=lambda old_label, new_label: ([6, 6], [5, 5], old_label))
    run(fake, "--books", 5, "--rounds", 1, "--budget", 4)
    assert len(fake.calls) == 3
    fake = FakeCloud()
    run(fake, "--books", "9,23", "--rounds", 2, "--budget", 8)
    assert len(fake.calls) <= 8
    assert sum("closing" == json.loads(x)["event"] for b in (9, 23) for x in (repo / "polish3_logs" / f"book{b}_rounds.jsonl").read_text().splitlines()) == 2


def test_the_comparison_names_the_complaint_without_saying_which_version_is_new(repo):
    fake = FakeCloud(compare=verdicts(([5, 5], [7, 7], True), ([6, 6], [8, 6], True)))
    run(fake, "--books", 5, "--rounds", 1, "--budget", 5, "--referee", "gpt-oss:120b-cloud")
    for user in (fake.prompts[2], fake.prompts[3]):
        assert 'A reader raised this concern about the stanza: "S1 is weak"' in user


# ---------- parsing and reference texts ----------

@pytest.mark.parametrize("book", range(1, 25))
def test_every_scene_parses_and_joins_back_exactly(book):
    text = assemble.scene_text(str(book))[0] + "\n"
    scene = polish3.parse_scene(text)
    assert "\n".join(scene.lines) + "\n" == text
    assert scene.stanzas, book
    st = scene.stanzas[len(scene.stanzas) // 2]
    assert polish3.parse_scene(polish3.replace_stanza(scene, st, polish3.stanza_lines(scene, st))).lines == scene.lines
    for s in scene.stanzas:
        assert s.speaker in polish3.PERSONAS
        for ln in polish3.stanza_lines(scene, s):
            assert ln.strip() and not ln.startswith("#") and ln.strip() != "---"


def test_a_reprise_changes_together(repo):
    scene = scene5(repo)
    st = stanza_with(scene, "He sacks my cities")
    assert len(polish3.copies_of(scene, st)) == 2
    new = plain_rewrite(polish3.stanza_lines(scene, st))
    after = polish3.replace_stanza(scene, st, new)
    assert "He sacks my cities" not in after and after.count(new[0]) == 2
    assert polish3.stanza_shape(polish3.parse_scene(after)) == polish3.stanza_shape(scene)


def test_a_homer_quote_the_judge_made_up_is_dropped():
    scene = polish3.parse_scene("# T\n\n### MUSE 🎩\n\nOne line here.\n\nAnother line here.\n")
    raw = json.dumps({"scores": {"S1": [5, 5], "S2": [6, 6]}, "weakest": [
        {"id": "S1", "problem": "p", "homer": "the Dawn arose"}, {"id": "S2", "problem": "q", "homer": "words Homer never wrote"}, {"id": "S99", "problem": "r", "homer": ""}]})
    verdict = polish3.read_judge_reply(raw, scene, FAKE_HOMER)
    assert [w["id"] for w in verdict["weakest"]] == ["S1", "S2"]
    assert verdict["weakest"][0]["homer"] == "the Dawn arose" and verdict["weakest"][1]["homer"] == ""


def test_a_judge_reply_that_skips_a_stanza_or_goes_off_scale_is_unreadable():
    scene = polish3.parse_scene("# T\n\n### MUSE 🎩\n\nOne line here.\n\nAnother line here.\n")
    with pytest.raises(polish3.Unreadable):
        polish3.read_judge_reply(json.dumps({"scores": {"S1": [5, 5]}}), scene, FAKE_HOMER)
    with pytest.raises(polish3.Unreadable):
        polish3.read_judge_reply(json.dumps({"scores": {"S1": [5, 50], "S2": [5, 5]}}), scene, FAKE_HOMER)


@pytest.mark.skipif(not os.path.exists(polish3.LIBRARY_DB), reason="no library here")
def test_homer_is_the_right_book_from_the_library():
    five = polish3.homer_book(5)
    assert "Calypso" in five and "Hermes" in five and "image" not in five.split("\n\n")
    assert "Ino" in five
    assert "Nausicaa" in polish3.homer_book(6)
    last = polish3.homer_book(24)
    assert "covenant" in last and "Thy verse seems" not in last


def test_requests_name_polish3_because_ollama_com_blocks_urllibs_default(monkeypatch):
    seen = {}

    class Reply:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"message": {"content": "ok"}}'

    def fake_urlopen(req, timeout=None):
        seen["ua"] = req.get_header("User-agent")
        seen["url"] = req.full_url
        return Reply()

    monkeypatch.setattr(polish3.urllib.request, "urlopen", fake_urlopen)
    assert polish3.http_post({"model": "x"})["message"]["content"] == "ok"
    assert "polish3" in seen["ua"] and "urllib" not in seen["ua"].lower()
    assert seen["url"].endswith("/api/chat")
