"""
Phase 6 (Multimodal Project Understanding) — unit tests for
multimodal/extractor.py: real text extraction from Markdown/code/CSV/JSON,
PDF, DOCX, images (metadata-only), and ZIP archives (including zip-slip and
size-limit safety checks).
"""

import io
import zipfile

from multimodal.extractor import (
    MAX_FILE_BYTES,
    _extract_single_file,
    _extract_zip,
    _safe_member_path,
    build_project_text,
)


def test_markdown_and_code_and_json_extracted_as_plain_text():
    md = _extract_single_file("README.md", b"# Water Pump Project\nMonitors pump vibration via MQTT.")
    assert md.format_category == "markdown"
    assert "Water Pump" in md.text

    code = _extract_single_file("main.py", b"import fastapi\n# predictive maintenance service")
    assert code.format_category == "code"
    assert "fastapi" in code.text

    js = _extract_single_file("config.json", b'{"industry": "industrial_iot"}')
    assert js.format_category == "code"
    assert "industrial_iot" in js.text

    csv = _extract_single_file("data.csv", b"device_id,status\n1,ok\n")
    assert csv.format_category == "csv"
    assert "device_id" in csv.text


def test_unsupported_extension_is_skipped_not_crashed():
    result = _extract_single_file("archive.rar", b"binary junk")
    assert result.format_category == "unknown"
    assert result.text == ""
    assert "Unsupported" in result.note


def test_pdf_extraction_with_real_pymupdf_document():
    fitz = __import__("fitz")
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hospital patient appointment scheduling system.")
    pdf_bytes = doc.tobytes()
    doc.close()

    result = _extract_single_file("spec.pdf", pdf_bytes)
    assert result.format_category == "pdf"
    assert "Hospital" in result.text or "patient" in result.text.lower()


def test_docx_extraction_with_real_python_docx_document():
    import docx as docx_lib

    document = docx_lib.Document()
    document.add_paragraph("Banking ledger and transfer processing platform.")
    buf = io.BytesIO()
    document.save(buf)

    result = _extract_single_file("spec.docx", buf.getvalue())
    assert result.format_category == "docx"
    assert "Banking ledger" in result.text


def test_image_extraction_returns_metadata_only_never_fabricated_text():
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (64, 32), color="white").save(buf, format="PNG")

    result = _extract_single_file("diagram.png", buf.getvalue())
    assert result.format_category == "image"
    assert result.text == ""
    assert "64x32" in result.note
    assert "no OCR/vision extraction" in result.note


def test_oversized_file_is_skipped():
    huge = b"x" * (MAX_FILE_BYTES + 1)
    result = _extract_single_file("big.txt", huge)
    assert result.text == ""
    assert "exceeds" in result.note


def test_zip_extraction_processes_multiple_members():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("notes.md", "# Smart Building occupancy monitoring")
        zf.writestr("app.py", "# access control service")
    results = _extract_zip("project.zip", buf.getvalue())
    assert len(results) == 2
    combined_text = " ".join(r.text for r in results)
    assert "Smart Building" in combined_text
    assert "access control" in combined_text


def test_zip_slip_path_traversal_is_rejected():
    assert not _safe_member_path("../../etc/passwd")
    assert not _safe_member_path("/etc/passwd")
    assert not _safe_member_path("C:\\Windows\\System32\\evil.dll")
    assert _safe_member_path("src/main.py")

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("../../evil.py", "malicious")
    results = _extract_zip("evil.zip", buf.getvalue())
    assert results[0].text == ""
    assert "unsafe archive path" in results[0].note


def test_bad_zip_file_does_not_crash():
    results = _extract_zip("not_really.zip", b"not a real zip file")
    assert len(results) == 1
    assert "Not a valid ZIP" in results[0].note


def test_build_project_text_combines_multiple_files():
    files = [
        ("readme.md", b"# Energy grid monitoring platform"),
        ("main.py", b"# substation telemetry ingestion service"),
    ]
    combined, results = build_project_text(files)
    assert "Energy grid" in combined
    assert "substation telemetry" in combined
    assert len(results) == 2


def test_build_project_text_never_raises_on_garbage_input():
    files = [("mystery.bin", b"\x00\x01\x02\x03"), ("empty.zip", b"")]
    combined, results = build_project_text(files)
    assert isinstance(combined, str)
    assert len(results) == 2
