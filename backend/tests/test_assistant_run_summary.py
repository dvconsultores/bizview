"""«Resumen del run» is read by a person — one decision per line, no wall of text (2026-10-26).

The report from production pasted the whole summary as a single paragraph
(`Decisiones tomadas: a; b; c; …`), because the run summary joined the list with «; » and the
planner had no way to scan it. The same decision, noted in two turns, also appeared twice.
"""
from app.assistant import service
from app.i18n import use_locale


def _summary(decisions: list[str], **extra) -> dict:
    return {"tokens": 10, "decisions": service._summary_decisions(decisions), **extra}


def test_each_decision_is_its_own_line():
    text = service._summary_text(_summary(["uno", "dos", "tres"]), None)
    lines = text.splitlines()
    assert lines[0] == "Resumen del run"
    assert "Decisiones tomadas:" in lines
    start = lines.index("Decisiones tomadas:")
    assert lines[start + 1:start + 4] == ["- uno", "- dos", "- tres"]
    assert all("; " not in line for line in lines[start + 1:start + 4])


def test_repeated_decisions_are_folded():
    assert service._summary_decisions(["A", " b ", "a", "B", ""]) == ["A", "b"]


def test_a_huge_decision_is_clipped_and_the_list_is_bounded():
    long = "x" * (service.SUMMARY_DECISION_CHARS + 50)
    items = service._summary_decisions([long, *[f"d{i}" for i in range(40)]])
    assert len(items) == service.SUMMARY_DECISIONS_MAX
    assert items[-1] == "d39"                       # the newest are kept
    clipped = service._summary_decisions([long])[0]
    assert len(clipped) == service.SUMMARY_DECISION_CHARS and clipped.endswith("…")


def test_newlines_inside_a_decision_do_not_break_the_list():
    text = service._summary_text(_summary(["primera\nsegunda"]), None)
    assert "- primera segunda" in text.splitlines()


def test_the_summary_follows_the_language():
    summary = _summary(["uno"], version=7)
    with use_locale("en"):
        text = service._summary_text(summary, "completed")
    assert "Decisions taken:" in text.splitlines()
    assert "- uno" in text.splitlines()
    assert "Tokens used: 10" in text.splitlines()
