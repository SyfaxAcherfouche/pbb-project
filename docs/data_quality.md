# Qualité des données

Ce document liste les anomalies détectées dans les sources brutes, comment
je les ai identifiées, et comment le pipeline les corrige. Toutes les
corrections se font en couche **silver** (ou directement en **bronze**
quand il s'agit de rendre un fichier lisible), jamais en modifiant les
fichiers sources, qui restent intacts dans `data/raw/`.

## 1. Fichiers billetterie corrompus (JSON tronqué)

**Détection** : le pipeline s'arrêtait en erreur (`Malformed JSON`) au
premier lancement sur les 358 fichiers `ORDERS_*.json`.

**Fichiers concernés** :
- `ORDERS_20251226_235959.json`
- `ORDERS_20260518_062546.json`

**Cause probable** : une coupure pendant le transfert SFTP. Le JSON
s'arrête au milieu d'une valeur (`unexpected end of data`).

**Correction** : `pipeline/bronze/load_bronze_billetterie.py` traite
chaque fichier dans un bloc `try/except`. Un fichier illisible est loggé
et ignoré, le pipeline continue avec les 356 fichiers valides plutôt que
de s'arrêter entièrement.

**Impact** : 300 819 tickets chargés sur 356/358 fichiers, soit 99.4% des
dépôts quotidiens exploités. Les deux fichiers manquants n'ont pas nui à
la complétude finale de `fact_match` : les billets vendus pour ces deux
journées sont probablement inclus dans un dépôt voisin, le système
semblant faire des dépôts incrémentaux (aucun doublon de `bar_code` entre
fichiers).

## 2. Fichier scan sans ligne d'en-tête

**Détection** : `gold.fact_match` affichait un `taux_presence` de 0 pour
le match M004 (17/10/2025 contre Hapoel Shlomo Tel Aviv) alors que 7577
billets avaient été vendus, une valeur impossible qui m'a mené jusqu'à sa
cause plutôt que de la laisser passer.

**Fichier concerné** : `scan_20251017.csv`

**Cause** : contrairement aux 40 autres fichiers scans, qui commencent
tous par `barcode,scan_ts_utc,portique,ext_id,type_billet,resultat`,
celui-ci commence directement par une ligne de données. Avec un
chargement en glob classique, le moteur SQL prenait cette première ligne
comme noms de colonnes : le schéma se décalait silencieusement, une vraie
ligne de scan était perdue (transformée en faux en-tête), et la colonne
`resultat` finissait `NULL` sur les 7164 lignes restantes.

**Correction** : `pipeline/bronze/load_bronze.py` charge chaque fichier
scan individuellement. La première ligne est comparée au nom de colonne
attendu (`barcode`) ; si elle ne correspond pas, le fichier est chargé
sans en-tête avec les noms de colonnes forcés.

**Impact** : avant correction, 7164 scans de ce match étaient invisibles.
Après correction, les 7165 lignes du fichier sont exploitées, et
`taux_presence` passe de 0 à 0.922, cohérent avec le reste de la saison.

## 3. Fichier scan vide

**Détection** : le pipeline s'arrêtait en erreur (`It was not possible to
detect the CSV Header`) sur `scan_20251224.csv`.

**Fichier concerné** : `scan_20251224.csv`, 0 octet, repéré dès
l'exploration initiale du dataset (taille affichée "0 Ko" dans
l'explorateur de fichiers).

**Correction** : le même chargeur fichier-par-fichier détecte une
première ligne vide avant de tenter de lire le fichier, et l'ignore avec
un avertissement plutôt que de faire planter le pipeline.

**Impact** : aucune donnée perdue, un fichier vide n'a rien à offrir. Le
match concerné dispose d'un autre fichier scan valide à une date proche.

## 4. `contacts.csv` : formats de date mixtes

**Détection** : inspection manuelle de `date_naissance`, deux formats
visibles dès les premières lignes.

**Formats coexistants** : `YYYY-MM-DD` et `DD/MM/YYYY`.

**Correction** : `pipeline/silver/clean_silver.py` essaie `YYYY-MM-DD`
puis, en repli, `DD/MM/YYYY`.

**Impact** : 190 000 lignes chargées, 1926 dates de naissance non
parsables (environ 1%), laissées à `NULL` plutôt que devinées.

## 5. `boutique_ventes_avoirs.csv` : trois formats de date, décimales FR, doublons

**Détection** : un premier passage du pipeline, avec seulement deux
formats de date gérés, laissait 9283 dates non parsables (18% du
fichier). Ce chiffre était trop élevé pour être normal, et une
investigation manuelle a révélé un troisième format.

**Formats de date coexistants** : `YYYY-MM-DD`, `DD/MM/YYYY`,
`DD-MM-YYYY`.

**Autres particularités** :
- délimiteur `;` plutôt que `,`
- décimales au format français (`39,00` au lieu de `39.00`)
- ventes à l'état `ANNULEE` (1480 lignes) mêlées aux ventes valides
- 307 lignes strictement dupliquées (même `ligne_id`, même contenu),
  probable artefact d'export du logiciel de caisse

**Correction** : `pipeline/silver/clean_silver.py` essaie les trois
formats de date en cascade, convertit les décimales, et déduplique via
`QUALIFY ROW_NUMBER() ... = 1` sur les colonnes clés. Les ventes
`ANNULEE` restent dans la table mais identifiables via `etat_vente`, à
exclure du calcul de chiffre d'affaires en gold.

**Impact** : 51 251 lignes en bronze deviennent 50 945 en silver après
déduplication (306 doublons supprimés). Quasi 100% des dates sont
parsables une fois le troisième format ajouté (2 lignes restent
invalides, correspondant à des lignes vides en source).

## 6. Feature leakage évité : classement "avant match"

Point de vigilance plutôt qu'un bug corrigé. `silver.resultats_matchs`
contient `rang_pbb_avant` et `rang_adversaire_avant`, déjà calculés par le
club comme le classement avant chaque match. La table gold utilise
exclusivement ces colonnes plutôt que le classement final de saison, pour
ne pas donner au modèle une information qui n'existait pas encore au
moment du match.

## Résumé chiffré

| Source | Lignes brutes | Lignes retenues | Anomalies corrigées |
|---|---|---|---|
| Billetterie (ORDERS) | 358 fichiers | 356 fichiers (300 819 tickets) | 2 fichiers JSON corrompus ignorés |
| Scans | 42 fichiers | 41 fichiers (271 657 lignes) | 1 sans en-tête (corrigé), 1 vide (ignoré) |
| Contacts | 190 000 | 190 000 | ~1% dates de naissance non parsables |
| Boutique | 51 251 | 50 945 | 3 formats de date, 306 doublons supprimés |
