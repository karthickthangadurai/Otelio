"""One-time ingestion: PDF -> chunks -> records -> ChromaDB.

Run:  python ingest.py
"""

from unstructured.partition.pdf import partition_pdf
from unstructured.chunking.title import chunk_by_title
from unstructured.staging.base import elements_from_base64_gzipped_json
import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction


from src.config import ( 
    PDF_PATH, CHROMA_PATH, COLLECTION_NAME, EMBEDDING_MODEL,
    MIN_NARRATIVE_CHARS, SKIP_CATEGORIES, HOTEL_NAME_OVERRIDE,
)

def extract_chunks(pdf_path):
    """Stage 1: PDF - list of title-bounded chunks."""
    blocks = partition_pdf(filename=str(pdf_path), strategy="fast")
    return chunk_by_title(blocks, combine_text_under_n_chars=0,
                          include_orig_elements=True)

def detect_hotel(chunks):
    """Stage 2: hotel name + slug from the document title (or config override)."""
    if HOTEL_NAME_OVERRIDE:
        name = HOTEL_NAME_OVERRIDE
    else:
        name = str(chunks[0]).strip().split(" - ")[0].strip()
    return name, name.lower().replace(" ", "-")

def build_records(chunks, hotel_name, hotel_slug):
    """Stage 3: chunks - list of {id, content, metadata} records."""
    records = []
    for counter, chunk in enumerate(chunks[1:], start=1):
        meta = chunk.metadata.to_dict()
        origs = elements_from_base64_gzipped_json(meta["orig_elements"])

        title, parts = "General", []
        for e in origs:
            if e.category == "Title":
                title = e.text
            elif e.category not in SKIP_CATEGORIES:
                parts.append(e.text)
        narrative = " ".join(parts)

        if len(narrative) < MIN_NARRATIVE_CHARS:
            continue

        records.append({
            "id": f"{hotel_slug}-{counter}",
            "content": f"{title}: {narrative}",
            "metadata": {
                "hotel_name": hotel_name,
                "section": title,
                "page_number": meta.get("page_number", 1),
                "chunk_id": counter,
            },
        })
    return records


def load_records(records):
    """Stage 4: records -> persistent Chroma collection."""
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    ef = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=ef,
        metadata={"hnsw:space": "cosine"},
    )
    collection.upsert(
        ids=[r["id"] for r in records],
        documents=[r["content"] for r in records],
        metadatas=[r["metadata"] for r in records],
    )
    return collection.count()

def main():
    chunks = extract_chunks(PDF_PATH)
    hotel_name, hotel_slug = detect_hotel(chunks)
    records = build_records(chunks, hotel_name, hotel_slug)
    count = load_records(records)
    print(f"Ingested {len(records)} sections for '{hotel_name}' "
          f"({count} total in collection '{COLLECTION_NAME}')")


if __name__ == "__main__":
    main()