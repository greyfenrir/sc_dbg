#!/bin/bash
OLD_PATH="$PATH"
PATH=/home/venv/bin:$PATH

for i in {1..100}
do 
  echo $i
  nosetests -v tests/test_screenshots.py
  date
done
