"""
Couche GOLD : construction de fact_match, une ligne par match à domicile.

Table centrale pour répondre à la question métier : quels matchs
sous-performent en remplissage, et quels leviers pourraient corriger ça ?

Sources et clés de jointure (cf. ERD) :
  - silver.calendrier_matchs (41 matchs domicile) : base de la table
  - silver.resultats_matchs, filtré sur lieu='DOMICILE', joint par date :
    donne le classement AVANT le match (rang_pbb_avant, rang_adversaire_avant)
    -- attention, ne jamais utiliser un classement "après" ou final ici,
    ce serait du feature leakage (donnée non connue au moment du match)
  - silver.sessions, joint par date(start_at) = date : fait le pont vers
    la billetterie (session_id)
  - silver.billets, filtré sur session_id, agrégé : billets vendus, revenu
  - silver.scans, joint par date_fichier = date (format YYYYMMDD) : entrées
    réelles scannées avec succès (resultat = 'OK')
  - bronze.raw_meteo_horaire, joint sur l'heure de coup d'envoi
  - bronze.raw_vacances_scolaires, jointure par plage de dates

Usage :
    python pipeline/gold/build_gold.py
    (nécessite d'avoir lancé bronze puis silver avant)
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
        raise FileNotFoundError(f"{WAREHOUSE} introuvable. Lance d'abord bronze puis silver.")
    con = duckdb.connect(str(WAREHOUSE))
    con.execute("CREATE SCHEMA IF NOT EXISTS gold")
    return con


def build_fact_match(con: duckdb.DuckDBPyConnection):
    con.execute("""
        CREATE OR REPLACE TABLE gold.fact_match AS
        WITH billets_agg AS (
            SELECT
                s.id AS session_id,
                CAST(s.start_at AS DATE) AS date_match,
                COUNT(*) AS billets_vendus,
                SUM(b.amount) AS revenu_billetterie,
                AVG(b.amount) AS prix_moyen_billet,
                SUM(CASE WHEN pt.code = 'ABONNEMENT' THEN 1 ELSE 0 END) AS billets_abonnement,
                SUM(CASE WHEN pt.code = 'BILLET_UNITE' THEN 1 ELSE 0 END) AS billets_unite
            FROM silver.billets b
            JOIN silver.sessions s ON b.session_id = s.id
            LEFT JOIN silver.product_types pt ON b.product_type_id = pt.id
            GROUP BY s.id, CAST(s.start_at AS DATE)
        ),
        annulations_agg AS (
            -- Basé sur bronze.raw_billets (TOUS les statuts, pas juste les
            -- billets valides) pour mesurer le volume de commandes qui
            -- n'aboutissent pas : annulées, remboursées, en attente.
            -- order_status_id : 1=Validée, 4=En attente, 8=Annulée, 9=Remboursée
            SELECT
                s.id AS session_id,
                CAST(s.start_at AS DATE) AS date_match,
                COUNT(*) AS billets_total_bronze,
                COUNT(*) FILTER (WHERE b.order_status_id = 8) AS billets_annules,
                COUNT(*) FILTER (WHERE b.order_status_id = 9) AS billets_rembourses,
                COUNT(*) FILTER (WHERE b.order_status_id = 4) AS billets_en_attente
            FROM bronze.raw_billets b
            JOIN silver.sessions s ON b.session_id = s.id
            GROUP BY s.id, CAST(s.start_at AS DATE)
        ),
        scans_agg AS (
            SELECT
                date_fichier,
                COUNT(*) FILTER (WHERE resultat = 'OK') AS entrees_ok,
                COUNT(*) AS scans_total
            FROM silver.scans
            GROUP BY date_fichier
        ),
        resultats_domicile AS (
            SELECT date, score_domicile, score_exterieur,
                   rang_pbb_avant, rang_adversaire_avant,
                   bilan_pbb, bilan_adversaire
            FROM silver.resultats_matchs
            WHERE lieu = 'DOMICILE'
        ),
        meteo_par_heure AS (
            SELECT CAST(heure AS TIMESTAMP) AS heure_ts, temperature, precipitation, code_meteo
            FROM bronze.raw_meteo_horaire
        )
        SELECT
            c.match_id,
            c.date,
            c.heure,
            c.competition,
            c.journee,
            c.adversaire,
            c.salle,
            c.capacite_salle,

            -- billetterie
            ba.billets_vendus,
            ROUND(ba.billets_vendus::DOUBLE / NULLIF(c.capacite_salle, 0), 3) AS taux_remplissage,
            ba.revenu_billetterie,
            ROUND(ba.prix_moyen_billet, 2) AS prix_moyen_billet,
            ba.billets_abonnement,
            ba.billets_unite,
            ROUND(ba.billets_unite::DOUBLE / NULLIF(ba.billets_vendus, 0), 3) AS part_billets_unite,

            -- annulations / no-show (basé sur TOUS les statuts en bronze)
            aa.billets_annules,
            aa.billets_rembourses,
            aa.billets_en_attente,
            ROUND(aa.billets_annules::DOUBLE / NULLIF(aa.billets_total_bronze, 0), 3) AS taux_annulation,

            -- présence réelle (scans)
            sa.entrees_ok,
            ROUND(sa.entrees_ok::DOUBLE / NULLIF(ba.billets_vendus, 0), 3) AS taux_presence,

            -- contexte sportif (classement AVANT le match, pas de leakage)
            rd.rang_pbb_avant,
            rd.rang_adversaire_avant,
            rd.rang_adversaire_avant - rd.rang_pbb_avant AS ecart_classement,
            rd.score_domicile,
            rd.score_exterieur,
            CASE WHEN rd.score_domicile > rd.score_exterieur THEN 1 ELSE 0 END AS victoire_pbb,

            -- contexte temporel
            dayname(c.date) AS jour_semaine,
            EXISTS (
                SELECT 1 FROM bronze.raw_vacances_scolaires v
                WHERE c.date BETWEEN CAST(v.start_date AS DATE) AND CAST(v.end_date AS DATE)
                  AND v.location = 'Paris'
            ) AS vacances_scolaires,

            -- météo à l'heure du match (jointure la plus proche)
            (SELECT temperature FROM meteo_par_heure m
             WHERE m.heure_ts = date_trunc('hour', c.date + c.heure)
             LIMIT 1) AS temperature,
            (SELECT precipitation FROM meteo_par_heure m
             WHERE m.heure_ts = date_trunc('hour', c.date + c.heure)
             LIMIT 1) AS precipitation

        FROM silver.calendrier_matchs c
        LEFT JOIN billets_agg ba ON CAST(ba.date_match AS DATE) = c.date
        LEFT JOIN annulations_agg aa ON CAST(aa.date_match AS DATE) = c.date
        LEFT JOIN scans_agg sa ON sa.date_fichier = strftime(c.date, '%Y%m%d')
        LEFT JOIN resultats_domicile rd ON rd.date = c.date
        ORDER BY c.date
    """)

    n = con.execute("SELECT COUNT(*) FROM gold.fact_match").fetchone()[0]
    n_no_billets = con.execute(
        "SELECT COUNT(*) FROM gold.fact_match WHERE billets_vendus IS NULL"
    ).fetchone()[0]
    n_no_scans = con.execute(
        "SELECT COUNT(*) FROM gold.fact_match WHERE entrees_ok IS NULL"
    ).fetchone()[0]
    n_no_resultats = con.execute(
        "SELECT COUNT(*) FROM gold.fact_match WHERE rang_pbb_avant IS NULL"
    ).fetchone()[0]
    logger.info("gold.fact_match : %d matchs", n)
    logger.info(
        "Complétude : %d sans billets vendus, %d sans scans, %d sans classement avant-match",
        n_no_billets, n_no_scans, n_no_resultats,
    )

    # Un taux de présence > 1 est impossible (on ne peut pas scanner plus de
    # billets qu'il n'y en a de vendus) : signe que billetterie et scans ne
    # couvrent pas la même période (fichiers manquants d'un côté ou de l'autre).
    anomalies = con.execute(
        "SELECT match_id, date, billets_vendus, entrees_ok, taux_presence "
        "FROM gold.fact_match WHERE taux_presence > 1.05"
    ).fetchall()
    if anomalies:
        logger.warning(
            "ATTENTION : %d match(s) avec taux_presence > 1 (impossible en théorie). "
            "Signe probable que billets_vendus est sous-estimé pour ces matchs -- "
            "vérifier que tous les fichiers ORDERS_*.json couvrant la période de vente "
            "de ces matchs sont bien dans data/raw/sftp/orders/. Matchs concernés : %s",
            len(anomalies), [(a[0], str(a[1])) for a in anomalies],
        )


def main():
    con = get_connection()
    build_fact_match(con)
    con.close()


if __name__ == "__main__":
    main()
