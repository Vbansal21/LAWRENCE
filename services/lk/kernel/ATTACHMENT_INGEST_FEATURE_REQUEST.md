# Attachment Ingest And UI Bridge Feature Request

The desktop popup now separates two different concepts:

- **Live kernel context**: screen/mic requests that should use LAWRENCE's existing capture mechanisms.
- **Document ingestion**: user-provided files or URLs that should be converted before model use.

Current kernel support already exists for parts of live context in CLI form:

- `/screenshot [q]` calls the screenshot capture path.
- `/record SECS [q]` records microphone audio.
- `/vision on|off` and `/audio-on|off` control rolling observers.
- `run_turn(... images, audios, capture_fn=...)` can receive model-compatible media.

Missing bridge support:

- UI command to request a fresh screenshot through the kernel capture path.
- UI command to request a short microphone sample through the kernel record path.
- UI command to toggle rolling vision/audio observers.
- UI command to attach converted document artifacts to a turn.
- Native file selection that passes a readable file path or bytes to the kernel/converter process.
- UI-visible acknowledgement/failure events for capture and conversion.

Requested document converters:

- Images: normalize format, preserve EXIF where useful, OCR if needed, route to native vision when available.
- Audio files: decode, VAD, transcribe, and optionally route native audio to capable models.
- Video files: extract keyframes, audio transcript, timeline/chapter summary.
- PDF: text extraction, OCR fallback, page image references, citation chunks.
- Markdown/MDX: frontmatter + Markdown parser.
- Web pages/HTML: fetch, readability extraction, link/citation metadata.
- Office documents: DOC/DOCX/ODT/RTF text extraction.
- Presentations: slide text, slide images, notes.
- Spreadsheets/CSV/TSV: sheet/table parser, schema and row summaries.
- LaTeX/BibTeX/equations: source parser, equation extraction, bibliography metadata.
- Mermaid diagrams: source parse plus render-preview artifact.
- JSON/JSONL/YAML/XML: structured parser and schema summary.
- EPUB: chapter text extraction.

Suggested payload shape from UI:

```json
{
  "text": "user question",
  "kernelContext": [
    {
      "kind": "screen",
      "label": "screenshot",
      "action": "capture_screenshot",
      "kernelCommand": "/screenshot",
      "route": "kernel_capture"
    }
  ],
  "attachments": [
    {
      "kind": "pdf",
      "name": "paper.pdf",
      "mime": "application/pdf",
      "extension": "pdf",
      "path": "/path/to/paper.pdf",
      "source": "file",
      "route": "document_ingest",
      "converter": "page text + OCR fallback + citation chunks"
    }
  ]
}
```

Until this bridge exists, the UI should classify attachments and send converter intent, but the kernel remains responsible for capture, conversion, privacy policy, and model routing.
