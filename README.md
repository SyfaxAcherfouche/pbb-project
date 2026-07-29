# Paris Basketball — Test technique Data & Digital

## Question métier

Quels matchs sous-performent en remplissage, et quels leviers (tarification,
campagnes, timing) pourraient corriger ça ?

*(à affiner au fil du projet — voir NOTES.md pour la version finale)*

## Architecture

Architecture en couches (médaillon bronze / silver / gold), pour isoler la
casse : si une source change de format, seule la couche bronze est rejouée,
silver et gold restent intactes.

```
ingestion/     scripts d'extraction (fichiers club + API EuroLeague + sources externes)
pipeline/
  bronze/      chargement brut, sans transformation (fidélité à la source)
  silver/      nettoyage, typage, dédoublonnage
  gold/        tables agrégées prêtes pour l'analyse (fact_match, etc.)
  run_pipeline.py   orchestrateur, enchaîne les 3 couches
data/
  raw/         copies brutes, non modifiées, des fichiers sources (ignoré par git)
  processed/   exports ponctuels si besoin (ignoré par git)
  warehouse/   base DuckDB, schémas bronze / silver / gold (ignoré par git)
analysis/      notebooks d'exploration et de modélisation
dashboard/     dashboard.html autonome
tests/         tests de cohérence des données
docs/          notes de qualité de données, schéma
presentation/  slides de soutenance
```

## Installation

```bash
python3 -m venv venv
source venv/bin/activate        # Windows : venv\Scripts\activate
pip install -r requirements.txt
```

## Lancer le pipeline

```bash
python pipeline/run_pipeline.py
```

*(à activer au fur et à mesure que les scripts bronze/silver/gold sont écrits)*

## Statut

- [x] Squelette du repo (dossiers, .gitignore, requirements.txt)
- [ ] Script d'ingestion EuroLeague
- [ ] Pipeline bronze (chargement brut)
- [ ] Pipeline silver (nettoyage)
- [ ] Pipeline gold (table de faits match)
- [ ] Analyse exploratoire
- [ ] Dashboard
- [ ] Modèle de prédiction 
