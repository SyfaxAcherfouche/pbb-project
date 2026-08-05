# NOTES.md

## Question métier

Quels matchs sous-performent en remplissage, et quels leviers (tarification, campagnes, timing) pourraient corriger ça ?

Cette question croise les quatre sources fournies (billetterie, scans, calendrier, contexte) et se vérifie facilement : le calendrier et les résultats sportifs sont réels. Elle débouche aussi sur des recommandations concrètes pour un dirigeant du club, ce qui n'était pas garanti avec d'autres angles possibles (satisfaction seule, ou performance de campagnes isolée).

## Démarche

J'ai ingéré toutes les sources fournies (billetterie, scans, boutique, contacts, calendrier, résultats, sessions et événements web, campagnes), plus des sources externes (météo, vacances scolaires, classement EuroLeague, population), dans une architecture en couches bronze / silver / gold sous DuckDB.

`gold.fact_match` regroupe les 41 matchs à domicile de la saison : taux de remplissage, taux de présence réelle, taux d'annulation, classement avant-match, contexte temporel et météo. L'exploration (`analysis/exploration.ipynb`, 13 sections) suit une règle simple : aucune corrélation n'est retenue sans qu'on ait cherché à l'expliquer autrement. Deux hypothèses raisonnables (effet horaire, effet météo) ont d'ailleurs été écartées après vérification.

Un modèle de régression confirme et chiffre les facteurs identifiés à l'œil, et une analyse séparée du funnel e-commerce et des campagnes marketing complète le tableau (branches `experiment/*`, mergées dans `main`). Le tout se lit en deux minutes dans `dashboard/dashboard.html`.

## Chiffres clés

Le taux de remplissage moyen tourne autour de 80% sur la saison, avec un écart important entre le pire match (40.5%) et le meilleur (95.1%).

Par compétition, les Playoffs et l'EuroLeague remplissent mieux (84.7% et 82.5%) que le championnat national Betclic ÉLITE (74.6%). Mais ce n'est pas le facteur le plus discriminant : c'est le classement de l'adversaire. Le remplissage passe d'environ 90% face à un adversaire du haut du tableau à environ 65% face à un adversaire en bas de classement, et le modèle de régression confirme que cette variable domine largement les autres.

Le jour de la semaine joue aussi : le dimanche affiche la moyenne la plus faible (74.8% sur 10 matchs) contre 81-82% les mardis et jeudis. Les vacances scolaires réduisent également le remplissage (75.2% contre 81% hors vacances), un résultat contre-intuitif que j'ai vérifié avant de le retenir : le rang moyen des adversaires est comparable pendant et hors vacances (9.6 contre 10.1), donc l'effet n'est pas un artefact de calendrier.

La météo, en revanche, n'a aucun effet mesurable (corrélations de 0.04 pour la température et 0.02 pour les précipitations). L'horaire du match non plus, une fois isolé de l'effet jour de semaine : 71% des matchs d'après-midi tombent un dimanche, donc l'écart apparent entre après-midi et soirée n'était qu'une reformulation de l'effet déjà identifié.

Deux résultats moins attendus s'ajoutent. D'abord, les annulations augmentent avec la demande (corrélation de 0.62) : les matchs les plus attendus génèrent proportionnellement plus d'achats annulés ensuite, même si l'ampleur reste faible en valeur absolue (0.2% à 1.8% du volume). Ensuite, la satisfaction du public dépend du résultat sportif, pas du remplissage : 8.14/10 en victoire contre 6.20/10 en défaite. Une corrélation initiale entre remplissage et satisfaction (-0.38) laissait croire à un lien direct ; en creusant, il s'agit en fait de deux conséquences distinctes du même facteur, le niveau de l'adversaire, puisque la victoire elle-même est corrélée à -0.45 avec le remplissage.

Côté géographie, les 18e et 19e arrondissements affichent la plus forte pénétration de fans rapportée à la population (68 et 63 contacts pour 1000 habitants), cohérent avec la proximité de l'Adidas Arena. Plusieurs communes de petite couronne (Poissy, Saint-Ouen, Villejuif) ressortent aussi bien.

Le modèle de régression (Ridge, validation croisée leave-one-out) obtient une erreur moyenne de 8.3%, solide pour 41 observations, et confirme que le classement adversaire est de loin la feature la plus influente.

Enfin, côté digital : les canaux propriétaires (SMS, newsletter, Google Ads payant) convertissent trois fois mieux (~22.5%) que l'organique et le social (~6.5-7%), et le SMS surperforme l'email en engagement (38.4% d'ouverture contre 21.3%) tout en convertissant aussi bien que la newsletter.

## Réponse à la question métier

Les matchs les plus faibles ont presque tous un point commun : un adversaire mal classé. Dijon, Saint-Quentin, LDLC ASVEL Villeurbanne tournent tous entre 40% et 60% de remplissage, et le modèle statistique confirme que ce facteur pèse plus que tous les autres réunis. Le championnat national reste structurellement en dessous de l'EuroLeague, et le dimanche comme les vacances scolaires sont des créneaux à surveiller indépendamment de l'adversaire du soir.

Deux points méritent d'être retenus au-delà du remplissage lui-même : les matchs premium génèrent davantage d'annulations, et la satisfaction du public suit le résultat sportif plutôt que l'affluence.

### Recommandations

1. **Tarification dynamique par force d'adversaire.** Une politique plus agressive (promotions, offres groupées) sur les matchs contre des adversaires classés au-delà de la 15e place.
2. **Campagnes ciblées sur les dimanches et les vacances scolaires**, en priorisant le SMS pour son meilleur taux d'engagement.
3. **Capitaliser sur l'EuroLeague dans la communication et le packaging des abonnements**, vu l'écart de 8 points avec le championnat.
4. **Adapter la politique d'annulation** sur les matchs premium, par exemple avec des frais modulés ou une liste d'attente pour récupérer les places libérées tardivement.
5. **Renforcer le marketing géolocalisé** dans le nord-est parisien tout en identifiant les zones à fort potentiel démographique mais faible pénétration actuelle.
6. **Réallouer le budget d'acquisition payante** vers les canaux qui convertissent le mieux (SMS, newsletter, Google Ads) plutôt que l'organique.

## Limites

L'échantillon reste petit : 41 matchs, avec parfois un seul match par catégorie (un seul vendredi, par exemple), donc certains découpages sont à prendre avec prudence. Le modèle de régression sert surtout à confirmer et chiffrer ce que l'analyse descriptive montrait déjà, pas à prédire des matchs hors de cette saison.

Deux hypothèses plausibles (effet horaire, effet météo) ont été testées puis écartées ; je les garde dans le notebook pour montrer la démarche complète, pas seulement les résultats qui confirment quelque chose.

L'analyse de satisfaction ne porte que sur les ~7956 réponses de type POST_MATCH : les enquêtes de mi-saison et fin de saison n'ont pas de match_id et ne sont donc pas exploitables à ce niveau. L'analyse géographique se limite au bassin francilien, avec 25 codes postaux sur 69 sans correspondance dans les référentiels de population utilisés. Le funnel digital, lui, porte sur la boutique en ligne et non sur la billetterie : ce sont deux systèmes de tracking distincts.

Côté qualité de données, le pipeline a rencontré et corrigé plusieurs anomalies réelles : deux fichiers billetterie corrompus sur 358, un fichier scan sans en-tête, un fichier scan vide, et des formats de date multiples dans les tables contacts et boutique. Le détail est dans `docs/data_quality.md`. Aucune donnée manquante n'a été estimée ou inventée pour combler un trou.

## Usage de l'IA

J'ai utilisé Claude tout au long du projet : conception de l'architecture bronze/silver/gold, écriture et débogage des scripts (Python, DuckDB, SQL), diagnostic d'anomalies (par exemple remonter jusqu'à la cause d'un `taux_presence` incohérent en gold, qui venait d'un fichier scan sans en-tête), vérification des analyses statistiques, et construction du modèle et du dashboard. J'ai exécuté et vérifié chaque requête et chaque résultat sur mes données réelles avant de les valider, et j'ai testé puis rejeté plusieurs hypothèses qui semblaient plausibles au départ (effet horaire, corrélation directe satisfaction-remplissage) plutôt que de les accepter telles quelles.
