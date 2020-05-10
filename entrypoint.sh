#!/bin/sh

cd /podcast/src && python -m migrations apply


if [ "${ENV}" = "web" ]
  then
    cd /podcast/src && \
    python -m collectstatic && \
    python -m migrations upgrade && \
    gunicorn app:create_app --bind 0.0.0.0:8000 --worker-class aiohttp.GunicornWebWorker --user podcast

elif [ "${ENV}" = "rq" ]
  then
    cd /podcast/src && python -m rq_worker youtube_downloads --user podcast
else
  echo "ENV environment variable is unexpected or was not provided (ENV='${ENV}')" >&2
  kill -s SIGINT 1

fi
