""" 
Created_at: 13 Oct. 2019 12:54:09
Target: Podcast: add download_automatically field

"""

from playhouse.migrate import *
from migrations.models import database

previous = "0007_12102019_migration"


def upgrade():
    migrator = PostgresqlMigrator(database)
    migrate(
        migrator.add_column(
            "podcasts", "download_automatically", BooleanField(null=False, default=True)
        ),
    )


def downgrade():
    migrator = PostgresqlMigrator(database)
    migrate(migrator.drop_column("podcasts", "download_automatically"),)
