#!/bin/sh
if [ -z "$1" ]; then
    echo "Usage: ./validate.sh <example-directory>" >&2
    exit 1
fi

echo "Home: $HOME"

cd "$1" && uv run --group examples mm.py -l README.md
