#!/data/data/com.termux/files/usr/bin/bash

pkill gunicorn
gunicorn -k gthread \
--workers 1 \
--threads 8 \
--timeout 180 \
--bind 0.0.0.0:5002 \
app:app
