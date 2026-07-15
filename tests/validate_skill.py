"""Self-contained structural validation for the packaged skill."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "speckit-jira-git"
ENTRYPOINT = SKILL / "SKILL.md"
REQUIRED_DIRS = ("agents", "assets", "bin", "references", "scripts")


def frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise ValueError("SKILL.md must begin with YAML frontmatter")
    raw = text.split("\n---\n", 1)[0][4:]
    values: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            raise ValueError(f"invalid frontmatter line: {line}")
        key, value = line.split(":", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


if not ENTRYPOINT.is_file():
    raise SystemExit("ERROR: missing skills/speckit-jira-git/SKILL.md")
metadata = frontmatter(ENTRYPOINT.read_text(encoding="utf-8"))
if set(metadata) != {"name", "description"}:
    raise SystemExit("ERROR: SKILL.md frontmatter must contain only name and description")
if metadata["name"] != "speckit-jira-git":
    raise SystemExit("ERROR: skill name must be speckit-jira-git")
if not metadata["description"] or len(metadata["description"]) > 1024:
    raise SystemExit("ERROR: skill description must contain 1-1024 characters")
missing = [name for name in REQUIRED_DIRS if not (SKILL / name).is_dir()]
if missing:
    raise SystemExit(f"ERROR: missing skill directories: {', '.join(missing)}")
if not (SKILL / "agents" / "openai.yaml").is_file():
    raise SystemExit("ERROR: missing agents/openai.yaml")
if not (SKILL / "bin" / "speckit-jira-git.js").is_file():
    raise SystemExit("ERROR: missing bundled CLI")

print("Validated skill structure: skills/speckit-jira-git")
