# syntax=docker/dockerfile:1
FROM python:3.12-slim AS builder

RUN pip install uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-editable

COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY src/ ./src/

FROM python:3.12-slim AS runtime

WORKDIR /app
COPY --from=builder /app /app
COPY --from=builder /root/.local/share/uv /root/.local/share/uv

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/src"

EXPOSE 8000

CMD ["uvicorn", "vox_pm.main:app", "--host", "0.0.0.0", "--port", "8000"]
