# Envira exposure service. Build: docker build -t envira-exposure .
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy PYTHONUNBUFFERED=1
WORKDIR /app

# Dependencies first so the layer is reused when only source or data changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project

# Then the package and the source data; the app loads data/ relative to /app.
COPY exposure/ exposure/
COPY data/ data/
RUN uv sync --locked --no-dev

ENV EXPOSURE_DATA_DIR=/app/data
EXPOSE 8000
CMD ["uv", "run", "--no-dev", "uvicorn", "exposure.api:app", "--host", "0.0.0.0", "--port", "8000"]
