#!/bin/sh
echo "Home: $HOME"

cd "$1" && uv run --group examples mm.py -l README.md
