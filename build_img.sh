#!/bin/sh
CPYTHON_DIR=`pwd`/python.src
if [ ! -d "$CPYTHON_DIR" ]; then
	git clone https://github.com/python/cpython.git "$CPYTHON_DIR"
	cd "$CPYTHON_DIR"
	git checkout "v3.5.5"
	cd ..
fi

docker build -t sc_dbg .

