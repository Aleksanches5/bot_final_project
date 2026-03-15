import logging
import io
import re
from typing import Optional
import pandas as pd
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def parse_csv(file_bytes: bytes, filename: str) -> tuple[str, dict]:
    try:
        for encoding in ["utf-8", "cp1251", "latin-1"]:
            try:
                df = pd.read_csv(io.BytesIO(file_bytes), encoding=encoding, sep=None, engine="python")
                break
            except Exception:
                continue
        else:
            raise ValueError("Не удалось определить кодировку CSV")
        return _dataframe_to_text(df, filename)
    except Exception as e:
        logger.error(f"Ошибка парсинга CSV: {e}")
        raise


def parse_excel(file_bytes: bytes, filename: str) -> tuple[str, dict]:
    try:
        xl = pd.ExcelFile(io.BytesIO(file_bytes))
        all_text = []
        all_data = {}
        for sheet_name in xl.sheet_names:
            df = xl.parse(sheet_name)
            if df.empty:
                continue
            text, data = _dataframe_to_text(df, f"{filename} / {sheet_name}")
            all_text.append(text)
            all_data[sheet_name] = data
        return "\n\n".join(all_text), all_data
    except Exception as e:
        logger.error(f"Ошибка парсинга Excel: {e}")
        raise


def _dataframe_to_text(df: pd.DataFrame, source_name: str) -> tuple[str, dict]:
    df = df.dropna(how="all")

    # ── Конвертировать ВСЕ нечисловые типы в строки ──────────────────────────
    for col in df.columns:
        if df[col].dtype == object or str(df[col].dtype).startswith("datetime"):
            df[col] = df[col].astype(str)

    # Конвертировать названия столбцов в строки (могут быть датами)
    df.columns = [str(c) for c in df.columns]

    df = df.fillna(0)
    rows, cols = df.shape

    numeric_stats = {}
    for col in df.select_dtypes(include="number").columns:
        try:
            numeric_stats[col] = {
                "min": round(float(df[col].min()), 2),
                "max": round(float(df[col].max()), 2),
                "mean": round(float(df[col].mean()), 2),
                "sum": round(float(df[col].sum()), 2),
            }
        except Exception:
            pass

    lines = [
        f"Файл: {source_name}",
        f"Строк: {rows}, Столбцов: {cols}",
        f"Столбцы: {', '.join(df.columns.tolist())}",
        "",
        "Статистика по числовым метрикам:"
    ]
    for col, stats in numeric_stats.items():
        lines.append(
            f"  {col}: мин={stats['min']}, макс={stats['max']}, "
            f"среднее={stats['mean']}, сумма={stats['sum']}"
        )
    lines.append("\nПервые строки данных:")
    lines.append(df.head(10).to_string(index=False))

    text = "\n".join(lines)
    data = {
        "source": source_name,
        "shape": [rows, cols],
        "columns": df.columns.tolist(),
        "numeric_stats": numeric_stats,
        "preview": df.head(20).to_dict(orient="records")
    }
    return text, data


def parse_txt_or_pdf(file_bytes: bytes, filename: str, mime_type: str) -> str:
    if "pdf" in mime_type or filename.endswith(".pdf"):
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                text = "\n\n".join(page.extract_text() or "" for page in pdf.pages)
            return text.strip()
        except Exception as e:
            logger.error(f"Ошибка парсинга PDF: {e}")
            raise
    else:
        for encoding in ["utf-8", "cp1251", "latin-1"]:
            try:
                return file_bytes.decode(encoding)
            except Exception:
                continue
        raise ValueError("Не удалось декодировать текстовый файл")


def fetch_url_content(url: str) -> str:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.content, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        text = "\n".join(lines)
        if len(text) > 15000:
            text = text[:15000] + "\n...[текст обрезан]"
        return text
    except Exception as e:
        logger.error(f"Ошибка загрузки URL {url}: {e}")
        raise


def split_text_into_chunks(text: str, chunk_size: int = 1000, overlap: int = 200) -> list[str]:
    if len(text) <= chunk_size:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        if end < len(text):
            last_period = text.rfind(".", start, end)
            if last_period > start + chunk_size // 2:
                end = last_period + 1
        chunks.append(text[start:end].strip())
        start = end - overlap
    return [c for c in chunks if c]


def detect_ad_channel(columns: list[str], text: str) -> str:
    text_lower = (text + " ".join(columns)).lower()
    if any(w in text_lower for w in ["яндекс", "yandex", "direct", "директ"]):
        return "Яндекс Директ"
    elif any(w in text_lower for w in ["google", "adwords", "google ads"]):
        return "Google Ads"
    elif any(w in text_lower for w in ["vk", "вконтакте", "вк реклама"]):
        return "VK Реклама"
    elif any(w in text_lower for w in ["facebook", "meta", "instagram"]):
        return "Meta Ads"
    elif any(w in text_lower for w in ["mytarget", "my target"]):
        return "myTarget"
    elif any(w in text_lower for w in ["xapads", "xerxes", "hapads"]):
        return "Xapads"
    else:
        return "Неизвестный канал"
