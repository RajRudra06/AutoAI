#!/usr/bin/env zsh
set -e
cd "$(dirname "$0")"
exec ./AutoAI_ENV/bin/python run_everything.py
