# hex-to-binary-smart-batch

Decode Grok export files (hex or base64 textual dumps, or raw binary/text files) in batch. The script tries to detect whether each input file contains:
- hex text (optionally with separators or 0x prefixes),
- base64 data,
- or is already binary/text (copied).

It guesses reasonable output extensions for common file types (PNG/JPEG/GIF/PDF/ZIP/SQLite/ELF/EXE), and for textual content will produce .txt/.csv/.json when possible. Collisions are avoided by appending `_1`, `_2`, ... unless `--overwrite` is set.

## Files to add to the repo
- `hex_to_binary_smart_batch.py` — the main script (Python 3, no external dependencies).

## Quick start (on your machine)

1. Clone or create the repository (you said you will create it manually).
2. Save `hex_to_binary_smart_batch.py` into the repo root.
3. Make it executable (optional):
   chmod +x hex_to_binary_smart_batch.py

4. Run a dry-run first to preview output mapping:
   python3 hex_to_binary_smart_batch.py --input /path/to/grok_export --output ./converted --recursive --dry-run

5. If the dry-run looks correct, run the actual conversion:
   python3 hex_to_binary_smart_batch.py --input /path/to/grok_export --output ./converted --recursive

6. To force overwrite of existing decoded files:
   python3 hex_to_binary_smart_batch.py --input /path/to/grok_export --output ./converted --recursive --overwrite

7. To restrict matching pattern, use `--pattern` (default `content*`). Example:
   python3 hex_to_binary_smart_batch.py --input ./grok_export --pattern "content_*" --recursive

## Example (quick local test)
Create a small test folder and files:
```bash
mkdir -p /tmp/grok_test
# hex file (2 bytes 0x01 0x02)
echo -n "0102" > /tmp/grok_test/content_hex.txt
# base64 file (PNG header sample: iVBORw0KGgo=)
echo -n "iVBORw0KGgo=" > /tmp/grok_test/content_b64.txt
# raw text
echo "Hello, world" > /tmp/grok_test/content_text.txt