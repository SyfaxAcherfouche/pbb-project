"""
Couche BRONZE : chargement des fichiers billetterie (sftp/orders/).

Structure des fichiers, confirmée sur échantillon :
  {"orders": [...], "included": {20 tables de nomenclature}}
  orders[].products[].tickets[]  (3 niveaux, cf. PDF du sujet)

On déplie jusqu'au niveau ticket (un ticket = un billet = un siège), et on
charge séparément les tables de nomenclature utiles (sessions, product_types,
order_status) depuis 'included' — stables d'un fichier à l'autre (mêmes 41
sessions vues dans plusieurs fichiers testés), donc on ne les charge qu'une
fois, depuis le premier fichier du dossier.

Usage :
    python pipeline/bronze/load_bronze_billetterie.py
"""

import logging
from pathlib import Path

import duckdb

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
RAW_ORDERS = ROOT / "data" / "raw" / "sftp" / "orders"
WAREHOUSE = ROOT / "data" / "warehouse" / "pbb.duckdb"


def get_connection() -> duckdb.DuckDBPyConnection:
    WAREHOUSE.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(WAREHOUSE))
    con.execute("CREATE SCHEMA IF NOT EXISTS bronze")
    return con


def load_tickets(con: duckdb.DuckDBPyConnection):
    """
    Déplie orders -> products -> tickets. Une ligne = un billet vendu
    (ou annulé/remboursé/en attente, cf. order_status_id à filtrer en silver).

    Traite les fichiers UN PAR UN plutôt qu'en un seul glob : sur 358 dépôts
    quotidiens automatiques, certains fichiers peuvent être tronqués/corrompus
    (cas rencontré en pratique : JSON malformé, coupure probable pendant le
    transfert SFTP). Un pipeline qui plante sur le premier fichier récalcitrant
    n'est pas exploitable — on isole et on logue les fichiers en échec, on
    continue avec les fichiers valides, et on rend visible le taux d'échec.
    """
    files = sorted(RAW_ORDERS.glob("ORDERS_*.json"))
    if not files:
        logger.warning("Aucun fichier ORDERS_*.json trouvé dans %s", RAW_ORDERS)
        return

    con.execute("DROP TABLE IF EXISTS bronze.raw_billets")
    ok_files = []
    failed_files = []

    for path in files:
        try:
            con.execute(f"""
                CREATE OR REPLACE TABLE bronze._tmp_billets AS
                WITH deplie_orders AS (
                    SELECT '{path.name}' AS filename, UNNEST(orders) AS o
                    FROM read_json_auto('{path}')
                ),
                deplie_products AS (
                    SELECT
                        filename,
                        o.order_id AS order_id,
                        o.event_id AS event_id,
                        o.order_status_id AS order_status_id,
                        o.channel_id AS channel_id,
                        o.customer.external_id AS ext_id,
                        o.creation_date AS order_creation_date,
                        o.validation_date AS order_validation_date,
                        o.is_secondary_market AS is_secondary_market,
                        UNNEST(o.products) AS p
                    FROM deplie_orders
                )
                SELECT
                    filename,
                    order_id,
                    event_id,
                    order_status_id,
                    channel_id,
                    ext_id,
                    order_creation_date,
                    order_validation_date,
                    is_secondary_market,
                    p.order_product_id AS order_product_id,
                    p.product_type_id AS product_type_id,
                    p.is_cancelled AS product_is_cancelled,
                    p.amount_inc_tax AS product_amount_inc_tax,
                    t.ticket_id AS ticket_id,
                    t.bar_code AS bar_code,
                    t.category_id AS category_id,
                    t.session_id AS session_id,
                    t.amount AS amount,
                    t.ticket_status_id AS ticket_status_id,
                    t.seats.gate AS seat_gate,
                    t.seats.stand AS seat_stand,
                    t.seats.row AS seat_row,
                    t.seats.number AS seat_number
                FROM (
                    SELECT *, UNNEST(p.tickets) AS t
                    FROM deplie_products
                )
            """)
            if "raw_billets" not in [
                t for (t,) in con.execute(
                    "SELECT table_name FROM duckdb_tables() WHERE schema_name='bronze'"
                ).fetchall()
            ]:
                con.execute("CREATE TABLE bronze.raw_billets AS SELECT * FROM bronze._tmp_billets")
            else:
                con.execute("INSERT INTO bronze.raw_billets SELECT * FROM bronze._tmp_billets")
            ok_files.append(path.name)
        except duckdb.Error as e:
            logger.warning("Fichier ignoré (JSON invalide) : %s -> %s", path.name, e)
            failed_files.append(path.name)

    con.execute("DROP TABLE IF EXISTS bronze._tmp_billets")

    if not ok_files:
        logger.error("Aucun fichier n'a pu être chargé.")
        return

    n = con.execute("SELECT COUNT(*) FROM bronze.raw_billets").fetchone()[0]
    n_distinct_barcode = con.execute("SELECT COUNT(DISTINCT bar_code) FROM bronze.raw_billets").fetchone()[0]
    logger.info(
        "bronze.raw_billets : %d tickets sur %d fichier(s) OK (%d fichier(s) en échec sur %d total)",
        n, len(ok_files), len(failed_files), len(files),
    )
    if failed_files:
        logger.warning("Fichiers en échec (à examiner) : %s", failed_files)
    if n != n_distinct_barcode:
        logger.warning(
            "ATTENTION : %d bar_code apparaissent plusieurs fois (%d lignes vs %d bar_code distincts). "
            "À dédupliquer en couche silver si confirmé (garder la ligne la plus récente).",
            n - n_distinct_barcode, n, n_distinct_barcode,
        )


def load_nomenclatures(con: duckdb.DuckDBPyConnection):
    """
    Tables de nomenclature (sessions, product_types, order_status) : lues
    depuis UN SEUL fichier (le premier trouvé), car identiques d'un fichier
    à l'autre à l'inspection (41 sessions vues dans plusieurs fichiers testés).
    À revérifier si le nombre de fichiers change beaucoup (ex: nouvelles
    sessions ajoutées en cours de saison).
    """
    files = sorted(RAW_ORDERS.glob("ORDERS_*.json"))
    if not files:
        return
    ref_file = files[0]

    con.execute(f"""
        CREATE OR REPLACE TABLE bronze.raw_billetterie_sessions AS
        SELECT UNNEST(included.sessions) AS s
        FROM read_json_auto('{ref_file}')
    """)
    con.execute("""
        CREATE OR REPLACE TABLE bronze.raw_billetterie_sessions AS
        SELECT s.* FROM bronze.raw_billetterie_sessions
    """)

    con.execute(f"""
        CREATE OR REPLACE TABLE bronze.raw_billetterie_product_types AS
        SELECT UNNEST(included.product_types) AS pt
        FROM read_json_auto('{ref_file}')
    """)
    con.execute("""
        CREATE OR REPLACE TABLE bronze.raw_billetterie_product_types AS
        SELECT pt.* FROM bronze.raw_billetterie_product_types
    """)

    con.execute(f"""
        CREATE OR REPLACE TABLE bronze.raw_billetterie_order_status AS
        SELECT UNNEST(included.order_status) AS os
        FROM read_json_auto('{ref_file}')
    """)
    con.execute("""
        CREATE OR REPLACE TABLE bronze.raw_billetterie_order_status AS
        SELECT os.* FROM bronze.raw_billetterie_order_status
    """)

    n_sessions = con.execute("SELECT COUNT(*) FROM bronze.raw_billetterie_sessions").fetchone()[0]
    logger.info(
        "Nomenclatures billetterie chargées depuis %s : %d sessions",
        ref_file.name, n_sessions,
    )


def main():
    con = get_connection()
    logger.info("Warehouse : %s", WAREHOUSE)

    load_tickets(con)
    load_nomenclatures(con)

    tables = con.execute(
        "SELECT table_name FROM duckdb_tables() WHERE schema_name = 'bronze' AND table_name LIKE '%billet%'"
    ).fetchall()
    logger.info("Tables billetterie créées : %s", [t[0] for t in tables])
    con.close()


if __name__ == "__main__":
    main()
