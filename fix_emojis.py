#!/usr/bin/env python3
# fix_emojis.py
# Backs up nexusverse.py, tries decoding, normalizes bytes, and replaces non-ascii characters
# with Unicode escape sequences (\uXXXX or \UXXXXXXXX), writing a cleaned file.

import os, sys, re
from pathlib import Path

SRC = Path("nexusverse.py")
BACKUP = Path("nexusverse_backup.py")
OUT = Path("nexusverse_fixed.py")

if not SRC.exists():
    print("Error: nexusverse.py not found in current directory.")
    sys.exit(1)

# backup
if not BACKUP.exists():
    BACKUP.write_bytes(SRC.read_bytes())
    print("Backup saved to nexusverse_backup.py")
else:
    print("Backup already exists: nexusverse_backup.py (will not overwrite)")

raw = SRC.read_bytes()

# Try decodings in order; pick first that decodes without UnicodeDecodeError and doesn't produce replacement characters
decoders = ["utf-8", "utf-8-sig", "latin-1", "cp1252"]
decoded = None
used = None
for dec in decoders:
    try:
        s = raw.decode(dec)
        # Heuristic: if there are replacement characters � then suspect wrong decode
        if "\uFFFD" in s:
            # but still accept latin-1 or cp1252 as last resorts
            if dec in ("latin-1", "cp1252"):
                decoded = s
                used = dec
                break
            else:
                continue
        decoded = s
        used = dec
        break
    except UnicodeDecodeError:
        continue

if decoded is None:
    print("Failed to decode file with utf-8/utf-8-sig/latin-1/cp1252. Will force latin-1 decode and try to salvage.")
    decoded = raw.decode("latin-1")
    used = "latin-1 (forced)"

print(f"Decoded using: {used}")

# Replace problematic characters (non-ascii) with escapes.
# We'll convert each non-ascii char to its \u or \U representation and keep ascii as-is.
def escape_char(c):
    code = ord(c)
    if code <= 0xFFFF:
        return "\\u{:04X}".format(code)
    else:
        return "\\U{:08X}".format(code)

# We should avoid escaping normal ASCII and common punctuation/newlines/tabs
def escape_non_ascii(text):
    return ''.join(ch if ord(ch) < 128 else escape_char(ch) for ch in text)

cleaned = escape_non_ascii(decoded)

# Ensure first line contains coding header (no blank lines before)
lines = cleaned.splitlines()
if not lines[0].startswith("# -*- coding: utf-8 -*-"):
    lines.insert(0, "# -*- coding: utf-8 -*-")
cleaned = "\n".join(lines) + ("\n" if not cleaned.endswith("\n") else "")

# Write out UTF-8 file
OUT.write_text(cleaned, encoding="utf-8")
print(f"Written cleaned file to {OUT} (UTF-8 with escaped non-ASCII characters).")
print("Review nexusverse_fixed.py, then replace original if all looks good:")
print("  mv nexusverse.py nexusverse_corrupt.py && mv nexusverse_fixed.py nexusverse.py")
print("Then try: python3 nexusverse.py")