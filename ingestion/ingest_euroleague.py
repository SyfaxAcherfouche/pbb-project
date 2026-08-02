"""
Ingestion des données EuroLeague / EuroCup.

Source : package `euroleague_api` (wrapper Python autour de l'API officielle,
non documentée publiquement). Choix justifié : réécrire un client HTTP pour
une API sans documentation officielle aurait consommé un temps disproportionné
sur 7 jours ; ce wrapper est maintenu, couvre calendrier/résultats/classements/
stats équipe, et produit directement des DataFrames pandas.

Ce script récupère, pour une saison donnée :
    - le calendrier / résultats (games)
    - les classements journée par journée (standings)
et les dépose en brut dans data/raw/euroleague/, au format Parquet.

Usage :
    python ingestion/ingest_euroleague.py --season 2025 --competition E

Notes :
    - competition_code : "E" = EuroLeague, "U" = EuroCup
    - le "classement au moment du match" (standing_diff) nécessite de croiser
    la date du match avec le classement de la journée correspondante :
    ATTENTION AU FEATURE LEAKAGE si on utilise le classement final au lieu
    du classement réel à la date du match (cf. NOTES.md).
"""

import argparse
import logging
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw" / "euroleague"


def fetch_games(competition_code: str, season: int) -> pd.DataFrame:
    """Récupère le calendrier et les résultats de la saison."""
    from euroleague_api.game_metadata import GameMetadata

    client = GameMetadata(competition_code)
    df = client.get_game_metadata_single_season(season)
    logger.info("Games récupérés : %d lignes", len(df))
    return df


def fetch_standings(competition_code: str, season: int, rounds: list[int]) -> pd.DataFrame:
    """
    Récupère le classement pour une liste de journées.

    On ne prend PAS uniquement le classement final : on reconstitue le
    classement journée par journée pour pouvoir associer à chaque match
    le classement réel des deux équipes AVANT ce match (pas après).
    """
    from euroleague_api.standings import Standings

    client = Standings(competition_code)
    frames = []
    for rnd in rounds:
        try:
            df_round = client.get_standings(season, rnd, endpoint="basicstandings")
            df_round["round"] = rnd
            frames.append(df_round)
        except Exception as e:
            # Une journée manquante ou pas encore jouée ne doit pas arrêter
            # le pipeline : on logue et on continue (cf. principe "un
            # pipeline qui ne casse pas au premier fichier récalcitrant").
            logger.warning("Classement round %s indisponible : %s", rnd, e)
    if not frames:
        raise RuntimeError("Aucun classement récupéré : vérifier la saison/l'API.")
    return pd.concat(frames, ignore_index=True)


def main():
    parser = argparse.ArgumentParser(description="Ingestion des données EuroLeague/EuroCup")
    parser.add_argument("--season", type=int, required=True, help="Année de saison, ex: 2025")
    parser.add_argument(
        "--competition", type=str, default="E", choices=["E", "U"],
        help="E = EuroLeague, U = EuroCup",
    )
    parser.add_argument(
        "--max-round", type=int, default=38,
        help="Nombre max de journées à interroger (championnat régulier ~34-38)",
    )
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Récupération du calendrier / résultats...")
    games = fetch_games(args.competition, args.season)
    games_path = RAW_DIR / f"games_{args.competition}{args.season}.parquet"
    games.to_parquet(games_path, index=False)
    logger.info("Écrit : %s", games_path)

    logger.info("Récupération des classements journée par journée...")
    standings = fetch_standings(args.competition, args.season, list(range(1, args.max_round + 1)))
    standings_path = RAW_DIR / f"standings_{args.competition}{args.season}.parquet"
    standings.to_parquet(standings_path, index=False)
    logger.info("Écrit : %s", standings_path)


if __name__ == "__main__":
    main()
