# -*- coding: utf-8 -*-
"""
Mixin regroupant l'infrastructure générale de l'interface : correction du style des
listes déroulantes, infobulles d'aide, remplissage initial des widgets, connexion
des signaux, bascule "vue simplifiée / mode édition", et filtre d'événements
(molette + verrouillage des combobox tant que le mode édition n'est pas actif).
"""
from qgis.PyQt import QtWidgets, QtCore, QtGui

from . import dialog_data as data
from . import dialog_field_maps as field_maps


class UiMixin:

    def fix_combobox_popup_style(self):
        """
        Corrige un problème d'affichage où le texte de la liste déroulante d'une combobox
        devient invisible (texte blanc sur fond blanc) au survol d'un élément. La feuille de
        style globale du dialogue ne s'applique pas toujours de façon fiable au menu déroulant
        (fenêtre popup gérée un peu à part par Qt) : on force donc explicitement le style
        directement sur chaque liste déroulante, ce qui est beaucoup plus fiable.
        """
        popup_style = (
            "QAbstractItemView {"
            "  background-color: white;"
            "  color: #2c3e50;"
            "  selection-background-color: white;"
            "  selection-color: #3498db;"
            "  outline: 0;"
            "}"
        )
        for widget in self.findChildren(QtWidgets.QComboBox):
            widget.view().setStyleSheet(popup_style)

    def setup_tooltips(self):
        """
        Configuration des infobulles : chaque label concerné se termine désormais par un
        pictogramme ❓ cliquable (lien HTML). L'infobulle ne s'affiche que lorsque la souris
        survole ce pictogramme, plus sur l'ensemble du texte du label.
        """
        self.help_texts = data.HELP_TEXTS
        # Le bloc géologique suit désormais le même système ❓ que les autres champs, via le
        # label lblGeolTitle ajouté à l'intérieur de la boîte (un QGroupBox ne prend pas en
        # charge le texte riche/lien dans son titre natif).

        for label_name in self.help_texts:
            label_widget = getattr(self, label_name, None)
            if label_widget is not None:
                label_widget.linkHovered.connect(self.on_help_link_hovered)

        # Cas particulier du bloc géologique : le mécanisme "lien HTML + survol" utilisé pour
        # tous les autres champs ne s'est pas montré fiable à cet endroit précis. On utilise donc
        # ici le mécanisme natif et le plus simple de Qt (setToolTip), posé directement sur le
        # petit widget ❓ dédié, sans passer par linkHovered.
        self.lblGeol1Help.setToolTip(
            "Quel est l'intérêt géologique du site ? Utilisez les listes pour générer le code géologique du site."
        )

    def on_help_link_hovered(self, link):
        """
        Affiche l'infobulle du champ uniquement lorsque le curseur survole le pictogramme ❓
        (link non vide), et la masque dès qu'il le quitte (link vide, signal émis par Qt).
        """
        if link:
            label_widget = self.sender()
            text = self.help_texts.get(label_widget.objectName(), "")
            if text:
                QtWidgets.QToolTip.showText(QtGui.QCursor.pos(), text, label_widget)
        else:
            QtWidgets.QToolTip.hideText()

    def init_ui_elements(self):
        """
        Permet de remplir de remplir les widgets au moment de l'ouverture du plugin
        """
        # Configuration des dictionnaires, permettant d'associer CHAQUE widget à SON dictionnaire de données.
        # Stocké en attribut (self.combo_dicts) pour être réutilisé tel quel dans on_selection_changed()
        # et save_current_feature(), et ainsi éviter toute confusion entre des listes qui partagent
        # certaines valeurs (ex : plusieurs listes utilisent 0/1, ou "OUI"/"NON").
        self.combo_dicts = field_maps.build_combo_dicts(self)

        # Boucle de remplissage automatique des valeurs dans les dictionnaires
        for cb, d in self.combo_dicts.items():
            cb.clear(); cb.addItems(d.keys())

        # Cas à part de la Géologie, permet de seulement remplir la 1ere colonne
        self.cbGeolStep1.clear();
        self.cbGeolStep1.addItems(self.dict_geol_step.keys())

    def connect_signals(self):
        """
        Permet la connexion entre nos widgets et nos fonctions
        """
        # Case "Non renseignée" cochée -> désactive (grise) le champ date associé, pour bien
        # signaler que sa valeur affichée n'a plus d'importance et ne sera pas sauvegardée
        for date_widget, checkbox in self.date_null_checkboxes.items():
            checkbox.toggled.connect(lambda checked, w=date_widget: w.setEnabled(not checked))
            # Idem pour la surbrillance rouge du champ date : elle doit se mettre à jour dès que
            # la case est cochée/décochée, pas seulement à l'ouverture du site.
            checkbox.toggled.connect(self.check_field_validity)

        # "Présence Doc Gestion" = NON : il n'existe alors, par définition, aucun document de
        # gestion à décrire. On remplit donc automatiquement les champs qui en dépendent avec
        # une valeur "néant" cohérente, et on les verrouille pour empêcher toute saisie
        # contradictoire (cf. apply_doc_gestion_lock). currentTextChanged (et non
        # currentIndexChanged) pour être également notifié lors du tout premier remplissage.
        self.cbDocPres.currentTextChanged.connect(self.apply_doc_gestion_lock)

        # Installation du filtre d'événements sur les listes déroulantes modifiables, pour pouvoir
        # bloquer leur interaction tant que le mode édition n'est pas activé (cf. toggle_simple_view)
        for widget in self.field_map.values():
            if isinstance(widget, QtWidgets.QComboBox):
                widget.installEventFilter(self)
        for cb in (self.cbGeolStep1, self.cbGeolStep2, self.cbGeolStep3, self.cbGeolStep4):
            cb.installEventFilter(self)

        # Mise en place des connexions principales (Naviguation et Boutons)
        self.txtSearch.textChanged.connect(self.filter_list)
        self.cbFilterResponsable.currentIndexChanged.connect(self.filter_list)
        self.listSites.itemSelectionChanged.connect(self.on_selection_changed)
        self.btnApply.clicked.connect(self.save_current_feature)
        self.btnCancel.clicked.connect(self.reject)
        self.button_box.accepted.connect(self.save_and_close)

        # Mise en place du sous-formulaire des parcelles (vue maître-détail)
        self.btnToggleParcelles.clicked.connect(self.toggle_parcelles_view)
        self.listParcelles.itemSelectionChanged.connect(self.on_parcelle_num_selection_changed)
        self.listParcellesProprietaires.itemSelectionChanged.connect(self.on_parcelle_selection_changed)

        # Bouton "Vue simplifiée" : masque/affiche les onglets d'informations complémentaires
        self.btnToggleSimpleView.toggled.connect(self.toggle_simple_view)

        # Mise en place de la surveillance automatique (Validation en temps réel)
        for widget in self.field_map.values():
            if isinstance(widget, QtWidgets.QComboBox): widget.currentIndexChanged.connect(self.check_field_validity)
            elif isinstance(widget, (QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox)): widget.valueChanged.connect(self.check_field_validity)
            elif isinstance(widget, QtWidgets.QLineEdit): widget.textChanged.connect(self.check_field_validity)
            elif isinstance(widget, (QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit)): widget.textChanged.connect(self.check_field_validity)

        # Mise en place des listes en cascades (Le système Géologique)
        self.cbGeolStep1.currentIndexChanged.connect(lambda: self.update_geol_cascade(1))
        self.cbGeolStep2.currentIndexChanged.connect(lambda: self.update_geol_cascade(2))
        self.cbGeolStep3.currentIndexChanged.connect(lambda: self.update_geol_cascade(3))
        self.cbGeolStep4.currentIndexChanged.connect(self.update_final_geol_code)

    def toggle_simple_view(self, checked):
        """
        Bascule le 'mode édition' : masque, DANS CHAQUE onglet (Identifiants, Statut, Surfaces...),
        les champs en lecture seule ainsi que leur en-tête, pour ne garder visibles que les champs
        modifiables (repérables par leur pictogramme ✏️). Ces derniers ne deviennent réellement
        modifiables qu'en mode édition ; en dehors, ils restent visibles mais grisés (lecture seule).
        La recherche de sites et la navigation dans les listes (sites, parcelles, propriétaires)
        restent quant à elles toujours actives, quel que soit le mode.
        """
        # Masque/affiche chaque champ complémentaire en lecture seule, ainsi que son label associé
        for field, widget in self.site_readonly_field_map.items():
            widget.setVisible(not checked)
            lbl_name = f"lbl_{widget.objectName()}"
            if hasattr(self, lbl_name):
                getattr(self, lbl_name).setVisible(not checked)

        # Masque/affiche l'en-tête "Informations (lecture seule)" de chaque onglet concerné
        tab_names = ["tab_site_ro_identifiants", "tab_site_ro_statut", "tab_site_ro_surfaces",
                     "tab_site_ro_historique", "tab_site_ro_gestion", "tab_site_ro_zpf"]
        for tab_name in tab_names:
            lbl_name = f"lbl_readonly_header_{tab_name}"
            if hasattr(self, lbl_name):
                getattr(self, lbl_name).setVisible(not checked)

        # Active/désactive réellement la saisie des champs modifiables (✏️) : en dehors du mode
        # édition, ils restent visibles mais grisés et non modifiables. La recherche de sites et
        # la navigation dans les listes (sites, parcelles, propriétaires) ne sont jamais concernées.
        # Verrouille/déverrouille la saisie des champs modifiables (✏️), en conservant le MÊME
        # rendu visuel que les champs non modifiables (texte de couleur normale, sélectionnable
        # et copiable) : QLineEdit/QTextEdit/QSpinBox/QDoubleSpinBox/QDateEdit disposent d'un
        # vrai mode "lecture seule" natif. Les QComboBox n'ont pas cet équivalent : elles restent
        # donc activées (couleur normale) mais leur interaction est bloquée par un filtre
        # d'événements (voir eventFilter) tant que le mode édition n'est pas actif.
        for field, widget in self.field_map.items():
            if field == "code_geol":
                continue  # Champ calculé automatiquement : toujours en lecture seule
            if isinstance(widget, QtWidgets.QComboBox):
                widget.setEnabled(True)
            elif isinstance(widget, (QtWidgets.QLineEdit, QtWidgets.QTextEdit,
                                      QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox, QtWidgets.QDateEdit)):
                widget.setReadOnly(not checked)

        for cb in (self.cbGeolStep1, self.cbGeolStep2, self.cbGeolStep3, self.cbGeolStep4):
            cb.setEnabled(True)

        # Cases "Non renseignée" : modifiables uniquement en mode édition. Si une case est cochée,
        # le champ date associé reste grisé même en mode édition (géré par son propre signal toggled).
        for date_widget, checkbox in self.date_null_checkboxes.items():
            checkbox.setEnabled(checked)
            if checkbox.isChecked():
                date_widget.setEnabled(False)

        self.fields_locked = not checked

        self.btnToggleSimpleView.setText(
            "Revenir à la consultation" if checked else "✏️ Activer le mode édition"
        )

    def eventFilter(self, obj, event):
        """
        Fonction permettant la maîtrise de la molette. Permet de régler le conflit entre les listes déroulantes et la barre de défilement
        Sert également à verrouiller les listes déroulantes (QComboBox) tant que le mode édition
        n'est pas activé, sans les griser (elles restent avec le même rendu que les champs
        non modifiables).
        """
        # Bloque toute interaction avec les listes déroulantes modifiables tant qu'elles sont verrouillées
        if getattr(self, 'fields_locked', False) and isinstance(obj, QtWidgets.QComboBox):
            if event.type() in (QtCore.QEvent.Type.MouseButtonPress, QtCore.QEvent.Type.MouseButtonRelease,
                                 QtCore.QEvent.Type.MouseButtonDblClick, QtCore.QEvent.Type.Wheel,
                                 QtCore.QEvent.Type.KeyPress):
                return True

        # Vérifié si l'utilisateur fait tourner sa molette
        if event.type() == QtCore.QEvent.Type.Wheel:
            # Si la souris survole un widget mais que l'utilisateur n'a pas cliqué dessus, on ignore l'action sur le widget
            if not obj.hasFocus(): return False
            #Récupération du scrolling de l'utilisateur pour l'appliquer à la barre de défilement
            if hasattr(self, 'scrollArea'):
                delta = event.angleDelta().y()
                sb = self.scrollArea.verticalScrollBar()
                sb.setValue(sb.value() - delta)
                return True
        # Permet de dire à l'applicatif d'avoir un comportement standard comme une fenêtre Windows/Linux classique
        # NB : on appelle QDialog.eventFilter directement (et non via super()) car avec les mixins,
        # l'ordre du MRO ne garantit plus que "super()" retombe sur QDialog.
        return QtWidgets.QDialog.eventFilter(self, obj, event)
