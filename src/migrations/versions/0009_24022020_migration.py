""" 
Created_at: 24 Feb. 2020 18:55:38
Target: Episodes: add column episodes.remote_url

"""

from playhouse.migrate import *
from migrations.models import database

previous = "0008_13102019_migration"

# see details http://docs.peewee-orm.com/en/latest/peewee/playhouse.html#schema-migrations

def upgrade():
    migrator = PostgresqlMigrator(database)
    migrate(
        migrator.add_column('episodes', 'remote_url', CharField(null=True, max_length=128)),
    )


def downgrade():
    migrator = PostgresqlMigrator(database)    
    migrate(
        migrator.drop_column('episodes', 'remote_url'),
    )

