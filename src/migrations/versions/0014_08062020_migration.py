""" 
Created_at: 08 Jun. 2020 19:54:51
Target: PODCASTS: logo_path -> image_url

"""

from playhouse.migrate import *
from migrations.models import database

previous = "0013_23052020_migration"

# see details http://docs.peewee-orm.com/en/latest/peewee/playhouse.html#schema-migrations


def upgrade():
    migrator = PostgresqlMigrator(database)    
    migrate(
        migrator.add_column("podcast_podcasts", "image_url", CharField(max_length=512, null=True)),
        migrator.drop_column("podcast_podcasts", "logo_path")
    )


def downgrade():
    migrator = PostgresqlMigrator(database)    
    migrate(
        migrator.add_column("podcast_podcasts", "logo_path", CharField(max_length=256, null=True)),
        migrator.drop_column("podcast_podcasts", "image_url")
    )
