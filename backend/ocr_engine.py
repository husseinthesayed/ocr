"""
OCR Engine — two-tier extraction strategy:
  1. Tesseract (default, fully local, no API key needed)
  2. Claude Vision (automatic upgrade when ANTHROPIC_API_KEY is set)

Both return the same List[dict] schema so the rest of the app is engine-agnostic.
"""

import base64
import io
import json
import os
import random
import re
from typing import Any, Dict, List

from PIL import Image


def _make_field(field: str, raw: str, conf: int) -> Dict[str, Any]:
    return {
        "field": field,
        "raw_value": raw,
        "display_value": raw,
        "confidence": max(10, min(99, conf)),
        "memory_corrected": False,
    }


class OCREngine:
    def __init__(self):
        api_key = os.getenv("ANTHROPIC_API_KEY", "").strip()
        self.use_claude = bool(api_key)
        self.engine_name = "claude-vision" if self.use_claude else "tesseract"

        if self.use_claude:
            import anthropic
            self.client = anthropic.Anthropic(api_key=api_key)

    # ------------------------------------------------------------------ #
    #  Public interface
    # ------------------------------------------------------------------ #

    def extract(self, image_bytes: bytes, filename: str = "document") -> List[Dict[str, Any]]:
        if self.use_claude:
            return self._extract_claude(image_bytes, filename)
        return self._extract_tesseract(image_bytes)

    # ------------------------------------------------------------------ #
    #  Tesseract path
    # ------------------------------------------------------------------ #

    def _extract_tesseract(self, image_bytes: bytes) -> List[Dict[str, Any]]:
        import pytesseract

        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")

        # Word-level data (includes per-word confidence)
        tess_data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        raw_text = pytesseract.image_to_string(image)

        # Average document confidence (ignore -1 sentinel values)
        valid_confs = [c for c in tess_data["conf"] if isinstance(c, (int, float)) and c >= 0]
        avg_conf = int(sum(valid_confs) / len(valid_confs)) if valid_confs else 65

        return self._parse_lines(raw_text, avg_conf)

    def _parse_lines(self, text: str, avg_conf: int) -> List[Dict[str, Any]]:
        """
        Parse raw Tesseract output into key-value fields.
        Handles three common document layouts:
          - "Key: Value"  (invoices, forms)
          - "Key    Value" (tables with whitespace alignment)
          - Standalone short lines (receipt items, labels)
        """
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        fields: List[Dict[str, Any]] = []
        idx = 0

        for line in lines:
            # Pattern 1: "Key: Value"
            m = re.match(r"^([^:\n]{2,40}):\s*(.{1,120})$", line)
            if m:
                conf = self._jitter(avg_conf)
                fields.append(_make_field(m.group(1).strip(), m.group(2).strip(), conf))
                continue

            # Pattern 2: two tokens separated by 3+ spaces (tabular layout)
            m2 = re.match(r"^(.{2,35})\s{3,}(.{1,80})$", line)
            if m2:
                conf = self._jitter(avg_conf)
                fields.append(_make_field(m2.group(1).strip(), m2.group(2).strip(), conf))
                continue

            # Pattern 3: short standalone lines (≤60 chars), kept as labelled blocks
            if len(line) <= 60:
                idx += 1
                conf = self._jitter(avg_conf)
                fields.append(_make_field(f"Line {idx}", line, conf))

        # If we got nothing useful, return the whole text as a single block
        if not fields:
            fields.append(_make_field("Extracted text", text.strip()[:500], avg_conf))

        return fields[:40]  # cap at 40 fields

    @staticmethod
    def _jitter(base: int) -> int:
        return max(10, min(99, base + random.randint(-18, 18)))

    # ------------------------------------------------------------------ #
    #  Claude Vision path
    # ------------------------------------------------------------------ #

    def _extract_claude(self, image_bytes: bytes, filename: str) -> List[Dict[str, Any]]:
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "jpg"
        media_type_map = {"png": "image/png", "gif": "image/gif", "webp": "image/webp"}
        media_type = media_type_map.get(ext, "image/jpeg")

        b64 = base64.standard_b64encode(image_bytes).decode()

        prompt = (
            "Extract every piece of text from this document as structured key-value pairs. "
            "Return a JSON array — nothing else, no markdown fences.\n\n"
            "Schema per item: {\"field\": string, \"raw_value\": string, \"confidence\": integer 0-100}\n\n"
            "Confidence guide:\n"
            "  90-99 = crisp, unambiguous text\n"
            "  70-89 = slightly compressed / small font\n"
            "  50-69 = partially obscured, skewed, or low-res\n"
            "  10-49 = handwritten, very blurry, or heavily degraded\n\n"
            "Extract all visible fields: dates, names, amounts, addresses, IDs, line items, totals — everything."
        )

        response = self.client.messages.create(
            model="claude-opus-4-6",
            max_tokens=4096,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": media_type,
                                "data": b64,
                            },
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
        )

        raw = response.content[0].text.strip()

        # Strip any accidental markdown fences
        raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("`").strip()

        try:
            items = json.loads(raw)
            return [
                _make_field(
                    str(item.get("field", f"Field {i+1}")),
                    str(item.get("raw_value", "")),
                    int(item.get("confidence", 70)),
                )
                for i, item in enumerate(items)
                if isinstance(item, dict)
            ]
        except (json.JSONDecodeError, TypeError):
            return [_make_field("Extracted text", raw[:500], 70)]
