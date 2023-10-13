FROM python:3.11-alpine

ENV POETRY_HOME=/opt/poetry
ENV POETRY_CACHE_DIR=/opt/.cache

WORKDIR "/yepcord"

RUN apk update && apk add --no-cache libmagic git bash && apk add --no-cache --virtual build-deps gcc libc-dev
RUN python -m venv $POETRY_HOME && $POETRY_HOME/bin/pip install -U pip setuptools && $POETRY_HOME/bin/pip install poetry
ENV PATH="${PATH}:${POETRY_HOME}/bin"

COPY poetry.lock poetry.lock
COPY pyproject.toml pyproject.toml
RUN poetry install --only main --no-interaction --no-root

RUN apk del build-deps

COPY . .
RUN chmod +x entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]