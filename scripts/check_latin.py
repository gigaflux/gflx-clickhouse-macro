"""Module for enforcing strict Latin-only (ASCII) character checks across the repository.

This script scans source code, tests, documentation, and configuration files
to ensure that no non-Latin characters are present.
"""

import pathlib
import sys


def check_file_characters(file_path: pathlib.Path, allowed_bytes: set[int]) -> bool:
    """Scan a single file byte by byte to find any non-Latin characters.

    Args:
        file_path (pathlib.Path): The path to the file being scanned.
        allowed_bytes (set[int]): A set of valid ASCII byte integers (0-127).

    Returns:
        bool: True if non-Latin characters were found, False otherwise.
    """
    content = file_path.read_bytes()
    for idx, byte in enumerate(content):
        if byte not in allowed_bytes:
            # Calculate the exact line number where the violation occurred
            line_num = content[:idx].count(b"\n") + 1
            # Attempt to decode the invalid byte for a cleaner error log
            try:
                content[idx : idx + 1].decode("utf-8")
            except UnicodeDecodeError:
                char = hex(byte)
                sys.stderr.write(f'\u274C Non-Latin character "{char}" found in {file_path}:{line_num}\n')
                return True
    return False

def main() -> None:
    """Execute the repository-wide validation for character layouts."""
    # Define the standard ASCII range (0-127) covering Latin layout, numbers, and basic punctuation
    allowed_bytes = set(range(128))
    has_failed = False

    # Folders to completely skip during layout analysis
    ignored_paths = {
        ".git", ".var", ".idea", ".vscode", ".venv",
        ".ruff_cache", ".DS_Store", "__pycache__", ".pytest_cache", ".coverage"}

    root = pathlib.Path(".")
    for path in root.rglob("*"):
        # Ensure we are dealing with a file, not a directory
        if path.is_file():
            # Check if any part of the file path belongs to an ignored directory
            # (e.g., skips '.var/dist/package.whl' or '.git/config')
            if any(part in ignored_paths for part in path.parts):
                continue

            if check_file_characters(path, allowed_bytes):
                has_failed = True

    if has_failed:
        sys.exit(1)

    sys.stdout.write("\u2705 Success: All validated files strictly use the Latin character layout.\n")

if __name__ == "__main__":
    main()
