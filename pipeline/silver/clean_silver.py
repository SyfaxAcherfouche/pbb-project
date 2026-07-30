"""
Couche SILVER : nettoyage, typage, correction des incohérences détectées en
bronze.

Problèmes de qualité connus et corrigés ici :
  - contacts.date_naissance : mélange YYYY-MM-DD et DD/MM/YYYY
  - boutique.VENTE_date : mélange TROIS formats (YYYY-MM-DD, DD/MM/YYYY,
    DD-MM-YYYY)
  - boutique : décimales format FR (virgule), ventes ANNULEE à isoler,
    doublons exacts de ligne_id (artefact d'export caisse)

Les autres tables bronze (déjà propres à l'inspection : un seul format de
date, pas de doublons connus) sont recopiées telles quelles vers silver,
pour garder un accès uniforme depuis le schéma silver.

Usage :
    python pipeline/silver/clean_silver.py
    (nécessite d'avoir lancé les scripts bronze avant)
"""

import logging
from pathlib import Path

import duckdb

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
WAREHOUSE = ROOT / "data" / "warehouse" / "pbb.duckdb"


def get_connection() -> duckdb.DuckDBPyConnection:
    if not WAREHOUSE.exists():
        raise FileNotFoundError(
            f"{WAREHOUSE} introuvable. Lance d'abord pipeline/bronze/load_bronze.py"
        )
    con = duckdb.connect(str(WAREHOUSE))
    con.execute("CREATE SCHEMA IF NOT EXISTS silver")
    return con


def clean_contacts(con: duckdb.DuckDBPyConnection):
    con.execute("""
        CREATE OR REPLACE TABLE silver.contacts AS
        SELECT
            ext_id,
            nom,
            prenom,
            genre,
            COALESCE(
                TRY_CAST(date_naissance AS DATE),
                TRY_STRPTIME(date_naissance, '%d/%m/%Y')::DATE
            ) AS date_naissance,
            telephone,
            code_postal,
            pays,
            segment,
            TRY_CAST(date_creation AS DATE) AS date_creation,
            TRY_CAST(optin_email AS BOOLEAN) AS optin_email,
            canal_acquisition,
            joueur_prefere
        FROM bronze.raw_contacts
    """)
    n = con.execute("SELECT COUNT(*) FROM silver.contacts").fetchone()[0]
    n_bad_date = con.execute("""
        SELECT COUNT(*) FROM silver.contacts c
        JOIN bronze.raw_contacts r USING (ext_id)
        WHERE c.date_naissance IS NULL AND r.date_naissance IS NOT NULL AND r.date_naissance != ''
    """).fetchone()[0]
    logger.info("silver.contacts : %d lignes. dates de naissance non parsables : %d", n, n_bad_date)


def clean_boutique(con: duckdb.DuckDBPyConnection):
    con.execute("""
        CREATE OR REPLACE TABLE silver.boutique_ventes AS
        SELECT
            "LIGNE_ligne" AS ligne_id,
            "LIGNE_vente" AS ticket_id,
            "LIGNE_CodeMag" AS magasin,
            "LIGNE_Famille" AS famille,
            "LIGNE_Rayon" AS rayon,
            "PRODUIT_ssfamille" AS sous_famille,
            "LIGNE_Designation" AS designation,
            "LIGNE_Couleur" AS couleur,
            "LIGNE_Taille" AS taille,
            TRY_CAST(REPLACE("LIGNE_PrixVente", ',', '.') AS DOUBLE) AS prix_vente,
            TRY_CAST("LIGNE_Quantite" AS INTEGER) AS quantite,
            TRY_CAST(REPLACE("LIGNE_Total", ',', '.') AS DOUBLE) AS total_ligne,
            "LIGNE_Motif" AS motif_avoir,
            "VENTE_vente" AS vente_id,
            -- 3 formats coexistent dans la source
            COALESCE(
                TRY_CAST("VENTE_date" AS DATE),
                TRY_STRPTIME("VENTE_date", '%d/%m/%Y')::DATE,
                TRY_STRPTIME("VENTE_date", '%d-%m-%Y')::DATE
            ) AS date_vente,
            "VENTE_codemag" AS vente_magasin,
            TRY_CAST(REPLACE("VENTE_total", ',', '.') AS DOUBLE) AS vente_total,
            "VENTE_nature" AS nature,
            "VENTe_client" AS ext_id,
            "CLIENT_Regroupement" AS segment_client,
            "VENTE_Etat" AS etat_vente
        FROM bronze.raw_boutique
        -- dédoublonnage des lignes strictement identiques (artefact d'export caisse)
        QUALIFY ROW_NUMBER() OVER (
            PARTITION BY ligne_id, ticket_id, "LIGNE_Designation", "VENTE_date", "VENTE_Etat"
            ORDER BY ligne_id
        ) = 1
    """)
    n = con.execute("SELECT COUNT(*) FROM silver.boutique_ventes").fetchone()[0]
    n_annulee = con.execute(
        "SELECT COUNT(*) FROM silver.boutique_ventes WHERE etat_vente = 'ANNULEE'"
    ).fetchone()[0]
    logger.info("silver.boutique_ventes : %d lignes (déduplication appliquée). ANNULEE : %d", n, n_annulee)


def pass_through_tables(con: duckdb.DuckDBPyConnection):
    """
    Sources déjà propres en bronze : simple recopie vers silver, sans
    transformation superflue, pour un accès uniforme depuis le schéma silver.
    Ajuste cette liste si une de tes tables bronze n'existe pas encore.
    """
    passthrough = [
        "resultats_matchs", "satisfaction", "calendrier_matchs", "campagnes",
        "effectif", "animations_participations", "fb_transactions",
        "web_sessions", "web_evenements", "campagnes_evenements", "scans",
    ]
    existing = {t for (t,) in con.execute("SHOW TABLES FROM bronze").fetchall()}
    for name in passthrough:
        bronze_table = f"raw_{name}"
        if bronze_table not in existing:
            logger.warning("bronze.%s absent, passthrough ignoré pour %s", bronze_table, name)
            continue
        con.execute(f"CREATE OR REPLACE TABLE silver.{name} AS SELECT * FROM bronze.{bronze_table}")
    logger.info("Tables passthrough bronze -> silver terminées")


def clean_billetterie(con: duckdb.DuckDBPyConnection):
    """
    Filtre les billets réellement vendus (order_status_id = 1, "Validée")
    et non annulés au niveau produit (product_is_cancelled = false).
    Les commandes en attente/annulées/remboursées sont exclues du décompte
    de billets vendus, mais on garde une table brute filtrée plutôt que
    d'agréger tout de suite -- l'agrégation par match se fera en gold.
    """
    existing = {t for (t,) in con.execute("SHOW TABLES FROM bronze").fetchall()}
    if "raw_billets" not in existing:
        logger.warning("bronze.raw_billets absent, silver billetterie ignoré")
        return

    con.execute("""
        CREATE OR REPLACE TABLE silver.billets AS
        SELECT
            bar_code,
            ext_id,
            session_id,
            order_id,
            ticket_id,
            product_type_id,
            category_id,
            amount,
            order_status_id,
            product_is_cancelled,
            ticket_status_id,
            order_creation_date,
            order_validation_date,
            seat_gate, seat_stand, seat_row, seat_number
        FROM bronze.raw_billets
        WHERE order_status_id = 1        -- "Validée"
          AND NOT product_is_cancelled   -- pas annulé au niveau produit
    """)
    n_total = con.execute("SELECT COUNT(*) FROM bronze.raw_billets").fetchone()[0]
    n_valid = con.execute("SELECT COUNT(*) FROM silver.billets").fetchone()[0]
    logger.info(
        "silver.billets : %d billets vendus retenus sur %d au total en bronze (%.1f%%)",
        n_valid, n_total, 100 * n_valid / n_total if n_total else 0,
    )

    con.execute("CREATE OR REPLACE TABLE silver.sessions AS SELECT * FROM bronze.raw_billetterie_sessions")
    con.execute("CREATE OR REPLACE TABLE silver.product_types AS SELECT * FROM bronze.raw_billetterie_product_types")
    n_sessions = con.execute("SELECT COUNT(*) FROM silver.sessions").fetchone()[0]
    logger.info("silver.sessions : %d sessions (matchs à domicile)", n_sessions)


def main():
    con = get_connection()
    clean_contacts(con)
    clean_boutique(con)
    clean_billetterie(con)
    pass_through_tables(con)

    tables = con.execute("SHOW TABLES FROM silver").fetchall()
    logger.info("Tables silver créées : %d", len(tables))
    con.close()


if __name__ == "__main__":
    main()
