# Custom Podcasts
AIOHttp based application for creation and moderation your own podcasts with episodes 
which are downloaded from other resources (from Youtube for example):

![GitHub Pipenv locked Python version](https://img.shields.io/github/pipenv/locked/python-version/DmitryBurnaev/podcast)

## Content
+ [Project Description](#project-description)
+ [Install Project](#install-project)
+ [Run Project](#run-project)
+ [Useful Commands](#useful-commands)
+ [Env Variables](#environment-variables)
+ [Localisation](#localisation)
+ [License](#license)


### Project Description

#### Target 
This application can be used for creation your podcasts. <br/>
If you have any sounds (or youtube videos as example) which you want to listen later, you can create podcast (via web interface) and attach this resources to this podcast <br/>
Created podcast (with prepared episodes) has direct link, which can be used for adding this one to your favorite podcast application (`Add by URL`) <br />
Every new episodes will be added to your podcast automatically.

#### Tech details
Technically project contains from 3 parts:
##### AIOHttp web application (run on `APP_PORT` from your env): 
  + user's registration/login (every podcast/episode is separated by users)
  + creation new podcast
  + creation new episodes (based on youtube videos)
  + display/edit podcast details
  + display/edit episode details

##### Background application: RQ 
  + download sounds from requested resource
  + perform sound and prepare mp3 files with `ffmpeg`
  + generate RSS feed file (xml) with episodes (by specification https://cyber.harvard.edu/rss/rss.html)  

##### Proxy application on your server (NGINX for example)
  + proxy to `APP_PORT`
  + aliases for media files `<PATH_TO_PROJECT>/media/audio`
  + aliases for RSS files `<PATH_TO_PROJECT>/media/rss`

##### Stack of technology
+ python 3.7
+ aiohttp
+ RQ (background tasks)
+ youtube-dl (download tracks from youtube)
+ redis (key-value storage + RQ)

### Install Project

#### Prepare virtual environment
```shell script
cd "<PATH_TO_PROJECT>"
cp .env.template .env
# update variables to actual (redis, postgres, etc.)
```

#### Prepare extra resources (postgres | redis)
```shell script
export $(cat .env | grep -v ^# | xargs)
docker run --name postgres-server -e POSTGRES_PASSWORD=${DATABASE_PASSWORD} -d postgres:10.11
docker run --name redis-server -d redis
```

#### Create database
```shell script
export $(cat .env | grep -v ^# | xargs)
PGPASSWORD=${DATABASE_PASSWORD} psql -U${DATABASE_USER} -h${DATABASE_HOST} -p${DATABASE_PORT} -c "create database ${DATABASE_NAME};"
```
#### Apply migrations
```shell script
cd "<PATH_TO_PROJECT>" && make migrations_apply
```


### Run Project

+ Run via docker-containers (like in production mode)
```shell script
cd "<PATH_TO_PROJECT>" && docker-compose up --build
```

+ Run in develop-mode
```shell script
# install pipenv https://pypi.org/project/pipenv/
cd "<PATH_TO_PROJECT>"
pipenv install --dev
make run_web
make run_rq
```

### Localisation

Project can provide web-interface on 2 languages: `English` | `Russian` <br />
Localisation is powered by `python babel`:
+ update messages (after adding new words, marked underscore `_`)
```shell script
cd "<PATH_TO_PROJECT>" && make locale_update
```
+ update `src/i18n/ru/LC_MESSAGES/messages.po` (or needed language)
+ compile messages
```shell script
cd "<PATH_TO_PROJECT>" && make locale_compile
```

### Useful commands

+ Create new db migration's file 
```shell script
make migrations_create
```
+ Apply all collected migrations
```shell script
make migrations_show
```
+ Collect static files (For providing web interface app uses static files)
```shell script
make collectstatic
```
+ Run tests
```shell script
make test
```
+ Apply formatting (`black`) and lint code (`flake8`)
```shell script
make lint
```

## Environment Variables

### REQUIRED Variables

| argument                  | description                                       | example               |
|:------------------------- |:-------------------------------------------------:| ---------------------:|
| APP_HOST                  | App default host running (used by docker compose) | 127.0.0.1             |
| APP_PORT                  | App default port running (used by docker compose) | 9000                  |
| APP_SERVICE               | Run service (web/celery/test) via entrypoint.sh   | web                   |
| SECRET_KEY                | Django secret key (security)                      | _abc3412j345j1f2d3f_  |
| SITE_URL                  | Your URL address (is used for email links)        | http://podcast.st.com |
| DATABASE_DB_HOST          | PostgreSQL database host                          | 127.0.0.1             |
| DATABASE_DB_PORT          | PostgreSQL database port                          | 5432                  |
| DATABASE_DB_NAME          | PostgreSQL database name                          | polls                 |
| DATABASE_DB_USER          | PostgreSQL database username                      | polls                 |
| DATABASE_DB_PASSWORD      | PostgreSQL database password                      | polls_asf2342         |
| DATABASE_NAME_TEST        | PostgreSQL database name (for test running)       | podcast_test|

### OPTIONAL Variables

| argument                  | description                                       | default               |
|:------------------------- |:-------------------------------------------------:| ---------------------:|
| APP_DEBUG                 | run app in debug mode                             | False                 |
| ALLOWED_HOSTS             | Django specific Allowed hosts (comma separated)   | localhost             |
| LOG_LEVEL                 | Allows to set current logging level               | DEBUG                 |
| LOG_PRODUCTION_MODE       | Format and detail log records for production      | False                 |
| DISABLE_LOG               | Allows to disable all logs                        | False                 |
| SENTRY_DSN                | Sentry dsn (if not set, error logs won't be sent) | _abc3412jsdb345jfdf_  |
| REDIS_HOST                | Redis host                                        | localhost             |
| REDIS_PORT                | Redis port                                        | 6379                  |

* * *

### License

This product is released under the MIT license. See LICENSE for details.
