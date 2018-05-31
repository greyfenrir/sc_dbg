#!/bin/bash
OLD_PATH="$PATH"
PATH=/home/venv/bin:$PATH

for i in {1..100}
do 
  echo $i
  date
  python3 sc.py
done
