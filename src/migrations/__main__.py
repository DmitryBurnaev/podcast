"""
This module helps to manipulate for peewee migrations:
  - create template for new migration
  - run not applied migrations
  - show all applied migrations

position arguments:
    Operation [create|apply|show]

Example:
    venv/bin/python -m src.migrations create|apply|show

You can get additional information by using:
$ venv/bin/python -m src.migrations --help

"""
import argparse

from common.utils import database_init
from migrations.models import database
from migrations.utils import create_migration, run_migrations, show_migration_history

operations_map = {
    "create": create_migration,
    "apply": run_migrations,
    "show": show_migration_history,
}


parser = argparse.ArgumentParser(
    usage="venv/bin/python -m migrations.run create|apply|show"
)
parser.add_argument(
    "operation",
    metavar="Operation-Type",
    type=str,
    choices=operations_map.keys(),
    help="""
        "create" - create migration module; 
        "apply" - apply all not applied migrations;  
        "show" - print list of applied migrations;
    """,
)
args = parser.parse_args()
handler = operations_map[args.operation]
database_init(database)
handler()
