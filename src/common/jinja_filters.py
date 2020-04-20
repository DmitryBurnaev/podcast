import datetime


def datetime_format(value: datetime.datetime, output_format="%d.%m.%Y %H:%M"):
    return value.strftime(output_format) if value else "-"


def human_length(length: int) -> str:
    return str(datetime.timedelta(seconds=length))
