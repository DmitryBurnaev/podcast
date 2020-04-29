""" 
Created_at: 23 May. 2019 19:59:20
Target: Publications: rename publications -> episodes

"""

from playhouse.migrate import *
from migrations.models import database

previous = "0001_07052019_migration"


def upgrade():
    migrator = PostgresqlMigrator(database)
    try:
        migrate(migrator.rename_table("publications", "episodes"))
    except Exception as err:
        print(f"Couldn't rename table publications -> episodes: {err}. SKIP")


def downgrade():
    migrator = PostgresqlMigrator(database)
    try:
        migrate(migrator.rename_table("publications", "episodes"))
    except Exception as err:
        print(f"Couldn't rename table episodes -> publications: {err}. SKIP")
