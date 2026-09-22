# -*- coding: utf-8 -*-
"""
Mixin regroupant tout ce qui concerne le canevas cartographique embarqué dans le
dialogue : création du canevas, fond de plan OpenStreetMap, style de la couche des
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

        # Fond de plan OpenStreetMap (tuiles XYZ), chargé comme une couche raster classique
        osm_uri = "type=xyz&url=https://tile.openstreetmap.org/{z}/{x}/{y}.png&zmax=19&zmin=0"
        self.osm_layer = QgsRasterLayer(osm_uri, "OpenStreetMap", "wms")
        if self.osm_layer.isValid():
            self.map_canvas.setLayers([self.osm_layer])
            self.map_canvas.setExtent(self.osm_layer.extent())
        else:
            # Si les tuiles ne sont pas accessibles (pas de réseau), la carte reste vide mais fonctionnelle
            if self.iface:
                self.iface.messageBar().pushMessage(
                    "Attention", "Fond OpenStreetMap indisponible (vérifiez la connexion internet).", level=1)

        # Insertion du canevas dans le conteneur prévu par le .ui
        layout = self.mapContainer.layout()
        if layout is None:
            layout = QtWidgets.QVBoxLayout(self.mapContainer)
            layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.map_canvas)

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

        # --- SÉLECTION D'ENTITÉ PAR CLIC SUR LA CARTE ---
        # L'outil reste actif en permanence (pas besoin d'activer un mode particulier) :
        # un simple clic identifie l'entité sous le curseur, un glisser déplace la carte.
        self.map_click_tool = _ClickIdentifyTool(self.map_canvas, self.on_map_canvas_clicked)
        self.map_canvas.setMapTool(self.map_click_tool)
        self.map_canvas.setCursor(QtCore.Qt.CursorShape.CrossCursor)

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
        aperçu des parcelles (si actif) > site(s) > fond OpenStreetMap.
        """
        if not self.map_canvas:
            return

        layers = []
        outline_layer = getattr(self, 'parcelles_outline_layer', None)
        if outline_layer is not None:
            layers.append(outline_layer)
        if self.layer is not None:
            layers.append(self.layer)
        if self.osm_layer is not None and self.osm_layer.isValid():
            layers.append(self.osm_layer)

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