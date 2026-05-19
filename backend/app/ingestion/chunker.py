from langchain_text_splitters import RecursiveCharacterTextSplitter

# 800-token chunks keep each chunk well under the 8192-token embedding limit.
# 100-token overlap preserves sentence context across chunk boundaries.
_CHUNK_SIZE = 800
_CHUNK_OVERLAP = 100

_splitter = RecursiveCharacterTextSplitter(
    chunk_size=_CHUNK_SIZE,
    chunk_overlap=_CHUNK_OVERLAP,
    separators=["\n\n", "\n", ". ", " ", ""],
)


def chunk_text(text: str) -> list[str]:
    return [c for c in _splitter.split_text(text) if c.strip()]
