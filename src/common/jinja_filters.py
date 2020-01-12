import datetime
from urllib.parse import urljoin

import settings


def datetime_format(value: datetime.datetime, output_format="%d.%m.%Y %H:%M"):
    return value.strftime(output_format) if value else "-"


def rss_link(publish_id: str):
    return urljoin(settings.SITE_URL, f"/rss/{publish_id}.xml")


def human_length(length: int) -> str:
    return str(datetime.timedelta(seconds=length))
