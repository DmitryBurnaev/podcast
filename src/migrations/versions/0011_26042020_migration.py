""" 
Created_at: 26 Apr. 2020 16:44:54
Target: REFACTOR: rename tables

"""

from playhouse.migrate import PostgresqlMigrator, migrate
from common.models import database
from common.utils import database_init

previous = "0010_20042020_migration"


def upgrade():
    database_init(database)
    migrator = PostgresqlMigrator(database)
    try:
        migrate(migrator.rename_table("users", "auth_users"))
        migrate(migrator.rename_table("podcasts", "podcast_podcasts"))
        migrate(migrator.rename_table("episodes", "podcast_episodes"))
    except Exception as err:
        print(f"Couldn't rename table: {err}. SKIP")


def downgrade():
    database_init(database)
    migrator = PostgresqlMigrator(database)
    try:
        migrate(migrator.rename_table("auth_users", "users"))
        migrate(migrator.rename_table("podcast_podcasts", "podcasts"))
        migrate(migrator.rename_table("podcast_episodes", "episodes"))
    except Exception as err:
        print(f"Couldn't rename table: {err}. SKIP")
