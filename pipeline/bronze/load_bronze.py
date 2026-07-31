"""
Couche BRONZE : chargement brut des sources, sans transformation.

Principe de l'architecture médaillon :
    bronze = copie fidèle de la source (mêmes valeurs, mêmes formats bruts)
    silver = nettoyée, typée, dédupliquée (voir pipeline/silver/clean_silver.py)
    gold   = agrégée, prête pour l'analyse et le dashboard (voir pipeline/gold/)

Objectif de cette étape : ne JAMAIS transformer la donnée ici. Si un fichier
source change de format demain, seule cette couche doit être rejouée — les
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
    """Sources CSV standards : chargement direct en bronze.raw_*."""
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
    Un fichier scan_AAAAMMJJ.csv par match. Traité fichier par fichier :
    au moins un fichier rencontré en pratique (scan_20251017.csv) n'a PAS
    de ligne d'en-tête -- la première ligne est déjà une donnée. Avec un
    chargement en glob classique, DuckDB prend alors cette ligne comme noms
    de colonnes : le schéma se décale silencieusement, une vraie ligne de
    scan est perdue, et 'resultat' finit NULL sur tout le fichier (bug
    découvert via taux_presence = 0 pour le match du 17/10/2025 en gold,
    alors que les scans existaient réellement).

    On détecte le cas en comparant la première ligne au nom de la première
    colonne attendue, et on force le bon schéma si l'en-tête est absent.
    """
    EXPECTED_COLUMNS = ["barcode", "scan_ts_utc", "portique", "ext_id", "type_billet", "resultat"]
    files = sorted(RAW_SCANS.glob("scan_*.csv"))
    if not files:
        logger.warning("Aucun fichier scan_*.csv trouvé dans %s", RAW_SCANS)
        return

    con.execute("DROP TABLE IF EXISTS bronze.raw_scans")
    files_no_header = []
    files_failed = []

    for path in files:
        try:
            with open(path, "r", encoding="utf-8") as f:
                first_line = f.readline().strip()
            if not first_line:
                raise ValueError("fichier vide")
            has_header = first_line.split(",")[0].strip() == EXPECTED_COLUMNS[0]
            date_fichier = path.stem.replace("scan_", "")

            if has_header:
                query = f"""
                    SELECT *, '{path.name}' AS filename, '{date_fichier}' AS date_fichier
                    FROM read_csv_auto('{path}', header=True)
                """
            else:
                files_no_header.append(path.name)
                query = f"""
                    SELECT *, '{path.name}' AS filename, '{date_fichier}' AS date_fichier
                    FROM read_csv_auto('{path}', header=False, names={EXPECTED_COLUMNS!r})
                """

            con.execute(f"CREATE OR REPLACE TABLE bronze._tmp_scans AS {query}")
            existing = {t for (t,) in con.execute("SHOW TABLES FROM bronze").fetchall()}
            if "raw_scans" not in existing:
                con.execute("CREATE TABLE bronze.raw_scans AS SELECT * FROM bronze._tmp_scans")
            else:
                con.execute("INSERT INTO bronze.raw_scans SELECT * FROM bronze._tmp_scans")
        except (duckdb.Error, ValueError, OSError) as e:
            logger.warning("Fichier scan ignoré (illisible/vide) : %s -> %s", path.name, e)
            files_failed.append(path.name)

    con.execute("DROP TABLE IF EXISTS bronze._tmp_scans")

    n = con.execute("SELECT COUNT(*) FROM bronze.raw_scans").fetchone()[0]
    n_files = con.execute("SELECT COUNT(DISTINCT filename) FROM bronze.raw_scans").fetchone()[0]
    logger.info(
        "bronze.raw_scans : %d lignes sur %d fichier(s) OK (%d en échec sur %d total)",
        n, n_files, len(files_failed), len(files),
    )
    if files_no_header:
        logger.warning(
            "Fichier(s) sans ligne d'en-tête détecté(s) et corrigé(s) automatiquement : %s",
            files_no_header,
        )
    if files_failed:
        logger.warning("Fichier(s) scan ignorés (vides/illisibles) : %s", files_failed)


def load_contacts(con: duckdb.DuckDBPyConnection):
    """contacts.csv chargé en texte brut (typage/nettoyage fait en silver)."""
    path = RAW_DATASET / "contacts.csv"
    con.execute(f"""
        CREATE OR REPLACE TABLE bronze.raw_contacts AS
        SELECT * FROM read_csv_auto('{path}', header=True, all_varchar=True)
    """)
    n = con.execute("SELECT COUNT(*) FROM bronze.raw_contacts").fetchone()[0]
    logger.info("bronze.raw_contacts : %d lignes chargées (texte brut)", n)


def load_boutique(con: duckdb.DuckDBPyConnection):
    """boutique_ventes_avoirs.csv chargé en texte brut (délimiteur ';', décimales FR)."""
    path = RAW_DATASET / "boutique_ventes_avoirs.csv"
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
