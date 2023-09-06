#!/bin/bash

mkdir migrations/versions
quart migrate -s "$SETTINGS"
quart run_all -s "$SETTINGS"