# -*- coding: utf-8 -*-
"""
Mixin regroupant le sous-formulaire "parcelles" (vue maître-détail, rattachée au
site actuellement sélectionné) : basculement entre vue sites/parcelles, filtrage
par numéro de parcelle puis par propriétaire, et affichage en lecture seule des
attributs de la parcelle choisie.
"""
from qgis.PyQt import QtWidgets, QtCore, QtGui
from qgis.core import NULL

from .dialog_data import alpha_sort_key


class ParcellesMixin:

    def toggle_parcelles_view(self):
        """
        Bascule entre la vue 'sites' et la vue 'parcelles du site sélectionné' (vue maître-détail).
        """
        if self.leftListStack.currentIndex() == 0:
            self.show_parcelles_for_selected_site()
        else:
            self.return_to_sites_view()

    def show_parcelles_for_selected_site(self):
        """
        Remplace la liste des sites par la liste des parcelles (table parcelles_cen) rattachées
        au site actuellement sélectionné, et bascule le formulaire vers la vue de détail (lecture seule).
        """
        if self.current_fid is None:
            QtWidgets.QMessageBox.information(self, "Information", "Veuillez d'abord sélectionner un site dans la liste.")
            return
        if not self.parcelles_layer:
            QtWidgets.QMessageBox.warning(self, "Attention", "La couche 'parcelles_cen' n'est pas disponible.")
            return

        # Si la vue "Bilan foncier" était ouverte, on la referme proprement AVANT de basculer
        # sur les parcelles, en décochant son bouton plutôt qu'en changeant formStack
        # directement : sans ça, btnShowBilan restait "coché" en interne (jamais redescendu),
        # ce qui laissait btnToggleSimpleView définitivement désactivé (grisé) après un passage
        # par le bilan, même après être revenu sur la vue des sites ou des parcelles.
        if hasattr(self, 'btnShowBilan') and self.btnShowBilan.isChecked():
            self.btnShowBilan.setChecked(False)

        site_feat = self.features_dict[self.current_fid]
        # Clé primaire du site (id_site_cen), comparée en tant que texte pour éviter les soucis de type (int/str)
        site_pk = str(site_feat['id_site_cen'])

        self.listParcelles.clear()
        self.listParcellesProprietaires.clear()
        self.parcelles_dict.clear()
        self.parcelles_by_num_parc = {}

        # Parcourt la couche parcelles_cen et ne garde que celles dont la clé étrangère correspond au site sélectionné
        for feat in self.parcelles_layer.getFeatures():
            if str(feat['id_site_fcen_parc']) == site_pk:
                fid = feat.id()
                self.parcelles_dict[fid] = feat
                num_parc = str(feat['num_parc']) if feat['num_parc'] not in (None, NULL) else f"ID {fid}"
                self.parcelles_by_num_parc.setdefault(num_parc, []).append(fid)

        # La liste de gauche n'affiche qu'une fois chaque numéro de parcelle (valeurs distinctes),
        # triées par ordre alphabétique ; le regroupement self.parcelles_by_num_parc permet ensuite
        # de filtrer les entités correspondantes
        for num_parc in sorted(self.parcelles_by_num_parc.keys(), key=alpha_sort_key):
            item = QtWidgets.QListWidgetItem(num_parc)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, num_parc)
            self.listParcelles.addItem(item)

        nom_site = str(site_feat['NOM_SITE']) if site_feat['NOM_SITE'] else "ce site"
        self.labelParcellesContext.setText(f"Parcelles du site : {nom_site} ({self.listParcelles.count()} numéro(s) de parcelle)")

        # Aperçu cartographique : contour de CHAQUE parcelle de ce site, avec son numéro
        # (self.parcelles_dict ne contient déjà que les parcelles de ce site, cf. ci-dessus)
        self.show_parcelles_outlines(self.parcelles_dict.values())

        # Retire la surbrillance rouge du site (posée par update_map_selection quand le site a
        # été sélectionné dans la liste) : sans ça, elle reste affichée par-dessus le contour
        # des parcelles ci-dessus, ce qui donne l'impression d'un remplissage rouge superposé.
        if self.map_highlight is not None:
            self.map_highlight.hide()
            self.map_highlight = None

        self.clear_parcelle_fields()
        self.leftListStack.setCurrentIndex(1)
        self.formStack.setCurrentIndex(1)
        self.btnToggleParcelles.setText("Retour aux sites")
        # Le bouton "Vue simplifiée" ne concerne que les onglets du formulaire des sites
        self.btnToggleSimpleView.setVisible(False)

    def return_to_sites_view(self):
        """
        Revient à la vue 'sites' (liste des sites + formulaire de saisie des sites).
        """
        # Même précaution que dans show_parcelles_for_selected_site (voir commentaire là-bas) :
        # s'assurer que le bouton "Bilan foncier" n'est pas resté coché, ce qui laisserait
        # btnToggleSimpleView désactivé.
        if hasattr(self, 'btnShowBilan') and self.btnShowBilan.isChecked():
            self.btnShowBilan.setChecked(False)

        self.leftListStack.setCurrentIndex(0)
        self.formStack.setCurrentIndex(0)
        self.btnToggleParcelles.setText("Voir les parcelles du site")
        self.btnToggleSimpleView.setVisible(True)

        # Retire l'aperçu des contours de parcelles, propre à la vue précédente
        self.hide_parcelles_outlines()

        # Recentre la carte sur le site (au lieu de rester sur la dernière parcelle affichée)
        if self.current_fid is not None:
            self.update_map_selection(self.features_dict[self.current_fid], self.layer)

    def clear_parcelle_fields(self):
        """
        Vide tous les champs du panneau de détail des parcelles (lecture seule).
        """
        for widget in self.parcelle_field_map.values():
            if hasattr(widget, 'setPlainText'):
                widget.setPlainText("")
            else:
                widget.clear()

    def on_parcelle_num_selection_changed(self):
        """
        Quand l'utilisateur clique sur un numéro de parcelle (liste de gauche, valeurs distinctes),
        filtre la liste des propriétaires pour n'y afficher QUE les entités qui partagent ce numéro
        (une seule entrée s'il n'y a pas de doublon, plusieurs sinon).
        """
        items = self.listParcelles.selectedItems()
        self.listParcellesProprietaires.clear()
        if not items:
            self.clear_parcelle_fields()
            return

        num_parc = items[0].data(QtCore.Qt.ItemDataRole.UserRole)
        fids = self.parcelles_by_num_parc.get(num_parc, [])

        def proprio_key(fid):
            val = self.parcelles_dict[fid]['proprietaires']
            return alpha_sort_key(str(val)) if val not in (None, NULL) else ""

        for fid in sorted(fids, key=proprio_key):
            feat = self.parcelles_dict[fid]
            proprio = str(feat['proprietaires']) if feat['proprietaires'] not in (None, NULL) else f"ID {fid}"
            item = QtWidgets.QListWidgetItem(proprio)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, fid)
            self.listParcellesProprietaires.addItem(item)

        if len(fids) == 1:
            # Une seule entité correspondante : sélection automatique, pas besoin d'un clic de plus
            self.listParcellesProprietaires.setCurrentRow(0)
        else:
            # Plusieurs entités partagent ce numéro : on attend que l'utilisateur précise laquelle
            self.clear_parcelle_fields()

    def on_parcelle_selection_changed(self):
        """
        Affiche, en lecture seule, l'ensemble des champs de la parcelle sélectionnée dans
        listParcellesProprietaires (aucune modification possible, simple visualisation du
        contenu de la table parcelles_cen).
        """
        items = self.listParcellesProprietaires.selectedItems()
        if not items:
            self.clear_parcelle_fields()
            return

        fid = items[0].data(QtCore.Qt.ItemDataRole.UserRole)
        feat = self.parcelles_dict.get(fid)
        if not feat:
            return

        def fmt(v, field=None):
            if v is None or str(v) == 'NULL':
                return ""
            # Mise en forme lisible des champs de type date (QDate / QDateTime)
            if hasattr(v, 'toString'):
                return v.toString('dd/MM/yyyy')
            raw = str(v)
            # Traduit la valeur brute en description lisible si un dictionnaire existe pour ce champ
            dico = self.parcelle_value_dicts.get(field)
            if dico and raw in dico:
                return dico[raw]
            return raw

        for field, widget in self.parcelle_field_map.items():
            try:
                val = feat[field]
            except KeyError:
                val = None
            text = fmt(val, field)
            if hasattr(widget, 'setPlainText'):
                widget.setPlainText(text)
            else:
                widget.setText(text)

        # Zoom + surbrillance sur la parcelle sélectionnée
        self.update_map_selection(feat, self.parcelles_layer, color=QtGui.QColor(255, 140, 0))
