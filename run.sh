#!/bin/bash

cd /data/project/qic
source venv/bin/activate

cd qic_bot
python qic2.py > ../www/static/`date | sed 's/ /_/g'`.txt 2>&1

