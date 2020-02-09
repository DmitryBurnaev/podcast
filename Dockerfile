FROM python:3.7.6-slim-buster
WORKDIR /podcast

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
	&& pip install pipenv && pipenv install --system \
	&& apt-get purge -y --auto-remove gcc python-dev wget unzip \
	&& apt-get -y autoremove \
	&& apt-get clean \
	&& rm -rf /var/lib/apt/lists/*

COPY ./src /podcast/src
COPY ./entrypoint.sh /podcast/entrypoint.sh
RUN chown -R podcast:podcast /podcast

ENTRYPOINT ["/bin/sh", "/podcast/entrypoint.sh"]
