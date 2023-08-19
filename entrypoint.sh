#!/bin/sh

cd /podcast/src && python -m migrations upgrade


if [ "${APP_SERVICE}" = "web" ]
  then
    cd /podcast/src && \
    python -m collectstatic && \
    gunicorn app:create_app --bind 0.0.0.0:8000 --worker-class aiohttp.GunicornWebWorker --user podcast

elif [ "${APP_SERVICE}" = "rq" ]
  then
    cd /podcast/src && \
    python -m rq_worker youtube_downloads --user podcast

elif [ "${APP_SERVICE}" = "test" ]
  then
    cd /podcast &&
    flake8 --count && \
    cd src && \

    coverage run --source="modules/" -m pytest && \
    coverage report

else
  echo "ENV environment variable is unexpected or was not provided (ENV='${ENV}')" >&2
  kill -s SIGINT 1

fi
