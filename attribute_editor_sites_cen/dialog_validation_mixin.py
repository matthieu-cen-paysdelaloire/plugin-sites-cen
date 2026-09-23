# -*- coding: utf-8 -*-
"""
Mixin regroupant la validation visuelle des champs (mise en surbrillance des
champs vides/invalides) et la sauvegarde de l'entité "site" actuellement affichée
dans la couche SIG.
"""
from qgis.PyQt import QtWidgets, QtCore
from qgis.core import NULL


class ValidationMixin:

    def apply_highlight(self, widget, is_invalid):
        """
        Applique le style rouge si le champ est vide ou considéré comme étant invalide. Utilisation de la méthode STYLESHEET.
        """
        if is_invalid:
            widget.setStyleSheet("background-color: #ffe6e6; border: 1px solid #ff4d4d; border-radius: 3px;")
        else:
            widget.setStyleSheet("")

    def check_field_validity(self):
        """
        Vérifie tous les champs, pour permettre la mise en surbrillance.
        """
        # ComboBoxes standards (listes de valeurs)
        combos = [self.cbLienRNX, self.cbMilitaire, self.cbType_milieu, self.cbNatureInpn,
                self.cbGeolInpn, self.cbCartoHab, self.cbTypoHab, self.cbDocPres,
                self.cbDocEval, self.cbOuverture, self.cbSensibilite, self.cbNonDiffusion]

        for cb in combos:
            # On vérifie si l'élément est visible (pour éviter de colorer des listes vides cachées)
            # et si le texte est celui par défaut
            is_invalid = cb.currentText() == "-- À renseigner --" or cb.currentText() == ""
            self.apply_highlight(cb, is_invalid)

        # ComboBoxes de la cascade géologique : certaines branches du dictionnaire s'arrêtent
        # avant la 4ème étape (toutes les branches n'ont pas la même profondeur). Dès qu'un code
        # final valide a été généré (txtGeolResult non vide), on désactive donc le rouge sur
        # l'ensemble de la cascade, même si certaines étapes restent vides par nature.
        geol_combos = [self.cbGeolStep1, self.cbGeolStep2, self.cbGeolStep3, self.cbGeolStep4]
        geol_complete = bool(self.txtGeolResult.text().strip())
        for cb in geol_combos:
            if geol_complete:
                self.apply_highlight(cb, False)
            else:
                is_invalid = cb.currentText() == "-- À renseigner --" or cb.currentText() == ""
                self.apply_highlight(cb, is_invalid)

        # SpinBoxes (Listes numériques)
        spins = [self.spinRNX, self.spinContrats, self.spinAgri, self.spinSurfContrat,
                self.spinLibreEvo, self.spinSurfDoc]
        for s in spins:
            self.apply_highlight(s, s.value() <= -1)

        # LineEdits (Edition de texte (Une seule ligne))
        lines = [self.txtGestionnaire, self.txtDocNom, self.txtUrlInpn, self.txtUrlCen, self.txtUrlPhoto, self.txtSite_responsable_de_site]
        for l in lines:
            self.apply_highlight(l, l.text().strip() == "")

        # TextEdits (Edition de texte (Multi-lignes))
        self.apply_highlight(self.txtDescription, self.txtDescription.toPlainText().strip() == "")
        self.apply_highlight(self.txtRemqSensibilite, self.txtRemqSensibilite.toPlainText().strip() == "")

        # DateEdits (dates du document de gestion) : cocher "Pas de date à renseigner" est une
        # réponse à part entière ("rien à mettre ici"), pas un champ resté vide - au même titre
        # que choisir "Pas d'évaluation" pour le champ Évaluation Doc. On ne les met donc JAMAIS
        # en rouge ici (cf. count_missing_fields, qui applique le même principe pour le comptage
        # des sites "à compléter").
        for date_widget in self.date_null_checkboxes:
            self.apply_highlight(date_widget, False)

    def save_current_feature(self):
        """
        Permet de récupérer les valeur saisies dans le formulaire, puis de les retranscrires au sein de la couche SIG
        """
        # Option de sécurité, permet de vérifier si un élément a bien été saisie dans l'éléménet 'listSites' et de vérifier si la couche SIG a bien été chargée
        items = self.listSites.selectedItems()
        if not items or not self.layer: return False

        # Permet la récupération du FID (l'identifiant unique) du polygone dans la couche SIG des sites
        item = items[0]
        fid = item.data(QtCore.Qt.ItemDataRole.UserRole)
        data_to_save = {}

        # Option permettant de parcourir tous les champs du formulaire
        for field, widget in self.field_map.items():
            if isinstance(widget, QtWidgets.QComboBox):
                # On utilise UNIQUEMENT le dictionnaire propre à ce widget (et non tous les dictionnaires),
                # pour éviter qu'une valeur partagée par plusieurs listes (ex : 0/1) ne soit mal interprétée.
                dico = self.combo_dicts.get(widget, {})
                val = dico.get(widget.currentText(), "NULL")
                data_to_save[field] = NULL if val == "NULL" else val
            elif isinstance(widget, (QtWidgets.QSpinBox, QtWidgets.QDoubleSpinBox)):
                data_to_save[field] = NULL if widget.value() <= -1 else widget.value()
            elif isinstance(widget, QtWidgets.QDateEdit):
                null_checkbox = self.date_null_checkboxes.get(widget)
                if null_checkbox is not None and null_checkbox.isChecked():
                    data_to_save[field] = NULL
                else:
                    data_to_save[field] = widget.date()
            else:
                txt = widget.toPlainText() if hasattr(widget, 'toPlainText') else widget.text()
                data_to_save[field] = txt.strip() if txt.strip() else NULL

        # Passage de la couche SIG en mode édition, récupère l'index de l'entité dans la table attributaire et modifie la valeur pour l'objet (fid) concerné
        self.layer.startEditing()
        for field, val in data_to_save.items():
            idx = self.layer.fields().indexFromName(field)
            if idx != -1:
                self.layer.changeAttributeValue(fid, idx, val)

        # Si la modification a été effectué, la boucle va enregistrer physiquement les modifications
        if self.layer.commitChanges():
            # Permet d'enregistre le 'cache' sans devoir relire toute la couche SIG entière
            for f, v in data_to_save.items():
                self.features_dict[fid][f] = v

            #Application de nos fonctions de  et de
            self.set_item_style(item, self.features_dict[fid])
            self.refresh_stats()

            if self.iface:
                self.iface.messageBar().pushMessage("Succès", "Données sauvegardées", level=0)
            else:
                QtWidgets.QMessageBox.information(self, "Succès", "Données sauvegardées.")
            return True
        else:
            # Permet de de tout annuler si l'écriture, on revient à l'état initial pour ne pas laisser de données corrompues en mémoire
            self.layer.rollBack()
            QtWidgets.QMessageBox.warning(self, "Erreur", "La sauvegarde a échoué.")
            return False

    def count_missing_fields(self, feat):
        """
        Compte, parmi l'ensemble des champs modifiables (field_map), combien n'ont aucune
        valeur renseignée ("à renseigner"), tous champs confondus.
        """
        def is_empty(v):
            return v is None or v == NULL or str(v) == 'NULL' or str(v).strip() == ""

        # Les 3 dates du document de gestion sont exclues du comptage : une date à NULL n'y
        # signifie pas "non renseignée" mais "Pas de date à renseigner" coché volontairement
        # (réponse à part entière, cf. check_field_validity) - elles ne doivent donc jamais
        # faire compter un site comme incomplet.
        excluded_fields = {"doc_gestion_date_ini", "doc_gestion_date_maj", "doc_gestion_date_fin"}

        count = 0
        for field in self.field_map:
            if field in excluded_fields:
                continue
            try:
                val = feat[field]
            except Exception:
                val = None
            if is_empty(val):
                count += 1
        return count
