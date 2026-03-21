import logging, os, json
logger = logging.getLogger(__name__)
STORE_DIR = "data/store"

def _user_dir(user_id):
    p = os.path.join(STORE_DIR, f"user_{user_id}")
    os.makedirs(p, exist_ok=True)
    return p

def add_texts(user_id, texts, metadatas=None):
    d = _user_dir(user_id)
    p = os.path.join(d, "texts.json")
    ex = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else []
    ex.extend(texts)
    json.dump(ex, open(p, "w", encoding="utf-8"), ensure_ascii=False)
    logger.info(f"Добавлено {len(texts)} чанков для user {user_id}")
    return [str(i) for i in range(len(ex)-len(texts), len(ex))]

def search_relevant(user_id, query, n_results=5):
    p = os.path.join(_user_dir(user_id), "texts.json")
    if not os.path.exists(p): return []
    texts = json.load(open(p, encoding="utf-8"))
    words = set(query.lower().split())
    scored = sorted([(sum(1 for w in words if w in t.lower()), t) for t in texts], reverse=True)
    return [t for s, t in scored[:n_results] if s > 0] or texts[:n_results]

def delete_collection(user_id):
    import shutil
    d = _user_dir(user_id)
    if os.path.exists(d): shutil.rmtree(d)

def get_collection_size(user_id):
    p = os.path.join(_user_dir(user_id), "texts.json")
    return len(json.load(open(p, encoding="utf-8"))) if os.path.exists(p) else 0
