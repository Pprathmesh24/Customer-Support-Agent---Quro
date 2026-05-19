from pathlib import Path
from typing import Callable

import pdfplumber
from docx import Document


def load_pdf(path: Path) -> str:
    with pdfplumber.open(path) as pdf:
        pages = [page.extract_text() or "" for page in pdf.pages]
    return "\n\n".join(pages)


def load_pdf_pages(path: Path) -> list[tuple[str, int]]:
    """Return (page_text, 1-based page_number) for every page in the PDF."""
    with pdfplumber.open(path) as pdf:
        return [(page.extract_text() or "", i + 1) for i, page in enumerate(pdf.pages)]


def load_docx(path: Path) -> str:
    doc = Document(path)
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n\n".join(paragraphs)


def load_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8")


_LOADERS: dict[str, Callable[[Path], str]] = {
    ".pdf": load_pdf,
    ".docx": load_docx,
    ".txt": load_txt,
}


def load_document(path: Path) -> str:
    suffix = path.suffix.lower()
    loader = _LOADERS.get(suffix)
    if loader is None:
        raise ValueError(f"Unsupported file type: {suffix!r}. Supported: {list(_LOADERS)}")
    return loader(path)
