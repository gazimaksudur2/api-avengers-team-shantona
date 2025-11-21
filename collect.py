from pathlib import Path

# Configure these if you want
PROJECT_ROOT = Path(__file__).resolve().parent  # or Path("path/to/project")
INCLUDE_EXTS = {".py", ".ipynb", ".json", ".toml", ".yaml", ".yml"}  # adjust as you like
OUTPUT_FILE = PROJECT_ROOT / "code_for_llm.txt"


def is_hidden(path: Path, root: Path) -> bool:
    """
    Return True if any part of the path (relative to root) starts with a dot.
    That means we skip .venv, .git, .pytest_cache, .whatever, and their contents.
    """
    try:
        parts = path.relative_to(root).parts
    except ValueError:
        # path is not under root
        parts = path.parts

    return any(part.startswith(".") for part in parts)


def iter_source_files(root: Path):
    """Yield source files under root, skipping hidden folders/files."""
    for p in root.rglob("*"):
        if p.is_dir():
            continue
        if is_hidden(p, root):
            continue
        if p.suffix in INCLUDE_EXTS:
            yield p


def main():
    with OUTPUT_FILE.open("w", encoding="utf-8") as out:
        for file_path in sorted(iter_source_files(PROJECT_ROOT)):
            rel = file_path.relative_to(PROJECT_ROOT)
            out.write(f"\n\n===== FILE: {rel} =====\n\n")
            try:
                text = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                # Fallback if there is some weird encoding
                text = file_path.read_text(errors="replace")

            out.write(text)

    print(f"Collected code into: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()