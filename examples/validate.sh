#!/bin/sh
echo "Home: $HOME"

cd $1 && uv run mm.py -l README.md
