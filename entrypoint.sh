#!/bin/bash

POETRY_VENV="$(poetry env info -p)"
export PATH="${PATH}:${POETRY_VENV}/bin"

poetry run python app.py migrate -c "$SETTINGS"
poetry run python app.py run_all -c "$SETTINGS"