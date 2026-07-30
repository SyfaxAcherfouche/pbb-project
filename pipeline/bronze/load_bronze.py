"""
Couche BRONZE : chargement brut des sources, sans transformation.

Principe de l'architecture médaillon :
    bronze = copie fidèle de la source (mêmes valeurs, mêmes formats bruts)
    silver = nettoyée, typée, dédupliquée (étape suivante, pas encore écrite)
    gold   = agrégée, prête pour l'analyse et le dashboard (à venir)

Objectif de cette étape : ne JAMAIS transformer la donnée ici. Si un fichier
source change de format demain, seule cette couche doit être rejouée, les
couches silver/gold restent intactes et inspectables.

Usage :
    python pipeline/bronze/load_bronze.py
"""

import logging
from pathlib import Path

import duckdb

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
RAW_DATASET = ROOT / "data" / "raw" / "dataset"
RAW_SCANS = ROOT / "data" / "raw" / "sftp" / "scans"
WAREHOUSE = ROOT / "data" / "warehouse" / "pbb.duckdb"


def get_connection() -> duckdb.DuckDBPyConnection:
    WAREHOUSE.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(WAREHOUSE))
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
    return con


def load_simple_csvs(con: duckdb.DuckDBPyConnection):
    """
    Sources CSV standards (encodage UTF-8, virgule comme séparateur) :
    chargement direct en bronze.raw_<nom>, sans transformation.

    Si un fichiers ne s'appelle pas exactement comme dans ce
    dictionnaire, faut ajuster le nom ici.
    """
    simple_files = {
        "resultats_matchs": "resultats_matchs.csv",
        "satisfaction": "satisfaction.csv",
        "calendrier_matchs": "calendrier_matchs.csv",
        "campagnes": "campagnes.csv",
        "effectif": "effectif.csv",
        "animations_participations": "animations_participations.csv",
        "fb_transactions": "fb_transactions.csv",
        "web_sessions": "web_sessions.csv",
        "web_evenements": "web_evenements.csv",
        "campagnes_evenements": "campagnes_evenements.csv",
    }
    for name, filename in simple_files.items():
        path = RAW_DATASET / filename
        table = f"bronze.raw_{name}"
        if not path.exists():
            logger.warning("Fichier absent, ignoré : %s", filename)
            continue
        con.execute(f"""
            CREATE OR REPLACE TABLE {table} AS
            SELECT * FROM read_csv_auto('{path}', header=True, sample_size=-1)
        """)
        n = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        logger.info("%s : %d lignes chargées", table, n)


def load_scans(con: duckdb.DuckDBPyConnection):
    """
    Un fichier scan_AAAAMMJJ.csv par match. On charge tous les fichiers du
    dossier en une seule table, avec le nom de fichier source en colonne
    pour traçabilité.
    """
    pattern = str(RAW_SCANS / "scan_*.csv")
    con.execute(f"""
        CREATE OR REPLACE TABLE bronze.raw_scans AS
        SELECT *, regexp_extract(filename, 'scan_(\\d{{8}})', 1) AS date_fichier
        FROM read_csv_auto('{pattern}', header=True, filename=True, union_by_name=True)
    """)
    n = con.execute("SELECT COUNT(*) FROM bronze.raw_scans").fetchone()[0]
    n_files = con.execute("SELECT COUNT(DISTINCT filename) FROM bronze.raw_scans").fetchone()[0]
    logger.info("bronze.raw_scans : %d lignes sur %d fichier(s)", n, n_files)


def load_contacts(con: duckdb.DuckDBPyConnection):
    """
    contacts.csv : chargé en texte brut (all_varchar=True). On ne type pas
    encore les dates ici car la source mélange plusieurs formats de date
    de naissance — ce nettoyage sera fait en couche silver, pas ici.
    """
    path = RAW_DATASET / "contacts.csv"
    if not path.exists():
        logger.warning("contacts.csv absent, ignoré")
        return
    con.execute(f"""
        CREATE OR REPLACE TABLE bronze.raw_contacts AS
        SELECT * FROM read_csv_auto('{path}', header=True, all_varchar=True)
    """)
    n = con.execute("SELECT COUNT(*) FROM bronze.raw_contacts").fetchone()[0]
    logger.info("bronze.raw_contacts : %d lignes chargées (texte brut)", n)


def load_boutique(con: duckdb.DuckDBPyConnection):
    """
    boutique_ventes_avoirs.csv : délimiteur ';' (pas ','), décimales au
    format français ('39,00' et non '39.00'). Chargé en texte brut, le
    nettoyage des 3 formats de date coexistants sera fait en silver.
    """
    path = RAW_DATASET / "boutique_ventes_avoirs.csv"
    if not path.exists():
        logger.warning("boutique_ventes_avoirs.csv absent, ignoré")
        return
    con.execute(f"""
        CREATE OR REPLACE TABLE bronze.raw_boutique AS
        SELECT * FROM read_csv_auto(
            '{path}', header=True, delim=';', all_varchar=True, decimal_separator=','
        )
    """)
    n = con.execute("SELECT COUNT(*) FROM bronze.raw_boutique").fetchone()[0]
    logger.info("bronze.raw_boutique : %d lignes chargées (texte brut)", n)


def main():
    con = get_connection()
    logger.info("Warehouse : %s", WAREHOUSE)

    load_simple_csvs(con)
    load_scans(con)
    load_contacts(con)
    load_boutique(con)

    tables = con.execute("SHOW TABLES FROM bronze").fetchall()
    logger.info("Tables bronze créées : %d", len(tables))
    con.close()


if __name__ == "__main__":
    main()
