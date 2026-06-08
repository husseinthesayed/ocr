# OCR Engine

Self-correcting OCR service with a human-in-the-loop correction memory. Extracts structured fields from images, learns from your corrections, and gets more accurate over time.

## Quick start

**1. Install Tesseract (one-time)**
```bash
brew install tesseract
```

**2. Clone and start**
```bash
git clone https://github.com/husseinthesayed/ocr.git
cd ocr
cp .env.example .env
./start.sh
```

**3. Open the app**
```
http://localhost:8000
```

That's it. Drop any image and start extracting.

---

## Upgrading to Claude Vision

Tesseract is free and local. For significantly better accuracy, add your Anthropic API key:

```bash
# Edit .env and add:
ANTHROPIC_API_KEY=sk-ant-...
```

Then restart with `./start.sh`. The engine switches automatically — no other changes needed. Your correction memory carries over.

Get a key at https://console.anthropic.com

---

## How it works

1. **Drop an image** — the engine extracts all text and structures it into key-value fields with per-field confidence scores (green ≥85%, yellow 65–84%, red <65%)
2. **Fix any mistakes** — edit wrong values directly in the table
3. **Click "Validate & update model memory"** — corrections are saved to `memory.json`
4. **Next extraction** — saved corrections are applied automatically before results are shown

The correction dictionary grows over time and makes the engine more accurate on your specific documents (same vendors, fonts, layouts).

---

## API

The backend exposes a REST API at `http://localhost:8000/docs`.

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/ocr/extract` | Upload an image, get structured fields |
| `POST` | `/ocr/correct` | Submit corrections to the memory |
| `GET` | `/ocr/memory` | View the correction dictionary |
| `DELETE` | `/ocr/memory` | Clear all corrections |
| `GET` | `/health` | Check engine status |

**Example:**
```bash
curl -X POST http://localhost:8000/ocr/extract \
  -F "file=@invoice.png"
```

---

## MCP Server (for AI agents)

Exposes the same OCR engine as tools that Claude agents can call directly.

```bash
# Run the MCP server
source .venv/bin/activate
python mcp_server/server.py
```

Add to `claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "ocr": {
      "command": "python",
      "args": ["/path/to/ocr/mcp_server/server.py"]
    }
  }
}
```

Available tools: `extract_document`, `submit_corrections`, `get_correction_memory`, `clear_correction_memory`

---

## Project structure

```
ocr/
├── backend/
│   ├── main.py          # FastAPI app + routes
│   ├── ocr_engine.py    # Tesseract + Claude Vision
│   ├── memory.py        # Correction dictionary
│   ├── models.py        # Pydantic schemas
│   └── requirements.txt
├── frontend/
│   └── index.html       # Single-page web app
├── mcp_server/
│   ├── server.py        # MCP server (4 tools)
│   └── requirements.txt
├── .env.example
└── start.sh
```
