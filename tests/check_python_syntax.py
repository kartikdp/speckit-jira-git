"""Compile Python source in memory so checks do not create package artifacts."""
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "speckit-jira-git" / "scripts"

for path in sorted(SCRIPTS.glob("*.py")):
    compile(path.read_text(encoding="utf-8"), str(path), "exec")

print(f"Validated Python syntax: {len(list(SCRIPTS.glob('*.py')))} files")
