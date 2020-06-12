FROM python:3.8-slim-buster
WORKDIR /podcast
ARG DEV_DEPS

COPY Pipfile /podcast
COPY Pipfile.lock /podcast

RUN groupadd -r podcast && useradd -r -g podcast podcast
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
		gcc \
		libpq-dev \
		python-dev \
		wget \
		unzip \
	&& wget https://github.com/vot/ffbinaries-prebuilt/releases/download/v4.1/ffmpeg-4.1-linux-64.zip -q -O /tmp/ffmpeg-4.1-linux-64.zip \
	&& unzip /tmp/ffmpeg-4.1-linux-64.zip -d /usr/bin \
	&& rm /tmp/ffmpeg-4.1-linux-64.zip \
	&& pip install pipenv \
	&& if [ ${DEV_DEPS} = "true" ]; then \
	     echo "=== Install DEV dependencies ===" && \
	     pipenv install --dev --system; \
       else \
         echo "=== Install PROD dependencies ===" && \
	     pipenv install --system; \
       fi \
	&& apt-get purge -y --auto-remove gcc python-dev \
	&& apt-get -y autoremove \
	&& apt-get clean \
	&& rm -rf /var/lib/apt/lists/*

COPY ./src ./src
COPY entrypoint.sh .
COPY pytest.ini .
COPY .flake8 .

RUN chown -R podcast:podcast /podcast

ENTRYPOINT ["/bin/sh", "/podcast/entrypoint.sh"]
