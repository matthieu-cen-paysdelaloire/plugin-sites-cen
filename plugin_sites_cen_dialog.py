# -*- coding: utf-8 -*-
"""
Point d'entrée du dialogue AttributeEditorSitesCENDialog.

Ce fichier ne contient que le câblage initial (__init__) : chargement du
.ui, dimensionnement de la fenêtre, construction des dictionnaires champ<->widget,
puis délégation de tout le reste du comportement aux mixins ci-dessous, chacun
centré sur une responsabilité :

  - dialog_map_mixin.py        : canevas cartographique (QgsMapCanvas, fond OSM, surbrillance)
  - dialog_validation_mixin.py : validation visuelle des champs + sauvegarde
  - dialog_sites_mixin.py      : liste des sites (peuplement, filtre, sélection)
  - dialog_parcelles_mixin.py  : sous-formulaire des parcelles (vue maître-détail)
  - dialog_geology_mixin.py    : cascade de listes déroulantes géologiques
  - dialog_ui_mixin.py         : infrastructure UI (tooltips, signaux, mode édition, eventFilter)
  - dialog_bilan_mixin.py      : panneau "Bilan foncier" (saisie de l'année, calcul, affichage)
  - dialog_data.py              : données métier statiques (dictionnaires, textes d'aide)
  - dialog_field_maps.py        : construction des dictionnaires champ SIG <-> widget
"""
import os
from qgis.PyQt import uic, QtWidgets, QtCore

from . import dialog_data as data
from . import dialog_field_maps as field_maps
from .dialog_map_mixin import MapMixin
from .dialog_validation_mixin import ValidationMixin
from .dialog_sites_mixin import SitesMixin
from .dialog_parcelles_mixin import ParcellesMixin
from .dialog_geology_mixin import GeologyMixin
from .dialog_ui_mixin import UiMixin
from .dialog_bilan_mixin import BilanMixin

# Ré-exporté pour compatibilité : du code externe pourrait importer alpha_sort_key
# directement depuis ce module (comportement historique du fichier monolithique).
from .dialog_data import alpha_sort_key  # noqa: F401


# Permet de créer la connexion entre notre fichier .ui contennant les codes pour le design de notre interface et notre fichier python
# Permet de modifier l'aspect visuel de notre plugin, sans toucher à la logique du code
UI_FILE = os.path.join(os.path.dirname(__file__), 'plugin_sites_cen_dialog_base.ui')
FORM_CLASS, _ = uic.loadUiType(UI_FILE)


# Configuration de la fonction permettant de lancer le script python
class AttributeEditorSitesCENDialog(
        QtWidgets.QDialog, FORM_CLASS,
        MapMixin, ValidationMixin, SitesMixin, ParcellesMixin, GeologyMixin, UiMixin, BilanMixin):

    def __init__(self, parent=None, iface=None):
        super(AttributeEditorSitesCENDialog, self).__init__(parent)
        self.setupUi(self)

        # --- BOUTONS DE FENÊTRE STANDARD (réduire / agrandir-restaurer / fermer) ---
        # Une QDialog n'affiche par défaut que le bouton fermer ; on ajoute les deux
        # autres boutons habituels de n'importe quelle fenêtre.
        self.setWindowFlags(
            self.windowFlags()
            | QtCore.Qt.WindowType.WindowMinimizeButtonHint
            | QtCore.Qt.WindowType.WindowMaximizeButtonHint
        )

        # --- DIMENSIONS LIBÉRÉES ---
        # On définit une taille minimale raisonnable pour ne pas écraser l'interface
        self.setMinimumSize(QtCore.QSize(800, 600))
        # On supprime le setMaximumSize pour permettre le plein écran
        self.setMaximumSize(QtCore.QSize(16777215, 16777215))

        self.iface = iface

        # --- CONFIGURATION SCROLLAREA (CORRIGÉE) ---
        if hasattr(self, 'scrollArea'):
            # IMPORTANT : True permet au contenu de s'étirer avec la fenêtre
            self.scrollArea.setWidgetResizable(True)
            if hasattr(self, 'scrollAreaWidgetContents'):
                # On garde seulement une largeur minimale pour la lisibilité
                self.scrollAreaWidgetContents.setMinimumSize(QtCore.QSize(590, 1750))

        self.layer = None
        self.features_dict = {}
        self.current_fid = None

        # --- SOUS-FORMULAIRE PARCELLES (parcelles_cen) ---
        self.parcelles_layer = None
        self.parcelles_dict = {}
        self.parcelles_by_num_parc = {}
        self.current_parcelle_fid = None

        # Dictionnaire associant chaque champ de parcelles_cen à son widget (lecture seule, visualisation uniquement)
        self.parcelle_field_map = field_maps.build_parcelle_field_map(self)

        # Dictionnaires de traduction "valeur brute -> description", utilisés UNIQUEMENT pour
        # l'affichage en lecture seule des parcelles (aide à la compréhension des codes stockés
        # en base, sans jamais permettre de saisie).
        self.parcelle_value_dicts = data.PARCELLE_VALUE_DICTS

        # Dictionnaire associant chaque champ complémentaire de sites_cen à son widget
        # (lecture seule, visualisation uniquement, aucune sauvegarde possible)
        self.site_readonly_field_map = field_maps.build_site_readonly_field_map(self)

        # Dictionnaires de traduction "valeur brute -> description", utilisés UNIQUEMENT pour
        # l'affichage en lecture seule des sites (aide à la compréhension des codes stockés en
        # base, sans jamais permettre de saisie).
        self.site_value_dicts = data.SITE_VALUE_DICTS

        # --- CARTE (OpenStreetMap) ---
        self.map_canvas = None
        self.map_highlight = None
        self.osm_layer = None
        # IMPORTANT : la carte n'est PAS construite ici, mais différée juste après le premier
        # affichage du formulaire (voir showEvent ci-dessous). Le rapport de plantage observé
        # pointait précisément sur .show(), au moment où Qt affiche récursivement TOUS les
        # widgets enfants d'un coup : si la carte était déjà construite à ce stade, son tout
        # premier rendu (contexte graphique, première tuile OSM peinte...) se retrouvait
        # mêlé à cette traversée unique. En la construisant une fois le reste du formulaire
        # déjà affiché, on isole ce moment sensible du reste, et un souci lié à la carte ne
        # peut plus faire échouer l'ouverture du formulaire entier.
        self._map_canvas_pending = hasattr(self, 'mapContainer')

        # --- DICTIONNAIRES ---
        # Contient les valeurs à renseigner dans la table, pour les listes déroulantes
        self.dict_rnx = data.DICT_RNX
        self.dict_militaire = data.DICT_MILITAIRE
        self.dict_type_milieu = data.DICT_TYPE_MILIEU
        self.dict_nature = data.DICT_NATURE
        self.dict_geol = data.DICT_GEOL
        self.dict_carto = data.DICT_CARTO
        self.dict_typo = data.DICT_TYPO
        self.dict_doc_pres = data.DICT_DOC_PRES
        self.dict_doc_eval = data.DICT_DOC_EVAL
        self.dict_oui_non = data.DICT_OUI_NON

        self.dict_geol_step = data.DICT_GEOL_STEP

        # Dictionnaire permettant la connexion entre les champs de la table SIG et les variables du script python
        self.field_map = field_maps.build_field_map(self)

        # Association de chaque champ date optionnel à sa case "Non renseignée" : quand elle est
        # cochée, le champ correspondant est sauvegardé comme NULL (et grisé, sa valeur affichée
        # n'ayant alors aucune importance).
        self.date_null_checkboxes = field_maps.build_date_null_checkboxes(self)

        self.init_ui_elements()
        self.setup_tooltips()
        self.connect_signals()
        self.fix_combobox_popup_style()

        # --- BILAN FONCIER (nouvel onglet + bouton à côté de "Activer le mode édition") ---
        self.setup_bilan_panel()

        # Le bouton "mode édition" (btnToggleSimpleView) occupait seul sa ligne dans le
        # panneau de droite ; on le regroupe avec le nouveau bouton "Bilan foncier" sur
        # une même ligne, sans toucher au fichier .ui.
        buttons_row_layout = self.rightContainerLayout
        insertion_index = buttons_row_layout.indexOf(self.btnToggleSimpleView)
        buttons_row_layout.removeWidget(self.btnToggleSimpleView)

        top_buttons_layout = QtWidgets.QHBoxLayout()
        top_buttons_layout.addWidget(self.btnToggleSimpleView)

        self.btnShowBilan = QtWidgets.QPushButton("📊 Bilan foncier")
        self.btnShowBilan.setCheckable(True)
        self.btnShowBilan.setToolTip("Affiche un tableau de bord du bilan foncier annuel (surfaces, sites, communes...)")
        self.btnShowBilan.toggled.connect(self.toggle_bilan_view)
        top_buttons_layout.addWidget(self.btnShowBilan)

        buttons_row_layout.insertLayout(insertion_index, top_buttons_layout)

        # "Comment ça marche ?" (aide globale sur l'outil) : placé juste en dessous de la ligne
        # des 2 boutons ci-dessus, avec un peu d'espace pour ne pas coller au bouton "Bilan
        # foncier". Même mécanisme de survol (❓) que le reste du formulaire ; le texte affiché
        # est défini dans dialog_data.HELP_TEXTS sous la clé "lblGlobalHelp".
        help_row_layout = QtWidgets.QHBoxLayout()
        help_row_layout.addSpacing(4)
        self.lblGlobalHelp = QtWidgets.QLabel('<a href="?" style="text-decoration:none;">❓ Comment ça marche ?</a>')
        self.lblGlobalHelp.setObjectName("lblGlobalHelp")  # requis : on_help_link_hovered s'appuie sur l'objectName
        self.lblGlobalHelp.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self.lblGlobalHelp.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self.lblGlobalHelp.linkHovered.connect(self.on_help_link_hovered)
        help_row_layout.addWidget(self.lblGlobalHelp)
        help_row_layout.addStretch()
        buttons_row_layout.insertLayout(insertion_index + 1, help_row_layout)

        # État initial : consultation par défaut, donc champs modifiables (✏️) désactivés
        # tant que l'utilisateur n'a pas cliqué sur "Activer le mode édition"
        self.toggle_simple_view(False)

        # Le rappel de démarrage est affiché au premier affichage de la fenêtre (voir
        # showEvent ci-dessous), pas ici : à ce stade la fenêtre n'est pas encore visible.
        self._startup_reminder_shown = False

    def showEvent(self, event):
        """
        Affiche un rappel à chaque ouverture du plugin (une seule fois par instance,
        au tout premier affichage de la fenêtre), et déclenche la construction DIFFÉRÉE
        de la carte (voir commentaire sur self._map_canvas_pending dans __init__).
        """
        super().showEvent(event)

        # IMPORTANT : le rappel modal est affiché AVANT de programmer la construction
        # différée de la carte, et non l'inverse. QMessageBox.information() démarre sa
        # propre boucle d'événements imbriquée tant qu'elle est ouverte ; si le timer de
        # la carte était programmé juste avant, il se déclenchait PENDANT cette boucle
        # imbriquée (donc en pleine boîte de dialogue modale), ce qui provoquait un
        # plantage natif côté Qt/QgsMapCanvas. En affichant d'abord le rappel (bloquant,
        # donc entièrement terminé avant la suite) puis en programmant le timer ensuite,
        # celui-ci se déclenche proprement sur la boucle d'événements principale.
        if not self._startup_reminder_shown:
            self._startup_reminder_shown = True
            QtWidgets.QMessageBox.information(
                self,
                "Avant de commencer",
                "Merci de vérifier que vous disposez bien de la dernière version du "
                "GeoPackage \"Foncier_CEN\" avant de continuer.\n\n"
                "La notice d'utilisation du plugin est disponible dans l'en-tête, en "
                "cliquant sur le lien prévu à cet effet."
            )

        if getattr(self, '_map_canvas_pending', False):
            self._map_canvas_pending = False
            # QTimer.singleShot(0, ...) reporte l'appel au prochain passage dans la boucle
            # d'événements Qt PRINCIPALE (plus aucune boîte modale n'est active à ce stade).
            QtCore.QTimer.singleShot(0, self.setup_map_canvas_with_crash_protection)
