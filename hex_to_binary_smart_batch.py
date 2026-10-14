#!/usr/bin/env python3
"""
Decode Grok export files in batch by detecting hex or base64 encodings,
guessing file types, and writing decoded binary/text files to an output folder.

Usage examples:
  python3 hex_to_binary_smart_batch.py --input /path/to/grok_export --output ./converted --recursive
  python3 hex_to_binary_smart_batch.py --input /path/to/grok_export --output ./converted --recursive --dry-run
"""
from __future__ import annotations
import argparse
import base64
import csv
import json
import re
import sys
from pathlib import Path
from typing import Optional, Tuple

def normalize_hex_text(value: str) -> str:
    value = value.replace("\r", "").replace("\n", "").replace(" ", "")
    value = value.replace("0x", "").replace("0X", "")
    value = value.replace(",", "").replace(":", "").replace("-", "")
    value = value.replace("\t", "")
    value = re.sub(r"[^0-9A-Fa-f]", "", value)
    return value

def looks_like_hex_text(text: str) -> bool:
    if not text:
        return False
    cleaned = normalize_hex_text(text)
    if len(cleaned) < 8 or len(cleaned) % 2 != 0:
        return False
    try:
        bytes.fromhex(cleaned)
        return True
    except ValueError:
        return False

def maybe_decode_utf8(raw: bytes) -> Optional[str]:
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return None

def try_hex_decode(raw: bytes) -> Tuple[Optional[bytes], Optional[str]]:
    # If the raw bytes are UTF-8 text that looks like hex, decode
    text = maybe_decode_utf8(raw)
    if text is not None and looks_like_hex_text(text):
        return bytes.fromhex(normalize_hex_text(text)), "hex"

    # Try decoding as latin-1 and check again (keeps bytes -> 1:1 mapping)
    text = raw.decode("latin-1", errors="replace")
    if looks_like_hex_text(text):
        return bytes.fromhex(normalize_hex_text(text)), "hex"

    return None, None

def try_base64_decode(raw: bytes) -> Tuple[Optional[bytes], Optional[str]]:
    # Base64.validate requires padding correctness and valid alphabet
    try:
        decoded = base64.b64decode(raw, validate=True)
        return decoded, "base64"
    except Exception:
        return None, None

def guess_output_extension(data: bytes, text: Optional[str] = None) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"GIF87a") or data.startswith(b"GIF89a"):
        return ".gif"
    if data.startswith(b"%PDF"):
        return ".pdf"
    if data.startswith(b"PK") and data[:4] in (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08"):
        return ".zip"
    if data.startswith(b"SQLite format 3\x00"):
        return ".db"
    if data.startswith(b"\x7fELF"):
        return ".elf"
    if data.startswith(b"MZ"):
        return ".exe"

    if text is not None:
        s = text.strip()
        if not s:
            return ".txt"
        if s.startswith("{") or s.startswith("["):
            try:
                json.loads(s)
                return ".json"
            except Exception:
                pass
        if "," in s or "\t" in s:
            try:
                csv.Sniffer().sniff(s[:4096], delimiters=",;\t|")
                return ".csv"
            except Exception:
                pass
        return ".txt"

    return ".bin"

def process_file(source: Path, output_dir: Path, dry_run: bool = False, overwrite: bool = False) -> bool:
    try:
        raw = source.read_bytes()
    except Exception as e:
        print(f"[!] Failed reading {source}: {e}", file=sys.stderr)
        return False

    decoded, kind = try_hex_decode(raw)
    text: Optional[str] = None

    if decoded is None:
        decoded, kind = try_base64_decode(raw)
        if decoded is not None:
            try:
                text = decoded.decode("utf-8-sig", errors="replace")
            except Exception:
                text = None

    if decoded is None:
        kind = "copy"
        decoded = raw

    if kind == "copy":
        # guess extension from raw bytes
        ext = guess_output_extension(decoded)
        # if the leading bytes are printable ASCII treat as text
        sample = decoded[:4096]
        if sample and all(((b >= 32 and b < 127) or b in (9, 10, 13)) for b in sample):
            ext = ".txt"
        output_path = output_dir / f"{source.name}{ext}"
    else:
        # decoded data; try to get textual representation to help guess extension
        try:
            text = decoded.decode("utf-8-sig", errors="replace") if decoded else None
        except Exception:
            text = None
        output_path = output_dir / f"{source.name}{guess_output_extension(decoded, text)}"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists() and not overwrite:
        stem = output_path.stem
        suffix = output_path.suffix
        n = 1
        while True:
            candidate = output_path.with_name(f"{stem}_{n}{suffix}")
            if not candidate.exists():
                output_path = candidate
                break
            n += 1

    if dry_run:
        print(f"[DRY] {source} -> {output_path}  (detected: {kind})")
        return True

    try:
        with open(output_path, "wb") as out:
            out.write(decoded)
        print(f"[✓] {source} -> {output_path}  (detected: {kind})")
        return True
    except Exception as e:
        print(f"[!] Failed writing {output_path}: {e}", file=sys.stderr)
        return False

def iter_files(root: Path, pattern: str, recursive: bool):
    if recursive:
        yield from (p for p in root.rglob(pattern) if p.is_file())
    else:
        yield from (p for p in root.glob(pattern) if p.is_file())

def main() -> int:
    parser = argparse.ArgumentParser(description="Decode Grok export files.")
    parser.add_argument("--input", default=".", help="Input directory containing Grok files.")
    parser.add_argument("--output", default="./converted", help="Output directory.")
    parser.add_argument("--pattern", default="content*", help="File pattern to match.")
    parser.add_argument("--recursive", action="store_true", help="Search recursively.")
    parser.add_argument("--dry-run", action="store_true", help="Preview actions only.")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files.")
    args = parser.parse_args()

    input_dir = Path(args.input).resolve()
    output_dir = Path(args.output).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(iter_files(input_dir, args.pattern, args.recursive))

    if not files:
        print(f"[!] No files matched '{args.pattern}' under {input_dir}")
        return 1

    any_failed = False
    for file_path in files:
        # skip files inside the output dir to avoid infinite loops
        try:
            if output_dir in file_path.resolve().parents:
                continue
        except Exception:
            # if path resolution fails, still attempt processing
            pass

        ok = process_file(file_path, output_dir, dry_run=args.dry_run, overwrite=args.overwrite)
        if not ok:
            any_failed = True

    return 2 if any_failed else 0

if __name__ == "__main__":
    raise SystemExit(main())