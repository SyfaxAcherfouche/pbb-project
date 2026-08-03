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
   contacts, calendrier, résultats, sessions/événements web, campagnes) +
   sources externes (météo, vacances scolaires, classement EuroLeague,
   population) dans une architecture en couches bronze / silver / gold
   (DuckDB).
2. Construction d'une table de faits `gold.fact_match` : une ligne par
   match à domicile (41 matchs), avec taux de remplissage, taux de
   présence réelle, taux d'annulation, classement avant-match, contexte
   temporel et météo.
3. Exploration statistique et visuelle (`analysis/exploration.ipynb`, 13
   sections), avec vérification systématique des hypothèses avant
   conclusion (pas de corrélation acceptée sans test des explications
   alternatives).
4. Modèle de régression pour confirmer et quantifier les facteurs
   identifiés, et analyse du funnel e-commerce / performance des
   campagnes (branches `experiment/*`, mergées dans `main`).
5. Dashboard autonome (`dashboard/dashboard.html`) synthétisant les
   résultats pour un public non-technique.

## Chiffres clés

- **Taux de remplissage moyen : 80%** sur la saison (min 40.5%, max 95.1%)
- **Par compétition** : Playoffs 84.7% > EuroLeague 82.5% > Championnat
  (Betclic ÉLITE) 74.6%
- **Facteur le plus discriminant : le classement de l'adversaire.** Le
  taux de remplissage chute nettement à mesure que l'adversaire est mal
  classé (~90% face à un top adversaire, ~65% face à un adversaire en bas
  de tableau) : confirmé par le modèle de régression comme feature la
  plus influente, de loin.
- **Effet jour de semaine** : le dimanche est systématiquement le jour le
  plus faible (74.8% de moyenne sur 10 matchs), contre ~81-82% les mardis
  et jeudis.
- **Effet vacances scolaires** (vérifié, pas un artefact de calendrier) :
  75.2% pendant les vacances vs 81% hors vacances. Rang moyen des
  adversaires comparable dans les deux groupes (9.6 vs 10.1).
- **Météo : aucun effet mesurable** (corrélation 0.04 avec la température,
  0.02 avec les précipitations).
- **Horaire du match : pas un facteur indépendant.** Un écart apparent
  après-midi/soirée s'est révélé confondu avec l'effet jour de semaine
  (71% des matchs d'après-midi sont des dimanches).
- **Annulations corrélées à la demande** (0.62) : les matchs à forte
  affluence attendue génèrent proportionnellement plus d'achats annulés,
  bien que l'ampleur reste modeste en absolu (0.2% à 1.8% du volume).
- **Satisfaction expliquée par le résultat sportif, pas le remplissage** :
  8.14/10 en victoire contre 6.20/10 en défaite. Le remplissage et la
  satisfaction semblaient corrélés (-0.38) mais sont en réalité deux
  conséquences distinctes du niveau de l'adversaire (la victoire étant
  elle-même corrélée à -0.45 avec le remplissage).
- **Géographie du bassin de fans** : les 18e et 19e arrondissements
  affichent la plus forte pénétration (68 et 63 contacts pour 1000
  habitants), cohérent avec la proximité de l'Adidas Arena. Plusieurs
  communes de petite couronne (Poissy, Saint-Ouen, Villejuif) ressortent
  aussi fortement.
- **Modèle de régression (Ridge, LOO-CV)** : MAE de 8.3% (erreur relative)
  — solide pour 41 observations. Confirme statistiquement que le
  classement adversaire domine largement les autres features.
- **Funnel digital et campagnes** : les canaux propriétaires (SMS,
  newsletter, Google Ads payant) convertissent 3x mieux (~22.5%) que
  l'organique et le social (~6.5-7%), malgré un volume de trafic bien
  plus faible. Le SMS surperforme l'email en engagement (38.4%
  d'ouverture, 34.5% de clic, contre 21.3%/22.6% pour l'email) tout en
  convertissant aussi bien que la newsletter.

## Réponse à la question métier

Les matchs qui sous-performent le plus nettement partagent un point commun
clair : un adversaire mal classé au moment du match (ex. Dijon,
Saint-Quentin, LDLC ASVEL Villeurbanne. Tous entre 40% et 60% de
remplissage), confirmé à la fois par l'analyse descriptive et par un
modèle statistique. Le championnat national remplit structurellement
moins bien que l'EuroLeague, et le dimanche ainsi que les périodes de
vacances scolaires sont des créneaux à surveiller, indépendamment de la
force de l'adversaire. Trois enseignements complémentaires enrichissent
le tableau : les matchs premium génèrent plus d'annulations (paradoxe du
succès), la satisfaction du public dépend du résultat sportif et non du
remplissage, et les canaux marketing propriétaires (SMS notamment)
convertissent nettement mieux que l'acquisition organique/sociale : un
levier digital directement activable pour les campagnes ciblées.

### Recommandations actionnables

1. **Tarification dynamique par force d'adversaire** : politique tarifaire
   plus agressive (promotions, offres groupées) pour les matchs contre des
   adversaires classés au-delà de la 15e place.
2. **Campagnes ciblées sur les dimanches et les périodes de vacances
   scolaires**, via SMS en priorité vu son meilleur taux d'engagement
   (38.4% d'ouverture contre 21.3% pour l'email).
3. **Capitaliser sur l'attrait EuroLeague** dans la communication et le
   packaging des abonnements : écart de 8 points avec le championnat.
4. **Politique d'annulation adaptée aux matchs à forte demande** :
   envisager des frais d'annulation modulés ou une liste d'attente pour
   récupérer les places libérées tardivement sur les matchs premium.
5. **Marketing géolocalisé** : intensifier la présence dans les zones à
   forte pénétration existante (nord-est parisien, Poissy, Saint-Ouen)
   pour consolider la base, et cibler l'acquisition dans les zones à fort
   potentiel démographique mais faible pénétration actuelle.
6. **Concentrer le budget d'acquisition payante** sur les canaux à forte
   conversion (SMS, newsletter, Google Ads) plutôt que sur l'élargissement
   de l'audience organique/sociale, déjà large mais peu convertissante.

## Limites

- **41 matchs seulement** : certains découpages reposent sur de petits
  échantillons (un seul match un vendredi, par exemple). Le modèle de
  régression sert surtout à confirmer et quantifier les facteurs déjà
  identifiés par l'analyse descriptive, pas à prédire de façon fiable des
  matchs hors de cette saison.
- **Hypothèses testées et écartées, documentées par transparence** :
  l'effet horaire (confondu avec le jour de semaine) et l'effet météo
  (non significatif) ont été explorés puis abandonnés comme facteurs
  explicatifs : inclus dans le notebook pour montrer la démarche complète,
  pas seulement les résultats positifs.
- **L'analyse satisfaction** porte sur ~7956 réponses `POST_MATCH`
  uniquement (les enquêtes `GENERALE_MI_SAISON`/`GENERALE_FIN_SAISON`
  n'ont pas de `match_id` et ne sont pas exploitables au niveau match).
- **L'analyse géographique** couvre le bassin francilien : 25 codes
  postaux sur 69 dans `silver.contacts` n'ont pas de correspondance dans
  les référentiels de population (fans hors Île-de-France ou codes
  fictifs issus des données de test).
- **Le funnel digital concerne la boutique en ligne**, pas la billetterie
  (deux systèmes de tracking distincts, GA4 vs plateforme de billetterie) :
  les taux de conversion mesurés portent sur les achats de produits
  dérivés, pas directement sur les billets de match.
- **Qualité de données** : plusieurs anomalies détectées et corrigées dans
  le pipeline (2 fichiers billetterie JSON corrompus sur 358, 1 fichier
  scan sans en-tête, 1 fichier scan vide, formats de date multiples dans
  contacts et boutique). Détail complet dans `docs/data_quality.md`.
  Toutes les corrections sont documentées et automatisées, aucune donnée
  n'a été estimée ou inventée pour combler un manque.

## Usage de l'IA

Claude (Anthropic) a été utilisé tout au long du projet : écriture et débogage des
scripts d'ingestion et de transformation (Python/DuckDB/SQL), diagnostic
d'anomalies de données (ex. remontée du bug `scan_20251017.csv` depuis un
`taux_presence` incohérent en gold jusqu'à sa cause racine), conception et
vérification des analyses statistiques (y compris le démêlage de la
variable confondante victoire/défaite dans l'analyse satisfaction, et de
l'effet horaire confondu avec le jour de semaine), construction du modèle
de prédiction, de l'analyse du funnel digital, et du dashboard. Toutes les
requêtes et tous les résultats ont été exécutés et vérifiés manuellement
sur les données réelles avant validation. Aucun résultat n'a été utilisé
sans être recalculé et confirmé sur le dataset complet, et plusieurs
hypothèses initialement plausibles (effet horaire, corrélation
satisfaction directe) ont été testées puis rejetées après vérification
plutôt qu'acceptées telles quelles.
