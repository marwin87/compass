FROM python:3.12-slim-bookworm AS builder
COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

FROM python:3.12-slim-bookworm
RUN useradd --system --uid 1000 --create-home app \
    && mkdir /data && chown app:app /data
COPY --from=builder /app/.venv /app/.venv
COPY web/assets /app/web/assets
ENV PATH="/app/.venv/bin:$PATH" COMPASS_DB_PATH=/data/compass.db COMPASS_ASSETS_DIR=/app/web/assets
USER app
VOLUME /data
EXPOSE 8011
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8011/health')"
CMD ["uvicorn", "compass.main:app", "--host", "0.0.0.0", "--port", "8011"]
