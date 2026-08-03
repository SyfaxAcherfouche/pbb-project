# Paris Basketball — Test technique Data & Digital

## Question métier

**Quels matchs sous-performent en remplissage, et quels leviers
(tarification, campagnes, timing) pourraient corriger ça ?**

Voir `NOTES.md` pour la réponse complète, les chiffres clés et les
recommandations. Voir `docs/data_quality.md` pour le détail des anomalies
de données rencontrées et corrigées.

## Architecture

Architecture en couches (médaillon bronze / silver / gold), pour isoler la
casse : si une source change de format, seule la couche bronze est rejouée,
silver et gold restent intactes.

```
ingestion/     script d'ingestion API EuroLeague (exploré, non retenu dans
               le pipeline final -- cf. plan_api/ comme source privilégiée)
pipeline/
  bronze/      chargement brut, sans transformation (fidélité à la source)
    load_bronze.py               dataset/ + sftp/scans/
    load_bronze_api.py           plan_api/ (météo, vacances, population, euroleague)
    load_bronze_billetterie.py   sftp/orders/
  silver/      nettoyage, typage, dédoublonnage
    clean_silver.py
  gold/        tables agrégées + livrables finaux
    build_gold.py         construit gold.fact_match
    build_dashboard.py    génère dashboard/dashboard.html
    vendor/                Chart.js embarqué (pas de dépendance CDN)
  run_pipeline.py   orchestrateur, enchaîne bronze -> silver -> gold -> dashboard
data/
  raw/         copies brutes, non modifiées, des fichiers sources (ignoré par git)
  processed/   exports ponctuels si besoin (ignoré par git)
  warehouse/   base DuckDB, schémas bronze / silver / gold (ignoré par git)
analysis/
  exploration.ipynb   notebook complet, 13 sections : remplissage,
                       classement adversaire, jour/vacances, météo,
                       annulations, satisfaction, horaire, géographie,
                       modèle de prédiction, funnel digital, synthèse
dashboard/
  dashboard.html       autonome (données + Chart.js embarqués)
  fig_*.png             graphiques exportés depuis le notebook
docs/
  data_quality.md       anomalies de données détectées et corrigées
tests/
  conftest.py                fixture de connexion DuckDB
  test_gold_fact_match.py     7 tests d'intégrité sur gold.fact_match
  test_silver_quality.py      5 tests de non-régression sur les corrections silver
presentation/   slides de soutenance
NOTES.md        question métier, chiffres clés, réponse, limites
```

| Couche | Contenu | Règle |
|---|---|---|
| `bronze.*` | copie fidèle des CSV/JSON sources | jamais de transformation, juste du typage minimal |
| `silver.*` | nettoyée : dates unifiées, doublons supprimés, décimales normalisées | une table silver par table bronze correspondante |
| `gold.*` | agrégée, orientée métier (`fact_match`) | seule couche consommée par `analysis/` et `dashboard/` |

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

Enchaîne automatiquement bronze -> silver -> gold -> dashboard. Chaque
étape peut aussi être lancée séparément pour du débogage :

```bash
python pipeline/bronze/load_bronze.py
python pipeline/bronze/load_bronze_api.py
python pipeline/bronze/load_bronze_billetterie.py
python pipeline/silver/clean_silver.py
python pipeline/gold/build_gold.py
python pipeline/gold/build_dashboard.py
```

**Prérequis** : déposer les fichiers sources dans `data/raw/` selon
l'arborescence attendue (`dataset/`, `sftp/scans/`, `sftp/orders/`,
`plan_api/euroleague/E2025/`, `plan_api/open_meteo/`,
`plan_api/calendrier_scolaire/`, `plan_api/population/`) avant de lancer.

## Lancer les tests

```bash
pytest tests/ -v
```

12 tests de cohérence : intégrité de `gold.fact_match` (pas de doublon,
bornes de valeurs, absence de feature leakage sur le classement) et
non-régression des corrections de qualité de données appliquées en silver
(dates, doublons boutique, scans sans en-tête).

## Consulter les résultats

- **`dashboard/dashboard.html`** : ouvrir directement dans un navigateur,
  autonome, se lit en 2 minutes.
- **`analysis/exploration.ipynb`** : notebook complet avec tout le détail
  de l'analyse, y compris les hypothèses testées et écartées (transparence
  sur la démarche, pas seulement les résultats positifs) et le modèle de
  prédiction.
- **`NOTES.md`** : synthèse écrite, chiffres clés, recommandations,
  limites.

## Robustesse du pipeline

Le pipeline a été construit pour ne jamais s'arrêter au premier fichier
récalcitrant, avec 3 cas réels rencontrés et corrigés automatiquement
(détail dans `docs/data_quality.md`) :
- fichiers billetterie JSON corrompus (2/358, isolés et ignorés)
- fichier scan sans ligne d'en-tête (détecté et corrigé)
- fichier scan vide (isolé et ignoré)

Ces 3 corrections sont couvertes par des tests de non-régression
(`tests/test_silver_quality.py`).

## Approche git

Développement principalement sur `main`, avec des branches dédiées
(`experiment/modele-remplissage`, `experiment/analyse-digital`) pour les
axes d'analyse les plus incertains ou exploratoires, mergées une fois
validées. Commits atomiques, un changement logique par commit.

## Statut

- [x] Squelette du repo, environnement reproductible
- [x] Pipeline bronze / silver / gold, robuste et testé
- [x] Table de faits `gold.fact_match` (41 matchs, 100% de complétude)
- [x] Qualité de données documentée (`docs/data_quality.md`)
- [x] Notebook d'exploration complet (13 sections, y compris hypothèses
      testées et écartées : météo, horaire)
- [x] Modèle de prédiction (régression Ridge, LOO-CV, MAE 8.3%)
- [x] Funnel e-commerce et performance des campagnes marketing
- [x] Dashboard autonome avec charte graphique du club
- [x] Tests de cohérence automatisés (12 tests, `tests/`)
- [x] `NOTES.md` (question, chiffres clés, recommandations, limites)
