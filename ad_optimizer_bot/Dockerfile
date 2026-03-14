FROM python:3.11-slim

WORKDIR /app

# Системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Python зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код приложения
COPY . .

# Создать директории для данных
RUN mkdir -p data/chroma_db data/uploads

# Отключить буферизацию Python-логов
ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
