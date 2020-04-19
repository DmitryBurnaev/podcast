import argparse

import rq
from redis import Redis

import settings
from modules.podcast import tasks


def main():
    p = argparse.ArgumentParser()
    p.add_argument("task_name", choices=["upload_all", "delete_files"])
    args = p.parse_args()
    print(f" ===== Run task {args.task_name} ===== ",)
    rq_queue = rq.Queue(
        name="youtube_downloads",
        connection=Redis(*settings.REDIS_CON),
        default_timeout=settings.RQ_DEFAULT_TIMEOUT,
    )
    rq_queue.enqueue(getattr(tasks, args.task_name))


if __name__ == "__main__":
    main()
