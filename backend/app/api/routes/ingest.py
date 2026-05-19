import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile
from pydantic import BaseModel
from supabase import Client

from app.api.deps import get_current_user_id, get_service_client
from app.ingestion.pipeline import ingest

router = APIRouter()

_CONTENT_TYPE_TO_SUFFIX: dict[str, str] = {
    "application/pdf": ".pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
    "text/plain": ".txt",
}

_EXTENSION_TO_SUFFIX: dict[str, str] = {
    ".pdf": ".pdf",
    ".docx": ".docx",
    ".txt": ".txt",
}


def _resolve_suffix(file: UploadFile) -> str:
    # Prefer MIME type; fall back to filename extension for clients that send
    # application/octet-stream (e.g. curl without explicit -T Content-Type).
    if file.content_type and file.content_type in _CONTENT_TYPE_TO_SUFFIX:
        return _CONTENT_TYPE_TO_SUFFIX[file.content_type]
    if file.filename:
        ext = Path(file.filename).suffix.lower()
        if ext in _EXTENSION_TO_SUFFIX:
            return _EXTENSION_TO_SUFFIX[ext]
    raise HTTPException(
        status_code=422,
        detail=f"Unsupported file type. Upload a PDF, DOCX, or TXT file.",
    )


class IngestResponse(BaseModel):
    document_id: str
    chunk_count: int


@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(
    file: UploadFile,
    category: str | None = Form(None),
    user_id: str = Depends(get_current_user_id),
    supabase: Client = Depends(get_service_client),
) -> IngestResponse:
    suffix = _resolve_suffix(file)
    content = await file.read()

    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)
        tmp_path.write_bytes(content)

    try:
        document_id = await ingest(
            file_path=tmp_path,
            user_id=user_id,
            supabase=supabase,
            storage_path=f"{user_id}/{file.filename}",
            category=category,
            original_name=file.filename,
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    doc = supabase.table("documents").select("chunk_count").eq("id", document_id).execute()
    chunk_count: int = doc.data[0]["chunk_count"]

    return IngestResponse(document_id=document_id, chunk_count=chunk_count)
