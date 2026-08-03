"""
Fixture partagée : connexion en lecture seule au warehouse DuckDB.
Nécessite d'avoir lancé pipeline/run_pipeline.py au moins une fois avant
de lancer les tests.
"""

from pathlib import Path

import duckdb
import pytest

WAREHOUSE = Path(__file__).resolve().parents[1] / "data" / "warehouse" / "pbb.duckdb"


@pytest.fixture(scope="session")
def con():
    if not WAREHOUSE.exists():
        pytest.skip(f"{WAREHOUSE} introuvable -- lance d'abord pipeline/run_pipeline.py")
    connection = duckdb.connect(str(WAREHOUSE), read_only=True)
    yield connection
    connection.close()
