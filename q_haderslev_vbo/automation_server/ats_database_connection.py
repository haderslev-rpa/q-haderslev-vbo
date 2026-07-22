"""
Opretter forbindelse til Automation Servers PostgreSQL-database.
"""

import psycopg2
from psycopg2.extensions import connection

from q_haderslev_vbo.automation_server.ats_credentials_database import (
    get_database_settings,
)


def get_connection() -> connection:
    """
    Opretter og returnerer en forbindelse til PostgreSQL.

    Databaseindstillingerne hentes fra Automation Server credentials.
    """

    settings = get_database_settings()

    return psycopg2.connect(
        host=settings["host"],
        port=settings["port"],
        database=settings["database"],
        user=settings["user"],
        password=settings["password"],
        connect_timeout=10,
    )