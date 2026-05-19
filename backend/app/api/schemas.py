from pydantic import BaseModel


class SourceRef(BaseModel):
    doc_name: str
    page_number: int | None = None
