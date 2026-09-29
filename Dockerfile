FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir requests pyyaml

COPY . .

EXPOSE 8800

ENV PORT=8800
ENV HOST=0.0.0.0
ENV PYTHONUNBUFFERED=1

CMD ["python3", "server/server.py", "8800"]
