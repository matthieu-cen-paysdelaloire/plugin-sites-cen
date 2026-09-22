# -*- coding: utf-8 -*-
"""
Fonctions de construction des dictionnaires associant les champs de la couche SIG
aux widgets du formulaire (self.txtXxx, self.cbXxx, ...).

Contrairement à dialog_data.py, ces dictionnaires ont besoin d'une instance du
dialogue (dlg) déjà passée par setupUi(), puisqu'ils référencent directement les
widgets. Ils sont donc construits par de simples fonctions prenant "dlg" en
paramètre, appelées une fois depuis __init__.
"""
from . import dialog_data as data


def build_parcelle_field_map(dlg):
    """
    Dictionnaire associant chaque champ de parcelles_cen à son widget (lecture
    seule, visualisation uniquement).
    """
    return {
        "num_prefixe": dlg.txtParcNumPrefixe,
        "num_section": dlg.txtParcNumSection,
        "num_parc_seul": dlg.txtParcNumParcSeul,
        "nom_site": dlg.txtParc_nom_site,
        "num_site": dlg.txtParc_num_site,
        "id_site_cen_parc": dlg.txtParc_id_site_cen_parc,
        "id_site_fcen_parc": dlg.txtParc_id_site_fcen_parc,
        "insee_com": dlg.txtParc_insee_com,
        "insee_dep": dlg.txtParc_insee_dep,
        "pour_part": dlg.txtParc_pour_part,
        "surf_parc_maitrise_ha": dlg.txtParc_surf_parc_maitrise_ha,
        "surf_parc_maitrise_m2": dlg.txtParc_surf_parc_maitrise_m2,
        "s_sig_ha": dlg.txtParc_s_sig_ha,
        "code_mfu1": dlg.txtParc_code_mfu1,
        "code_mfu2": dlg.txtParc_code_mfu2,
        "type_prop": dlg.txtParc_type_prop,
        "domaine_public": dlg.txtParc_domaine_public,
        "parc_gestion_rnx": dlg.txtParc_parc_gestion_rnx,
        "bnd": dlg.txtParc_bnd,
        "parc_N2000": dlg.txtParc_parc_N2000,
        "source_geom_parc_nature": dlg.txtParc_source_geom_parc_nature,
        "source_geom_parc_date": dlg.txtParc_source_geom_parc_date,
        "echelle_num_parc": dlg.txtParc_echelle_num_parc,
        "source_surf_parc": dlg.txtParc_source_surf_parc,
        "date_maj_parcelle": dlg.txtParc_date_maj_parcelle,
        "date_maj_p": dlg.txtParc_date_maj_p,
        "id_proprietaire": dlg.txtParc_id_proprietaire,
        "proprietaires": dlg.txtParc_proprietaires,
        "tresfonds": dlg.txtParc_tresfonds,
        "fdd": dlg.txtParc_fdd,
        "doc_foncier": dlg.txtParc_doc_foncier,
        "source_doc_foncier": dlg.txtParc_source_doc_foncier,
        "date_acquisition": dlg.txtParc_date_acquisition,
        "mesure_compens": dlg.txtParc_mesure_compens,
        "surf_ore_m2": dlg.txtParc_surf_ore_m2,
        "date_debut_ore": dlg.txtParc_date_debut_ore,
        "date_fin_ore": dlg.txtParc_date_fin_ore,
        "ZPF": dlg.txtParc_ZPF,
        "mode_ZPF": dlg.txtParc_mode_ZPF,
        "surface_ZPF": dlg.txtParc_surface_ZPF,
        "date_ZPF": dlg.txtParc_date_ZPF,
        "intervention_SAFER": dlg.txtParc_intervention_SAFER,
        "financeurs": dlg.txtParc_financeurs,
        "prix_ha_net_vendeur": dlg.txtParc_prix_ha_net_vendeur,
        "prix_ha_achat": dlg.txtParc_prix_ha_achat,
        "actes": dlg.txtParc_actes,
        "remarques": dlg.txtParc_remarques,
    }


def build_site_readonly_field_map(dlg):
    """
    Dictionnaire associant chaque champ complémentaire de sites_cen à son widget
    (lecture seule, visualisation uniquement, aucune sauvegarde possible).
    """
    return {
        "id_site_cen": dlg.txtSite_id_site_cen,
        "id_site_inpn": dlg.txtSite_id_site_inpn,
        "nom_site": dlg.txtSite_nom_site,
        "num_site": dlg.txtSite_num_site,
        "id_rnx_inpn": dlg.txtSite_id_rnx_inpn,
        "code_departement": dlg.txtSite_code_departement,
        "code_compta": dlg.txtSite_code_compta,
        "ens": dlg.txtSite_ens,
        "site_cdl": dlg.txtSite_site_cdl,
        "site_classe": dlg.txtSite_site_classe,
        "site_cen_communicable": dlg.txtSite_site_cen_communicable,
        "site_marin": dlg.txtSite_site_marin,
        "n2000_directive": dlg.txtSite_n2000_directive,
        "n2000_surface_m2": dlg.txtSite_n2000_surface_m2,
        "surf_carto_habitat_m2": dlg.txtSite_surf_carto_habitat_m2,
        "surf_sig_ha": dlg.txtSite_surf_sig_ha,
        "surf_sylvae_m2": dlg.txtSite_surf_sylvae_m2,
        "date_crea_site": dlg.txtSite_date_crea_site,
        "date_maj_site": dlg.txtSite_date_maj_site,
        "date_maj_s": dlg.txtSite_date_maj_s,
        "nature_perimetre": dlg.txtSite_nature_perimetre,
        "source_geom_site_nature": dlg.txtSite_source_geom_site_nature,
        "source_geom_site_date": dlg.txtSite_source_geom_site_date,
        "echelle_num_site": dlg.txtSite_echelle_num_site,
        "precision_num_site": dlg.txtSite_precision_num_site,
        "operateur": dlg.txtSite_operateur,
        "lien_vers_actes": dlg.txtSite_lien_vers_actes,
        "prix": dlg.txtSite_prix,
        "doc_justif_admin": dlg.txtSite_doc_justif_admin,
        "ZPF": dlg.txtSite_ZPF,
        "mode_ZPF": dlg.txtSite_mode_ZPF,
        "surface_ZPF": dlg.txtSite_surface_ZPF,
        "date_ZPF": dlg.txtSite_date_ZPF,
    }


def build_field_map(dlg):
    """
    Dictionnaire permettant la connexion entre les champs de la table SIG et les
    widgets modifiables du formulaire.
    """
    return {
        "site_lien_rnx": dlg.cbLienRNX, "site_rnx_surface_m2": dlg.spinRNX,
        "terrain_militaire": dlg.cbMilitaire, "nbre_contrat_agri": dlg.spinContrats,
        "nb_agri": dlg.spinAgri, "surf_contra_m2": dlg.spinSurfContrat,
        "code_milieu_princ": dlg.cbType_milieu, "nature_site_inpn": dlg.cbNatureInpn,
        "geol_site_inpn": dlg.cbGeolInpn, "carto_habitats": dlg.cbCartoHab,
        "typo_carto_habitat": dlg.cbTypoHab, "gestionnaire_site": dlg.txtGestionnaire,
        "surf_libre_evolution_m2": dlg.spinLibreEvo, "doc_gestion_presence": dlg.cbDocPres,
        "doc_gestion_nom": dlg.txtDocNom, "doc_gestion_evaluation": dlg.cbDocEval,
        "surf_doc_gestion_m2": dlg.spinSurfDoc, "url_fiche_inpn": dlg.txtUrlInpn,
        "url_fiche_cen": dlg.txtUrlCen, "ouverture_public": dlg.cbOuverture,
        "description_site": dlg.txtDescription, "url_site_photo": dlg.txtUrlPhoto,
        "sensibilite": dlg.cbSensibilite, "non_diffusion": dlg.cbNonDiffusion,
        "remq_sensibilite": dlg.txtRemqSensibilite, "code_geol": dlg.txtGeolResult,
        "doc_gestion_date_ini": dlg.dateIni, "doc_gestion_date_maj": dlg.dateMaj, "doc_gestion_date_fin": dlg.dateFin,
        "responsable_de_site": dlg.txtSite_responsable_de_site,
    }


def build_date_null_checkboxes(dlg):
    """
    Association de chaque champ date optionnel à sa case "Non renseignée" : quand
    elle est cochée, le champ correspondant est sauvegardé comme NULL (et grisé).
    """
    return {
        dlg.dateIni: dlg.chkDateIniNull,
        dlg.dateMaj: dlg.chkDateMajNull,
        dlg.dateFin: dlg.chkDateFinNull,
    }


def build_combo_dicts(dlg):
    """
    Associe CHAQUE combobox de valeurs à SON dictionnaire de données (et lui seul),
    pour éviter toute confusion entre des listes qui partagent certaines valeurs
    (ex : plusieurs listes utilisent 0/1, ou "OUI"/"NON").
    """
    return {
        dlg.cbLienRNX: data.DICT_RNX,
        dlg.cbMilitaire: data.DICT_MILITAIRE,
        dlg.cbType_milieu: data.DICT_TYPE_MILIEU,
        dlg.cbCartoHab: data.DICT_CARTO,
        dlg.cbTypoHab: data.DICT_TYPO,
        dlg.cbDocPres: data.DICT_DOC_PRES,
        dlg.cbOuverture: data.DICT_OUI_NON,
        dlg.cbSensibilite: data.DICT_OUI_NON,
        dlg.cbNonDiffusion: data.DICT_OUI_NON,
        dlg.cbNatureInpn: data.DICT_NATURE,
        dlg.cbGeolInpn: data.DICT_GEOL,
        dlg.cbDocEval: data.DICT_DOC_EVAL,
    }
