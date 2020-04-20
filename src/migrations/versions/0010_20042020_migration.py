""" 
Created_at: 20 Apr. 2020 15:17:35
Target: Podcasts: add column podcasts.remote_url

"""

from playhouse.migrate import *
from migrations.models import database

previous = "0009_24022020_migration"


def upgrade():
    migrator = PostgresqlMigrator(database)    
    migrate(migrator.add_column('podcasts', 'rss_link', CharField(max_length=128, null=True)))


def downgrade():
    migrator = PostgresqlMigrator(database)    
    migrate(
        migrator.drop_column('podcasts', 'rss_link'),
    )

