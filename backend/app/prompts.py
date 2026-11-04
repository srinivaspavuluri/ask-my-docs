from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

def load_prompt(version: str) -> str:
    path = PROMPTS_DIR / f"{version}.txt"
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8")
