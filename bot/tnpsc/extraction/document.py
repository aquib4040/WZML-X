import hashlib
import re
from pathlib import Path


def normalize_text(text):
    return re.sub(r"\s+", " ", (text or "").replace("\x00", " ")).strip()


def extract_pdf(path):
    from pypdf import PdfReader

    pages = []
    for number, page in enumerate(PdfReader(str(path)).pages, 1):
        text = normalize_text(page.extract_text() or "")
        if text:
            pages.append({"page": number, "text": text})
    return pages


def extract_text(path):
    return [{"page": None, "text": normalize_text(Path(path).read_text(encoding="utf-8", errors="ignore"))}]


def extract(path):
    suffix = Path(path).suffix.lower()
    if suffix == ".pdf":
        return extract_pdf(path)
    if suffix in {".txt", ".md", ".csv"}:
        return extract_text(path)
    raise ValueError(f"Unsupported document type: {suffix or 'unknown'}")


def chunks(pages, size=1800, overlap=150):
    result = []
    for page in pages:
        text = page["text"]
        start = 0
        while start < len(text):
            value = text[start : start + size].strip()
            if value:
                result.append({"page": page["page"], "text": value, "content_hash": hashlib.sha256(value.encode()).hexdigest()})
            start += max(1, size - overlap)
    return result

