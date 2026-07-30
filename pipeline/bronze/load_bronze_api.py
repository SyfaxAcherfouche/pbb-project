"""
Couche BRONZE : chargement des fichiers plan_api/ (filet de sécurité pour
les APIs externes, cf. README fourni par le club — utilisé quand l'API en
direct est indisponible ou pour éviter la dépendance réseau le jour J).

Sources chargées :
    - open_meteo/paris_horaire_*.json      -> bronze.raw_meteo_horaire
    - calendrier_scolaire/zone_c_*.json    -> bronze.raw_vacances_scolaires
    - population/communes_idf_*.json       -> bronze.raw_population_communes
    - population/arrondissements_paris_*.json -> bronze.raw_population_arrondissements
    - euroleague/streaks_r*.json           -> bronze.raw_euroleague_streaks
        (structure imbriquée : un fichier = un classement à une journée donnée,
        avec une liste d'équipes ; on garde le round dans le nom de fichier)

Usage :
    python pipeline/bronze/load_bronze_api.py
    (nécessite d'avoir lancé pipeline/bronze/load_bronze.py avant, ou peut
    être lancé seul si tu veux juste tester cette partie)
"""

import json
import logging
import re
from pathlib import Path

import duckdb

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
PLAN_API = ROOT / "data" / "raw" / "plan_api"
WAREHOUSE = ROOT / "data" / "warehouse" / "pbb.duckdb"


def get_connection() -> duckdb.DuckDBPyConnection:
    WAREHOUSE.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(WAREHOUSE))
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
    return con


def load_meteo(con: duckdb.DuckDBPyConnection):
    """
    Open-Meteo renvoie un objet avec une clé 'hourly' contenant des listes
    parallèles (une valeur par heure). DuckDB peut lire ça directement via
    read_json_auto en dépliant les colonnes.
    """
    files = list((PLAN_API / "open_meteo").glob("*.json"))
    if not files:
        logger.warning("Aucun fichier météo trouvé dans plan_api/open_meteo/")
        return
    path = files[0]  # un seul fichier attendu
    con.execute(f"""
        CREATE OR REPLACE TABLE bronze.raw_meteo_horaire AS
        SELECT UNNEST(hourly.time) AS heure,
                UNNEST(hourly.temperature_2m) AS temperature,
                UNNEST(hourly.apparent_temperature) AS temperature_ressentie,
                UNNEST(hourly.precipitation) AS precipitation,
                UNNEST(hourly.weather_code) AS code_meteo
        FROM read_json_auto('{path}')
    """)
    n = con.execute("SELECT COUNT(*) FROM bronze.raw_meteo_horaire").fetchone()[0]
    logger.info("bronze.raw_meteo_horaire : %d lignes", n)


def load_vacances(con: duckdb.DuckDBPyConnection):
    """Format simple : {"results": [{...}, {...}]} -> on déplie 'results'."""
    files = list((PLAN_API / "calendrier_scolaire").glob("*.json"))
    if not files:
        logger.warning("Aucun fichier vacances trouvé dans plan_api/calendrier_scolaire/")
        return
    pattern = str(PLAN_API / "calendrier_scolaire" / "*.json")
    con.execute(f"""
        CREATE OR REPLACE TABLE bronze.raw_vacances_scolaires AS
        SELECT UNNEST(results) AS periode
        FROM read_json_auto('{pattern}', union_by_name=True)
    """)
    # on aplatit le struct 'periode' en colonnes directes pour usage facile
    con.execute("""
        CREATE OR REPLACE TABLE bronze.raw_vacances_scolaires AS
        SELECT periode.* FROM bronze.raw_vacances_scolaires
    """)
    n = con.execute("SELECT COUNT(*) FROM bronze.raw_vacances_scolaires").fetchone()[0]
    logger.info("bronze.raw_vacances_scolaires : %d lignes", n)


def load_population(con: duckdb.DuckDBPyConnection):
    """Deux fichiers distincts : communes IDF et arrondissements Paris."""
    communes_path = PLAN_API / "population" / "communes_idf_population.json"
    if communes_path.exists():
        con.execute(f"""
            CREATE OR REPLACE TABLE bronze.raw_population_communes AS
            SELECT * FROM read_json_auto('{communes_path}')
        """)
        n = con.execute("SELECT COUNT(*) FROM bronze.raw_population_communes").fetchone()[0]
        logger.info("bronze.raw_population_communes : %d lignes", n)
    else:
        logger.warning("communes_idf_population.json absent")

    arr_path = PLAN_API / "population" / "arrondissements_paris_population.json"
    if arr_path.exists():
        con.execute(f"""
            CREATE OR REPLACE TABLE bronze.raw_population_arrondissements AS
            SELECT * FROM read_json_auto('{arr_path}')
        """)
        n = con.execute("SELECT COUNT(*) FROM bronze.raw_population_arrondissements").fetchone()[0]
        logger.info("bronze.raw_population_arrondissements : %d lignes", n)
    else:
        logger.warning("arrondissements_paris_population.json absent")


def load_euroleague_streaks(con: duckdb.DuckDBPyConnection):
    """
    Un fichier streaks_rNN.json par journée, structure imbriquée
    {"winner": {...}, "teams": [{...}, ...]}. On extrait le numéro de
    journée depuis le nom de fichier et on déplie 'teams'.
    """
    files = sorted((PLAN_API / "euroleague").glob("streaks_r*.json"))
    if not files:
        logger.warning("Aucun fichier streaks trouvé dans plan_api/euroleague/")
        return

    con.execute("CREATE OR REPLACE TABLE bronze.raw_euroleague_streaks AS SELECT 1 WHERE FALSE")
    con.execute("DROP TABLE bronze.raw_euroleague_streaks")

    frames = []
    for path in files:
        match = re.search(r"streaks_r(\d+)\.json", path.name)
        round_number = int(match.group(1)) if match else None
        con.execute(f"""
            CREATE OR REPLACE TABLE bronze._tmp_streaks AS
            SELECT {round_number} AS round, UNNEST(teams) AS team
            FROM read_json_auto('{path}')
        """)
        con.execute("""
            CREATE OR REPLACE TABLE bronze._tmp_streaks AS
            SELECT round, team.* FROM bronze._tmp_streaks
        """)
        if "bronze.raw_euroleague_streaks" not in [
            f"{s}.{t}" for s, t in con.execute("SELECT schema_name, table_name FROM duckdb_tables()").fetchall()
        ]:
            con.execute("CREATE TABLE bronze.raw_euroleague_streaks AS SELECT * FROM bronze._tmp_streaks")
        else:
            con.execute("INSERT INTO bronze.raw_euroleague_streaks SELECT * FROM bronze._tmp_streaks")
    con.execute("DROP TABLE IF EXISTS bronze._tmp_streaks")

    n = con.execute("SELECT COUNT(*) FROM bronze.raw_euroleague_streaks").fetchone()[0]
    n_rounds = con.execute("SELECT COUNT(DISTINCT round) FROM bronze.raw_euroleague_streaks").fetchone()[0]
    logger.info("bronze.raw_euroleague_streaks : %d lignes sur %d journée(s)", n, n_rounds)


def main():
    con = get_connection()
    logger.info("Warehouse : %s", WAREHOUSE)

    load_meteo(con)
    load_vacances(con)
    load_population(con)
    load_euroleague_streaks(con)

    tables = con.execute("SHOW TABLES FROM bronze").fetchall()
    logger.info("Tables bronze (total) : %d", len(tables))
    con.close()


if __name__ == "__main__":
    main()
