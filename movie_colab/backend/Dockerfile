FROM python:3.11-slim

LABEL maintainer="movie-colab" \
      description="Direct-to-Drive Cloud Ingestion Engine Backend"

RUN apt-get update && apt-get install -y --no-install-recommends \
        aria2 \
        ffmpeg \
        curl \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL \
        https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp \
        -o /usr/local/bin/yt-dlp \
    && chmod +x /usr/local/bin/yt-dlp

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
