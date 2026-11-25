FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.5 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY app ./app
ENV MIGRATIONS_DIR=/db/migrations
CMD ["sh", "-c", "uv run --no-dev python -m app.migrate && uv run --no-dev uvicorn app.main:app --host 0.0.0.0 --port 8000"]
