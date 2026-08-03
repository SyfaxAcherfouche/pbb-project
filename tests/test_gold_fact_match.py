"""
Tests de cohérence sur gold.fact_match. Vérifient des invariants qui
doivent TOUJOURS être vrais, quel que soit le contenu réel des données --
pas des tests sur des valeurs métier précises (qui dépendent des vraies
données de chacun), mais sur des règles structurelles.

Usage :
    pytest tests/ -v
"""


def test_pas_de_match_id_duplique(con):
    """Chaque match_id doit apparaître exactement une fois dans fact_match."""
    total, distincts = con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT match_id) FROM gold.fact_match"
    ).fetchone()
    assert total == distincts, (
        f"{total - distincts} match_id dupliqué(s) dans gold.fact_match"
    )


def test_nombre_de_matchs_coherent_avec_calendrier(con):
    """
    fact_match doit avoir exactement autant de lignes que calendrier_matchs
    (silver) -- une jointure qui perd ou duplique des lignes serait un bug
    silencieux grave.
    """
    n_fact = con.execute("SELECT COUNT(*) FROM gold.fact_match").fetchone()[0]
    n_calendrier = con.execute("SELECT COUNT(*) FROM silver.calendrier_matchs").fetchone()[0]
    assert n_fact == n_calendrier, (
        f"gold.fact_match a {n_fact} lignes, silver.calendrier_matchs en a "
        f"{n_calendrier} -- la jointure a perdu ou dupliqué des matchs"
    )


def test_taux_remplissage_dans_les_bornes(con):
    """
    taux_remplissage ne peut pas être négatif, et ne devrait normalement
    pas dépasser 1 (capacité de la salle) -- une petite tolérance (1.02)
    est acceptée pour des cas limites de sur-vente légitime (invitations,
    accès non comptés dans la capacité officielle).
    """
    rows = con.execute(
        "SELECT match_id, taux_remplissage FROM gold.fact_match "
        "WHERE taux_remplissage IS NOT NULL "
        "AND (taux_remplissage < 0 OR taux_remplissage > 1.02)"
    ).fetchall()
    assert not rows, f"taux_remplissage hors bornes pour : {rows}"


def test_taux_presence_dans_les_bornes(con):
    """
    taux_presence (entrées scannées / billets vendus) ne peut pas dépasser
    1 de façon significative -- si c'est le cas, c'est le signe que la
    billetterie et les scans ne couvrent pas la même période (cf.
    docs/data_quality.md, bug déjà rencontré sur un échantillon partiel).
    """
    rows = con.execute(
        "SELECT match_id, taux_presence FROM gold.fact_match "
        "WHERE taux_presence IS NOT NULL AND taux_presence > 1.05"
    ).fetchall()
    assert not rows, (
        f"taux_presence > 1.05 pour : {rows} -- vérifier la complétude des "
        f"fichiers billetterie (data/raw/sftp/orders/) pour ces matchs"
    )


def test_capacite_salle_positive(con):
    """La capacité de la salle doit toujours être un nombre positif."""
    rows = con.execute(
        "SELECT match_id, capacite_salle FROM gold.fact_match "
        "WHERE capacite_salle IS NULL OR capacite_salle <= 0"
    ).fetchall()
    assert not rows, f"capacite_salle invalide pour : {rows}"


def test_rang_classement_positif(con):
    """Un rang de classement ne peut pas être négatif ou nul."""
    rows = con.execute(
        "SELECT match_id, rang_pbb_avant, rang_adversaire_avant FROM gold.fact_match "
        "WHERE rang_pbb_avant <= 0 OR rang_adversaire_avant <= 0"
    ).fetchall()
    assert not rows, f"rang de classement invalide pour : {rows}"


def test_pas_de_leakage_classement_final(con):
    """
    Vérifie qu'on utilise bien un classement 'avant match', pas le
    classement final de saison, pour éviter le feature leakage identifié
    dans build_gold.py. On vérifie que le rang varie bien d'un match à
    l'autre pour Paris Basketball (un classement final serait constant
    sur toute la table).
    """
    n_valeurs_distinctes = con.execute(
        "SELECT COUNT(DISTINCT rang_pbb_avant) FROM gold.fact_match"
    ).fetchone()[0]
    assert n_valeurs_distinctes > 1, (
        "rang_pbb_avant est constant sur toute la saison -- "
        "suspect de classement final plutôt qu'avant-match"
    )
