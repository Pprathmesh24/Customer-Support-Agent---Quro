from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from supabase import Client


class _NoInput(BaseModel):
    pass


class DocumentScopeTool(BaseTool):
    """
    Returns a formatted list of all documents in the knowledge base.
    The agent calls this to understand what source material is available
    before deciding how to answer a question.
    """

    name: str = "document_scope"
    description: str = (
        "Lists all documents currently in the knowledge base. "
        "Call this first to understand what source material is available "
        "before searching for specific information."
    )
    args_schema: type[BaseModel] = _NoInput
    supabase: Client = Field(exclude=True)

    class Config:
        arbitrary_types_allowed = True

    def _run(self) -> str:
        rows = (
            self.supabase.table("documents")
            .select("name, file_type, category, chunk_count")
            .order("created_at", desc=False)
            .execute()
        )

        if not rows.data:
            return "No documents are currently in the knowledge base."

        lines = ["Available documents in the knowledge base:\n"]
        for i, doc in enumerate(rows.data, start=1):
            category = f" [{doc['category']}]" if doc["category"] else ""
            lines.append(
                f"{i}. {doc['name']}{category} "
                f"({doc['file_type'].upper()}, {doc['chunk_count']} chunks)"
            )
        return "\n".join(lines)

    async def _arun(self) -> str:
        return self._run()
