#!/bin/bash
# aptitude install {libssl,libxml2,libxslt,python,lib32z1,libjpeg}-dev
PY_VER="3.5"
BUILDER_DIR=`pwd`
CPYTHON_DIR="$BUILDER_DIR"/python.src
TAURUS_DIR="$BUILDER_DIR"/../taurus
TMP_BUILD_DIR="$BUILDER_DIR"/tmp
PREFIX="$BUILDER_DIR"/python.inst
VENV_DIR="$BUILDER_DIR"/venv

if [ ! -d "$CPYTHON_DIR" ]; then
	git clone https://github.com/python/cpython.git "$CPYTHON_DIR"
	cd "$CPYTHON_DIR"
	git checkout "v3.5.5"
	cd ..
fi

if [ -d "$TMP_BUILD_DIR" ]; then
	echo "removing old $TMP_BUILD_DIR..."
	rm -rf "$TMP_BUILD_DIR"
fi

if [ -d "$PREFIX" ]; then
	echo "removing old $PREFIX..."
	rm -rf "$PREFIX"
fi

if [ -d "$VENV_DIR" ]; then
	echo "removing old $VENV_DIR..."
	rm -rf "$VENV_DIR"
fi

echo "creation dirs..."
mkdir "$TMP_BUILD_DIR"
mkdir "$PREFIX"
mkdir "$VENV_DIR"

cd "$TMP_BUILD_DIR"

"$CPYTHON_DIR"/configure --with-pydebug --prefix="$PREFIX"

make && make install

python -m virtualenv "$VENV_DIR" -p "$PREFIX"/bin/python3

_OLD_PATH="$PATH"
PATH="$VENV_DIR"/bin:"$PATH"

pip install -U pip setuptools wheel
pip install -r "$BUILDER_DIR"/r1.txt
pip install -r "$BUILDER_DIR"/r2.txt
pip install git+https://github.com/Blazemeter/taurus.git

PATH="$_OLD_PATH"
