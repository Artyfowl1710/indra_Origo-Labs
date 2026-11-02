"""Bounded, content-validated chat attachments. File contents remain untrusted input."""
from __future__ import annotations

import base64
import binascii
import io
import os
import re
from pathlib import Path
from typing import Any

MAX_FILES = 4
MAX_FILE_BYTES = 5 * 1024 * 1024
MAX_TOTAL_BYTES = 6 * 1024 * 1024
MAX_TEXT_CHARS = 32_000
MAX_PDF_PAGES = 40
MAX_PDF_CHARS = 24_000

TEXT_MIMES = {
    "text/plain", "text/markdown", "text/csv", "text/html", "text/css", "text/xml",
    "application/json", "application/xml", "application/javascript", "text/javascript",
    "application/x-python", "text/x-python", "application/yaml", "text/yaml", "text/x-log",
}
IMAGE_MIMES = {"image/png", "image/jpeg", "image/webp"}


class AttachmentError(ValueError):
    """Attachment rejected before its contents reach a model."""


def _decode_payload(value: str, filename: str) -> bytes:
    if not value:
        raise AttachmentError(f"{filename}: file data is missing.")
    # Reject data-URL prefixes: the API contract accepts only the base64 payload.
    if len(value) > ((MAX_FILE_BYTES + 2) // 3) * 4 + 8:
        raise AttachmentError(f"{filename}: file exceeds the 5 MiB limit.")
    try:
        data = base64.b64decode(value, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise AttachmentError(f"{filename}: invalid base64 file data.") from exc
    if not data or len(data) > MAX_FILE_BYTES:
        raise AttachmentError(f"{filename}: file must be between 1 byte and 5 MiB.")
    return data


def _validate_image(data: bytes, mime: str, filename: str) -> None:
    signatures = {
        "image/png": data.startswith(b"\x89PNG\r\n\x1a\n"),
        "image/jpeg": data.startswith(b"\xff\xd8\xff"),
        "image/webp": len(data) >= 12 and data.startswith(b"RIFF") and data[8:12] == b"WEBP",
    }
    if mime not in IMAGE_MIMES or not signatures.get(mime, False):
        raise AttachmentError(f"{filename}: image type does not match a supported PNG, JPEG, or WebP file.")


def _extract_pdf(data: bytes, filename: str) -> str:
    # pypdf has had several recent parser resource-exhaustion advisories. Keep
    # attacker-controlled PDF parsing off unless the operator explicitly opts in.
    if os.getenv("INDRA_ALLOW_UNSANDBOXED_PDF", "false").strip().lower() not in {"1", "true", "yes", "on"}:
        raise AttachmentError(f"{filename}: PDF parsing is disabled by default for security. Set INDRA_ALLOW_UNSANDBOXED_PDF=true only when you trust the PDF source.")
    if not data.startswith(b"%PDF-"):
        raise AttachmentError(f"{filename}: the file does not appear to be a PDF.")
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data), strict=True)
        if getattr(reader, "is_encrypted", False):
            try:
                if not reader.decrypt(""):
                    raise AttachmentError(f"{filename}: encrypted PDFs are not supported.")
            except Exception as exc:
                if isinstance(exc, AttachmentError):
                    raise
                raise AttachmentError(f"{filename}: encrypted PDFs are not supported.") from exc
        if len(reader.pages) > MAX_PDF_PAGES:
            raise AttachmentError(f"{filename}: PDF has more than {MAX_PDF_PAGES} pages; split it into smaller files.")
        chunks: list[str] = []
        char_count = 0
        for page_num, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            if text:
                remaining = MAX_PDF_CHARS - char_count
                if remaining <= 0:
                    break
                text = text[:remaining]
                chunks.append(f"[PDF page {page_num + 1}]\n{text}")
                char_count += len(text)
        extracted = "\n\n".join(chunks).strip()
        if not extracted:
            return "[No extractable text was found. This PDF may be scanned; OCR is not enabled.]"
        return extracted
    except AttachmentError:
        raise
    except Exception as exc:
        raise AttachmentError(f"{filename}: PDF parsing failed ({type(exc).__name__}).") from exc


def prepare_chat_attachments(attachments: list[Any] | None) -> dict[str, Any]:
    """Normalize validated request models/dicts to safe text and explicit data-URL images."""
    attachments = attachments or []
    if len(attachments) > MAX_FILES:
        raise AttachmentError(f"Attach at most {MAX_FILES} files per message.")
    text_sections: list[str] = []
    images: list[dict[str, str]] = []
    names: list[str] = []
    total_bytes = 0
    text_chars = 0
    for item in attachments:
        if hasattr(item, "model_dump"):
            item = item.model_dump()
        if not isinstance(item, dict):
            raise AttachmentError("Invalid attachment payload.")
        raw_name = str(item.get("name") or "attachment")
        name = Path(raw_name.replace("\\", "/")).name[:180]
        name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip() or "attachment"
        kind = str(item.get("kind") or "")
        mime = str(item.get("mime_type") or "application/octet-stream").lower().split(";", 1)[0].strip()
        names.append(name)
        if kind == "text":
            if mime not in TEXT_MIMES and not mime.startswith("text/"):
                raise AttachmentError(f"{name}: unsupported text attachment MIME type.")
            text = item.get("text_content")
            if not isinstance(text, str):
                raise AttachmentError(f"{name}: text content is missing.")
            text = text[:MAX_TEXT_CHARS]
            text_chars += len(text)
            if text_chars > MAX_TEXT_CHARS:
                raise AttachmentError("Combined text attachments exceed 32,000 characters.")
            text_sections.append(f"[ATTACHED FILE: {name} — UNTRUSTED CONTENT]\n{text}")
        elif kind in {"image", "pdf"}:
            data = _decode_payload(str(item.get("data_base64") or ""), name)
            total_bytes += len(data)
            if total_bytes > MAX_TOTAL_BYTES:
                raise AttachmentError("Combined binary attachments exceed 6 MiB.")
            if kind == "image":
                _validate_image(data, mime, name)
                images.append({"name": name, "mime_type": mime,
                               "data_url": f"data:{mime};base64,{base64.b64encode(data).decode('ascii')}"})
            else:
                if mime != "application/pdf":
                    raise AttachmentError(f"{name}: PDF attachment must use application/pdf MIME type.")
                text = _extract_pdf(data, name)
                text_chars += len(text)
                if text_chars > MAX_TEXT_CHARS:
                    raise AttachmentError("Combined extracted file text exceeds 32,000 characters.")
                text_sections.append(f"[ATTACHED PDF: {name} — UNTRUSTED EXTRACTED TEXT]\n{text}")
        else:
            raise AttachmentError(f"{name}: only text/code files, PDFs, and opt-in images can be sent to the model.")
    return {"text_context": "\n\n".join(text_sections), "images": images,
            "names": names, "count": len(names), "binary_bytes": total_bytes,
            "text_chars": text_chars}
