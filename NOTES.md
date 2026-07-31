# NOTES.md

## Question métier

**Quels matchs sous-performent en remplissage, et quels leviers (tarification,
campagnes, timing) pourraient corriger ça ?**

Question choisie parce qu'elle croise directement les quatre sources
fournies (billetterie, scans, calendrier, contexte), qu'elle a une réponse
vérifiable (le calendrier et les résultats sportifs sont réels), et qu'elle
débouche sur des recommandations concrètes pour un dirigeant du club.

## Démarche

1. Ingestion de toutes les sources fournies (billetterie, scans, boutique,
   contacts, calendrier, résultats) + sources externes (météo, vacances
   scolaires, classement EuroLeague) dans une architecture en couches
   bronze / silver / gold (DuckDB).
2. Construction d'une table de faits `gold.fact_match` : une ligne par
   match à domicile (41 matchs), avec taux de remplissage, taux de
   présence réelle, classement avant-match, contexte temporel et météo.
3. Exploration statistique et visuelle (`analysis/exploration.ipynb`).

## Chiffres clés

- **Taux de remplissage moyen : 80%** sur la saison (min 40.5%, max 95.1%)
- **Par compétition** : Playoffs 84.7% > EuroLeague 82.5% > Championnat
  (Betclic ÉLITE) 74.6%
- **Facteur le plus discriminant : le classement de l'adversaire.** Le
  taux de remplissage chute nettement à mesure que l'adversaire est mal
  classé (~90% face à un adversaire du haut du classement, ~65% face à un
  adversaire en bas de tableau) — tendance nette sur les 41 matchs.
- **Effet jour de semaine** : le dimanche est systématiquement le jour le
  plus faible (74.8% de moyenne sur 10 matchs), contre ~81-82% les mardis
  et jeudis.
- **Effet vacances scolaires** (vérifié, pas un artefact de calendrier) :
  les matchs joués pendant les vacances scolaires remplissent moins bien
  (75.2%) que hors vacances (81%). Le rang moyen des adversaires est
  comparable dans les deux groupes (9.6 vs 10.1) — l'effet n'est donc pas
  expliqué par une programmation d'adversaires plus faibles pendant les
  vacances.

## Réponse à la question métier

Les matchs qui sous-performent le plus nettement partagent un point commun
clair : un adversaire mal classé au moment du match (ex. Dijon, Saint-Quentin,
LDLC ASVEL Villeurbanne — tous entre 40% et 60% de remplissage). Le
championnat national remplit structurellement moins bien que l'EuroLeague,
et le dimanche ainsi que les périodes de vacances scolaires sont des
créneaux à surveiller, indépendamment de la force de l'adversaire.

### Recommandations actionnables

1. **Tarification dynamique par force d'adversaire** : envisager une
   politique tarifaire plus agressive (promotions, offres groupées) pour
   les matchs contre des adversaires classés au-delà de la 15e place, où
   l'attractivité sportive seule ne suffit pas à remplir la salle.
2. **Campagnes ciblées sur les dimanches et les périodes de vacances
   scolaires** : ces créneaux sous-performent de façon récurrente et
   indépendante du calendrier sportif — un axe marketing autonome plutôt
   qu'un simple effet de programmation.
3. **Capitaliser sur l'attrait EuroLeague** dans la communication et le
   packaging des abonnements : l'écart de 8 points avec le championnat
   suggère un effet de marque à exploiter davantage.

## Limites

- **41 matchs seulement** : certains découpages (ex. par jour de semaine)
  reposent sur de petits échantillons — un seul match un vendredi, par
  exemple. Les tendances par compétition et par classement adversaire
  sont plus robustes (15 à 19 matchs par groupe).
- **L'effet "vacances scolaires" est observé et vérifié comme non expliqué
  par le classement adversaire, mais sa cause reste ouverte** (moins
  d'abonnés disponibles ? changement de profil de public ?) — une piste
  pour une future analyse croisée avec les données de satisfaction ou de
  profil des acheteurs.
- **Qualité de données** : plusieurs anomalies détectées et corrigées dans
  le pipeline (2 fichiers billetterie JSON corrompus sur 358, 1 fichier
  scan sans en-tête, 1 fichier scan vide, formats de date multiples dans
  contacts et boutique) — détail complet dans `docs/data_quality.md`.
  Toutes les corrections sont documentées et automatisées, aucune donnée
  n'a été estimée ou inventée pour combler un manque.
- **Modèle de prédiction** : envisagé mais non prioritaire au vu du temps
  disponible et de la taille de l'échantillon (41 matchs) — les
  corrélations observées ici (classement adversaire notamment) sont deja
  fortes et interprétables sans modèle, ce qui limite le gain d'un modèle
  formel pour ce livrable.

## Usage de l'IA

Claude (Anthropic) a été utilisé tout au long du projet : conception de
l'architecture (médaillon bronze/silver/gold), écriture et débogage des
scripts d'ingestion et de transformation (Python/DuckDB/SQL), diagnostic
d'anomalies de données (ex. remontée du bug `scan_20251017.csv` depuis un
`taux_presence` incohérent en gold jusqu'à sa cause racine), et relecture
de la structure d'analyse. Toutes les requêtes ont été exécutées et
vérifiées manuellement sur les données réelles avant validation — aucun
résultat n'a été utilisé sans être recalculé et confirmé sur le dataset
complet.
