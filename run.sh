#!/usr/bin/env bash
set -e

cd "$(dirname "${BASH_SOURCE[0]}")"
source .venv/bin/activate
clear
flask run --host=0.0.0.0 --port=5000
