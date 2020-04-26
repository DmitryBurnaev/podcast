deploy:
	git pull
	docker build -t podcast .
	supervisorctl stop podcast:
	docker-compose down
	supervisorctl start podcast:
	echo y | docker image prune -a

run_web:
	cd src && pipenv run python -m app

run_rq:
	cd src && pipenv run python -m rq_worker youtube_downloads

collectstatic:
	PYTHONPATH=${PWD}/src pipenv run python -m src.collectstatic

locale_init:
	pipenv run pybabel extract -F babel.cfg -o src/i18n/messages.pot src
	pipenv run pybabel init -i src/i18n/messages.pot -d src/i18n -l ru en

locale_update:
	pipenv run pybabel extract -F babel.cfg -o src/i18n/messages.pot src
	pipenv run pybabel update -i src/i18n/messages.pot -d src/i18n -l ru en

locale_compile:
	pipenv run pybabel compile -d src/i18n/

migrations_create:
	pipenv run python -m src.migrations create

migrations_apply:
	. ./.env && echo "=========== \n Applying migrations to \"$$DATABASE_NAME\" \n=========== \n "
	pipenv run python -m src.migrations apply
	. ./.env && echo "=========== \n Applying migrations to \"$$DATABASE_TEST_NAME\" \n=========== \n "
	. ./.env && PIPENV_DONT_LOAD_ENV=1 DATABASE_NAME=$$DATABASE_NAME_TEST pipenv run python -m src.migrations apply

migrations_show:
	pipenv run python -m src.migrations show

test:
	PYTHONPATH=${PWD}/src pipenv run pytest src/tests --aiohttp-fast --aiohttp-loop=uvloop --disable-warnings

lint:
	pipenv run black . --exclude migrations
	pipenv run flake8
