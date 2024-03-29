import logging
import sys

from redis import Redis
from rq import Connection, Worker
import sentry_sdk
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.rq import RqIntegration

import settings
from app import database
from common.utils import get_logger, database_init

logger = get_logger("rq.worker")


def run_worker():
    """Allows to run RQ worker for consuming background tasks (like downloading youtube tracks)"""
    database_init(database)

    if settings.SENTRY_DSN:
        sentry_logging = LoggingIntegration(level=logging.INFO, event_level=logging.ERROR)
        sentry_sdk.init(settings.SENTRY_DSN, integrations=[RqIntegration(), sentry_logging])

    with Connection(Redis(*settings.REDIS_CON)):
        qs = sys.argv[1:] or ["default"]
        Worker(qs).work()


if __name__ == "__main__":
    run_worker()
