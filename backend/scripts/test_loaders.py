"""
Smoke-tests loaders and chunker against a generated TXT file.
Usage: uv run scripts/test_loaders.py
"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1]))

from app.ingestion.chunker import chunk_text
from app.ingestion.loaders import load_document

SAMPLE_TEXT = "\n\n".join(
    [
        "Enterprise Customer Support Agent — Sample Document",
        "This product helps companies automate customer support using AI. "
        "It ingests documentation, indexes it into a vector database, and answers "
        "customer questions with cited references.",
        "Getting Started\n"
        "Upload your product documentation via the admin dashboard. "
        "Supported formats are PDF, DOCX, and plain text. "
        "Each file is chunked, embedded, and stored in Supabase pgvector.",
        "Hybrid Search\n"
        "The retrieval pipeline combines dense vector search (HNSW cosine similarity) "
        "with sparse BM25 keyword search. Results are merged via Reciprocal Rank Fusion "
        "and re-ranked by a cross-encoder model to return the most relevant chunks.",
        "Escalation\n"
        "When the agent cannot answer with sufficient confidence it escalates: "
        "a Linear ticket is created, a Slack notification is sent, and the customer "
        "receives an email confirmation via Resend.",
    ]
    * 10  # repeat to generate enough text to produce multiple chunks
)


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        txt_path = Path(tmp) / "sample.txt"
        txt_path.write_text(SAMPLE_TEXT, encoding="utf-8")

        print("Loading TXT...")
        text = load_document(txt_path)
        print(f"  characters loaded: {len(text)}")

        print("Chunking...")
        chunks = chunk_text(text)
        print(f"  chunks produced: {len(chunks)}")
        for i, chunk in enumerate(chunks):
            print(f"  chunk {i + 1}: {len(chunk)} chars — {chunk[:60]!r}...")

    print("\nLoaders OK")


if __name__ == "__main__":
    main()
