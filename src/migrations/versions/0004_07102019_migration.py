""" 
Created_at: 07 Oct. 2019 07:58:21
Target: Episodes: remove uniq for source_id

"""
from playhouse.migrate import *
from migrations.models import database

previous = "0003_06102019_migration"


def upgrade():
    migrator = PostgresqlMigrator(database)
    migrate(
        migrator.add_index(
            "episodes", ["source_id", "podcast_id"], unique=True
        )  # add new index
    )
    try:
        migrate(migrator.drop_index("episodes", "publication_source_id"),)
    except Exception as err:
        print(f"Couldn't delete index 'publication_source_id': {err}")


def downgrade():
    migrator = PostgresqlMigrator(database)
    try:
        migrate(migrator.drop_index("episodes", "episodes_source_id_podcast_id"),)
    except Exception as err:
        print(f"Couldn't delete index 'episodes_source_id_podcast_id': {err}")
