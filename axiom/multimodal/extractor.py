"""
Multimodal Project Understanding — Phase 6.

Builds one unified text representation from arbitrary uploaded project
files (PDF, DOCX, PPTX, images, ZIP, source code, Markdown, CSV, JSON) so
the Project Intelligence Engine (ocif/engines/project_understanding.py)
classifies from real project content instead of a hand-typed description
alone. Reuses the existing multi-format text extractors in
datasets/ingestion.py (PDF via PyMuPDF, DOCX via python-docx, PPTX via
python-pptx, XLSX via openpyxl, markdown/code/csv/plain-text via direct
read) instead of duplicating them — this module adds exactly the two
things that were missing there: ZIP archive expansion and image metadata
capture.

Fail-soft throughout: an unreadable/unsupported file contributes an empty
extraction with an explanatory note, never a crash and never fabricated
content — the same grounding invariant the rest of the platform holds.

Security note: uploaded files (including ZIP members) are untrusted input.
Extraction is bounded (file count, per-file size, total extracted bytes,
ZIP member count) and ZIP member paths are validated against path traversal
("zip slip") before anything is read, to avoid decompression-bomb and
path-escape attacks from a malicious upload.
"""

import io
import os
import tempfile
import zipfile
from dataclasses import dataclass
from typing import List, Tuple

from datasets.ingestion import FORMAT_REGISTRY, _extract_text_content

MAX_FILES_PER_UPLOAD = 25
MAX_ZIP_MEMBERS = 50
MAX_FILE_BYTES = 20 * 1024 * 1024               # 20 MB per file
MAX_TOTAL_EXTRACTED_BYTES = 100 * 1024 * 1024   # 100 MB per request (ZIP contents)
MAX_TEXT_CHARS_PER_FILE = 200_000               # cap what feeds into the LLM prompt


@dataclass
class ExtractedFile:
    filename: str
    format_category: str
    text: str
    note: str = ""


def _is_zip(filename: str) -> bool:
    return filename.lower().endswith(".zip")


def _format_category(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    for category, extensions in FORMAT_REGISTRY.items():
        if ext in extensions:
            return category
    return "unknown"


def _safe_member_path(name: str) -> bool:
    """Rejects zip-slip attempts: absolute paths, drive letters, or any
    path that normalizes to escaping the extraction root via '..'.
    Checks POSIX-style leading slashes explicitly — os.path.isabs() is
    platform-dependent and does not treat "/etc/passwd" as absolute on
    Windows, where a malicious archive built on Linux would slip through."""
    if os.path.isabs(name) or ":" in name or name.startswith("/") or name.startswith("\\"):
        return False
    normalized = os.path.normpath(name)
    return not (normalized.startswith("..") or os.path.isabs(normalized))


def _extract_single_file(filename: str, content: bytes) -> ExtractedFile:
    category = _format_category(filename)
    ext = os.path.splitext(filename)[1].lower()

    if category == "unknown":
        return ExtractedFile(filename, category, "", note="Unsupported file type — skipped.")

    if category == "image":
        return _extract_image_metadata(filename, content)

    if len(content) > MAX_FILE_BYTES:
        return ExtractedFile(
            filename, category, "",
            note=f"File exceeds {MAX_FILE_BYTES // (1024 * 1024)}MB limit — skipped.",
        )

    if category in ("markdown", "code", "csv", "plain_text"):
        text = content.decode("utf-8", errors="replace")
        return ExtractedFile(filename, category, text[:MAX_TEXT_CHARS_PER_FILE])

    # Binary formats (pdf/docx/pptx/xlsx) — the shared extractors in
    # datasets/ingestion.py operate on a filesystem path, not bytes.
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        text = _extract_text_content(tmp_path, category)
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    if not text:
        return ExtractedFile(
            filename, category, "",
            note=f"No text extracted — the optional parser for {ext} files may not be installed.",
        )
    return ExtractedFile(filename, category, text[:MAX_TEXT_CHARS_PER_FILE])


def _extract_image_metadata(filename: str, content: bytes) -> ExtractedFile:
    """No OCR/vision extraction is wired — this is descriptive only, never
    fabricated content, matching ProjectUnderstandingFrame.required_images
    being explicitly 'descriptive only' elsewhere in the platform (see
    ocif/frames.py). A vision-capable inference provider could be wired in
    here later without changing this module's contract."""
    try:
        from PIL import Image
        with Image.open(io.BytesIO(content)) as img:
            note = f"Image received: {img.format} {img.width}x{img.height} — no OCR/vision extraction is configured."
    except Exception:
        note = "Image received — no OCR/vision extraction is configured."
    return ExtractedFile(filename, "image", "", note=note)


def _extract_zip(filename: str, content: bytes) -> List[ExtractedFile]:
    results: List[ExtractedFile] = []
    try:
        with zipfile.ZipFile(io.BytesIO(content)) as zf:
            members = [m for m in zf.infolist() if not m.is_dir()][:MAX_ZIP_MEMBERS]
            total = 0
            for member in members:
                if not _safe_member_path(member.filename):
                    results.append(ExtractedFile(member.filename, "unknown", "", note="Skipped — unsafe archive path."))
                    continue
                if member.file_size > MAX_FILE_BYTES:
                    results.append(ExtractedFile(member.filename, "unknown", "", note="Skipped — member exceeds size limit."))
                    continue
                total += member.file_size
                if total > MAX_TOTAL_EXTRACTED_BYTES:
                    results.append(ExtractedFile(member.filename, "unknown", "", note="Skipped — archive exceeds total extraction budget."))
                    continue
                member_bytes = zf.read(member)
                results.append(_extract_single_file(member.filename, member_bytes))
    except zipfile.BadZipFile:
        results.append(ExtractedFile(filename, "unknown", "", note="Not a valid ZIP archive."))
    return results


def build_project_text(files: List[Tuple[str, bytes]]) -> Tuple[str, List[ExtractedFile]]:
    """
    Extracts and concatenates text from arbitrary uploaded project files —
    PDF/DOCX/PPTX/XLSX/images/ZIP/source code/Markdown/CSV/JSON — into one
    combined string the Project Intelligence Engine can classify, plus a
    per-file summary for the API response. Never raises: unsupported or
    unreadable files degrade to an explanatory note rather than blocking
    the rest of the request.
    """
    all_results: List[ExtractedFile] = []
    for filename, content in files[:MAX_FILES_PER_UPLOAD]:
        if _is_zip(filename):
            all_results.extend(_extract_zip(filename, content))
        else:
            all_results.append(_extract_single_file(filename, content))

    sections = [f"--- {r.filename} ---\n{r.text}" for r in all_results if r.text]
    combined = "\n\n".join(sections)
    return combined, all_results
