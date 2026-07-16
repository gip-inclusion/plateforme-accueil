FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-cache --no-dev --no-install-project
COPY . .
RUN uv sync --frozen --no-cache --no-dev
RUN .venv/bin/python manage.py collectstatic --noinput

EXPOSE 8080
CMD [".venv/bin/gunicorn", "config.wsgi", "--bind", "0.0.0.0:8080"]
