FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY . .
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8502 8000
CMD ["streamlit", "run", "app/dashboard.py", "--server.port=8502", "--server.address=0.0.0.0"]
