"""
OCR MCP Server
Exposes the OCR engine as four tools callable by any MCP-compatible AI agent
(Claude Code, Claude Desktop, Cursor, etc.)

Shares the same memory.json as the FastAPI backend — corrections made via the
web UI are immediately available here, and vice versa.

Usage:
  python server.py          # stdio transport (default, use in Claude Desktop)
  python server.py --sse    # SSE transport for remote MCP clients

Configure in Claude Desktop (claude_desktop_config.json):
  {
    "mcpServers": {
      "ocr": {
        "command": "python",
        "args": ["/path/to/ocr/mcp_server/server.py"],
        "env": { "ANTHROPIC_API_KEY": "sk-..." }   // optional: enables Claude Vision
      }
    }
  }
"""

import argparse
import base64
import json
import os
import sys
from pathlib import Path

# Make backend modules importable
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from mcp.server.fastmcp import FastMCP
from ocr_engine import OCREngine
from memory import CorrectionMemory

mcp = FastMCP(
    "ocr-service",
    instructions=(
        "OCR extraction service with self-learning correction memory. "
        "Use extract_document to pull structured fields from an image, "
        "submit_corrections to teach it your fixes, and get_correction_memory "
        "to inspect what it has learned."
    ),
)

engine = OCREngine()
mem = CorrectionMemory()


# ------------------------------------------------------------------ #
#  Tools
# ------------------------------------------------------------------ #

@mcp.tool()
def extract_document(image_base64: str, filename: str = "document.jpg") -> str:
    """
    Extract all text and structured key-value fields from a document image.

    Args:
        image_base64: Base64-encoded bytes of the image (PNG, JPG, TIFF, WEBP).
                      To encode a file: base64.b64encode(open('doc.jpg','rb').read()).decode()
        filename:     Original filename — used to infer the media type. Defaults to 'document.jpg'.

    Returns:
        JSON object with:
          fields[]:
            field            - detected field name / label
            raw_value        - raw string from OCR engine
            display_value    - value after memory corrections applied
            confidence       - integer 0-100 (higher = more certain)
            memory_corrected - true if a prior correction was applied
          filename  - echoed back
          engine_used - "tesseract" or "claude-vision"
    """
    image_bytes = base64.b64decode(image_base64)
    fields = engine.extract(image_bytes, filename)

    for f in fields:
        corrected = mem.apply(f["raw_value"])
        if corrected != f["raw_value"]:
            f["display_value"] = corrected
            f["memory_corrected"] = True

    return json.dumps(
        {"fields": fields, "filename": filename, "engine_used": engine.engine_name},
        indent=2,
        ensure_ascii=False,
    )


@mcp.tool()
def submit_corrections(corrections: dict) -> str:
    """
    Persist human corrections to the OCR correction memory matrix.

    After calling this, every future extraction will automatically replace the
    raw OCR strings with their corrected versions before returning results.

    Args:
        corrections: A dict mapping raw (wrong) OCR strings to their correct values.
                     Example: {"J8#2823on": "Johnson", "0rganic": "Organic", "lnc": "Inc"}

    Returns:
        JSON with:
          status        - "ok"
          new_entries   - count of corrections added/updated in this call
          total_entries - total size of the correction dictionary
    """
    new_count = mem.add_batch(corrections)
    return json.dumps(
        {"status": "ok", "new_entries": new_count, "total_entries": len(mem.get_all())},
        indent=2,
    )


@mcp.tool()
def get_correction_memory() -> str:
    """
    Retrieve the full correction dictionary map.

    Returns:
        JSON object with:
          corrections - dict of {raw_string: corrected_string} pairs
          count       - total number of entries
    """
    data = mem.get_all()
    return json.dumps({"corrections": data, "count": len(data)}, indent=2, ensure_ascii=False)


@mcp.tool()
def clear_correction_memory() -> str:
    """
    Wipe all learned corrections from the memory matrix.

    Use this to reset the engine to a clean slate. This action is irreversible.

    Returns:
        JSON confirmation message.
    """
    mem.clear()
    return json.dumps({"status": "cleared", "message": "Correction memory has been reset."})


# ------------------------------------------------------------------ #
#  Entry point
# ------------------------------------------------------------------ #

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OCR MCP Server")
    parser.add_argument("--sse", action="store_true", help="Use SSE transport instead of stdio")
    parser.add_argument("--port", type=int, default=8001, help="Port for SSE transport (default 8001)")
    args = parser.parse_args()

    if args.sse:
        mcp.run(transport="sse", port=args.port)
    else:
        mcp.run(transport="stdio")
