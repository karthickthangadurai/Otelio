from src.config import CHROMA_PATH, COLLECTION_NAME, EMBEDDING_MODEL, TOP_K, \
    DISTANCE_THRESHOLD, NO_RESULT_SENTINEL, DEFAULT_HOTEL

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction


_client = chromadb.PersistentClient(path=CHROMA_PATH)
_ef = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
_collection = _client.get_collection(name=COLLECTION_NAME, embedding_function=_ef)


def search_hotel_info(query, n_results=TOP_K):
    
    """Search the hotel's information document.

    Use for any factual question about the hotel — location, timings, amenities,
    hygiene, safety, dining, policies. Always search before answering; never
    answer from your own knowledge. If nothing relevant is found, say so.

    Args:
        query: The guest's question.

    Returns:
        Relevant document sections, or a not-found message.
    """
    res = _collection.query(
        query_texts=[query],
        n_results=n_results,
        where={"hotel_name": DEFAULT_HOTEL},
        include=["documents", "metadatas", "distances"],
    )
    docs, metas, dists = res["documents"][0], res["metadatas"][0], res["distances"][0]

    if not docs or dists[0] > DISTANCE_THRESHOLD:
        return NO_RESULT_SENTINEL

    return "\n\n".join(
        f"[Section: {m['section']}]\n{d}" for d, m in zip(docs, metas)
    )