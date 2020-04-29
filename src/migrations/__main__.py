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
from migrations.utils import (
    create_migration,
    migrations_upgrade,
    migrations_downgrade,
    show_migration_history,
)

operations_map = {
    "create": create_migration,
    "upgrade": migrations_upgrade,
    "downgrade": migrations_downgrade,
    "show": show_migration_history,
}


parser = argparse.ArgumentParser(
    usage="venv/bin/python -m migrations.run create|upgrade|downgrade|show"
)
parser.add_argument(
    "operation",
    metavar="Operation-Type",
    type=str,
    choices=operations_map.keys(),
    help="""
        "create" - create migration module; 
        "upgrade" - apply all not applied migrations;  
        "downgrade" - downgrade applied migrations (all after specified);  
        "show" - print list of applied migrations;
    """,
)
parser.add_argument(
    "--revision",
    metavar="Migration Number",
    type=str,
    default="",
)

args = parser.parse_args()
handler = operations_map[args.operation]
database_init(database)
args = [args.revision] if args.revision else []
handler(*args)
