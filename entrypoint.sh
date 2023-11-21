#!/bin/bash

POETRY_VENV="$(poetry env info -p)"
export PATH="${PATH}:${POETRY_VENV}/bin"

mkdir migrations
yepcord migrate -s "$SETTINGS"
yepcord run_all -s "$SETTINGS"