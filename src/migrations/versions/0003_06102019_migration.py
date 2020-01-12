""" 
Created_at: 06 Oct. 2019 10:20:50
Target: Episodes: set nullable `episodes.published_at`

"""

from playhouse.migrate import *
from migrations.models import database

previous = "0002_23052019_migration"


def upgrade():
    migrator = PostgresqlMigrator(database)
    migrate(migrator.drop_not_null("episodes", "published_at"))


def downgrade():
    migrator = PostgresqlMigrator(database)
    migrate(migrator.add_not_null("episodes", "published_at"))
