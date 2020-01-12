""" 
Created_at: 12 Oct. 2019 11:12:34
Target: Episodes: drop episodes.downloaded

"""

from playhouse.migrate import *
from migrations.models import database

previous = "0006_12102019_migration"


def upgrade():
    migrator = PostgresqlMigrator(database)
    migrate(migrator.drop_column("episodes", "downloaded"))


def downgrade():
    migrator = PostgresqlMigrator(database)
    migrate(migrator.add_column("episodes", "downloaded", BooleanField(default=False)))
