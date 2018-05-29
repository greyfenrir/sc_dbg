#!/bin/sh
OLD_PATH="$PATH"
PATH=/home/venv/bin:$PATH
nosetests -v tests/test_screenshots.py
