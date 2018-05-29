#!/bin/sh
OLD_PATH="$PATH"
PATH=/home/venv/bin
nosetests -v tests/test_screenshots.py
