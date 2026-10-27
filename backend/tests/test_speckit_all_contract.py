"""Feature 039 FR-007 / SC-006: the product command and the repo toolchain ship one contract.

The wording is per locale (a Spanish prompt cannot be byte-identical to an English one), so what
is asserted is what actually has to agree: the same eight stages in the same order, the same six
rules, and the markers that delimit the block.
"""
import re
from pathlib import Path

from app.assistant.commands import pipeline

ROOT = Path(__file__).resolve().parents[2]
PROMPTS = {
    "es": ROOT / "cli/bizview_cli/workspace_template/agent_commands/es/speckit-all.md",
    "en": ROOT / "cli/bizview_cli/workspace_template/agent_commands/en/speckit-all.md",
}
SKILL = ROOT / ".claude/skills/speckit-all/SKILL.md"
CONTRACT = ROOT / "specs/039-speckit-all/contracts/speckit-all.md"

OPEN, CLOSE = "<!-- bizview:contrato-autonomo -->", "<!-- /bizview:contrato-autonomo -->"
STAGE_LINE = " → ".join(pipeline.STAGES)


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_every_toolchain_carries_the_markers_once():
    for path in (*PROMPTS.values(), SKILL):
        text = _text(path)
        assert text.count(OPEN) == 1, path
        assert text.count(CLOSE) == 1, path
        assert text.index(OPEN) < text.index(CLOSE), path


def test_the_block_has_the_same_six_rules():
    for path in (*PROMPTS.values(), SKILL):
        text = _text(path)
        block = text[text.index(OPEN):text.index(CLOSE)]
        bullets = [line for line in block.splitlines() if line.startswith("- ")]
        assert len(bullets) == 6, path


def test_the_stage_order_is_the_code_and_the_prompts():
    assert STAGE_LINE == ("specify → clarify → plan → tasks → analyze → implement → converge "
                          "→ verify")
    for path in (*PROMPTS.values(), SKILL, CONTRACT):
        assert STAGE_LINE in _text(path), path


def test_the_decision_format_is_the_one_the_guard_reads():
    for path in (*PROMPTS.values(), SKILL):
        assert pipeline.DECISIONS_HEADING in _text(path), path
    assert pipeline.is_decision("- [clarify] se agrupa por día — es el orden de la spec")
    es = _text(PROMPTS["es"])
    en = _text(PROMPTS["en"])
    assert re.search(r"- \[(etapa|stage)\]", es)
    assert re.search(r"- \[(etapa|stage)\]", en)
