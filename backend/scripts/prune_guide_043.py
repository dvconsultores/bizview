"""043 WS-A: drop the `agente` section and its 15 topics from the guide index. Run once, delete.

Line-based surgery, not a YAML round-trip: the index carries comments and flow styles
(`{es: …}`, `[a, b]`) that a dump would reformat, and the drift test diffs the file. The result is
re-read with `yaml.safe_load` and checked before it is written, so a broken prune fails loudly.

Usage: python scripts/prune_guide_043.py [path/to/index.yaml]
"""
import re
import sys
from pathlib import Path

import yaml

INDEX = Path(__file__).resolve().parents[1] / "app" / "guide" / "index.yaml"
SECTION = "agente"
TOPICS = (
    "chat-del-agente", "brief-con-imagen", "alcance-del-agente", "metodo-spec-kit",
    "comandos-especificar", "comandos-planificar", "comandos-construir", "todo-el-recorrido",
    "tipos-de-spec", "definir-una-integracion", "definir-un-reporte", "distribuciones",
    "recorrido-integracion-a-distribucion", "recorrido-reporte-directo",
    "perfiles-de-ejecucion",
)
EXPECTED = (8, 41)          # sections, topics after the prune


def _blocks(text: str) -> list[str]:
    """Split a YAML list body into entries, each starting at `  - id: ` (leading text kept)."""
    return re.split(r"(?m)^(?=  - id: )", text)


def _id(block: str) -> str | None:
    match = re.match(r"  - id: (\S+)", block)
    return match.group(1) if match else None


def main(path: Path = INDEX) -> int:
    text = path.read_text(encoding="utf-8")
    head, topics_marker, topics_body = text.partition("\ntopics:")
    header, sections_marker, sections_body = head.partition("\nsections:")
    if not topics_marker or not sections_marker:
        print("index.yaml: sections/topics markers not found", file=sys.stderr)
        return 1

    kept, removed_sections = [], 0
    for block in _blocks(sections_body):
        if _id(block) == SECTION:
            removed_sections += 1
            continue
        kept.append(block)
    kept_sections = kept

    kept, removed_topics = [], 0
    for block in _blocks(topics_body):
        if _id(block) in TOPICS:
            removed_topics += 1
            continue
        kept.append(block)

    alive = {_id(block) for block in kept if _id(block)}

    def fix_related(match: re.Match[str]) -> str:
        ids = [i.strip() for i in match.group(1).split(",") if i.strip()]
        keep = [i for i in ids if i in alive]
        return f"    related: [{', '.join(keep)}]" if keep else "    related: []"

    body = re.sub(r"(?m)^    related: \[(.*)\]$", fix_related, "".join(kept))
    result = f"{header}\nsections:{''.join(kept_sections)}\ntopics:{body}"

    parsed = yaml.safe_load(result)
    got = (len(parsed["sections"]), len(parsed["topics"]))
    if got != EXPECTED:
        print(f"index.yaml: expected {EXPECTED}, got {got}", file=sys.stderr)
        return 1
    ids = {t["id"] for t in parsed["topics"]}
    dangling = sorted({r for t in parsed["topics"] for r in t.get("related", [])} - ids)
    if dangling:
        print(f"index.yaml: dangling related ids: {dangling}", file=sys.stderr)
        return 1
    missing = [t["id"] for t in parsed["topics"]
               if not all((path.parent / lang / f"{t['id']}.md").is_file()
                          for lang in ("es", "en"))]
    if missing:
        print(f"index.yaml: topics without a body: {missing}", file=sys.stderr)
        return 1

    path.write_text(result, encoding="utf-8")
    print(f"removed {removed_sections} section / {removed_topics} topics")
    return 0 if (removed_sections, removed_topics) == (1, len(TOPICS)) else 1


if __name__ == "__main__":
    raise SystemExit(main(Path(sys.argv[1]) if len(sys.argv) > 1 else INDEX))
