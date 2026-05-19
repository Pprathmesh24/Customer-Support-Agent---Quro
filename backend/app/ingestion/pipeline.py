from pathlib import Path

from supabase import Client

from app.ingestion.chunker import chunk_text
from app.ingestion.embedder import embed_and_store
from app.ingestion.loaders import load_document, load_pdf_pages

_SUPPORTED_TYPES = {"pdf", "docx", "txt"}


async def ingest(
    file_path: Path,
    user_id: str,
    supabase: Client,
    storage_path: str | None = None,
    category: str | None = None,
    original_name: str | None = None,
) -> str:
    """
    Full ingestion pipeline: load → chunk → embed → store.

    For PDFs, text is extracted page-by-page so each chunk carries a page_number.
    For DOCX and TXT, page_number is None (no reliable page boundary information).

    Args:
        file_path:    Local path to the file being ingested.
        user_id:      Supabase auth UID of the uploading user.
        supabase:     Service-role Supabase client (bypasses RLS).
        storage_path: Supabase Storage path recorded for audit; falls back to file_path.
        category:     Optional document category tag.

    Returns:
        document_id (UUID string) of the newly created documents row.
    """
    suffix = file_path.suffix.lower()
    file_type = suffix.lstrip(".")
    if file_type not in _SUPPORTED_TYPES:
        raise ValueError(f"Unsupported file type: {suffix!r}")

    size_bytes = file_path.stat().st_size
    recorded_path = storage_path or str(file_path)

    # ── Load & chunk ──────────────────────────────────────────────────────────
    chunks: list[str] = []
    page_numbers: list[int | None] = []

    if suffix == ".pdf":
        for page_text, page_num in load_pdf_pages(file_path):
            if not page_text.strip():
                continue
            page_chunks = chunk_text(page_text)
            chunks.extend(page_chunks)
            page_numbers.extend([page_num] * len(page_chunks))
    else:
        text = load_document(file_path)
        chunks = chunk_text(text)
        page_numbers = [None] * len(chunks)

    # ── Create documents row ──────────────────────────────────────────────────
    doc_resp = (
        supabase.table("documents")
        .insert({
            "user_id": user_id,
            "name": original_name or file_path.name,
            "file_path": recorded_path,
            "file_type": file_type,
            "category": category,
            "size_bytes": size_bytes,
        })
        .execute()
    )
    document_id: str = doc_resp.data[0]["id"]

    # ── Embed and store chunks ────────────────────────────────────────────────
    await embed_and_store(chunks, document_id, supabase, page_numbers)

    # ── Update chunk_count on the document row ────────────────────────────────
    supabase.table("documents").update({"chunk_count": len(chunks)}).eq("id", document_id).execute()

    return document_id
