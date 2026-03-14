import logging
import os
import json
import pickle
import numpy as np
from config import CHROMA_PATH  # переиспользуем путь как папку хранилища

logger = logging.getLogger(__name__)

# Папка хранилища
STORE_DIR = CHROMA_PATH

_model = None


def _get_model():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer("paraphrase-multilingual-MiniLM-L12-v2")
    return _model


def _user_dir(user_id: int) -> str:
    path = os.path.join(STORE_DIR, f"user_{user_id}")
    os.makedirs(path, exist_ok=True)
    return path


def _load_store(user_id: int):
    """Загрузить индекс и тексты пользователя."""
    import faiss
    d = _user_dir(user_id)
    index_path = os.path.join(d, "index.faiss")
    texts_path = os.path.join(d, "texts.json")

    if os.path.exists(index_path) and os.path.exists(texts_path):
        index = faiss.read_index(index_path)
        with open(texts_path, "r", encoding="utf-8") as f:
            texts = json.load(f)
    else:
        index = faiss.IndexFlatL2(384)  # размерность MiniLM
        texts = []

    return index, texts


def _save_store(user_id: int, index, texts: list):
    import faiss
    d = _user_dir(user_id)
    faiss.write_index(index, os.path.join(d, "index.faiss"))
    with open(os.path.join(d, "texts.json"), "w", encoding="utf-8") as f:
        json.dump(texts, f, ensure_ascii=False)


def add_texts(user_id: int, texts: list[str], metadatas: list[dict] = None) -> list[str]:
    """Добавить тексты в векторное хранилище."""
    model = _get_model()
    index, existing_texts = _load_store(user_id)

    embeddings = model.encode(texts, normalize_embeddings=True).astype("float32")
    index.add(embeddings)
    existing_texts.extend(texts)

    _save_store(user_id, index, existing_texts)
    logger.info(f"Добавлено {len(texts)} чанков для user {user_id}")

    # Возвращаем условные ID
    start = len(existing_texts) - len(texts)
    return [str(i) for i in range(start, len(existing_texts))]


def search_relevant(user_id: int, query: str, n_results: int = 5) -> list[str]:
    """Найти релевантные фрагменты по запросу."""
    model = _get_model()
    index, texts = _load_store(user_id)

    if index.ntotal == 0:
        return []

    query_vec = model.encode([query], normalize_embeddings=True).astype("float32")
    k = min(n_results, index.ntotal)
    distances, indices = index.search(query_vec, k)

    results = []
    for idx in indices[0]:
        if 0 <= idx < len(texts):
            results.append(texts[idx])
    return results


def delete_collection(user_id: int):
    """Удалить все данные пользователя."""
    import shutil
    d = _user_dir(user_id)
    if os.path.exists(d):
        shutil.rmtree(d)
        logger.info(f"Хранилище user_{user_id} удалено")


def get_collection_size(user_id: int) -> int:
    _, texts = _load_store(user_id)
    return len(texts)