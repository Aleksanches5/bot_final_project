"""
Парсер входных данных:
- CSV (текст или файл)
- Excel (.xlsx / .xls)
- Обычный текст с метриками
"""

import io
import csv
import json
import re
from typing import Optional


def parse_csv_text(text: str) -> list[dict]:
    """Парсит CSV из строки."""
    reader = csv.DictReader(io.StringIO(text.strip()))
    rows = []
    for row in reader:
        rows.append(dict(row))
    return rows


def parse_csv_bytes(data: bytes, encoding: str = "utf-8") -> list[dict]:
    """Парсит CSV из байтов (файл)."""
    # Пробуем несколько кодировок
    for enc in [encoding, "utf-8-sig", "cp1251", "latin-1"]:
        try:
            text = data.decode(enc)
            return parse_csv_text(text)
        except (UnicodeDecodeError, Exception):
            continue
    raise ValueError("Не удалось декодировать CSV файл.")


def parse_excel_bytes(data: bytes) -> list[dict]:
    """Парсит Excel из байтов."""
    try:
        import openpyxl
        wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        ws = wb.active
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            return []
        headers = [str(h) if h is not None else f"col_{i}" for i, h in enumerate(rows[0])]
        result = []
        for row in rows[1:]:
            if all(v is None for v in row):
                continue
            result.append({headers[i]: (str(v) if v is not None else "") for i, v in enumerate(row)})
        return result
    except ImportError:
        raise ImportError("Установите openpyxl: pip install openpyxl")


def summarize_data(rows: list[dict]) -> str:
    """Создаёт краткое текстовое описание таблицы."""
    if not rows:
        return "Пустая таблица."
    cols = list(rows[0].keys())
    n = len(rows)

    # Пытаемся найти числовые столбцы и посчитать статистику
    stats = []
    for col in cols:
        values = []
        for row in rows:
            val = row.get(col, "")
            try:
                values.append(float(str(val).replace(",", ".").replace(" ", "").replace("%", "")))
            except (ValueError, AttributeError):
                pass
        if values:
            avg = sum(values) / len(values)
            stats.append(f"{col}: min={min(values):.2f}, max={max(values):.2f}, avg={avg:.2f}")

    summary = f"Строк: {n}, Столбцы: {', '.join(cols)}."
    if stats:
        summary += "\nСтатистика по числовым полям:\n" + "\n".join(stats)
    return summary


def detect_channel_from_columns(rows: list[dict]) -> Optional[str]:
    """Пытается определить рекламный канал по названиям столбцов."""
    if not rows:
        return None
    cols_str = " ".join(rows[0].keys()).lower()

    if any(k in cols_str for k in ["яндекс", "директ", "yandex", "direct", "ctr", "показы", "клики"]):
        return "Яндекс.Директ"
    if any(k in cols_str for k in ["google", "adwords", "impressions", "clicks", "conversions"]):
        return "Google Ads"
    if any(k in cols_str for k in ["vk", "вконтакте", "охват", "подписчики"]):
        return "VK Реклама"
    if any(k in cols_str for k in ["facebook", "meta", "instagram", "fb"]):
        return "Meta Ads"
    if any(k in cols_str for k in ["mytarget", "мойтаргет"]):
        return "myTarget"
    return None


def extract_metrics_from_text(text: str) -> dict:
    """
    Извлекает числовые метрики из произвольного текста.
    Например: 'CTR: 2.5%, показы: 10000, конверсии: 150'
    """
    metrics = {}
    # Ищем паттерны вида "Название: число" или "Название = число"
    pattern = r'([A-Za-zА-Яа-я][A-Za-zА-Яа-я\s_\-\.]{1,40})\s*[:=]\s*([\d\s,.]+\s*%?)'
    for match in re.finditer(pattern, text):
        key = match.group(1).strip()
        val = match.group(2).strip()
        if key and val:
            metrics[key] = val
    return metrics
