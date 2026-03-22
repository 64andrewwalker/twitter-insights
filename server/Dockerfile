FROM python:3.12-slim

# Verify SQLite version supports trigram tokenizer (>= 3.34)
RUN python3 -c "import sqlite3; v = sqlite3.sqlite_version_info; assert v >= (3,34,0), f'SQLite {sqlite3.sqlite_version} < 3.34'"

WORKDIR /app

# Install server dependencies
COPY server/requirements.txt server/requirements.txt
RUN pip install --no-cache-dir -r server/requirements.txt

# Install ti package (needed for search/output/db modules)
COPY pyproject.toml .
COPY src/ src/
RUN pip install --no-cache-dir .

# Copy server code
COPY server/ server/

EXPOSE 8000

CMD uvicorn server.app:create_app --host 0.0.0.0 --port ${PORT:-8000} --factory
