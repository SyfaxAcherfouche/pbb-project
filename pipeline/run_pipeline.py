"""
Orchestrateur du pipeline : enchaîne les couches bronze -> silver -> gold.

Volontairement un simple script séquentiel plutôt qu'un orchestrateur
(Airflow, Dagster...) : à l'échelle d'un pipeline solo sur 1 semaine, un
outil plus lourd ajouterait de la complexité sans bénéfice réel.

Si une étape échoue, le pipeline s'arrête proprement avec un message clair
plutôt que de continuer sur des données potentiellement incomplètes.

Usage :
    python pipeline/run_pipeline.py
"""

import logging
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent

STEPS = [
    ("bronze (dataset + scans)", ROOT / "bronze" / "load_bronze.py"),
    ("bronze (plan_api)", ROOT / "bronze" / "load_bronze_api.py"),
    ("bronze (billetterie)", ROOT / "bronze" / "load_bronze_billetterie.py"),
    ("silver", ROOT / "silver" / "clean_silver.py"),
    ("gold", ROOT / "gold" / "build_gold.py"),
]


def main():
    for layer, script in STEPS:
        if not script.exists():
            logger.warning("Étape '%s' ignorée : %s introuvable", layer, script)
            continue
        logger.info("=== %s : %s ===", layer, script.name)
        result = subprocess.run([sys.executable, str(script)])
        if result.returncode != 0:
            logger.error("Échec à l'étape '%s', arrêt du pipeline.", layer)
            sys.exit(result.returncode)
    logger.info("Pipeline terminé avec succès.")


if __name__ == "__main__":
    main()
