# -*- coding: utf-8 -*-
"""
Mixin regroupant la logique de la cascade géologique (4 listes déroulantes en
cascade, self.dict_geol_step) : mise à jour des listes suivantes selon le choix
courant, calcul du code final, et reconstruction inverse (présélection des listes
à partir d'un code déjà enregistré en base).
"""


class GeologyMixin:

    def update_geol_cascade(self, step):
        """
        Permet la mise à jours de nos menus, pour la partie géologique de notre formulaire
        """
        # Blocage du signal entre le formulaire et la table attributaire de la couche SIG
        self.blockSignals(True)
        t1, t2, t3 = self.cbGeolStep1.currentText(), self.cbGeolStep2.currentText(), self.cbGeolStep3.currentText()

        # Vérifier si c'est bien la première ligne qui a été sélectionné
        if step == 1:
            # Reset des valeurs des autres listes si il y a eu des saisies
            self.cbGeolStep2.clear(); self.cbGeolStep3.clear(); self.cbGeolStep4.clear()
            # Recherche de la branche correspondante
            node = self.dict_geol_step.get(t1)
            # Si c'est un dictionnaire, alors on récupère toutes les clés liées au dictionnaire suivant, pour les réinjecter dans l'étape suivante
            if isinstance(node, dict): self.cbGeolStep2.addItems(node.keys())

        # Vérifier si c'est bien la seconde ligne qui a été sélectionné
        elif step == 2:
            # Reset des valeurs des autres listes si il y a eu des saisies
            self.cbGeolStep3.clear(); self.cbGeolStep4.clear()
            # Recherche de la branche correspondante
            node1 = self.dict_geol_step.get(t1, {})
            # Si c'est un dictionnaire, alors on récupère toutes les clés liées au dictionnaire suivant, pour les réinjecter dans l'étape suivante ...
            if isinstance(node1, dict):
                node2 = node1.get(t2)
                if isinstance(node2, dict): self.cbGeolStep3.addItems(node2.keys())

        # Vérifier si c'est bien la troisième ligne qui a été sélectionné
        elif step == 3:
            # Reset des valeurs des autres listes si il y a eu des saisies
            self.cbGeolStep4.clear()
            # Recherche de la branche correspondante
            node1 = self.dict_geol_step.get(t1, {})
            # Si c'est un dictionnaire, alors on récupère toutes les clés liées au dictionnaire suivant, pour les réinjecter dans l'étape suivante ...
            if isinstance(node1, dict):
                node2 = node1.get(t2, {})
                if isinstance(node2, dict):
                    node3 = node2.get(t3)
                    if isinstance(node3, dict): self.cbGeolStep4.addItems(node3.keys())

        # Relancement du signal entre le formulaire et la table attributaire + application de la fonction 'update_final_geol_code' pour les valeurs
        self.blockSignals(False)
        self.update_final_geol_code()

    def find_geol_path(self, target_value):
        """
        Parcourt le dictionnaire dict_geol_step (en profondeur) pour retrouver le chemin de clés
        (une par branche) qui mène à la valeur finale donnée. Renvoie une liste de clés (ex :
        ["Site à vocation purement biologique", "Absence de site géologique..."]) ou None si
        aucun chemin ne correspond (code non reconnu, valeur vide, etc.).
        """
        if target_value is None or str(target_value).strip() == "" or str(target_value) == 'NULL':
            return None

        def _search(node, path):
            if not isinstance(node, dict):
                return path if str(node) == str(target_value) else None
            for key, sub in node.items():
                if key == "-- À renseigner --":
                    continue
                result = _search(sub, path + [key])
                if result is not None:
                    return result
            return None

        return _search(self.dict_geol_step, [])

    def populate_geol_cascade_from_value(self, code_value):
        """
        Opération inverse de update_final_geol_code() : à partir d'un code final déjà enregistré
        en base, retrouve le chemin de branches correspondant dans le dictionnaire et présélectionne
        les 4 listes déroulantes en conséquence, afin que l'utilisateur voie les intitulés choisis
        plutôt que le seul code brut.
        """
        combos = [self.cbGeolStep1, self.cbGeolStep2, self.cbGeolStep3, self.cbGeolStep4]
        path = self.find_geol_path(code_value)

        if path is None:
            # Valeur vide ou code non reconnu (donnée ancienne, modifiée manuellement...) :
            # on réinitialise simplement la cascade sans lever d'erreur.
            for cb in combos:
                cb.setCurrentIndex(0)
            return

        for cb, key in zip(combos, path):
            idx = cb.findText(key)
            if idx >= 0:
                cb.setCurrentIndex(idx)
        # Les niveaux au-delà de la profondeur du chemin trouvé restent vides (branche plus courte)
        for cb in combos[len(path):]:
            cb.setCurrentIndex(0)

    def update_final_geol_code(self):
        """
        Permet de parcourir notre arbre et de récupérer les valeurs au bout de chaque branche de notre dictionnaire, puis de faire la concaténation de tous les valeurs récupérées
        """
        val = self.dict_geol_step
        # Boucle permettant de chekquer nos 4 listes géologiques l'une après l'autre dans l'ordre
        for cb in [self.cbGeolStep1, self.cbGeolStep2, self.cbGeolStep3, self.cbGeolStep4]:
            # Récupération du texte sélectionné par l'utilisateur pour la liste en cours
            txt = cb.currentText()
            # Arrête la boucle si : la liste est vide, c'est une valeur finale ou le texte choisit n'est pas dans le dictionnaire
            if not txt or not isinstance(val, dict) or txt not in val: break
            # La variable val définit au début de notre fonction, elle va se réduire en fonction de la sous-partie du dictionnaire correpondant au choix de l'utilisateur
            val = val[txt]
            # Détection du résultat final, si val n'est plus un dictionnaire, on arrête tout et on affiche le résultat final
            if not isinstance(val, dict):
                self.txtGeolResult.setText(str(val))
                self.check_field_validity()
                return
        # Si la boucle s'est arrêté prématurément (à cause du break) sans arriver au bout, alors on efface le code final car incomplet
        self.txtGeolResult.clear()
        self.check_field_validity()
