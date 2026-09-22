# -*- coding: utf-8 -*-
"""
dialog_bilan_data.py
=====================

Calcul du "bilan foncier" annuel, à partir des mêmes requêtes SQL que le
script fourni par le CEN Pays de la Loire, paramétrées par année et exécutées
directement sur le fichier GeoPackage (via le module 'sqlite3' de la
bibliothèque standard Python — aucune dépendance supplémentaire, un
GeoPackage étant une base SQLite).

Ce module est volontairement indépendant de Qt/PyQGIS (aucun import qgis.* ni
qgis.PyQt.*) : il ne fait que lire des données, ce qui le rend facile à
tester ou à réutiliser tel quel.
"""
import os
import sqlite3

# Codes à 4 lettres des sites militaires (champ 'id_site_cen_parc' de parcelles_cen),
# systématiquement exclus des indicateurs "hors sites militaires"
CODES_SITES_MILITAIRES = ('TORP', 'HTF', 'BREI', 'AUVO', 'FONT')


def gpkg_path_from_layer(layer):
    """
    Récupère le chemin du fichier .gpkg à partir de la source d'une couche QGIS
    (ex : '/chemin/vers/fichier.gpkg|layername=sites_cen' -> '/chemin/vers/fichier.gpkg').
    Retourne None si la couche est absente ou si le fichier n'existe pas sur le disque.
    """
    if layer is None:
        return None
    source = layer.source()
    path = source.split('|')[0].strip()
    return path if os.path.isfile(path) else None


def compute_evolution_annuelle(gpkg_path, year_end):
    """
    Calcule, pour chaque année depuis la première année où des données existent
    jusqu'à 'year_end' inclus, la "Surface totale (ha)" — exactement la même requête
    que celle utilisée pour cette carte du tableau de bord (voir 'ha_total' dans
    compute_bilan_foncier), simplement rejouée année par année, avec sa variante "hors
    sites militaires" (même jointure réelle que pour le camembert). Sert au graphique
    linéaire "Évolution annuelle".

    Retourne un dict : {'annees': [...], 'ha_total': [...], 'ha_total_hors_militaire': [...]}
    (listes de même longueur, une valeur par année). Renvoie des listes vides si aucune
    donnée n'est trouvée dans le fichier.
    """
    conn = sqlite3.connect(gpkg_path)
    try:
        cur = conn.cursor()

        def scalar(query, params=()):
            cur.execute(query, params)
            row = cur.fetchone()
            val = row[0] if row else None
            return val if val is not None else 0

        # Première année à afficher : l'année de la plus ancienne acquisition/ORE connue.
        # (Si aucune donnée de date n'existe, on se limite à l'année choisie, un seul point.)
        premiere_date = scalar(
            """SELECT min(d) FROM (
                   SELECT date_acquisition AS d FROM parcelles_cen WHERE date_acquisition IS NOT NULL
                   UNION ALL
                   SELECT date_debut_ore AS d FROM parcelles_cen WHERE date_debut_ore IS NOT NULL
               )""")
        year_start = int(str(premiere_date)[:4]) if premiere_date else year_end

        # Même jointure réelle que pour le camembert "Répartition de la maîtrise foncière" :
        # sites_cen.id_site_cen = parcelles_cen.id_site_fcen_parc, filtrée sur
        # sites_cen.terrain_militaire = 1 (et non la liste de codes en dur utilisée ailleurs).
        militaire_join_excl = """
            AND NOT EXISTS (
                SELECT 1 FROM sites_cen s
                WHERE s.id_site_cen = parcelles_cen.id_site_fcen_parc
                AND s.terrain_militaire = 1
            )"""

        annees, ha_total_serie = [], []
        ha_total_hors_militaire_serie = []

        for year in range(year_start, year_end + 1):
            y_end = f"{year}-12-31"
            y_next_start = f"{year + 1}-01-01"

            ha_total = scalar(
                """SELECT sum(surf_parc_maitrise_ha) FROM parcelles_cen
                   WHERE (date_debut_ore < ? OR date_acquisition < ?)
                   AND (date_fin_ore IS NULL OR date_fin_ore > ?)""",
                (y_next_start, y_next_start, y_end))

            ha_total_hors_militaire = scalar(
                f"""SELECT sum(surf_parc_maitrise_ha) FROM parcelles_cen
                    WHERE (date_debut_ore < ? OR date_acquisition < ?)
                    AND (date_fin_ore IS NULL OR date_fin_ore > ?)
                    {militaire_join_excl}""",
                (y_next_start, y_next_start, y_end))

            annees.append(year)
            ha_total_serie.append(ha_total)
            ha_total_hors_militaire_serie.append(ha_total_hors_militaire)

        return {
            'annees': annees,
            'ha_total': ha_total_serie,
            'ha_total_hors_militaire': ha_total_hors_militaire_serie,
        }
    finally:
        conn.close()


def compute_bilan_foncier(gpkg_path, year):
    """
    Exécute l'ensemble des requêtes du bilan foncier pour l'année 'year' (entier),
    directement sur le fichier GeoPackage. Retourne un dictionnaire de résultats
    (toutes les valeurs numériques sont garanties non None : 0 par défaut).

    Lève une exception (sqlite3.Error) en cas de problème d'accès ou de requête
    invalide (ex : table/colonne absente) ; à charge de l'appelant de l'intercepter
    pour l'afficher proprement à l'utilisateur.
    """
    y_start = f"{year}-01-01"
    y_end = f"{year}-12-31"
    y_next_start = f"{year + 1}-01-01"

    placeholders_mil = ",".join("?" for _ in CODES_SITES_MILITAIRES)

    conn = sqlite3.connect(gpkg_path)
    try:
        cur = conn.cursor()

        def scalar(query, params=()):
            cur.execute(query, params)
            row = cur.fetchone()
            val = row[0] if row else None
            return val if val is not None else 0

        def column_list(query, params=()):
            """Exécute une requête à une seule colonne et retourne la liste des valeurs (non nulles)."""
            cur.execute(query, params)
            return [row[0] for row in cur.fetchall() if row[0] is not None]

        resultats = {}

        # -- Nombre d'actes de propriété signés jusqu'à {year} inclus (valeurs distinctes de
        #    'actes' pour les parcelles en propriété, code_mfu2 = 'P1'), sur la base de la
        #    date d'acquisition --
        resultats['nb_actes_propriete'] = scalar(
            """SELECT count(DISTINCT actes) FROM parcelles_cen
               WHERE code_mfu2 = 'P1' AND date_acquisition < ?""",
            (y_next_start,))

        # -- Nombre de baux emphytéotiques signés jusqu'à {year} inclus et toujours en cours à
        #    cette date (code_mfu2 = 'L1'), sur la base de la date de début d'ORE/bail (même
        #    colonne que pour ha_maitrise_usage, par cohérence avec le reste du plugin), en
        #    excluant les baux déjà expirés au 31/12 de {year} (date_fin_ore dépassée) --
        resultats['nb_actes_bail'] = scalar(
            """SELECT count(DISTINCT actes) FROM parcelles_cen
               WHERE code_mfu2 = 'L1' AND date_debut_ore < ?
               AND (date_fin_ore IS NULL OR date_fin_ore > ?)""",
            (y_next_start, y_end))

        # -- Nombre d'obligations réelles environnementales (ORE) signées jusqu'à {year}
        #    inclus et toujours en cours à cette date (code_mfu2 = 'O'), même logique --
        resultats['nb_actes_ore'] = scalar(
            """SELECT count(DISTINCT actes) FROM parcelles_cen
               WHERE code_mfu2 = 'O' AND date_debut_ore < ?
               AND (date_fin_ore IS NULL OR date_fin_ore > ?)""",
            (y_next_start, y_end))

        # -- Surface RNX (ha) : somme de site_rnx_surface_m2 (en m², convertie en ha) pour les
        #    sites dont site_lien_rnx = 2 (Réserve Naturelle Régionale), créés jusqu'à {year}
        #    inclus (date_crea_site) --
        resultats['ha_rnx'] = scalar(
            """SELECT sum(site_rnx_surface_m2) FROM sites_cen
               WHERE site_lien_rnx = 2 AND date_crea_site < ?""",
            (y_next_start,)) / 10000

        # -- Surface ZPF (ha) : somme de surface_ZPF (déjà en ha) pour les sites dont ZPF = 1,
        #    créés jusqu'à {year} inclus (date_crea_site) --
        resultats['ha_zpf'] = scalar(
            """SELECT sum(surface_ZPF) FROM sites_cen
               WHERE ZPF = 1 AND date_crea_site < ?""",
            (y_next_start,))

        # -- Nombre de nouveaux sites en {year} --
        resultats['nouveaux_sites'] = scalar(
            "SELECT count(*) FROM sites_cen WHERE date_crea_site BETWEEN ? AND ?",
            (y_start, y_end))

        # -- Noms des nouveaux sites créés en {year} --
        resultats['noms_nouveaux_sites'] = column_list(
            "SELECT nom_site FROM sites_cen WHERE date_crea_site BETWEEN ? AND ? ORDER BY nom_site",
            (y_start, y_end))

        # -- Nombre total de sites en {year} --
        resultats['total_sites'] = scalar(
            "SELECT count(*) FROM sites_cen WHERE date_crea_site < ?",
            (y_next_start,))

        # (Anciennement, un indicateur 'ha_total_absolu' était calculé ici sans aucun filtre de
        # date — somme de TOUTES les parcelles, peu importe l'année choisie. Il a été retiré :
        # la carte "Surface totale (ha)" du tableau de bord utilise désormais 'ha_total'
        # ci-dessous, qui est correctement filtré sur l'année sélectionnée.)

        # -- Nombre d'hectares supplémentaires en {year} (hors sites militaires) --
        resultats['ha_supplementaires_hors_militaire'] = scalar(
            f"""SELECT sum(surf_parc_maitrise_ha) FROM parcelles_cen
                WHERE (date_debut_ore BETWEEN ? AND ? OR date_acquisition BETWEEN ? AND ?)
                AND id_site_cen_parc NOT IN ({placeholders_mil})""",
            (y_start, y_end, y_start, y_end, *CODES_SITES_MILITAIRES))

        # -- Nombre d'hectares supplémentaires en {year} (toutes) --
        resultats['ha_supplementaires_total'] = scalar(
            """SELECT sum(surf_parc_maitrise_ha) FROM parcelles_cen
               WHERE date_debut_ore BETWEEN ? AND ? OR date_acquisition BETWEEN ? AND ?""",
            (y_start, y_end, y_start, y_end))

        # -- Nombre total d'hectares (hors sites militaires) en {year} --
        resultats['ha_total_hors_militaire'] = scalar(
            f"""SELECT sum(surf_parc_maitrise_ha) FROM parcelles_cen
                WHERE id_site_cen_parc NOT IN ({placeholders_mil})
                AND (date_debut_ore < ? OR date_acquisition < ?)
                AND (date_fin_ore IS NULL OR date_fin_ore > ?)""",
            (*CODES_SITES_MILITAIRES, y_next_start, y_next_start, y_end))

        # -- Nombre total d'hectares de sites militaires en {year} --
        resultats['ha_total_militaire'] = scalar(
            f"""SELECT sum(surf_parc_maitrise_ha) FROM parcelles_cen
                WHERE id_site_cen_parc IN ({placeholders_mil})
                AND (date_debut_ore < ? OR date_acquisition < ?)
                AND (date_fin_ore IS NULL OR date_fin_ore > ?)""",
            (*CODES_SITES_MILITAIRES, y_next_start, y_next_start, y_end))

        # -- Nombre total d'hectares en {year} (toutes) --
        resultats['ha_total'] = scalar(
            """SELECT sum(surf_parc_maitrise_ha) FROM parcelles_cen
               WHERE (date_debut_ore < ? OR date_acquisition < ?)
               AND (date_fin_ore IS NULL OR date_fin_ore > ?)""",
            (y_next_start, y_next_start, y_end))

        # -- Nombre de communes concernées en {year} --
        resultats['nb_communes'] = scalar(
            """SELECT count(distinct insee_com) FROM parcelles_cen
               WHERE (date_debut_ore < ? OR date_acquisition < ?)
               AND (date_fin_ore IS NULL OR date_fin_ore > ?)""",
            (y_next_start, y_next_start, y_end))

        # -- Nombre d'hectares en propriété du CEN en {year} --
        resultats['ha_propriete'] = scalar(
            """SELECT sum(surf_parc_maitrise_ha) FROM parcelles_cen
               WHERE code_mfu2 = 'P1'
               AND (date_acquisition < ? OR date_debut_ore < ?)
               AND (date_fin_ore IS NULL OR date_fin_ore > ?)""",
            (y_next_start, y_next_start, y_end))

        # -- Nombre d'hectares sous maîtrise d'usage (ORE / baux) en {year} --
        resultats['ha_maitrise_usage'] = scalar(
            """SELECT sum(surf_parc_maitrise_ha) FROM parcelles_cen
               WHERE code_mfu2 IN ('O', 'L1')
               AND (date_debut_ore < ? OR date_acquisition < ?)
               AND (date_fin_ore IS NULL OR date_fin_ore > ?)""",
            (y_next_start, y_next_start, y_end))

        # -- Nombre d'hectares en convention de gestion en {year} --
        resultats['ha_convention_gestion'] = scalar(
            """SELECT sum(surf_parc_maitrise_ha) FROM parcelles_cen
               WHERE code_mfu2 in ('C7', 'C8')
               AND (date_debut_ore < ? OR date_acquisition < ?)
               AND (date_fin_ore IS NULL OR date_fin_ore > ?)""",
            (y_next_start, y_next_start, y_end))

        # -- Variantes "hors sites militaires" des 3 requêtes ci-dessus, pour le camembert
        #    "Répartition de la maîtrise foncière" (case à cocher dédiée dans l'interface).
        #    Contrairement aux indicateurs plus haut (qui excluent une liste fixe de codes de
        #    sites, CODES_SITES_MILITAIRES), on se base ici sur une VRAIE jointure avec
        #    sites_cen.terrain_militaire, via la même clé que la vue parcellaire
        #    (sites_cen.id_site_cen = parcelles_cen.id_site_fcen_parc) : c'est donc bien la
        #    case "Terrain militaire" cochée dans la fiche du site qui fait foi.
        militaire_join_excl = """
            AND NOT EXISTS (
                SELECT 1 FROM sites_cen s
                WHERE s.id_site_cen = parcelles_cen.id_site_fcen_parc
                AND s.terrain_militaire = 1
            )"""

        resultats['ha_propriete_hors_militaire'] = scalar(
            f"""SELECT sum(surf_parc_maitrise_ha) FROM parcelles_cen
                WHERE code_mfu2 = 'P1'
                AND (date_acquisition < ? OR date_debut_ore < ?)
                AND (date_fin_ore IS NULL OR date_fin_ore > ?)
                {militaire_join_excl}""",
            (y_next_start, y_next_start, y_end))

        resultats['ha_maitrise_usage_hors_militaire'] = scalar(
            f"""SELECT sum(surf_parc_maitrise_ha) FROM parcelles_cen
                WHERE code_mfu2 IN ('O', 'L1')
                AND (date_debut_ore < ? OR date_acquisition < ?)
                AND (date_fin_ore IS NULL OR date_fin_ore > ?)
                {militaire_join_excl}""",
            (y_next_start, y_next_start, y_end))

        resultats['ha_convention_gestion_hors_militaire'] = scalar(
            f"""SELECT sum(surf_parc_maitrise_ha) FROM parcelles_cen
                WHERE code_mfu2 in ('C7', 'C8')
                AND (date_debut_ore < ? OR date_acquisition < ?)
                AND (date_fin_ore IS NULL OR date_fin_ore > ?)
                {militaire_join_excl}""",
            (y_next_start, y_next_start, y_end))

        resultats['ha_total_hors_militaire_join'] = scalar(
            f"""SELECT sum(surf_parc_maitrise_ha) FROM parcelles_cen
                WHERE (date_debut_ore < ? OR date_acquisition < ?)
                AND (date_fin_ore IS NULL OR date_fin_ore > ?)
                {militaire_join_excl}""",
            (y_next_start, y_next_start, y_end))

        # -- Nombre d'hectares de sites Natura 2000 (cumulé jusqu'à {year}) --
        resultats['ha_natura2000'] = scalar(
            """SELECT round(sum(n2000_surface_m2) / 10000, 4) FROM sites_cen
               WHERE n2000_directive IN ('ZPS', 'ZSC', 'ZPS_ZSC')
               AND date_crea_site < ?""",
            (y_next_start,))

        return resultats
    finally:
        conn.close()
