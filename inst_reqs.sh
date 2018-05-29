#!/bin/sh
pip install -U pip setuptools wheel
pip install -r `pwd`/../taurus/requirements.txt
pip install -r `pwd`/../taurus-cloud/r2.txt
