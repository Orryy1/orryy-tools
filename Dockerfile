FROM python:3.11-slim

# System deps for essentia, soundfile, and pyacoustid
RUN apt-get update && apt-get install -y --no-install-recommends \
    libfftw3-dev \
    libyaml-dev \
    libsamplerate0-dev \
    libtag1-dev \
    libchromaprint-dev \
    libsndfile1 \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Init the SQLite database
RUN python -c "import sqlite3; conn = sqlite3.connect('orryy_tools.db'); conn.executescript(open('db/init.sql').read()); conn.close()"

EXPOSE ${PORT:-8000}

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
