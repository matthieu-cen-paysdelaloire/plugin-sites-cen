# -*- coding: utf-8 -*-
"""
dialog_bilan_mixin.py
=======================

Mixin regroupant le panneau "Bilan foncier" : saisie de l'année, calcul (via
dialog_bilan_data), et affichage sous forme d'indicateurs clés + graphiques
interactifs (chart_widgets). Ce panneau remplace temporairement le formulaire
de saisie (dans formStack), à la manière du sous-formulaire des parcelles.

Ce mixin n'est PAS utilisable seul : il est combiné avec QtWidgets.QDialog (et
les autres mixins) dans AttributeEditorSitesCENDialog.
Cependant, il est "indépendant" de l'interface de saisie globale ("plugin_sites_cen_dialog_base.ui").
"""
import datetime

from qgis.PyQt import QtWidgets, QtGui, QtCore

from .. import dialog_bilan_data as bilan_data
from .chart_widgets import InteractiveBarChart, InteractivePieChart, InteractiveLineChart


class BilanMixin:

    def setup_bilan_panel(self):
        """
        Construit (une seule fois, à l'ouverture du plugin) le panneau "Bilan foncier"
        et l'ajoute comme nouvelle page de formStack. Le contenu n'est calculé qu'à la
        demande (bouton "Générer le bilan"), pas à la construction.
        """
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # --- Saisie de l'année ---
        controls_layout = QtWidgets.QHBoxLayout()
        controls_layout.addWidget(QtWidgets.QLabel("Bilan de l'année :"))

        self.spinBilanAnnee = QtWidgets.QSpinBox()
        self.spinBilanAnnee.setRange(1990, 2100)
        self.spinBilanAnnee.setValue(datetime.date.today().year)
        # Flèches natives masquées au profit de boutons -/+ dédiés (voir ci-dessous) : sur
        # certaines installations, le bouton flèche du haut du QSpinBox ne répond pas au clic
        # (probablement un souci de thème/style propre à l'environnement Qt local).
        self.spinBilanAnnee.setButtonSymbols(QtWidgets.QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.spinBilanAnnee.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.spinBilanAnnee.setFixedWidth(70)

        btn_annee_moins = QtWidgets.QToolButton()
        btn_annee_moins.setText("−")
        btn_annee_moins.setToolTip("Année précédente")
        btn_annee_moins.setAutoRaise(True)
        btn_annee_moins.clicked.connect(self.spinBilanAnnee.stepDown)

        btn_annee_plus = QtWidgets.QToolButton()
        btn_annee_plus.setText("+")
        btn_annee_plus.setToolTip("Année suivante")
        btn_annee_plus.setAutoRaise(True)
        btn_annee_plus.clicked.connect(self.spinBilanAnnee.stepUp)

        controls_layout.addWidget(btn_annee_moins)
        controls_layout.addWidget(self.spinBilanAnnee)
        controls_layout.addWidget(btn_annee_plus)

        self.btnGenererBilan = QtWidgets.QPushButton("Générer le bilan")
        self.btnGenererBilan.clicked.connect(self.generer_bilan_foncier)
        controls_layout.addWidget(self.btnGenererBilan)
        controls_layout.addStretch()

        # Pictogramme d'aide, même mécanisme (survol) que le reste du formulaire
        self.lblBilanHelp = QtWidgets.QLabel('<a href="?" style="text-decoration:none;">❓ Comment ça marche ?</a>')
        self.lblBilanHelp.setObjectName("lblBilanHelp")  # requis : on_help_link_hovered s'appuie sur l'objectName
        self.lblBilanHelp.setTextFormat(QtCore.Qt.TextFormat.RichText)
        self.lblBilanHelp.setTextInteractionFlags(QtCore.Qt.TextInteractionFlag.LinksAccessibleByMouse)
        self.lblBilanHelp.linkHovered.connect(self.on_help_link_hovered)
        controls_layout.addWidget(self.lblBilanHelp)

        layout.addLayout(controls_layout)

        # --- Chiffres clés, sous forme de petites cartes visuelles ---
        kpi_grid = QtWidgets.QGridLayout()
        kpi_grid.setSpacing(8)

        self._kpi_cards = {}
        self._kpi_detail_labels = {}
        kpi_specs = [
            ("nouveaux_sites", "Nouveaux sites"),
            ("total_sites", "Total sites"),
            ("ha_total_absolu", "Surface totale (ha)"),
            ("ha_supplementaires_total", "Surface ajoutée (ha)"),
            ("nb_communes", "Communes concernées"),
        ]
        # Indicateurs proches, regroupés dans une seule carte à sous-lignes plutôt qu'en
        # cartes séparées (voir _create_multi_kpi_card) : on passait à 11 cartes distinctes,
        # ce qui devenait difficile à lire d'un coup d'œil.
        multi_kpi_specs = [
            ("Surfaces protégées (ha)", [
                ("ha_natura2000", "Natura 2000"),
                ("ha_rnx", "RNX"),
                ("ha_zpf", "ZPF"),
            ]),
            ("Actes signés", [
                ("nb_actes_propriete", "Propriété"),
                ("nb_actes_bail", "Bail emphytéotique"),
                ("nb_actes_ore", "ORE"),
            ]),
        ]

        # Les 5 cartes simples sur une grille (1 ligne), et les 2 cartes groupées sur une
        # disposition INDÉPENDANTE juste en dessous (voir plus bas) : avec une seule grille
        # partagée, ces 2 cartes n'auraient occupé que la largeur des 2 premières colonnes
        # de la grille du dessus, sans s'étirer sur le reste de la largeur disponible.
        for col, (key, caption) in enumerate(kpi_specs):
            card, value_label, detail_label = self._create_kpi_card(caption)
            kpi_grid.addWidget(card, 0, col)
            self._kpi_cards[key] = value_label
            self._kpi_detail_labels[key] = detail_label

        layout.addLayout(kpi_grid)

        # Ligne à part (QHBoxLayout, stretch=1 sur chaque carte) : les 2 cartes groupées se
        # partagent alors À PARTS ÉGALES toute la largeur disponible, quel que soit le
        # nombre de colonnes de la grille au-dessus.
        multi_kpi_row = QtWidgets.QHBoxLayout()
        multi_kpi_row.setSpacing(8)
        for title, subitems in multi_kpi_specs:
            card, value_labels = self._create_multi_kpi_card(title, subitems)
            multi_kpi_row.addWidget(card, 1)
            self._kpi_cards.update(value_labels)
        layout.addLayout(multi_kpi_row)

        # --- Détail affiché au clic sur une barre/part de graphique ---
        self.labelBilanDetail = QtWidgets.QLabel("")
        self.labelBilanDetail.setWordWrap(True)
        self.labelBilanDetail.setStyleSheet(
            "background-color: #eef6ff; border: 1px solid #b6d4f5; border-radius: 4px; padding: 6px;")
        self.labelBilanDetail.setVisible(False)
        layout.addWidget(self.labelBilanDetail)

        # --- Graphiques + Nouveaux sites, organisés en onglets ---
        self.bilanTabWidget = QtWidgets.QTabWidget()

        graphs_tab_scroll = QtWidgets.QScrollArea()
        graphs_tab_scroll.setWidgetResizable(True)
        graphs_tab_scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)

        graphs_tab = QtWidgets.QWidget()
        graphs_tab_layout = QtWidgets.QVBoxLayout(graphs_tab)

        charts_layout = QtWidgets.QHBoxLayout()
        graphs_tab_layout.addLayout(charts_layout)

        bar_box = QtWidgets.QGroupBox("Surface gérée : hors sites militaires / sites militaires")
        bar_layout = QtWidgets.QVBoxLayout(bar_box)
        self.chartBilanBarres = InteractiveBarChart()
        self.chartBilanBarres.setToolTip("Cliquez sur une barre pour afficher sa valeur exacte en hectares.")
        self.chartBilanBarres.barClicked.connect(self._on_bilan_bar_clicked)
        bar_layout.addWidget(self.chartBilanBarres)
        charts_layout.addWidget(bar_box)

        pie_box = QtWidgets.QGroupBox("Répartition de la maîtrise foncière")
        pie_layout = QtWidgets.QVBoxLayout(pie_box)

        # Case à cocher : exclut du camembert les parcelles dont le site associé a la case
        # "Terrain militaire" cochée dans sa fiche (sites_cen.terrain_militaire), en s'appuyant
        # sur la même clé de jointure que la vue parcellaire (id_site_cen <-> id_site_fcen_parc).
        self.chkCamembertHorsMilitaire = QtWidgets.QCheckBox("Exclure les sites militaires")
        self.chkCamembertHorsMilitaire.setToolTip(
            "Retire du graphique les parcelles rattachées à un site coché "
            "\"Terrain militaire\" dans sa fiche.")
        self.chkCamembertHorsMilitaire.toggled.connect(self._refresh_camembert)
        pie_layout.addWidget(self.chkCamembertHorsMilitaire)

        self.chartBilanCamembert = InteractivePieChart()
        self.chartBilanCamembert.setToolTip(
            "Cliquez sur une part pour afficher sa valeur exacte en hectares et son pourcentage.")
        self.chartBilanCamembert.sliceClicked.connect(self._on_bilan_pie_clicked)
        pie_layout.addWidget(self.chartBilanCamembert)
        charts_layout.addWidget(pie_box)

        # --- 3e graphique : évolution année par année, jusqu'à l'année choisie ---
        line_box = QtWidgets.QGroupBox("Évolution annuelle : surface totale")
        line_layout = QtWidgets.QVBoxLayout(line_box)

        # Même principe que la case du camembert : exclut, via la même jointure réelle sur
        # sites_cen.terrain_militaire, les parcelles rattachées à un site militaire.
        self.chkEvolutionHorsMilitaire = QtWidgets.QCheckBox("Exclure les sites militaires")
        self.chkEvolutionHorsMilitaire.setToolTip(
            "Retire du graphique les parcelles rattachées à un site coché "
            "\"Terrain militaire\" dans sa fiche.")
        self.chkEvolutionHorsMilitaire.toggled.connect(self._refresh_evolution_chart)
        line_layout.addWidget(self.chkEvolutionHorsMilitaire)

        self.chartBilanEvolution = InteractiveLineChart()
        self.chartBilanEvolution.setToolTip(
            "Cliquez sur un point pour afficher sa valeur exacte, année par année, "
            "jusqu'à l'année sélectionnée ci-dessus.")
        self.chartBilanEvolution.pointClicked.connect(self._on_bilan_evolution_point_clicked)
        line_layout.addWidget(self.chartBilanEvolution)
        graphs_tab_layout.addWidget(line_box)

        graphs_tab_scroll.setWidget(graphs_tab)
        self.bilanTabWidget.addTab(graphs_tab_scroll, "Graphiques")

        # --- Onglet "Nouveaux sites" : liste en colonne des sites créés dans l'année ---
        new_sites_tab = QtWidgets.QWidget()
        new_sites_layout = QtWidgets.QVBoxLayout(new_sites_tab)
        self.listBilanNouveauxSites = QtWidgets.QListWidget()
        new_sites_layout.addWidget(self.listBilanNouveauxSites)
        self.bilanTabWidget.addTab(new_sites_tab, "Nouveaux sites")

        layout.addWidget(self.bilanTabWidget, 1)

        self.bilan_panel_index = self.formStack.addWidget(panel)
        self._bilan_last_resultats = None
        self._bilan_bar_labels = []
        self._bilan_pie_labels = []
        self._bilan_pie_values = []
        self._bilan_evolution = {
            'annees': [], 'ha_total': [], 'ha_total_hors_militaire': [],
        }

    @staticmethod
    def _create_kpi_card(caption):
        """
        Construit une petite carte visuelle pour un chiffre clé du bilan foncier :
        une grande valeur en gras, avec sa légende en dessous. Retourne (carte, label_valeur,
        label_detail) — label_detail est une petite ligne supplémentaire, vide par défaut,
        que l'appelant peut utiliser pour une précision visible en permanence (pas seulement
        au survol).
        """
        card = QtWidgets.QFrame()
        card.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        card.setStyleSheet(
            "QFrame { background-color: #f5f7fa; border: 1px solid #d8dee6; border-radius: 6px; }")

        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(8, 8, 8, 8)
        card_layout.setSpacing(2)

        value_label = QtWidgets.QLabel("—")
        value_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        value_label.setStyleSheet("font-size: 15pt; font-weight: bold; color: #1b5e20; border: none;")

        caption_label = QtWidgets.QLabel(caption)
        caption_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        caption_label.setWordWrap(True)
        caption_label.setStyleSheet("font-size: 8pt; color: #5a6472; border: none;")

        detail_label = QtWidgets.QLabel("")
        detail_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        detail_label.setWordWrap(True)
        detail_label.setStyleSheet("font-size: 7pt; color: #7a8592; border: none;")
        detail_label.setVisible(False)

        card_layout.addWidget(value_label)
        card_layout.addWidget(caption_label)
        card_layout.addWidget(detail_label)

        return card, value_label, detail_label

    @staticmethod
    def _create_multi_kpi_card(title, subitems):
        """
        Variante "groupée" de _create_kpi_card : une seule carte affiche plusieurs valeurs
        étroitement liées, réparties HORIZONTALEMENT côte à côte (valeur en gras au-dessus
        de son sous-titre, comme une carte simple en miniature), plutôt que de multiplier
        les cartes individuelles pour des indicateurs proches (ex : Natura 2000 / RNX / ZPF,
        ou Propriété / Bail / ORE).

        :param subitems: liste de tuples (clé, sous-titre)
        :return: (carte, dict {clé: label_valeur}) — le dict a exactement la même forme que
            self._kpi_cards pour les cartes simples, donc le code qui fait
            self._kpi_cards[cle].setText(...) fonctionne à l'identique, que la clé
            appartienne à une carte simple ou à une carte groupée.
        """
        card = QtWidgets.QFrame()
        card.setFrameShape(QtWidgets.QFrame.Shape.StyledPanel)
        card.setStyleSheet(
            "QFrame { background-color: #f5f7fa; border: 1px solid #d8dee6; border-radius: 6px; }")

        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(8, 6, 8, 6)
        card_layout.setSpacing(4)

        title_label = QtWidgets.QLabel(title)
        title_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        title_label.setWordWrap(True)
        title_label.setStyleSheet("font-size: 8pt; font-weight: bold; color: #5a6472; border: none;")
        card_layout.addWidget(title_label)

        subitems_row = QtWidgets.QHBoxLayout()
        subitems_row.setSpacing(4)

        value_labels = {}
        for key, sub_caption in subitems:
            sub_block = QtWidgets.QVBoxLayout()
            sub_block.setSpacing(0)

            value_label = QtWidgets.QLabel("—")
            value_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            value_label.setStyleSheet("font-size: 12pt; font-weight: bold; color: #1b5e20; border: none;")
            sub_block.addWidget(value_label)

            sub_label = QtWidgets.QLabel(sub_caption)
            sub_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            sub_label.setWordWrap(True)
            sub_label.setStyleSheet("font-size: 7pt; color: #5a6472; border: none;")
            sub_block.addWidget(sub_label)

            subitems_row.addLayout(sub_block, 1)
            value_labels[key] = value_label

        card_layout.addLayout(subitems_row)
        return card, value_labels

    def toggle_bilan_view(self, checked):
        """
        Bascule vers (ou hors de) l'onglet "Bilan foncier", appelé par le bouton dédié
        (📊 Bilan foncier, placé à côté de "Activer le mode édition").
        """
        if checked:
            self.btnToggleSimpleView.setEnabled(False)
            self.formStack.setCurrentIndex(self.bilan_panel_index)
            if self._bilan_last_resultats is None:
                self.generer_bilan_foncier()
        else:
            self.btnToggleSimpleView.setEnabled(True)
            # Retour à la vue précédente (formulaire du site, ou détail parcelle
            # si le sous-formulaire des parcelles était affiché)
            self.formStack.setCurrentIndex(1 if self.leftListStack.currentIndex() == 1 else 0)

    def generer_bilan_foncier(self):
        """Calcule le bilan foncier pour l'année saisie et met à jour indicateurs + graphiques."""
        gpkg_path = bilan_data.gpkg_path_from_layer(self.layer)
        if not gpkg_path:
            QtWidgets.QMessageBox.warning(
                self, "Bilan foncier",
                "Aucun GeoPackage chargé : ouvrez d'abord un site pour pouvoir générer un bilan.")
            return

        year = self.spinBilanAnnee.value()

        try:
            resultats = bilan_data.compute_bilan_foncier(gpkg_path, year)
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Bilan foncier",
                f"Erreur lors du calcul du bilan foncier :\n{e}")
            return

        # Série "Évolution annuelle" (3e graphique) : calcul séparé, avec sa propre gestion
        # d'erreur pour ne pas faire échouer tout le reste du bilan si elle pose problème.
        try:
            self._bilan_evolution = bilan_data.compute_evolution_annuelle(gpkg_path, year)
        except Exception:
            self._bilan_evolution = {
                'annees': [], 'ha_total': [], 'ha_total_hors_militaire': [],
            }

        self._bilan_last_resultats = resultats
        self.labelBilanDetail.setVisible(False)

        # --- Chiffres clés (cartes) ---
        self._kpi_cards['nouveaux_sites'].setText(str(resultats['nouveaux_sites']))
        self._kpi_cards['total_sites'].setText(str(resultats['total_sites']))
        # NOTE : on affiche ici resultats['ha_total'] (filtré sur l'année choisie), et non
        # resultats['ha_total_absolu'] (somme de TOUTES les parcelles, sans filtre de date) —
        # cette dernière ne variait jamais selon l'année sélectionnée, ce qui n'était pas le
        # comportement attendu pour cette carte "Surface totale (ha)".
        self._kpi_cards['ha_total_absolu'].setText(f"{resultats['ha_total']:.2f}")
        self._kpi_cards['ha_supplementaires_total'].setText(f"{resultats['ha_supplementaires_total']:.2f}")
        self._kpi_cards['nb_communes'].setText(str(resultats['nb_communes']))
        self._kpi_cards['ha_natura2000'].setText(f"{resultats['ha_natura2000']:.2f}")
        self._kpi_cards['ha_rnx'].setText(f"{resultats['ha_rnx']:.2f}")
        self._kpi_cards['ha_zpf'].setText(f"{resultats['ha_zpf']:.2f}")
        self._kpi_cards['nb_actes_propriete'].setText(str(resultats['nb_actes_propriete']))
        self._kpi_cards['nb_actes_bail'].setText(str(resultats['nb_actes_bail']))
        self._kpi_cards['nb_actes_ore'].setText(str(resultats['nb_actes_ore']))

        # Détail visible en permanence (hors sites militaires), directement dans la carte
        detail_label = self._kpi_detail_labels['ha_supplementaires_total']
        detail_label.setText(
            f"dont {resultats['ha_supplementaires_hors_militaire']:.2f} ha hors sites militaires")
        detail_label.setVisible(True)

        # --- Onglet "Nouveaux sites" : liste en colonne ---
        self.listBilanNouveauxSites.clear()
        noms = resultats['noms_nouveaux_sites']
        if noms:
            self.listBilanNouveauxSites.addItems([str(n) for n in noms])
        else:
            self.listBilanNouveauxSites.addItem("Aucun nouveau site créé cette année.")
        self.bilanTabWidget.setTabText(1, f"Nouveaux sites ({len(noms)})")

        # --- Graphique en barres : surface hors militaire / militaire ---
        self._bilan_bar_labels = ["Hors sites militaires", "Sites militaires"]
        bar_values = [resultats['ha_total_hors_militaire'], resultats['ha_total_militaire']]
        self.chartBilanBarres.set_data(
            self._bilan_bar_labels, bar_values,
            colors=[QtGui.QColor(52, 152, 219), QtGui.QColor(230, 126, 34)],
            value_suffix=" ha")

        # --- Camembert : propriété / maîtrise d'usage / convention de gestion / autre ---
        self._bilan_pie_labels = ["Propriété [P1]", "Maîtrise d'usage (ORE/bail) [O, L1]", "Convention de gestion [C7, C8]", "Autre"]
        self._refresh_camembert()

        # --- Graphique linéaire : évolution annuelle jusqu'à l'année choisie ---
        self._refresh_evolution_chart()

    def _refresh_evolution_chart(self):
        """
        (Re)dessine le graphique d'évolution annuelle à partir de la dernière série
        calculée, en choisissant "toutes entités" ou "hors sites militaires" selon l'état
        de chkEvolutionHorsMilitaire. Ne re-requête pas la base : les deux jeux de valeurs
        sont déjà présents dans self._bilan_evolution (voir generer_bilan_foncier).
        """
        evolution = self._bilan_evolution
        if not evolution.get('annees'):
            return

        ha_total_serie = (evolution['ha_total_hors_militaire']
                           if self.chkEvolutionHorsMilitaire.isChecked()
                           else evolution['ha_total'])

        self.chartBilanEvolution.set_data(
            evolution['annees'],
            [
                {"name": "Surface totale (ha)", "values": ha_total_serie,
                 "color": QtGui.QColor(52, 152, 219)},
            ])

    def _refresh_camembert(self):
        """
        (Re)dessine le camembert "Répartition de la maîtrise foncière" à partir du dernier
        bilan calculé, en choisissant le jeu de valeurs "toutes entités" ou "hors sites
        militaires" selon l'état de la case à cocher chkCamembertHorsMilitaire. Appelée à la
        fois après un calcul de bilan et à chaque bascule de la case, sans requêter à nouveau
        la base (les deux jeux de valeurs sont déjà présents dans _bilan_last_resultats).
        """
        resultats = self._bilan_last_resultats
        if not resultats:
            return

        if self.chkCamembertHorsMilitaire.isChecked():
            propriete = resultats['ha_propriete_hors_militaire']
            usage = resultats['ha_maitrise_usage_hors_militaire']
            convention = resultats['ha_convention_gestion_hors_militaire']
            total = resultats['ha_total_hors_militaire_join'] or 0
        else:
            propriete = resultats['ha_propriete']
            usage = resultats['ha_maitrise_usage']
            convention = resultats['ha_convention_gestion']
            total = resultats['ha_total'] or 0

        autre = max(total - propriete - usage - convention, 0)
        self._bilan_pie_values = [propriete, usage, convention, autre]
        self.labelBilanDetail.setVisible(False)
        self.chartBilanCamembert.set_data(
            self._bilan_pie_labels, self._bilan_pie_values,
            colors=[QtGui.QColor(46, 204, 113), QtGui.QColor(155, 89, 182),
                    QtGui.QColor(52, 152, 219), QtGui.QColor(189, 195, 199)])

    def _on_bilan_bar_clicked(self, index):
        """Affiche la valeur exacte de la barre cliquée."""
        if not self._bilan_last_resultats or index >= len(self._bilan_bar_labels):
            return
        label = self._bilan_bar_labels[index]
        value = [
            self._bilan_last_resultats['ha_total_hors_militaire'],
            self._bilan_last_resultats['ha_total_militaire'],
        ][index]
        self.labelBilanDetail.setText(f"<b>{label}</b> : {value:.2f} ha")
        self.labelBilanDetail.setVisible(True)

    def _on_bilan_pie_clicked(self, index):
        """Affiche la valeur exacte et le pourcentage de la part de camembert cliquée."""
        if not self._bilan_last_resultats or index >= len(self._bilan_pie_labels):
            return
        label = self._bilan_pie_labels[index]
        value = self._bilan_pie_values[index]
        total = sum(self._bilan_pie_values)
        pct = (100 * value / total) if total else 0
        suffixe = " (hors sites militaires)" if self.chkCamembertHorsMilitaire.isChecked() else ""
        self.labelBilanDetail.setText(f"<b>{label}</b>{suffixe} : {value:.2f} ha ({pct:.1f} % du total)")
        self.labelBilanDetail.setVisible(True)

    def _on_bilan_evolution_point_clicked(self, index_serie, index_point):
        """Affiche la valeur exacte du point cliqué sur le graphique d'évolution annuelle."""
        annees = self._bilan_evolution.get('annees', [])
        if index_point >= len(annees):
            return
        annee = annees[index_point]
        hors_militaire = self.chkEvolutionHorsMilitaire.isChecked()
        suffixe = " (hors sites militaires)" if hors_militaire else ""
        key = 'ha_total_hors_militaire' if hors_militaire else 'ha_total'
        valeur = self._bilan_evolution[key][index_point]
        self.labelBilanDetail.setText(f"<b>Surface totale (ha)</b>{suffixe} en {annee} : {valeur:.2f} ha")
        self.labelBilanDetail.setVisible(True)
