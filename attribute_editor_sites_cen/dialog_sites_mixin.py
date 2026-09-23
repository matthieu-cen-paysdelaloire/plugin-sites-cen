# -*- coding: utf-8 -*-
"""
Mixin regroupant la gestion de la liste des sites (colonne de gauche) : peuplement
depuis la couche SIG, filtrage par texte/responsable, statistiques de complétude,
et mise à jour du formulaire lors du changement de sélection.
"""
from qgis.PyQt import QtWidgets, QtCore, QtGui
from qgis.core import NULL

from .dialog_data import alpha_sort_key


class SitesMixin:

    def refresh_stats(self):
        """
        Permet de décompter le nombre de sites à compléter (au moins 1 champ manquant,
        donc oranges + rouges) sur le nombre total de sites
        """
        total = self.listSites.count()
        inc = sum(1 for i in range(total)
                if self.count_missing_fields(self.features_dict[self.listSites.item(i).data(QtCore.Qt.ItemDataRole.UserRole)]) >= 1)
        self.setWindowTitle(f"Gestionnaire CEN - {inc} à compléter sur {total}")

    def set_item_style(self, item, feat):
        """
        Colore le nom du site dans la liste selon le nombre de champs manquants : orange dès
        qu'il en manque au moins 1, rouge au-delà de 5 (sinon couleur normale).
        """
        missing = self.count_missing_fields(feat)
        font = item.font()
        if missing > 5:
            item.setForeground(QtGui.QColor('red'))
            font.setBold(True)
        elif missing >= 1:
            item.setForeground(QtGui.QColor('orange'))
            font.setBold(True)
        else:
            item.setForeground(QtGui.QColor('black'))
            font.setBold(False)
        item.setFont(font)

    def apply_doc_gestion_lock(self):
        """
        "Présence Doc Gestion" = NON : il n'existe alors, par définition, aucun document de
        gestion à décrire pour ce site. On remplit donc automatiquement les champs qui en
        dépendent (nom, évaluation, surface, dates) avec une valeur "néant" cohérente, puis on
        les verrouille pour empêcher toute saisie contradictoire tant que cette réponse reste
        NON. Dès que la réponse change (OUI, Ne sais pas, ou -- À renseigner --), ces champs
        sont redéverrouillés pour une saisie normale ; les valeurs déjà en place ne sont volon-
        tairement pas effacées, afin de ne rien perdre si l'utilisateur change d'avis.
        """
        is_non = self.cbDocPres.currentText() == "NON"

        if is_non:
            self.txtDocNom.setText("/")
            self.cbDocEval.setCurrentText("Pas d'évaluation")
            self.spinSurfDoc.setValue(0)
            self.chkDateIniNull.setChecked(True)
            self.chkDateMajNull.setChecked(True)
            self.chkDateFinNull.setChecked(True)

        for widget in (self.txtDocNom, self.cbDocEval, self.spinSurfDoc):
            widget.setEnabled(not is_non)
        # Les champs date eux-mêmes restent pilotés par leur propre case "Pas de date à
        # renseigner" (déjà cochée et grisée ci-dessus) : on se contente donc de verrouiller
        # les 3 cases pour empêcher l'utilisateur de les décocher tant que NON est actif.
        for checkbox in (self.chkDateIniNull, self.chkDateMajNull, self.chkDateFinNull):
            checkbox.setEnabled(not is_non)

        self.check_field_validity()

    def on_selection_changed(self):
        """
        Permet d'associer les descriptions des différents champs en fonction de la valeur contenue dans les dictionnaires de données
        """
        # Identification du site sélectionné, récupération de l'élément cliqué dans la liste
        items = self.listSites.selectedItems()
        if not items: return
        self.current_fid = items[0].data(QtCore.Qt.ItemDataRole.UserRole)
        feat = self.features_dict[self.current_fid]

        # Blocage du signal entre le formulaire et la table attributaire de la couche SIG
        # (permet d'éviter au formulaire de devoir refaire des calculs si l'on possède des formules effectuant des calculs automatiques)
        self.blockSignals(True)

        try:
            # Cherche, dans le dictionnaire PROPRE à ce widget (et lui seul), la clé associée à la valeur
            # brute de la table SIG (jointure attributaire en quelque sorte)
            for field, widget in self.field_map.items():
                try:
                    val = feat[field]
                except Exception:
                    val = None
                # NOTE : l'écriture dans le widget est elle aussi protégée (ex : valeur non
                # convertible en nombre pour un QSpinBox). Sans ce garde-fou, une seule valeur
                # imprévue interrompait toute la boucle : les champs suivants gardaient alors
                # l'ancienne valeur (et l'ancienne couleur) du site précédemment sélectionné,
                # sans qu'aucune erreur ne soit visible pour l'utilisateur.
                try:
                    if isinstance(widget, QtWidgets.QComboBox):
                        dico = self.combo_dicts.get(widget, {})
                        found = False
                        # Comparaison insensible à la casse et aux espaces superflus : la valeur
                        # enregistrée en base ("Evaluation Finale") ne correspond pas toujours
                        # EXACTEMENT, caractère pour caractère, à celle du dictionnaire ("Evaluation
                        # finale"). Sans cet assouplissement, une simple différence de casse fait
                        # retomber le champ sur "-- À renseigner --" alors qu'une valeur existe bien.
                        val_normalized = str(val).strip().casefold()
                        for k, v in dico.items():
                            if str(v).strip().casefold() == val_normalized:
                                widget.setCurrentText(k)
                                found = True
                                break
                        if not found: widget.setCurrentText("-- À renseigner --")
                    elif isinstance(widget, (QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox)):
                        widget.setValue(int(val) if val is not None and str(val) != 'NULL' else -1)
                    elif isinstance(widget, QtWidgets.QDateEdit):
                        has_valid_date = val and hasattr(val, 'isValid') and val.isValid()
                        null_checkbox = self.date_null_checkboxes.get(widget)
                        if has_valid_date:
                            widget.setDate(val)
                            if null_checkbox is not None:
                                null_checkbox.setChecked(False)
                        else:
                            widget.setDate(QtCore.QDate.currentDate())
                            if null_checkbox is not None:
                                null_checkbox.setChecked(True)
                    elif isinstance(widget, QtWidgets.QLineEdit): widget.setText(str(val) if val and str(val) != 'None' else "")
                    elif isinstance(widget, QtWidgets.QTextEdit): widget.setPlainText(str(val) if val and str(val) != 'None' else "")
                except Exception:
                    # Valeur imprévue pour CE champ précis (ex : texte dans un champ numérique) :
                    # on retombe sur un état "vide/à renseigner" propre à ce widget plutôt que de
                    # laisser planter toute la boucle, afin que TOUS les autres champs (et la
                    # surbrillance qui suit) restent fiables.
                    if isinstance(widget, QtWidgets.QComboBox):
                        widget.setCurrentText("-- À renseigner --")
                    elif isinstance(widget, (QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox)):
                        widget.setValue(-1)
                    elif isinstance(widget, QtWidgets.QDateEdit):
                        widget.setDate(QtCore.QDate.currentDate())
                        null_checkbox = self.date_null_checkboxes.get(widget)
                        if null_checkbox is not None:
                            null_checkbox.setChecked(True)
                    elif isinstance(widget, QtWidgets.QLineEdit) or isinstance(widget, QtWidgets.QTextEdit):
                        widget.clear()

            # Reconstruction de la cascade géologique (opération inverse) : à partir du code final
            # déjà enregistré en base, on retrouve le chemin de branches qui y mène dans le
            # dictionnaire, puis on présélectionne les 4 listes en conséquence.
            try:
                code_geol_val = feat['code_geol']
            except Exception:
                code_geol_val = None
            try:
                self.populate_geol_cascade_from_value(code_geol_val)
            except Exception:
                # Idem : un souci sur la reconstruction de la cascade géologique ne doit jamais
                # empêcher le reste du formulaire (champs en lecture seule, surbrillance, carte)
                # de se mettre à jour correctement.
                pass

            # Champs complémentaires en lecture seule (simple visualisation, aucune sauvegarde)
            def fmt_readonly(v, field=None):
                if v is None or str(v) == 'NULL':
                    return ""
                if hasattr(v, 'toString'):
                    return v.toString('dd/MM/yyyy')
                raw = str(v)
                # Traduit la valeur brute en description lisible si un dictionnaire existe pour ce champ
                dico = self.site_value_dicts.get(field)
                if dico and raw in dico:
                    return dico[raw]
                return raw

            for field, widget in self.site_readonly_field_map.items():
                try:
                    val = feat[field]
                    widget.setText(fmt_readonly(val, field))
                except Exception:
                    # Un champ manquant ou inattendu ne doit jamais interrompre le reste du formulaire
                    # (carte, validation, etc.) : on laisse simplement ce champ vide.
                    widget.setText("")
        finally:
            # Déblocage du signal entre le formulaire et la table : ce bloc s'exécute TOUJOURS,
            # même si une erreur imprévue est survenue plus haut, pour ne jamais laisser le
            # formulaire bloqué (carte, validation des champs, bloc géologique, etc.)
            self.blockSignals(False)

        # Ces trois lignes sont volontairement protégées : elles DOIVENT s'exécuter à chaque
        # changement de site, sinon les champs affichés garderaient la couleur/l'état du site
        # précédent (c'est exactement ce qui pouvait auparavant faire passer un champ vide
        # inaperçu, non surligné).
        try:
            self.check_field_validity()
        except Exception:
            pass
        try:
            self.update_map_selection(feat)
        except Exception:
            pass
        if hasattr(self, 'scrollArea'): self.scrollArea.setFocus()

    def populate_list(self, layer, parcelles_layer=None):
        """
        Passerelle entre QGIS et l'interface
        """
        self.layer = layer
        self.parcelles_layer = parcelles_layer
        # Le bouton "Voir les parcelles du site" n'est actif que si la couche parcelles_cen a bien été chargée
        self.btnToggleParcelles.setEnabled(self.parcelles_layer is not None)
        self.listSites.clear()
        self.features_dict.clear()
        if not self.layer: return

        # Scannage de la couche SIG, en triant les sites par ordre alphabétique de leur nom
        features_list = []
        for feat in self.layer.getFeatures():
            fid = feat.id()
            self.features_dict[fid] = feat
            nom = str(feat['NOM_SITE']) if feat['NOM_SITE'] else f"ID {fid}"
            features_list.append((nom, fid, feat))

        features_list.sort(key=lambda t: alpha_sort_key(t[0]))

        for nom, fid, feat in features_list:
            # Création de notre interface visuelle
            item = QtWidgets.QListWidgetItem(nom)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, fid)

            # Mise en forme et statistiques
            self.set_item_style(item, feat)
            self.listSites.addItem(item)
        self.refresh_stats()
        self.populate_responsable_filter()

        # Affichage de la couche des sites sur la carte, par-dessus le fond OSM
        if self.map_canvas:
            self.style_sites_layer()
            self.parcelles_outline_layer = None  # nouveau chargement : on repart sans aperçu de parcelles
            self._refresh_canvas_layers()

        # Cadrage initial de la carte sur l'emprise de la couche entière
        if self.map_canvas and self.layer.featureCount() > 0:
            from qgis.core import QgsCoordinateTransform, QgsProject
            canvas_crs = self.map_canvas.mapSettings().destinationCrs()
            extent = self.layer.extent()
            if self.layer.crs() != canvas_crs:
                transform = QgsCoordinateTransform(self.layer.crs(), canvas_crs, QgsProject.instance())
                extent = transform.transformBoundingBox(extent)
            if not extent.isEmpty():
                self.map_canvas.setExtent(extent)
                self.map_canvas.refresh()

    def save_and_close(self):
        """
        Fonction permettant de sauvegarder et de quitter le plugin (connecté à un boutton)
        """
        if self.save_current_feature():
            self.accept()

    def filter_list(self):
        """
        Fonction filtre, permettant de retrouver plus rapidement un site grâce à la barre de recherche
        et/ou au responsable de site sélectionné dans la liste déroulante à côté.
        """
        # Récupération de la saisie de l'utilisateur et le convertit en minuscule pour éviter la casse au moment de la saisie
        txt = self.txtSearch.text().lower()
        # None (valeur par défaut "-- Tous les responsables --") = pas de filtre sur ce critère
        responsable_filtre = self.cbFilterResponsable.currentData()

        # Boucle permettant de parcourir l'intégralité de nos sites, et de masquer tous les sites
        # qui ne correspondent pas à la recherche texte ET/OU au responsable sélectionné
        for i in range(self.listSites.count()):
            item = self.listSites.item(i)
            match_txt = txt in item.text().lower()

            match_responsable = True
            if responsable_filtre is not None:
                fid = item.data(QtCore.Qt.ItemDataRole.UserRole)
                feat = self.features_dict.get(fid)
                val = feat['responsable_de_site'] if feat else None
                match_responsable = (val not in (None, NULL)) and (str(val) == responsable_filtre)

            item.setHidden(not (match_txt and match_responsable))

    def populate_responsable_filter(self):
        """
        Peuple la liste déroulante de filtrage par responsable de site avec les valeurs distinctes
        trouvées dans la couche (triées par ordre alphabétique), précédées d'une valeur par défaut
        permettant d'afficher l'intégralité des sites.
        """
        self.cbFilterResponsable.blockSignals(True)
        self.cbFilterResponsable.clear()
        self.cbFilterResponsable.addItem("-- Tous les responsables --", None)

        responsables = set()
        for feat in self.features_dict.values():
            val = feat['responsable_de_site']
            if val not in (None, NULL) and str(val).strip():
                responsables.add(str(val))

        for r in sorted(responsables, key=alpha_sort_key):
            self.cbFilterResponsable.addItem(r, r)

        self.cbFilterResponsable.setCurrentIndex(0)
        self.cbFilterResponsable.blockSignals(False)
