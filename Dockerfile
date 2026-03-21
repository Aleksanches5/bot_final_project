FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y gcc g++ && rm -rf /var/lib/apt/lists/*

# Сначала только requirements — этот слой кешируется
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Потом код — этот слой пересобирается быстро
COPY . .

RUN mkdir -p data/chroma_db data/uploads data/store

ENV PYTHONUNBUFFERED=1

CMD ["python", "main.py"]
