import logging
import uuid
from typing import Optional
import chromadb
from chromadb.utils import embedding_functions
from config import CHROMA_PATH

logger = logging.getLogger(__name__)

# Используем встроенную sentence-transformers модель для эмбеддингов (работает офлайн)
_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
    model_name="paraphrase-multilingual-MiniLM-L12-v2"
)

_client = None


def get_client() -> chromadb.PersistentClient:
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMA_PATH)
    return _client


def get_collection(user_id: int):
    """Получить коллекцию для конкретного пользователя."""
    client = get_client()
    collection_name = f"user_{user_id}"
    return client.get_or_create_collection(
        name=collection_name,
        embedding_function=_ef,
        metadata={"hnsw:space": "cosine"}
    )


def add_texts(user_id: int, texts: list[str], metadatas: list[dict] = None) -> list[str]:
    """Добавить тексты в векторную БД. Возвращает список ID."""
    collection = get_collection(user_id)
    ids = [str(uuid.uuid4()) for _ in texts]
    meta = metadatas if metadatas else [{}] * len(texts)
    collection.add(documents=texts, metadatas=meta, ids=ids)
    logger.info(f"Добавлено {len(texts)} чанков для user {user_id}")
    return ids


def search_relevant(user_id: int, query: str, n_results: int = 5) -> list[str]:
    """Поиск релевантных фрагментов по запросу."""
    collection = get_collection(user_id)
    count = collection.count()
    if count == 0:
        return []
    n = min(n_results, count)
    results = collection.query(
        query_texts=[query],
        n_results=n
    )
    docs = results.get("documents", [[]])[0]
    return docs


def delete_collection(user_id: int):
    """Очистить всю память пользователя."""
    client = get_client()
    collection_name = f"user_{user_id}"
    try:
        client.delete_collection(collection_name)
        logger.info(f"Коллекция user_{user_id} удалена")
    except Exception:
        pass


def get_collection_size(user_id: int) -> int:
    collection = get_collection(user_id)
    return collection.count()
