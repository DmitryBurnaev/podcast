import datetime
import inspect
import os
import re
import pprint
from types import ModuleType
from typing import Dict, Callable, List, Type

import settings
from common.models import BaseModel
from migrations.models import MigrationHistory, database


SCRIPTS_PATH = os.path.join(settings.BASE_DIR, "migrations", "versions")
LAST_APPLIED = None
ZERO_MIGRATION = "0000"
MIGRATION_TEMPLATE = """\""" 
Created_at: {now:%d %b. %Y %H:%M:%S}
Target: 

\"""

from playhouse.migrate import *
from migrations.models import database

previous = "{prev_migration_name}"

# see details http://docs.peewee-orm.com/en/latest/peewee/playhouse.html#schema-migrations

def upgrade():
    migrator = PostgresqlMigrator(database)    
    # migrate(
    #     migrator.add_column('episodes', 'test_status_2', CharField(null=True)),
    # )


def downgrade():
    migrator = PostgresqlMigrator(database)    
    # migrate(
    #     migrator.drop_column('episodes', 'test_status_2'),
    # )

"""


class MigrationModuleType(ModuleType):
    previous: str
    upgrade: Callable
    downgrade: Callable


def _get_last_applied() -> str:
    """ Get last record (if exists) from table migration_history and returns it name """

    MigrationHistory.create_table()

    last_applied = (
        MigrationHistory.select(MigrationHistory.migration_name)
        .order_by(MigrationHistory.applied_at.desc())
        .first()
    )
    if last_applied:
        return last_applied.migration_name

    return ZERO_MIGRATION


def _get_migration_module(module_name: str) -> MigrationModuleType:
    """ Inspects got module from migration's scripts """

    module_obj = __import__(f"migrations.versions.{module_name}")
    for _, obj in inspect.getmembers(module_obj):
        if inspect.ismodule(obj) and hasattr(obj, module_name):
            return getattr(obj, module_name)
    else:
        raise RuntimeError(f"Not found migration module for {module_name}")


def _inspect_modules(reverse=False) -> Dict[str, str]:
    """ Returns map for found migrations scripts (linked via `previous` attribute) """

    migrations_map = {}
    for module_name in os.listdir(SCRIPTS_PATH):
        module_path = os.path.join(SCRIPTS_PATH, module_name)
        if os.path.isfile(module_path) and module_name != "__init__.py":
            module_name = module_name.replace(".py", "")
            migration_module = _get_migration_module(module_name)
            migrations_map[migration_module.previous or ZERO_MIGRATION] = module_name

    if reverse:
        migrations_map = {val: key for key, val in migrations_map.items()}

    print("--- Prepared migration chains: ---")
    pprint.pprint(migrations_map, indent=4)
    print("---")
    return migrations_map


def create_tables(models: List[Type[BaseModel]]):
    for model in models:
        print(f"Creation table for {model}")
        model.create_table()


def remove_tables(models: List[Type[BaseModel]]):
    for model in models:
        print(f"Remove table for {model}")
        model.drop_table()


def migrations_upgrade() -> None:
    """ Finds not applied migrations; detect exists migration's modules and apply it. """
    print(f"=========== \n Applying migrations for {os.getenv('DATABASE_NAME')} \n=========== \n ")

    migrations_map = _inspect_modules()
    last_applied = _get_last_applied()
    applied_count = 0
    next_migration_name = migrations_map.get(last_applied)
    while next_migration_name is not None:
        print(f"Applying '{next_migration_name}'...")
        migration_module = _get_migration_module(next_migration_name)
        with database.transaction():
            migration_module.upgrade()
            MigrationHistory.create(
                migration_name=next_migration_name,
                migration_details=(migration_module.__doc__ or "")
                .strip()
                .replace("\n", ". "),
            )
        next_migration_name = migrations_map.get(next_migration_name)
        applied_count += 1

    if not applied_count:
        print("No migrations to apply.")
    else:
        print(f"Successful applied {applied_count} migrations")


def migrations_downgrade(migration_number: str) -> None:
    """ Finds not applied migrations; detect exists migration's modules and apply it. """
    db_name = os.getenv('DATABASE_NAME')
    print(f"=========== \n Rolling back migrations for {db_name} \n=========== \n ")

    migrations_map = _inspect_modules(reverse=True)
    last_applied = _get_last_applied()
    applied_count = 0
    next_migration_name = last_applied
    print(next_migration_name)
    while not next_migration_name.startswith(migration_number):
        print(f"Rolling back '{next_migration_name}'...")
        migration_module = _get_migration_module(next_migration_name)
        with database.transaction():
            migration_module.downgrade()
            query = MigrationHistory.delete().where(
                MigrationHistory.migration_name == next_migration_name
            )
            query.execute()

        next_migration_name = migrations_map.get(next_migration_name)
        applied_count += 1

    if not applied_count:
        print("No migrations to rollback.")


def create_migration():
    """ Allows to create new migration module with link to previous (last by number migration) """

    number_pattern = re.compile("^0*(\d{1,4})")
    max_number, last_migration_name = 0, ZERO_MIGRATION
    for module_name in os.listdir(SCRIPTS_PATH):
        match = re.search(number_pattern, module_name)
        if match:
            migration_number = int(match.groups()[0])
            if migration_number > max_number:
                max_number = migration_number
                last_migration_name = module_name.replace(".py", "")

    now = datetime.datetime.utcnow()
    new_migration_name = f"{max_number+1:0>4}_{now:%d%m%Y}_migration.py"
    new_migration_path = os.path.join(SCRIPTS_PATH, new_migration_name)

    with open(new_migration_path, "w") as dest:
        migration_content = MIGRATION_TEMPLATE.format(
            now=now, prev_migration_name=last_migration_name
        )
        dest.write(migration_content)

    print(f"Created migration {new_migration_name}")


def show_migration_history() -> None:
    """ Display all saved in `migration_history` table records and print it as formated string """

    MigrationHistory.create_table()
    applied_migrations = MigrationHistory.select().order_by(MigrationHistory.applied_at)

    print("--- Applied migrations: --- ")
    for migration in applied_migrations:
        print(
            f"{migration.migration_name:>30} | {migration.applied_at:%d %b. %Y %H:%M:%S} | "
            f"{migration.migration_details} "
        )
    print("---")
