# -*- coding: utf-8 -*-
"""
Données métier statiques utilisées par AttributeEditorSitesCENDialog.

Ce module ne contient QUE des données pures (dictionnaires de correspondance,
textes d'aide) et une fonction utilitaire de tri : rien ici ne dépend d'un
widget Qt ou d'une instance du dialogue. Objectif : isoler ces gros blocs de
données (auparavant définis en dur dans __init__) pour alléger le fichier
principal, sans changer la moindre valeur ni le moindre comportement.
"""
import unicodedata


def alpha_sort_key(text):
    """
    Clé de tri alphabétique insensible à la casse ET aux accents (ex : "Étang" se trie
    comme "etang"), sans dépendre des paramètres régionaux (locale) du système d'exploitation.
    """
    normalized = unicodedata.normalize('NFKD', text or "")
    stripped = ''.join(c for c in normalized if not unicodedata.combining(c))
    return stripped.lower()


# Dictionnaires de traduction "valeur brute -> description", utilisés UNIQUEMENT pour
# l'affichage en lecture seule des parcelles (aide à la compréhension des codes stockés
# en base, sans jamais permettre de saisie).
PARCELLE_VALUE_DICTS = {
    "pour_part": {"1": "OUI", "0": "NON"},
    "bnd": {"1": "OUI", "0": "NON"},
    "code_mfu1": {
        "P": "[P] Propriétés",
        "L": "[L] Contrats de gestion ≥ 18 ans",
        "C": "[C] Contrats de gestion 18 ans",
        "O": "[O] Obligations réelles environnementales",
    },
    "code_mfu2": {
        "P1": "[P1] acquisition réalisées par le CEN, pleines ou indivises",
        "P2": "[P2] usufruit temporaire au bénéfice du CEN",
        "L1": "[L1] bail emphytéotique (\"classique\" et administratif)",
        "L4": "[L4] bail civil",
        "L6": "[L6] prêt à usage / commodat",
        "L7": "[L7] convention d'usage / de gestion / de mise à disposition",
        "L8": "[L8] convention de gestion avec le Conservatoire du littoral",
        "L17": "[L17] accord oraux",
        "L18": "[L18] autre",
        "L19": "[L19] convention de gestion sur domaine public de l'Etat",
        "L20": "[L20] convention de gestion sur domaine privé de l'Etat",
        "C4": "[C4] bail civil",
        "C5": "[C5] bail rural au bénéfice du CEN",
        "C6": "[C6] prêt à usage / commodat",
        "C7": "[C7] convention d'usage / de gestion / de mise à disposition",
        "C8": "[C8] convention de gestion avec le Conservatoire du littoral",
        "C11": "[C11] autorisation d'occupation temporaire ou tout autre contrat sur domaine public de l'Etat",
        "C12": "[C12] convention d'occupation temporaire ou tout autre contrat sur domaine privé de l'Etat",
        "C17": "[C17] accord oraux",
        "C18": "[C18] autre",
        "C19": "[C19] convention de gestion sur domaine public de l'Etat",
        "C20": "[C20] convention de gestion sur domaine privé de l'Etat",
        "O": "[O] Obligations réelles environnementales",
    },
    "type_prop": {
        "1_PRI": "Privé (PRI) - Personne physique",
        "2_0_MIX": "Public / Privé (MIX) - Personnes morales non remarquables",
        "2_1_PUB": "Public (PUB) - État",
        "2_2_PUB": "Public (PUB) - Religion",
        "2_3_PUB": "Public (PUB) - Département",
        "2_4_COM": "Communal (COM) - Commune",
        "2_5_PUB": "Public (PUB) - Officie HLM",
        "2_6_PRI": "Privé (PRI) - Personnes morales représentant des sociétés d'économie mixte",
        "2_7_PRI": "Privé (PRI) - Copropriétaires",
        "2_8_PRI": "Privé (PRI) - Associés",
        "2_9_PUB": "Public (PUB) - Etablissements publics ou organismes associés",
        "3_CEN": "Conservatoire d'espaces naturels (CEN) et fond de dotation",
    },
    "mesure_compens": {"1": "OUI", "0": "NON"},
    "doc_foncier": {"1": "OUI", "0": "NON"},
    "parc_gestion_rnx": {"1": "OUI", "0": "NON"},
    "source_geom_parc_nature": {
        "0": "inconnue",
        "1": "Numérisation manuelle CEN",
        "2": "Bd Parcellaire IGN",
        "3": "Plan cadastral informatisé (PCI)",
        "4": "BD Ortho IGN",
        "5": "Scan 25 IGN",
        "6": "BD Topo IGN",
        "7": "BD Adresse",
        "8": "Bd Carto",
        "9": "autre",
        "10": "ETALAB",
    },
    "echelle_num_parc": {
        "0": "inconnue",
        "1": "500",
        "2": "1000",
        "3": "2000",
        "4": "5000",
        "5": "10000",
        "6": "25000",
        "7": "autre",
    },
    "source_surf_parc": {
        "0": "inconnue",
        "1": "DGFIP (fichiers fonciers, visuDGFIP)",
        "2": "document justificatif (contrat, convention, acte)",
        "3": "autre",
    },
    "domaine_public": {"1": "OUI", "0": "NON"},
    "fdd": {"1": "OUI", "0": "NON"},
    "ZPF": {"1": "OUI", "0": "NON"},
    "intervention_SAFER": {"1": "OUI", "0": "NON"},
    "parc_N2000": {
        "ZPS": "Directive oiseaux - Zones de Protection Spéciale (ZPS)",
        "ZSC": "Directive habitat - Zones Spéciales de Conservation (SIC - ZSC)",
        "ZPS_ZSC": "Concerné par les deux directives (ZPS + ZSC)",
        "0": "Non concerné par un site Natura 2000",
    },
}


# Dictionnaires de traduction "valeur brute -> description", utilisés UNIQUEMENT pour
# l'affichage en lecture seule des sites (aide à la compréhension des codes stockés en
# base, sans jamais permettre de saisie).
SITE_VALUE_DICTS = {
    "ens": {"1": "OUI", "0": "NON"},
    "site_cdl": {"1": "oui totalement", "2": "oui en partie", "0": "non"},
    "n2000_directive": {
        "ZPS": "Directive oiseaux - Zones de Protection Spéciale (ZPS)",
        "ZSC": "Directive habitat - Zones Spéciales de Conservation (SIC - ZSC)",
        "ZPS_ZSC": "Concerné par les deux directives (ZPS + ZSC)",
        "0": "Non concerné par un site Natura 2000",
    },
    "site_marin": {"T": "Vrai", "F": "Faux"},
    "nature_perimetre": {
        "0": "inconnue",
        "1": "fusion des parcelles maîtrisées (foncier et/ou usage)",
        "2": "unité écologique cohérente / unité de gestion",
        "3": "autres",
    },
    "source_geom_site_nature": {
        "0": "inconnue",
        "1": "numérisation manuelle CEN",
        "2": "Bd Parcellaire IGN",
        "3": "plan cadastral informatisé (PCI)",
        "4": "BD ortho IGN",
        "5": "Scan 25 IGN",
        "6": "BD Topo IGN",
        "7": "BD Adresse",
        "8": "BD Carto",
        "9": "autre",
        "10": "ETALAB",
    },
    "echelle_num_site": {
        "0": "inconnue",
        "1": "500",
        "2": "1000",
        "3": "2000",
        "4": "5000",
        "5": "10000",
        "6": "25000",
        "7": "autre",
    },
    "precision_num_site": {
        "DM": "Décimétrique",
        "M": "Métrique",
        "DC": "Décamétrique",
        "HM": "Hectométrique",
        "KM": "Kilométrique",
        "NE": "Non estimée",
    },
    "doc_justif_admin": {"1": "OUI", "0": "NON"},
    "ZPF": {"1": "OUI", "0": "NON"},
}


# Contient les valeurs à renseigner dans la table, pour les listes déroulantes
DICT_RNX = {"-- À renseigner --": "NULL", "Le site ne correspond à aucune réserve": 0, "Le site correspond à une Réserve Naturelle Nationale (RNN)": 1, "Le site correspond à une Réserve Naturelle Régionale (RNR)": 2, "Le site correspond exactement à une Réserve Naturelle Corse (RNC)": 3}
DICT_MILITAIRE = {"-- À renseigner --": "NULL", "OUI": 1, "NON": 0}
DICT_TYPE_MILIEU = {"-- À renseigner --": "NULL", "Inconnu" : "0", "Toubière et Marais" : "1", "Pelouses sèches" : "2", "Landes, fruticées et prairies" : "3", "Écosystèmes alluviaux" : "4", "Gîtes à Chiroptères" : "5", "Écosystèmes littoraux et marins" : "6", "Écosystèmes aquatiques" : "7", "Écosystèmes forestiers" : "8", "Écosystèmes lacustres" : "9", "Milieux variés" : "10", "Milieux rupestres ou rocheux" : "11", "Milieux artificialisés (carrières, terrils, gravières ...)" : "12", "Sites géologiques" : "13", "Écosystèmes montagnards" : "14", "Autres" : "16"}
DICT_NATURE = {"-- À renseigner --": "NULL", "Ne sais pas": "N", "Vrai": "T", "Faux": "F"}
DICT_GEOL = {"-- À renseigner --": "NULL", "Ne sais pas": "N", "Vrai": "V", "Faux": "F"}
DICT_CARTO = {"-- À renseigner --": "NULL", "Site non cartographié": 0, "Site partiellement cartographié": 1, "Site entièrement cartographié": 2}
DICT_TYPO = {"-- À renseigner --": "NULL", "Inconnue": 0, "Corine biotopes": 1, "EUNIS": 2, "Prodromes des végétations de France (PVF)": 3, "Autre": 4}
DICT_DOC_PRES = {"-- À renseigner --": "NULL", "OUI": 1, "NON": 0}
DICT_DOC_EVAL = {"-- À renseigner --": "NULL", "Pas d'évaluation": "Null", "Evaluation intermédiaire": "Evaluation intermédiaire", "Evaluation finale": "Evaluation finale"}
DICT_OUI_NON = {"-- À renseigner --": "NULL", "OUI": 1, "NON": 0}

DICT_GEOL_STEP = {
    "-- À renseigner --": "",
    "Présence d'objets géologiques": {
        "-- À renseigner --": "",
        "Présence de patrimoine géologique": 10,
        "Patrimoine géologique identifié en se basant sur l'IRPG": {
            "-- À renseigner --": "",
            "Le site correspond exactement à un périmètre IRPG": {"-- À renseigner --": "", "Patrimoine géologique géré": 1111, "Patrimoine géologique non géré": 1112},
            "Le site est contenu entièrement au sein d'un périmètre IRPG": {"-- À renseigner --": "", "Patrimoine géologique géré": 1121, "Patrimoine géologique non géré": 1122},
            "Le site contient entièrement un périmètre IRPG": {"-- À renseigner --": "", "Patrimoine géologique géré": 1131, "Patrimoine géologique non géré": 1132},
            "Le site intersecte un périmètre IRPG": {"-- À renseigner --": "", "Patrimoine géologique géré": 1141, "Patrimoine géologique non géré": 1142}
        },
        "Patrimoine géologique identifié à dire d'expert": {
            "-- À renseigner --": "", "Site à vocation géologique, géré pour cela": 121,
            "Site géré pour sa biodiversité mais qui présente également du patrimoine géolgique": {"-- À renseigner --": "", "Patrimoine géologique géré": 1221, "Patrimoine géologique non géré": 1222}
        },
    },
    "Site à vocation purement biologique": {"-- À renseigner --": "", "Absence de site géologique en limite ou dans le voisinage": 21, "Présence d'un site géologique en limite ou dans le voisinage": 22},
    "On ne sais pas si le site présente des objets géologiques...": {"-- À renseigner --": "", "Absence de site géologique en limite ou dans le voisinage": 31, "Présence d'un site géologique en limite ou dans le voisinage": 32},
    "Objets géologiques ordinaires...": {"-- À renseigner --": "", "Absence de site géologique en limite ou dans le voisinage": 41, "Présence d'un site géologique en limite ou dans le voisinage": 42}
}


# Textes d'aide affichés en infobulle (❓) au survol de chaque label concerné. La clé
# correspond au nom (objectName) du label dans le fichier .ui.
HELP_TEXTS = {
    "lblGlobalHelp": (
        "<b>Comment fonctionne l'outil :</b><br><br>"
        "• <b>Filtres</b> (en haut à gauche) : tapez du texte dans \"Filtrer les sites...\" pour "
        "chercher un site par nom, et/ou choisissez un responsable dans la liste déroulante "
        "juste à côté pour n'afficher que ses sites.<br><br>"
        "• <b>Aide sur les champs (❓)</b> : à côté du nom de chaque champ, passez simplement le "
        "curseur de la souris sur le ❓ pour afficher sa description - pas besoin de cliquer "
        "dessus, et cela fonctionne à tout moment, que le mode édition soit activé ou non.<br><br>"
        "• <b>Mode édition</b> (bouton \"✏️ Activer le mode édition\") : par défaut, les champs "
        "du formulaire sont verrouillés (lecture seule) pour éviter les modifications "
        "accidentelles. Cliquez sur ce bouton pour pouvoir les modifier.<br><br>"
        "• <b>Voir les parcelles du site</b> (sous la liste des sites) : affiche, pour le site "
        "actuellement sélectionné, la liste de ses parcelles cadastrales et leurs "
        "propriétaires. Cliquez à nouveau sur le bouton pour revenir à la liste des sites.<br><br>"
        "• <b>Enregistrer les modifications</b> : le bouton \"Appliquer\" sauvegarde le site "
        "actuellement affiché sans fermer la fenêtre (pratique pour enchaîner plusieurs sites) ; "
        "le bouton \"OK\" sauvegarde et ferme la fenêtre ; \"Annuler\" ferme sans sauvegarder."
    ),
    "lblBilanHelp": (
        "<b>Comment fonctionne le bilan foncier :</b><br><br>"
        "• Choisissez l'année avec les boutons − / + (ou en saisissant directement le "
        "chiffre), puis cliquez sur \"Générer le bilan\".<br><br>"
        "• Les chiffres clés en haut résument l'année choisie (nouveaux sites, surfaces, "
        "communes, Natura 2000...).<br><br>"
        "• Dans l'onglet \"Graphiques\", cliquez sur une barre ou une part de camembert pour "
        "afficher sa valeur exacte en hectares (et son pourcentage pour le camembert).<br><br>"
        "• L'onglet \"Nouveaux sites\" liste les sites créés au cours de l'année choisie."
    ),
    "label_rnx": "Le site est-il inclus dans une réserve naturelle (nationale, régionale, corse) ?",
    "label_num": "Surface totale du site déclarée dans le cadre de la RNX (en m²).",
    "label_militaire": "Le site est-il un terrain militaire ? (entièrement ou en partie)",
    "label_contrats": "Nombre de contrats agricole (0 est une réponse possible).",
    "label_agri": "Nombre d’agriculteurs sous contrat (écrit ou oral) sur le site (0 est une réponse possible).",
    "label_surf_contrat": "Superficie (en m²) du site sous contrat (écrit ou oral) avec un ou N agriculteurs (0 est une réponse possible).",
    "label_type_milieu": "Milieu naturel prédominant sur le site.",
    "label_nature": "Le site est-il classé pour protéger des éléments du patrimoine naturel ?",
    "label_geol": "Le site est-il classé pour protéger des éléments du patrimoine géologique ?",
    "label_carto_hab": "Existe-t-il une cartographie d'habitats naturels sur le site ? Est-elle complète ou pas ?",
    "label_typo_hab": "Quel est la typologie utilisée pour la cartographie d'habitats ou de végétation.<br><br> Si plusieurs typologies ont été utilisées, prenez celle qui a le plus été utilisé lors de la cartographie d'habitat",
    "label_gestionnaire": "Organisme localement responsable de la gestion de l'espace naturel protégé.",
    "label_surf_libre": "Surface du site laissée en libre évolution (en m²).",
    "label_doc_pres": "Existe-t-il un plan de gestion ou un document notifiant l'action du CEN ? La mise en place en cours d'un plan de gestion est considérée comme recevable pour répondre OUI.",
    "label_doc_nom": "Titre complet du document de gestion en vigueur.<br> Mettez '/' s'il n'y a pas de document de gestion.",
    "label_doc_eval": "Résultat de la dernière évaluation du plan de gestion.",
    "label_date_ini": "Date de mise en œuvre initiale du document de gestion.<br> Cocher la case 'Pas de date à renseigner' s'il n'y a pas de date à renseigner.",
    "label_date_maj": "Date de la dernière mise à jour du document.<br> Cocher la case 'Pas de date à renseigner' s'il n'y a pas de date à renseigner.",
    "label_date_fin": "Date d'échéance ou de fin de validité du document.<br> Cocher la case 'Pas de date à renseigner' s'il n'y a pas de date à renseigner.",
    "label_surf_doc": "Surface couverte par le document de gestion actuel (en m²).",
    "label_url_inpn": "Lien d'accès direct (adresse https) vers la fiche de l'inventaire national du patrimoine naturel.",
    "label_url_cen": "Lien d'accès direct (adresse https) vers la page web du site naturel dédiée sur le site web du CEN.",
    "label_ouverture": "Le site est-il accessible au public ?",
    "label_desc": "Résumé des enjeux et caractéristiques principales du site.",
    "label_url_photo": "Lien d'accès direct (adresse https) vers une photographie représentative du paysage.<br><br> Si vous possédez une photographie de votre site sur le serveur commun, vous pouvez récupérer le lien 'https' en faisant un clic droit, puis cliquez sur 'copier le lien'.",
    "label_sensi": "Le site est-il sensible à la diffusion au grand public?<br> (Les données foncières sont envoyés à fédération des CEN, afin de les valoriser sur une grand cartographie web diffusable au grand public.)",
    "label_diffusion": "Si le site est sensible à la diffusion au grand public, est-ce pour des raisons de partenariat ?",
    "label_remq_sensi": "Précisions sur les raisons de la sensibilité ou de la non-diffusion.",

    "lbl_txtSite_responsable_de_site": "Personne ou organisme responsable du suivi de ce site.",
    "lbl_txtSite_id_site_cen": "Identifiant unique du site interne au CEN",
    "lbl_txtSite_id_site_inpn": "Identifiant unique INPN du site",
    "lbl_txtSite_nom_site": "Libellée du site",
    "lbl_txtSite_num_site": "Numéro du site",
    "lbl_txtSite_id_rnx_inpn": "Identifiant unique de la réserve naturelle (régionale, nationale ou Corse) liée au site",
    "lbl_txtSite_code_departement": "Codes des départements concernées par le site CEN",
    "lbl_txtSite_code_compta": "Code d'identification (comptabilité) du site naturel",
    "lbl_txtSite_ens": "S'agit-il d'un site en espace naturel sensible ?",
    "lbl_txtSite_site_cdl": "S'agit-il d'un site du Conservatoire du Littoral ?",
    "lbl_txtSite_site_classe": "",
    "lbl_txtSite_site_cen_communicable": "Le site est-il communicable au grand public ? Est-ce un site officiel ?",
    "lbl_txtSite_site_marin": "S'agit-il d'un site marin ? ",
    "lbl_txtSite_n2000_directive": "Directive concernée par un site CEN situé (entièrement ou en partie) sur site Natura 2000",
    "lbl_txtSite_n2000_surface_m2": "Superficie (en m²) du site concerné par un site Natura 2000 (totale ou partielle du site selon les cas)",
    "lbl_txtSite_surf_carto_habitat_m2": "Superficie en (m²) de la cartographie d'habitats réalisée (entièrement ou partie) sur le site",
    "lbl_txtSite_surf_sig_ha": "La surface informatique de la parcelle (avec le $area) (en hectares)",
    "lbl_txtSite_surf_sylvae_m2": "Superficie (en m²) des forêts sylvie présentes sur le site CEN",
    "lbl_txtSite_date_crea_site": "Date de création du site",
    "lbl_txtSite_date_maj_site": "Date de dernière mise à jour des attributs de la donnée du site",
    "lbl_txtSite_date_maj_s": "Date de dernière mise à jour de la géométrie du site",
    "lbl_txtSite_nature_perimetre": "La nature du périmètre du site",
    "lbl_txtSite_source_geom_site_nature": "Référentiel utilisé pour la délimitation du périmètre du site",
    "lbl_txtSite_source_geom_site_date": "Millésime de la carte ou du référentiel de saisie ayant servi de source géométrique",
    "lbl_txtSite_echelle_num_site": "Echelle de numérisation du site",
    "lbl_txtSite_precision_num_site": "Ordre de grandeur de la précision relative de la saisie",
    "lbl_txtSite_operateur": " Organisme assurant le rôle d'opérateur technique chargé de la production ou de la collecte des données auprès de l'INPN",
    "lbl_txtSite_lien_vers_actes": "Lien d'accès direct (adresse https) vers l'acte de propriété du site",
    "lbl_txtSite_prix": "",
    "lbl_txtSite_doc_justif_admin": "Existe-il un document(s) administratif(s) ?",
    "lbl_txtSite_ZPF": "La parcelle est-elle située dans une Zone de Protection Forte ?",
    "lbl_txtSite_mode_ZPF": "Mode d'action de la parcelle en ZPF",
    "lbl_txtSite_surface_ZPF": "Surface de la parcelle en ZPF",
    "lbl_txtSite_date_ZPF": "Date de la parcelle en ZPF",

    "lbl_txtParc_nom_site": "Nom du site CEN contenant la parcelle",
    "lbl_txtParc_num_site": "Numéro d'identification (attribué par le CEN Pays la Loire) du site CEN",
    "lbl_txtParc_id_site_cen_parc": "Code à 4 lettres d'identification du site CEN",
    "lbl_txtParc_id_site_fcen_parc": "Identifiant unique FCEN du site (identifiant du CEN correspondant + numéro du site)",
    "lbl_txtParc_insee_com": "Code de la commune",
    "lbl_txtParc_insee_dep": "Code du département",
    "lbl_txtParc_surf_parc_maitrise_ha": "La surface déclarée de la parcelle (en hectares)",
    "lbl_txtParc_surf_parc_maitrise_m2": "Superficie déclarée de la parcelle (en m²)",
    "lbl_txtParc_s_sig_ha": "La surface informatique de la parcelle (avec le $area) (en hectares)",
    "lbl_txtParc_code_mfu1": "Code de maîtrise foncière usage n°1",
    "lbl_txtParc_code_mfu2": "Code de maîtrise foncière usage n°2 (sous-partie du code n°1)",
    "lbl_txtParc_type_prop": "Le type de propriétaire de la parcelle ",
    "lbl_txtParc_domaine_public": "S'agit-il d'une parcelle dessinée n'appartenant pas au cadastre ? ",
    "lbl_txtParc_parc_gestion_rnx": "La parcelle est-elle gérée dans le cadre du mandat de gestion de réserve naturelle (nationale, régionale, corse) accordée au CEN par l'autorité compétente ? ",
    "lbl_txtParc_bnd": "S'agit-il d'un bien non délimitée ? ",
    "lbl_txtParc_parc_N2000": "La parcelle est-elle située sur un site natura 2000 ? ",
    "lbl_txtParc_pour_part": "S'agit-il d'une parcelle maîtrisée en partie ? ",
    "lbl_txtParc_source_geom_parc_nature": "Référentiel utilisé pour la délimitation (digitalisation) du périmètre",
    "lbl_txtParc_source_geom_parc_date": "Millésime de la source de données de géométrie parcelle",
    "lbl_txtParc_echelle_num_parc": "Echelle de numérisation du site",
    "lbl_txtParc_source_surf_parc": "Source de la superficie de la parcelle",
    "lbl_txtParc_date_maj_parcelle": "Date de la dernière mise à jour de la table attributaire de la parcelle",
    "lbl_txtParc_date_maj_p": "Date de la dernière mise à jour de la géométrie de la parcelle",
    "lbl_txtParc_id_proprietaire": "Numéro du CEN propriétaire",
    "lbl_txtParc_proprietaires": "Le propriétaire de la parcelle (uniquement si il y a plusieurs propriétaires pour une même parcelle)",
    "lbl_txtParc_tresfonds": "S'agit-il d'un sous-sol ?",
    "lbl_txtParc_fdd": "S'agit-il d'une parcelle en FDD ?",
    "lbl_txtParc_doc_foncier": "Les documents administratif(s) justifiant la maîtrise foncière du site sont-elles numérisés et mobilisables ?",
    "lbl_txtParc_source_doc_foncier": "Organisme auquel on peut s'adresser pour obtenir ce(s) document(s) justifiant la maîtrise foncière du site ",
    "lbl_txtParc_date_acquisition": "Date d'acquisition de la parcelle",
    "lbl_txtParc_mesure_compens": "La parcelle est-elle issue d'une mesure compensatoire ? ",
    "lbl_txtParc_surf_ore_m2": "Superficie (en m²) en obligation réelle environnementale sur la parcelle concernée (entièrement ou en partie)",
    "lbl_txtParc_date_debut_ore": " Date de début de la convention",
    "lbl_txtParc_date_fin_ore": "Date de fin de la convention",
    "lbl_txtParc_ZPF": "La parcelle est-elle située dans une Zone de Protection Forte ? ",
    "lbl_txtParc_mode_ZPF": "Mode d'action de la parcelle en ZPF",
    "lbl_txtParc_surface_ZPF": "Surface de la parcelle en ZPF",
    "lbl_txtParc_date_ZPF": "Date de la parcelle en ZPF",
    "lbl_txtParc_intervention_SAFER": "La SAFER est-elle intervenue dans l'acquisition ou la convention de la parcelle ? ",
    "lbl_txtParc_financeurs": "Les différents financeurs pour l'acquisition de la parcelle (si acquisition)",
    "lbl_txtParc_prix_ha_net_vendeur": "Prix de vente de la parcelle renseigné dans l'acte",
    "lbl_txtParc_prix_ha_achat": "Prix d'achat de la parcelle en cumulant le prix de vente plus les factuers et frais d'honoraires",
    "lbl_txtParc_actes": "Lien d'accès direct (adresse https) vers l'acte de propriété du site",
    "lbl_txtParc_remarques": "Potentielles remarques sur la parcelle",
    "label_parc_prefixe": "Le numéro de préfixe (numéro de l'ancienne commune)",
    "label_parc_section": "Le numéro de section de la parcelle",
    "label_parc_numseul": "Le numéro de la parcelle",
}
