from __future__ import annotations

import io
from typing import BinaryIO

import pdfplumber
from docx import Document


class UnsupportedFileTypeError(RuntimeError):
    """Raised when uploaded file type is not supported."""


def sniff_extension(filename: str | None) -> str:
    if not filename:
        return ""
    return filename.rsplit(".", maxsplit=1)[-1].lower()


def extract_text_from_pdf(file_bytes: bytes) -> str:
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    return "\n".join(pages)


def extract_text_from_docx(file_bytes: bytes) -> str:
    buffer = io.BytesIO(file_bytes)
    document = Document(buffer)
    paragraphs = [p.text for p in document.paragraphs]
    return "\n".join(paragraphs)


def read_uploaded_file(file_obj: BinaryIO, filename: str | None = None) -> str:
    ext = sniff_extension(filename)
    payload = file_obj.read()
    if ext in {"pdf"}:
        return extract_text_from_pdf(payload)
    if ext in {"docx"}:
        return extract_text_from_docx(payload)
    if ext in {"txt"} or not ext:
        return payload.decode("utf-8", errors="ignore")
    raise UnsupportedFileTypeError(f"Unsupported file type: {ext}")

