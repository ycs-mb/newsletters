# shared/assemble_prompt.py
"""
Assembles topics/<slug>/prompt.md from three layers:
  1. topics/<slug>/topic.md      — topic-specific research
  2. shared/prompts/design-guide.md — locked design conventions
  3. shared/prompts/ops-guide.md    — locked delivery steps

The string {SLUG} in design-guide.md and ops-guide.md is replaced with the slug.
"""
import sys
from pathlib import Path

_DEFAULT_REPO_ROOT = Path(__file__).parent.parent


def assemble(slug: str, repo_root: Path = _DEFAULT_REPO_ROOT) -> Path:
    """Assemble prompt.md from three layers. Returns path to written file.

    Raises FileNotFoundError if any layer file is missing.
    """
    shared_prompts = repo_root / "shared" / "prompts"
    layers = {
        "topic":  repo_root / "topics" / slug / "topic.md",
        "design": shared_prompts / "design-guide.md",
        "ops":    shared_prompts / "ops-guide.md",
    }
    for name, path in layers.items():
        if not path.exists():
            raise FileNotFoundError(f"Missing {name} layer: {path}")

    topic_text  = layers["topic"].read_text()
    design_text = layers["design"].read_text().replace("{SLUG}", slug)
    ops_text    = layers["ops"].read_text().replace("{SLUG}", slug)

    prompt = "\n\n---\n\n".join([topic_text, design_text, ops_text])
    out = repo_root / "topics" / slug / "prompt.md"
    out.write_text(prompt)
    return out


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: assemble_prompt.py <slug>", file=sys.stderr)
        sys.exit(1)
    slug = sys.argv[1]
    try:
        out = assemble(slug)
        print(f"Assembled: {out}")
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
