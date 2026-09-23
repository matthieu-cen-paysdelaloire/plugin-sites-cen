# -*- coding: utf-8 -*-
"""
Mixin regroupant tout ce qui concerne le canevas cartographique embarqué dans le
dialogue : création du canevas, fonds de plan (OpenStreetMap, photographies aériennes
IGN, Plan IGN, mode automatique selon le zoom) avec leur sélecteur flottant, style de la couche des
sites, surbrillance/zoom sur l'entité sélectionnée (site ou parcelle), et
sélection d'une entité PAR CLIC directement sur la carte.

Ce mixin n'est PAS utilisable seul : il est combiné avec QtWidgets.QDialog (et les
autres mixins) dans AttributeEditorSitesCENDialog. Il suppose donc la présence des
attributs habituels du dialogue (self.mapContainer, self.layer, self.map_canvas, ...).
"""
import math
import os

from qgis.PyQt import QtWidgets, QtGui, QtCore
from qgis.gui import QgsMapToolPan


# QActionGroup a changé de module entre Qt5 (QtWidgets) et Qt6 (QtGui) : QGIS 3 / QGIS 4
try:
    _QActionGroup = QtGui.QActionGroup
except AttributeError:
    _QActionGroup = QtWidgets.QActionGroup


# ======================================================================
# FONDS DE PLAN : catalogue + contrôleur de couches
# ======================================================================
# Ajouter un nouveau fond = ajouter une entrée dans BASEMAPS ci-dessous, rien d'autre.

# ----------------------------------------------------------------------
# Catalogue des fonds de plan (tuiles XYZ, toutes en EPSG:3857 comme le canevas)
# ----------------------------------------------------------------------
# Les flux IGN sont servis par la Géoplateforme (data.geopf.fr) : accès libre, sans clé.
# Ils sont appelés en WMTS "déguisé" en XYZ, avec la pyramide standard PM (Pseudo-Mercator).
_IGN_WMTS = (
    "https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0"
    "&LAYER={layer}&STYLE=normal&TILEMATRIXSET=PM&FORMAT={fmt}"
    "&TILEMATRIX={{z}}&TILEROW={{y}}&TILECOL={{x}}"
)

BASEMAPS = {
    "osm": {
        "label": "Plan OpenStreetMap",
        "url": "https://tile.openstreetmap.org/{z}/{x}/{y}.png",
        "zmin": 0, "zmax": 19,
        "attribution": "© contributeurs OpenStreetMap",
    },
    "ign_ortho": {
        "label": "Photographies aériennes (IGN)",
        "url": _IGN_WMTS.format(layer="ORTHOIMAGERY.ORTHOPHOTOS", fmt="image/jpeg"),
        "zmin": 0, "zmax": 19,
        "attribution": "© IGN – Géoplateforme",
    },
    "ign_plan": {
        "label": "Plan IGN",
        "url": _IGN_WMTS.format(layer="GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2", fmt="image/png"),
        "zmin": 0, "zmax": 19,
        "attribution": "© IGN – Géoplateforme",
    },
}

# Mode spécial (pas un fond en soi) : choisit le fond selon l'échelle courante
AUTO_MODE = "auto"
AUTO_LABEL = "Automatique (plan ↔ photo selon le zoom)"
# En dessous de cette échelle (1:10 000 et plus zoomé), le mode auto passe en photo aérienne
AUTO_SWITCH_SCALE = 10000
AUTO_FAR_KEY = "osm"
AUTO_NEAR_KEY = "ign_ortho"

DEFAULT_MODE = "osm"
SETTINGS_KEY = "attribute_editor_sites_cen/fond_de_plan"


class _OverlayPositioner(QtCore.QObject):
    """
    Filtre d'événements dédié qui repositionne les widgets flottants (bouton de choix du
    fond, mention des sources) à chaque redimensionnement du canevas.

    Volontairement un QObject séparé : le dialogue possède déjà son propre eventFilter
    (UiMixin, gestion de la molette sur les listes déroulantes), qu'on ne veut pas toucher.
    """
    MARGIN = 6

    def __init__(self, canvas, top_right_widget, bottom_right_widget):
        super().__init__(canvas)
        self._canvas = canvas
        self._top_right = top_right_widget
        self._bottom_right = bottom_right_widget
        canvas.installEventFilter(self)

    def eventFilter(self, obj, event):
        if obj is self._canvas and event.type() in (QtCore.QEvent.Type.Resize, QtCore.QEvent.Type.Show):
            self.reposition()
        return False  # on ne consomme jamais l'événement

    def reposition(self):
        w, h, m = self._canvas.width(), self._canvas.height(), self.MARGIN
        tr = self._top_right
        tr.adjustSize()
        tr.move(max(0, w - tr.width() - m), m)
        br = self._bottom_right
        br.adjustSize()
        br.move(max(0, w - br.width()), max(0, h - br.height()))
        tr.raise_()
        br.raise_()


def _nice_scale_distance(raw_distance):
    """
    Arrondit 'raw_distance' (en mètres) à la valeur "ronde" immédiatement inférieure ou
    égale, parmi 1, 2 ou 5 x une puissance de 10 (ex : 47 -> 20, 380 -> 200, 1250 -> 1000).
    C'est le même principe que les barres d'échelle graphiques classiques (Leaflet, Google
    Maps...) : on préfère toujours afficher une distance "ronde" plutôt que la valeur exacte.
    """
    if raw_distance <= 0:
        return 0
    exponent = math.floor(math.log10(raw_distance))
    fraction = raw_distance / (10 ** exponent)
    if fraction >= 5:
        nice_fraction = 5
    elif fraction >= 2:
        nice_fraction = 2
    else:
        nice_fraction = 1
    return nice_fraction * (10 ** exponent)


class _GraphicalScaleBar(QtWidgets.QWidget):
    """
    Barre d'échelle graphique façon Leaflet : un segment dont la longueur (en pixels)
    représente une distance réelle "ronde" (ex : 200 m, 1 km...), affichée en légende.
    La longueur du segment s'ajuste automatiquement à chaque zoom/déplacement de la carte.
    """
    MAX_BAR_WIDTH_PX = 100

    def __init__(self, parent=None):
        super().__init__(parent)
        self._distance_m = 0
        self._bar_width_px = 0
        self.setFixedHeight(26)
        self.setMinimumWidth(self.MAX_BAR_WIDTH_PX + 16)

    def update_from_map_units_per_pixel(self, map_units_per_pixel):
        """
        Recalcule la distance "ronde" et la longueur du segment à afficher, à partir du
        nombre d'unités de la carte (mètres, car le canevas est en EPSG:3857) par pixel
        écran. Cette valeur est fournie directement par QgsMapCanvas.
        """
        if not map_units_per_pixel or map_units_per_pixel <= 0:
            return
        max_distance = self.MAX_BAR_WIDTH_PX * map_units_per_pixel
        nice_distance = _nice_scale_distance(max_distance)
        if nice_distance <= 0:
            return
        self._distance_m = nice_distance
        self._bar_width_px = nice_distance / map_units_per_pixel
        self.update()  # déclenche un repaint

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        bar_color = QtGui.QColor(40, 40, 40)
        pen = QtGui.QPen(bar_color)
        pen.setWidth(2)
        painter.setPen(pen)

        margin_left = 6
        bar_y = 20
        bar_w = max(self._bar_width_px, 1)

        # Trait horizontal principal + petites moustaches verticales aux deux extrémités
        painter.drawLine(int(margin_left), bar_y, int(margin_left + bar_w), bar_y)
        painter.drawLine(int(margin_left), bar_y - 4, int(margin_left), bar_y + 4)
        painter.drawLine(int(margin_left + bar_w), bar_y - 4, int(margin_left + bar_w), bar_y + 4)

        # Distance affichée en km au-delà de 1000 m, sinon en m
        if self._distance_m >= 1000:
            km = self._distance_m / 1000
            label = f"{km:.0f} km" if km == int(km) else f"{km:.1f} km"
        else:
            label = f"{self._distance_m:.0f} m"

        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        text_rect = QtCore.QRect(int(margin_left), 0, int(bar_w), 14)
        painter.drawText(text_rect, QtCore.Qt.AlignmentFlag.AlignCenter, label)


class _ClickIdentifyTool(QgsMapToolPan):
    """
    Outil de carte combinant :
      - le comportement standard de déplacement de la carte (glisser-déposer),
        hérité de QgsMapToolPan, qui reste donc inchangé ;
      - la détection d'un simple clic (déplacement de la souris quasi nul entre
        l'appui et le relâchement), qui déclenche un callback avec les
        coordonnées du point cliqué (dans le CRS du canevas).

    Cela permet de conserver la possibilité de déplacer la carte à la souris
    tout en ajoutant la sélection d'entité par clic, sans les faire interférer.
    """
    CLICK_TOLERANCE_PX = 4

    def __init__(self, canvas, on_click):
        super().__init__(canvas)
        self._on_click = on_click
        self._press_pos = None

    def canvasPressEvent(self, event):
        self._press_pos = event.pos()
        super().canvasPressEvent(event)

    def canvasReleaseEvent(self, event):
        super().canvasReleaseEvent(event)
        if (self._press_pos is not None
                and event.button() == QtCore.Qt.MouseButton.LeftButton):
            moved = (event.pos() - self._press_pos).manhattanLength()
            if moved <= self.CLICK_TOLERANCE_PX:
                point = self.toMapCoordinates(event.pos())
                self._on_click(point)
        self._press_pos = None


class MapMixin:

    def _safe_mode_marker_path(self):
        """
        Chemin du fichier marqueur utilisé pour détecter, d'une exécution à l'autre, qu'un
        plantage NATIF (access violation) a eu lieu PENDANT la construction de la carte.

        Volontairement un simple fichier sur le disque, à un emplacement fixe DANS LE DOSSIER
        DU PLUGIN (donc identique que le plugin soit lancé depuis l'interface QGIS ou depuis le
        raccourci Bureau autonome — contrairement à QgsSettings, dont le fichier de stockage
        peut différer selon le nom d'organisation/application défini par le processus Qt en
        cours, qui n'est pas forcément le même entre QGIS Desktop et un lancement autonome via
        QgsApplication([], True)).
        """
        plugin_dir = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(plugin_dir, ".carte_construction_en_cours")

    def setup_map_canvas_with_crash_protection(self):
        """
        Enrobe setup_map_canvas() d'une protection "mode sans échec" persistante, basée sur
        un fichier marqueur (voir _safe_mode_marker_path) :
        - Si un plantage a eu lieu la dernière fois pendant la construction de la carte
          (fichier marqueur toujours présent, jamais nettoyé), on ne retente PAS
          automatiquement : on affiche un message de repli avec un bouton pour réessayer
          manuellement (l'utilisateur reste maître).
        - Sinon, on crée le fichier marqueur, on construit la carte normalement, puis on
          supprime le marqueur une fois la construction terminée avec succès.
        """
        marker_path = self._safe_mode_marker_path()

        if os.path.isfile(marker_path):
            self._show_map_safe_mode_placeholder()
            return

        try:
            # Écriture + flush + fsync explicites : on veut que ce fichier soit VRAIMENT sur
            # le disque avant de lancer le code à risque, pas seulement dans un cache mémoire
            # que Windows n'aurait pas encore écrit au moment d'un plantage natif.
            with open(marker_path, "w", encoding="utf-8") as f:
                f.write("Construction de la carte en cours...\n")
                f.flush()
                os.fsync(f.fileno())
        except OSError:
            # Si on ne peut même pas écrire ce fichier (dossier en lecture seule...), on ne
            # bloque pas l'utilisateur pour autant : on tente la carte sans protection.
            pass

        self.setup_map_canvas()

        # Si on arrive ici, la construction s'est terminée sans plantage : on efface le marqueur.
        try:
            if os.path.isfile(marker_path):
                os.remove(marker_path)
        except OSError:
            pass

    def _show_map_safe_mode_placeholder(self):
        """
        Affiche, à la place de la carte, un message expliquant qu'elle a été désactivée
        automatiquement suite à un plantage précédent, avec un bouton pour retenter
        manuellement (utile une fois le problème corrigé sur ce poste, ex : mise à jour
        du pilote graphique).
        """
        layout = self.mapContainer.layout()
        if layout is None:
            layout = QtWidgets.QVBoxLayout(self.mapContainer)
            layout.setContentsMargins(0, 0, 0, 0)

        placeholder = QtWidgets.QWidget()
        placeholder_layout = QtWidgets.QVBoxLayout(placeholder)
        placeholder_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        label = QtWidgets.QLabel(
            "🗺️ Carte désactivée automatiquement\n\n"
            "L'affichage de la carte a provoqué la fermeture inattendue de QGIS lors "
            "d'une précédente ouverture sur ce poste. Elle a donc été désactivée par "
            "précaution.\n\n"
            "Le reste du formulaire fonctionne normalement.")
        label.setWordWrap(True)
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet("color: #5a6472; padding: 16px;")
        placeholder_layout.addWidget(label)

        btn_retry = QtWidgets.QPushButton("Réessayer d'afficher la carte")
        btn_retry.clicked.connect(self._retry_map_canvas)
        placeholder_layout.addWidget(btn_retry, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)

        layout.addWidget(placeholder)
        self._map_safe_mode_placeholder = placeholder

    def _retry_map_canvas(self):
        """
        Appelée par le bouton "Réessayer d'afficher la carte" du mode sans échec :
        retire le message de repli, supprime le marqueur (sinon on retomberait
        immédiatement sur le même message sans rien retenter), puis relance la
        construction normale (protégée par le même mécanisme, donc sans risque de
        boucle si ça re-plante : il faudra alors relancer le plugin pour réessayer).
        """
        if getattr(self, '_map_safe_mode_placeholder', None) is not None:
            self._map_safe_mode_placeholder.setParent(None)
            self._map_safe_mode_placeholder.deleteLater()
            self._map_safe_mode_placeholder = None

        marker_path = self._safe_mode_marker_path()
        try:
            if os.path.isfile(marker_path):
                os.remove(marker_path)
        except OSError:
            pass

        self.setup_map_canvas_with_crash_protection()

    def setup_map_canvas(self):
        """
        Crée le canevas cartographique (QgsMapCanvas) et charge un fond de plan OpenStreetMap.
        Le canevas est inséré dans le conteneur 'mapContainer' défini dans le fichier .ui.
        """
        from qgis.gui import QgsMapCanvas
        from qgis.core import QgsRasterLayer, QgsCoordinateReferenceSystem

        self.map_canvas = QgsMapCanvas(self.mapContainer)
        self.map_canvas.setCanvasColor(QtGui.QColor(255, 255, 255))
        self.map_canvas.setDestinationCrs(QgsCoordinateReferenceSystem("EPSG:3857"))

        # Fond de plan : voir la section "FONDS DE PLAN" en bas de ce fichier. Plusieurs fonds sont
        # disponibles (OSM, photographies aériennes IGN, Plan IGN, mode automatique) ; on
        # affiche ici le dernier choix mémorisé de l'utilisateur.
        self.init_basemap()
        if self.basemap_layer is not None:
            self.map_canvas.setLayers([self.basemap_layer])
            self.map_canvas.setExtent(self.basemap_layer.extent())

        # Insertion du canevas dans le conteneur prévu par le .ui
        layout = self.mapContainer.layout()
        if layout is None:
            layout = QtWidgets.QVBoxLayout(self.mapContainer)
            layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.map_canvas)

        # Contrôleur de couches flottant (choix du fond de plan) + mention des sources
        self.setup_basemap_switcher()

        # --- BARRE D'ÉCHELLE INTERACTIVE + BOUTONS DE ZOOM ---
        # Placée sous la carte, à la manière de la barre d'état de QGIS. L'échelle peut être
        # cliquée/modifiée directement (widget natif QGIS QgsScaleComboBox), et les boutons +/-
        # zooment via les méthodes standard du canevas ; le zoom à la molette reste inchangé,
        # les deux mécanismes étant totalement indépendants.
        from qgis.gui import QgsScaleComboBox

        scale_bar_layout = QtWidgets.QHBoxLayout()
        scale_bar_layout.setContentsMargins(4, 2, 4, 2)

        # Barre d'échelle graphique (façon Leaflet) : segment qui s'allonge/se rétracte
        # visuellement selon le niveau de zoom
        self.graphical_scale_bar = _GraphicalScaleBar()

        btn_zoom_out = QtWidgets.QToolButton()
        btn_zoom_out.setText("−")
        btn_zoom_out.setToolTip("Zoom arrière")
        btn_zoom_out.setAutoRaise(True)
        btn_zoom_out.clicked.connect(self.map_canvas.zoomOut)

        btn_zoom_in = QtWidgets.QToolButton()
        btn_zoom_in.setText("+")
        btn_zoom_in.setToolTip("Zoom avant")
        btn_zoom_in.setAutoRaise(True)
        btn_zoom_in.clicked.connect(self.map_canvas.zoomIn)

        self.scale_combo = QgsScaleComboBox()
        self.scale_combo.setToolTip(
            "Échelle de la carte : cliquez pour en choisir une, ou saisissez-la directement (ex. 1:5000)")
        self.scale_combo.setMinimumWidth(110)
        self.scale_combo.setScale(self.map_canvas.scale())

        scale_bar_layout.addWidget(self.graphical_scale_bar)
        scale_bar_layout.addStretch()
        scale_bar_layout.addWidget(QtWidgets.QLabel("Échelle :"))
        scale_bar_layout.addWidget(self.scale_combo)
        scale_bar_layout.addWidget(btn_zoom_out)
        scale_bar_layout.addWidget(btn_zoom_in)

        layout.addLayout(scale_bar_layout)

        # Synchronisation bidirectionnelle : la carte met à jour l'affichage de l'échelle
        # (zoom molette, boutons, glisser...), et modifier l'échelle affichée zoome la carte
        self.map_canvas.scaleChanged.connect(self.scale_combo.setScale)
        self.scale_combo.scaleChanged.connect(self.map_canvas.zoomScale)

        # La barre graphique se recalcule à chaque changement d'étendue (zoom OU déplacement),
        # à partir du nombre d'unités-carte par pixel écran (mètres, car canevas en EPSG:3857)
        self.map_canvas.extentsChanged.connect(self._update_graphical_scale_bar)

        # --- SÉLECTION D'ENTITÉ PAR CLIC SUR LA CARTE ---
        # L'outil reste actif en permanence (pas besoin d'activer un mode particulier) :
        # un simple clic identifie l'entité sous le curseur, un glisser déplace la carte.
        self.map_click_tool = _ClickIdentifyTool(self.map_canvas, self.on_map_canvas_clicked)
        self.map_canvas.setMapTool(self.map_click_tool)
        self.map_canvas.setCursor(QtCore.Qt.CursorShape.CrossCursor)

        self.map_canvas.refresh()
        self._update_graphical_scale_bar()  # premier affichage, une fois l'étendue initiale posée

        # IMPORTANT : populate_list() (dialog_sites_mixin.py) applique normalement le style de
        # la couche des sites et cadre la carte sur son emprise, mais UNIQUEMENT si self.map_canvas
        # existait déjà à ce moment-là (if self.map_canvas: ...). Or la construction de la carte
        # est désormais DIFFÉRÉE au premier affichage du formulaire (voir showEvent), donc
        # populate_list() s'exécute AVANT que le canevas n'existe : ce bloc était silencieusement
        # sauté. Résultat : self.layer restait ajouté à la carte plus tard (via
        # show_parcelles_outlines -> _refresh_canvas_layers) mais SANS JAMAIS avoir été stylé
        # (bleu) au préalable, et gardait donc le style d'origine du GeoPackage (rouge chez cet
        # utilisateur), visible sous le contour transparent des parcelles. On rejoue donc ici ce
        # que populate_list() aurait dû faire, maintenant que le canevas est prêt.
        if self.layer is not None:
            self.style_sites_layer()
            self._refresh_canvas_layers()
            if self.layer.featureCount() > 0:
                from qgis.core import QgsCoordinateTransform, QgsProject
                canvas_crs = self.map_canvas.mapSettings().destinationCrs()
                extent = self.layer.extent()
                if self.layer.crs() != canvas_crs:
                    transform = QgsCoordinateTransform(self.layer.crs(), canvas_crs, QgsProject.instance())
                    extent = transform.transformBoundingBox(extent)
                if not extent.isEmpty():
                    self.map_canvas.setExtent(extent)
                    self.map_canvas.refresh()

    def _update_graphical_scale_bar(self):
        """Recalcule la barre d'échelle graphique à partir de l'étendue actuelle du canevas."""
        if not self.map_canvas or not hasattr(self, 'graphical_scale_bar'):
            return
        self.graphical_scale_bar.update_from_map_units_per_pixel(self.map_canvas.mapUnitsPerPixel())


    def on_map_canvas_clicked(self, canvas_point):
        """
        Appelé lors d'un simple clic (et non d'un glisser) sur la carte. Recherche
        l'entité présente à cet endroit et sélectionne l'élément correspondant dans
        la liste, ce qui affiche automatiquement ses attributs (même mécanisme
        qu'un clic dans la liste de gauche).

        Le comportement dépend de la vue actuellement affichée :
          - vue "sites" : recherche parmi les sites (self.layer) ;
          - vue "parcelles du site sélectionné" : recherche parmi les parcelles de
            ce site (self.parcelles_dict), dont le contour est alors affiché sur
            la carte (voir show_parcelles_outlines).
        """
        if getattr(self, 'leftListStack', None) is not None and self.leftListStack.currentIndex() == 1:
            self._select_parcelle_at_point(canvas_point)
        else:
            self._select_site_at_point(canvas_point)

    def _map_point_to_layer_crs(self, canvas_point, target_layer):
        """Reprojette un point du CRS du canevas vers le CRS de la couche cible."""
        from qgis.core import QgsCoordinateTransform, QgsProject

        canvas_crs = self.map_canvas.mapSettings().destinationCrs()
        if not target_layer or target_layer.crs() == canvas_crs:
            return canvas_point
        transform = QgsCoordinateTransform(canvas_crs, target_layer.crs(), QgsProject.instance())
        return transform.transform(canvas_point)

    def _select_site_at_point(self, canvas_point):
        """Identifie le site cliqué (parmi self.features_dict, déjà chargé en mémoire) et le sélectionne."""
        if not self.layer or not self.features_dict:
            return

        point = self._map_point_to_layer_crs(canvas_point, self.layer)
        for fid, feat in self.features_dict.items():
            geom = feat.geometry()
            if geom and not geom.isEmpty() and geom.contains(point):
                self._select_list_item_by_user_data(self.listSites, fid)
                return
        # Aucune entité à cet endroit précis : on ne modifie pas la sélection en cours

    def _select_parcelle_at_point(self, canvas_point):
        """Identifie la parcelle cliquée (parmi self.parcelles_dict, filtré sur le site courant) et la sélectionne."""
        if not self.parcelles_layer or not getattr(self, 'parcelles_dict', None):
            return

        from qgis.core import NULL

        point = self._map_point_to_layer_crs(canvas_point, self.parcelles_layer)
        for fid, feat in self.parcelles_dict.items():
            geom = feat.geometry()
            if not geom or geom.isEmpty() or not geom.contains(point):
                continue

            num_parc = str(feat['num_parc']) if feat['num_parc'] not in (None, NULL) else f"ID {fid}"
            # 1. Sélectionne d'abord le numéro de parcelle dans la liste de gauche (déclenche le
            #    filtrage automatique de la liste des propriétaires, via le signal existant)
            self._select_list_item_by_user_data(self.listParcelles, num_parc)
            # 2. Sélectionne ensuite le propriétaire correspondant à l'entité précisément cliquée
            self._select_list_item_by_user_data(self.listParcellesProprietaires, fid)
            return
        # Aucune parcelle à cet endroit précis : on ne modifie pas la sélection en cours

    @staticmethod
    def _select_list_item_by_user_data(list_widget, value):
        """Sélectionne, dans un QListWidget, le premier item dont la donnée (UserRole) correspond à 'value'."""
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item.data(QtCore.Qt.ItemDataRole.UserRole) == value:
                list_widget.setCurrentItem(item)
                return

    # ------------------------------------------------------------------
    # Aperçu des parcelles du site sélectionné : contour + numéro affiché
    # ------------------------------------------------------------------

    def show_parcelles_outlines(self, features):
        """
        Affiche, sur la carte, UNIQUEMENT le contour des parcelles passées en
        paramètre (typiquement : les parcelles du site actuellement sélectionné),
        avec le numéro de parcelle (champ 'num_parc_seul') centré sur chacune.

        Volontairement limité aux parcelles du site en cours (et non à la couche
        parcelles_cen entière) afin de ne pas surcharger visuellement la carte.
        """
        if not self.map_canvas or not self.parcelles_layer:
            return

        from qgis.core import (QgsVectorLayer, QgsFeature, QgsField, QgsWkbTypes,
                                QgsFillSymbol, QgsSingleSymbolRenderer,
                                QgsPalLayerSettings, QgsTextFormat, QgsVectorLayerSimpleLabeling)

        # Nettoyage de l'éventuel aperçu précédent avant d'en construire un nouveau
        self.hide_parcelles_outlines()

        features = list(features)
        if not features:
            return

        # Couche mémoire temporaire, reconstruite à chaque changement de site : ne contient
        # QUE les parcelles à afficher, avec un seul champ utile (le numéro de parcelle)
        wkb_type_str = QgsWkbTypes.displayString(self.parcelles_layer.wkbType())
        outline_layer = QgsVectorLayer(wkb_type_str, "Parcelles du site (aperçu)", "memory")
        outline_layer.setCrs(self.parcelles_layer.crs())

        try:
            from qgis.PyQt.QtCore import QVariant
            outline_layer.dataProvider().addAttributes([QgsField("num_parc_seul", QVariant.String)])
        except Exception:
            from qgis.core import QMetaType
            outline_layer.dataProvider().addAttributes([QgsField("num_parc_seul", QMetaType.Type.QString)])
        outline_layer.updateFields()

        mem_feats = []
        for feat in features:
            if not feat.hasGeometry():
                continue
            new_feat = QgsFeature(outline_layer.fields())
            new_feat.setGeometry(feat.geometry())
            try:
                val = feat['num_parc_seul']
            except KeyError:
                val = None
            new_feat.setAttribute("num_parc_seul", "" if val in (None,) else str(val))
            mem_feats.append(new_feat)

        if not mem_feats:
            return

        outline_layer.dataProvider().addFeatures(mem_feats)
        outline_layer.updateExtents()

        # Style : contour seul (remplissage transparent), pour ne pas masquer le site en dessous.
        # IMPORTANT : on ne s'appuie plus sur QgsFillSymbol.createSimple({'color': '0,0,0,0', ...})
        # pour la transparence du remplissage — sur certaines versions de QGIS (constaté avec
        # 4.2.0), le parsing de cette chaîne peut ne pas donner un remplissage réellement
        # transparent, et retomber sur une couleur par défaut (visible, parfois rougeâtre).
        # On construit donc le symbole "à la main" : couleur de remplissage forcée à alpha=0,
        # à la fois au niveau du symbole ET de chacune de ses couches internes (le contour,
        # lui, n'est pas touché : il reste pleinement visible, c'est une propriété séparée).
        symbol = QgsFillSymbol.createSimple({
            'outline_color': '230,126,34,255',
            'outline_width': '0.8',
            'outline_style': 'solid',
        })
        transparent = QtGui.QColor(0, 0, 0, 0)
        symbol.setColor(transparent)
        for layer_sym in symbol.symbolLayers():
            try:
                layer_sym.setFillColor(transparent)
            except AttributeError:
                pass  # certains types de symbol layer n'ont pas de remplissage (ex: ligne seule)
        outline_layer.setRenderer(QgsSingleSymbolRenderer(symbol))

        # Étiquette : numéro de parcelle centré sur chaque entité
        label_settings = QgsPalLayerSettings()
        label_settings.fieldName = "num_parc_seul"
        try:
            label_settings.placement = QgsPalLayerSettings.Placement.Horizontal
        except AttributeError:
            label_settings.placement = QgsPalLayerSettings.Horizontal

        text_format = QgsTextFormat()
        text_format.setSize(9)
        text_color = QtGui.QColor(120, 60, 0)
        text_format.setColor(text_color)
        buffer_settings = text_format.buffer()
        buffer_settings.setEnabled(True)
        buffer_settings.setSize(1)
        buffer_settings.setColor(QtGui.QColor(255, 255, 255))
        text_format.setBuffer(buffer_settings)
        label_settings.setFormat(text_format)

        outline_layer.setLabeling(QgsVectorLayerSimpleLabeling(label_settings))
        outline_layer.setLabelsEnabled(True)

        self.parcelles_outline_layer = outline_layer
        self._refresh_canvas_layers()

    def hide_parcelles_outlines(self):
        """Retire l'aperçu des contours de parcelles de la carte (retour à la vue 'sites')."""
        if getattr(self, 'parcelles_outline_layer', None) is not None:
            self.parcelles_outline_layer = None
            self._refresh_canvas_layers()

    def _refresh_canvas_layers(self):
        """
        Reconstruit la liste des couches affichées sur la carte, dans l'ordre :
        aperçu des parcelles (si actif) > site(s) > fond de plan (OSM, IGN...).
        """
        if not self.map_canvas:
            return

        layers = []
        outline_layer = getattr(self, 'parcelles_outline_layer', None)
        if outline_layer is not None:
            layers.append(outline_layer)
        if self.layer is not None:
            layers.append(self.layer)
        basemap = getattr(self, 'basemap_layer', None)
        if basemap is not None and basemap.isValid():
            layers.append(basemap)

        self.map_canvas.setLayers(layers)
        self.map_canvas.refresh()

    def style_sites_layer(self):
        """
        Applique un style simple et semi-transparent à la couche des sites, afin qu'elle reste
        lisible tout en laissant apparaître le fond OpenStreetMap en dessous.
        """
        if not self.layer:
            return

        from qgis.core import (QgsWkbTypes, QgsSingleSymbolRenderer,
                                QgsFillSymbol, QgsLineSymbol, QgsMarkerSymbol)

        geom_type = self.layer.geometryType()
        if geom_type == QgsWkbTypes.PolygonGeometry:
            symbol = QgsFillSymbol.createSimple({
                'color': '52,152,219,70',
                'outline_color': '41,128,185,255',
                'outline_width': '0.6'
            })
        elif geom_type == QgsWkbTypes.LineGeometry:
            symbol = QgsLineSymbol.createSimple({
                'line_color': '41,128,185,255',
                'line_width': '0.8'
            })
        else:
            symbol = QgsMarkerSymbol.createSimple({
                'color': '41,128,185,255',
                'size': '3'
            })

        self.layer.setRenderer(QgsSingleSymbolRenderer(symbol))

    def update_map_selection(self, feat, source_layer=None, color=None):
        """
        Recentre la carte sur la géométrie de l'entité sélectionnée (site OU parcelle) et l'entoure
        d'une surbrillance colorée. 'source_layer' permet de préciser la couche d'origine de la
        géométrie (par défaut : la couche des sites, self.layer). 'color' permet de personnaliser
        la couleur du contour (rouge par défaut pour les sites ; une autre couleur peut être
        passée, par exemple pour distinguer visuellement une sélection de parcelle).
        """
        source_layer = source_layer or self.layer
        if not self.map_canvas or not source_layer:
            return

        from qgis.core import QgsGeometry, QgsCoordinateTransform, QgsProject
        from qgis.gui import QgsHighlight

        # Nettoyage de l'ancienne surbrillance avant d'en afficher une nouvelle
        if self.map_highlight is not None:
            self.map_highlight.hide()
            self.map_highlight = None

        if not feat.hasGeometry():
            return

        # Géométrie D'ORIGINE (dans le CRS de la couche source) : c'est celle qu'il faut
        # transmettre à QgsHighlight, qui se charge LUI-MÊME de la reprojeter vers le CRS
        # du canevas à partir du CRS de "source_layer". Lui transmettre une géométrie déjà
        # reprojetée provoquerait une DOUBLE reprojection (contour mal placé, souvent hors
        # champ) : c'était le bug qui empêchait l'affichage du contour sur les parcelles,
        # dont la couche n'a pas le même CRS que le canevas.
        original_geom = QgsGeometry(feat.geometry())

        # Géométrie reprojetée séparément, utilisée UNIQUEMENT pour calculer l'emprise de zoom
        canvas_crs = self.map_canvas.mapSettings().destinationCrs()
        zoom_geom = QgsGeometry(original_geom)
        if source_layer.crs() != canvas_crs:
            transform = QgsCoordinateTransform(source_layer.crs(), canvas_crs, QgsProject.instance())
            zoom_geom.transform(transform)

        # Zoom sur l'emprise de l'entité, avec une marge de confort autour
        bbox = zoom_geom.boundingBox()
        bbox.scale(1.5)
        if not bbox.isEmpty():
            self.map_canvas.setExtent(bbox)

        # Affichage d'un contour coloré pour repérer l'entité sur le fond OSM
        highlight_color = color or QtGui.QColor(255, 0, 0)
        fill_color = QtGui.QColor(highlight_color)
        fill_color.setAlpha(40)

        # On transmet bien la géométrie D'ORIGINE (pas "zoom_geom") : QgsHighlight applique
        # sa propre transformation CRS en interne à partir de "source_layer".
        self.map_highlight = QgsHighlight(self.map_canvas, original_geom, source_layer)
        self.map_highlight.setColor(highlight_color)
        self.map_highlight.setFillColor(fill_color)
        self.map_highlight.setWidth(3)
        self.map_highlight.show()

        self.map_canvas.refresh()

    # ==================================================================
    # FONDS DE PLAN (OSM / photographies aériennes IGN / Plan IGN / auto)
    # ==================================================================
    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def init_basemap(self):
        """
        Crée le fond de plan initial (dernier choix mémorisé, OSM par défaut). À appeler
        juste après la création de self.map_canvas, AVANT le cadrage initial de la carte.
        """
        self._basemap_layers = {}           # cache : clé -> QgsRasterLayer (créés à la demande)
        self._current_basemap_key = None    # fond réellement affiché
        self._basemap_warned = set()        # fonds déjà signalés indisponibles (évite le spam)
        self.basemap_layer = None

        mode = self._load_basemap_preference()
        if mode != AUTO_MODE and mode not in BASEMAPS:
            mode = DEFAULT_MODE
        self._basemap_mode = mode
        self._apply_effective_basemap(refresh=False)

    def setup_basemap_switcher(self):
        """
        Construit le contrôleur de couches flottant (en haut à droite de la carte) et la
        mention des sources (en bas à droite). À appeler une fois le canevas inséré dans
        son layout.
        """
        canvas = self.map_canvas

        # --- Bouton + menu de choix du fond ---
        btn = QtWidgets.QToolButton(canvas)
        btn.setText("🗺️ Fond de plan")
        btn.setToolTip("Changer le fond de plan de la carte")
        btn.setPopupMode(QtWidgets.QToolButton.ToolButtonPopupMode.InstantPopup)
        btn.setCursor(QtCore.Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(
            "QToolButton { background: rgba(255,255,255,235); border: 1px solid #b8c0cc;"
            " border-radius: 4px; padding: 3px 8px; font-size: 9pt; color: #2c3e50; }"
            "QToolButton:hover { background: #ffffff; border-color: #2980b9; }"
            "QToolButton::menu-indicator { image: none; width: 0px; }"
        )

        menu = QtWidgets.QMenu(btn)
        group = _QActionGroup(menu)
        group.setExclusive(True)
        self._basemap_actions = {}

        entries = [(AUTO_MODE, AUTO_LABEL)] + [(key, cfg["label"]) for key, cfg in BASEMAPS.items()]
        for i, (key, label) in enumerate(entries):
            if i == 1:
                menu.addSeparator()  # sépare le mode automatique des fonds "fixes"
            action = menu.addAction(label)
            action.setCheckable(True)
            action.setChecked(key == self._basemap_mode)
            action.setData(key)
            group.addAction(action)
            self._basemap_actions[key] = action

        group.triggered.connect(lambda act: self.set_basemap_mode(act.data()))
        btn.setMenu(menu)

        # --- Mention des sources ---
        attribution = QtWidgets.QLabel(canvas)
        attribution.setStyleSheet(
            "QLabel { background: rgba(255,255,255,190); color: #444; font-size: 7pt;"
            " padding: 1px 4px; border-top-left-radius: 3px; }"
        )
        attribution.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self.basemap_button = btn
        self.basemap_attribution_label = attribution
        self._basemap_overlay_positioner = _OverlayPositioner(canvas, btn, attribution)

        btn.show()
        attribution.show()
        self._update_basemap_attribution()

        # Le mode automatique doit réévaluer le fond à chaque changement d'échelle
        canvas.scaleChanged.connect(self._on_canvas_scale_changed_for_basemap)

    # ------------------------------------------------------------------
    # Changement de fond
    # ------------------------------------------------------------------

    def set_basemap_mode(self, mode):
        """Change le mode de fond de plan ('auto' ou une clé de BASEMAPS) et le mémorise."""
        if mode != AUTO_MODE and mode not in BASEMAPS:
            return
        self._basemap_mode = mode
        self._save_basemap_preference(mode)
        action = getattr(self, "_basemap_actions", {}).get(mode)
        if action is not None and not action.isChecked():
            action.setChecked(True)
        self._apply_effective_basemap()

    def _on_canvas_scale_changed_for_basemap(self, _scale):
        if getattr(self, "_basemap_mode", None) == AUTO_MODE:
            self._apply_effective_basemap()

    def _effective_basemap_key(self):
        """Fond à afficher réellement, compte tenu du mode et (en mode auto) de l'échelle."""
        mode = getattr(self, "_basemap_mode", DEFAULT_MODE)
        if mode != AUTO_MODE:
            return mode
        scale = self.map_canvas.scale() if self.map_canvas else 0
        if scale and scale <= AUTO_SWITCH_SCALE:
            return AUTO_NEAR_KEY
        return AUTO_FAR_KEY

    def _apply_effective_basemap(self, refresh=True):
        """Affiche le fond correspondant au mode courant (sans rien faire s'il est déjà affiché)."""
        if not self.map_canvas:
            return
        key = self._effective_basemap_key()
        if key == self._current_basemap_key and self.basemap_layer is not None:
            return

        layer = self._get_basemap_layer(key)
        if layer is None and key != DEFAULT_MODE:
            # Fond demandé indisponible (réseau, service IGN en panne...) : repli sur OSM
            self._warn_basemap_unavailable(key)
            key = DEFAULT_MODE
            layer = self._get_basemap_layer(key)
        if layer is None:
            self._warn_basemap_unavailable(key)

        self._current_basemap_key = key if layer is not None else None
        self.basemap_layer = layer
        # Compatibilité : l'ancien code s'appuyait sur self.osm_layer comme "le" fond de plan
        self.osm_layer = layer

        self._update_basemap_attribution()
        if refresh:
            self._refresh_canvas_layers()

    def _get_basemap_layer(self, key):
        """Renvoie la couche raster du fond 'key' (créée au premier besoin puis mise en cache)."""
        if key in self._basemap_layers:
            return self._basemap_layers[key]

        from qgis.core import QgsRasterLayer, QgsDataSourceUri

        cfg = BASEMAPS[key]
        # IMPORTANT : on passe par QgsDataSourceUri pour construire l'URI. Les URL IGN (WMTS)
        # contiennent elles-mêmes des '&' et des '=', qui seraient sinon confondus avec les
        # séparateurs de paramètres de l'URI QGIS ("type=xyz&url=...&zmax=...") : l'URI
        # construite "à la main" par simple concaténation serait alors silencieusement tronquée.
        uri = QgsDataSourceUri()
        uri.setParam("type", "xyz")
        uri.setParam("url", cfg["url"])
        uri.setParam("zmin", str(cfg["zmin"]))
        uri.setParam("zmax", str(cfg["zmax"]))
        encoded = uri.encodedUri().data().decode("utf-8")

        layer = QgsRasterLayer(encoded, cfg["label"], "wms")
        if not layer.isValid():
            layer = None
        self._basemap_layers[key] = layer
        return layer

    # ------------------------------------------------------------------
    # Affichage : attribution + avertissements
    # ------------------------------------------------------------------

    def _update_basemap_attribution(self):
        label = getattr(self, "basemap_attribution_label", None)
        if label is None:
            return
        key = self._current_basemap_key
        label.setText(BASEMAPS[key]["attribution"] if key else "Fond de plan indisponible")

        btn = getattr(self, "basemap_button", None)
        if btn is not None and key:
            suffix = " (auto)" if self._basemap_mode == AUTO_MODE else ""
            btn.setToolTip(f"Fond actuel : {BASEMAPS[key]['label']}{suffix}\nCliquer pour changer")

        positioner = getattr(self, "_basemap_overlay_positioner", None)
        if positioner is not None:
            positioner.reposition()

    def _warn_basemap_unavailable(self, key):
        if key in self._basemap_warned:
            return
        self._basemap_warned.add(key)
        label = BASEMAPS.get(key, {}).get("label", key)
        if getattr(self, "iface", None):
            self.iface.messageBar().pushMessage(
                "Attention",
                f"Fond « {label} » indisponible (vérifiez la connexion internet).",
                level=1)

    # ------------------------------------------------------------------
    # Mémorisation du choix
    # ------------------------------------------------------------------

    @staticmethod
    def _load_basemap_preference():
        try:
            from qgis.core import QgsSettings
            return str(QgsSettings().value(SETTINGS_KEY, DEFAULT_MODE))
        except Exception:
            return DEFAULT_MODE

    @staticmethod
    def _save_basemap_preference(mode):
        try:
            from qgis.core import QgsSettings
            QgsSettings().setValue(SETTINGS_KEY, mode)
        except Exception:
            pass  # la mémorisation est un confort : jamais bloquante