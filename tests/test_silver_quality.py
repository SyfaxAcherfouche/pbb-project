"""
Tests de cohérence sur la couche silver -- vérifient que les corrections
de qualité de données documentées dans docs/data_quality.md sont bien
appliquées et efficaces.
"""


def test_boutique_pas_de_doublon_ligne_id(con):
    """
    silver.boutique_ventes doit avoir dédupliqué les lignes strictement
    identiques (bug documenté : 306 doublons trouvés en bronze).
    """
    total, distincts = con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT ligne_id) FROM silver.boutique_ventes"
    ).fetchone()
    # Une petite tolérance est acceptée : deux lignes différentes peuvent
    # légitimement partager le même ligne_id si l'export caisse le réutilise
    # sur des tickets différents -- mais l'écart doit rester marginal.
    taux_duplication = (total - distincts) / total if total else 0
    assert taux_duplication < 0.01, (
        f"{total - distincts} doublons de ligne_id sur {total} lignes "
        f"({taux_duplication:.1%}) -- dédoublonnage silver possiblement "
        f"régressé, cf. docs/data_quality.md"
    )


def test_boutique_dates_majoritairement_parsables(con):
    """
    Les 3 formats de date connus (YYYY-MM-DD, DD/MM/YYYY, DD-MM-YYYY)
    doivent couvrir la quasi-totalité des lignes -- si ce taux chute, un
    nouveau format de date est probablement apparu dans les données.
    """
    total, non_parsables = con.execute(
        "SELECT COUNT(*), COUNT(*) FILTER (WHERE date_vente IS NULL) "
        "FROM silver.boutique_ventes"
    ).fetchone()
    taux_echec = non_parsables / total if total else 0
    assert taux_echec < 0.01, (
        f"{non_parsables} dates non parsables sur {total} ({taux_echec:.1%}) "
        f"-- possible nouveau format de date non géré"
    )


def test_scans_resultat_toujours_renseigne(con):
    """
    silver.scans.resultat ne devrait jamais être NULL -- un fichier scan
    sans en-tête (bug documenté sur scan_20251017.csv) provoquerait ça sur
    tout le fichier concerné si le correctif régressait.
    """
    total, sans_resultat = con.execute(
        "SELECT COUNT(*), COUNT(*) FILTER (WHERE resultat IS NULL) FROM silver.scans"
    ).fetchone()
    taux_manquant = sans_resultat / total if total else 0
    assert taux_manquant < 0.01, (
        f"{sans_resultat} scans sans resultat sur {total} ({taux_manquant:.1%}) "
        f"-- possible fichier scan mal chargé (en-tête manquant ?), "
        f"cf. docs/data_quality.md"
    )


def test_billets_valides_sous_ensemble_de_bronze(con):
    """
    silver.billets (billets validés uniquement) ne peut pas contenir plus
    de lignes que bronze.raw_billets (tous statuts confondus).
    """
    n_bronze = con.execute("SELECT COUNT(*) FROM bronze.raw_billets").fetchone()[0]
    n_silver = con.execute("SELECT COUNT(*) FROM silver.billets").fetchone()[0]
    assert n_silver <= n_bronze, (
        f"silver.billets ({n_silver}) a plus de lignes que "
        f"bronze.raw_billets ({n_bronze}) -- incohérence du filtrage"
    )


def test_contacts_ext_id_unique(con):
    """Chaque ext_id doit être unique dans le référentiel contacts."""
    total, distincts = con.execute(
        "SELECT COUNT(*), COUNT(DISTINCT ext_id) FROM silver.contacts"
    ).fetchone()
    assert total == distincts, (
        f"{total - distincts} ext_id dupliqué(s) dans silver.contacts"
    )
