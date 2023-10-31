#!/bin/bash

POETRY_VENV="$(poetry env info -p)"
export PATH="${PATH}:${POETRY_VENV}/bin"

mkdir migrations
quart migrate -s "$SETTINGS"
quart run_all -s "$SETTINGS"