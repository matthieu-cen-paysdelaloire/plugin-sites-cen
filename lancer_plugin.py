# -*- coding: utf-8 -*-
"""
lancer_plugin.py
=================

Point d'entrée AUTONOME du plugin "MAJ des sites CEN".

Ce script permet d'ouvrir le formulaire d'édition des sites CEN directement
depuis le Bureau (double-clic), SANS ouvrir l'application QGIS au préalable.

⚠️ QGIS doit être installé sur l'ordinateur (ses bibliothèques Python
   PyQGIS/PyQt sont réutilisées), mais son interface graphique n'est
   jamais affichée : seul le formulaire du plugin s'ouvre.

--------------------------------------------------------------------------
EN CAS DE PROBLÈME
--------------------------------------------------------------------------
Si le formulaire ne s'affiche pas après la sélection du GeoPackage :
  - Une boîte de dialogue d'erreur devrait maintenant s'afficher (version
    corrigée : toutes les erreurs sont désormais interceptées).
  - Un fichier 'lancer_plugin_erreur.log' est créé à côté de ce script,
    contenant le détail technique de l'erreur (utile pour le support).
  - Sous Windows, la fenêtre noire (console) reste ouverte en cas d'erreur
    tant que vous n'appuyez pas sur Entrée : lisez son contenu avant de
    la fermer.
"""

import os
import sys
import traceback
import datetime
import importlib


# --------------------------------------------------------------------------
# 1. Localisation du plugin et mise en place des imports
# --------------------------------------------------------------------------
PLUGIN_DIR = os.path.dirname(os.path.abspath(__file__))
PACKAGE_NAME = os.path.basename(PLUGIN_DIR)
PARENT_DIR = os.path.dirname(PLUGIN_DIR)

if PARENT_DIR not in sys.path:
    sys.path.insert(0, PARENT_DIR)

LOG_PATH = os.path.join(PLUGIN_DIR, "lancer_plugin_erreur.log")


# --------------------------------------------------------------------------
# 2. Localisation de l'installation QGIS (bibliothèques PyQGIS)
# --------------------------------------------------------------------------
QGIS_PREFIX_PATH = os.environ.get("QGIS_PREFIX_PATH", "")


def demarrer_qgis():
    """Initialise QGIS en mode autonome (sans interface QGIS) et retourne l'application Qt."""
    from qgis.core import QgsApplication

    if QGIS_PREFIX_PATH:
        QgsApplication.setPrefixPath(QGIS_PREFIX_PATH, True)

    qgs_app = QgsApplication([], True)
    qgs_app.initQgis()
    return qgs_app


def charger_couches(chemin_gpkg):
    """Charge les couches sites_cen et parcelles_cen depuis le GeoPackage sélectionné."""
    # Fonction pouvant être réutilisé dans le module "plugin_sites_cen.py" aux lignes 96-113
    
    from qgis.core import QgsVectorLayer

    uri_sites = f"{chemin_gpkg}|layername=sites_cen"
    layer = QgsVectorLayer(uri_sites, "Edition Sites CEN", "ogr")

    uri_parcelles = f"{chemin_gpkg}|layername=parcelles_cen"
    parcelles_layer = QgsVectorLayer(uri_parcelles, "Parcelles CEN", "ogr")
    if not parcelles_layer.isValid():
        parcelles_layer = None

    return layer, parcelles_layer


def _log_error():
    """Écrit la trace complète de l'erreur en cours dans un fichier log, à côté du script."""
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"\n--- {datetime.datetime.now().isoformat()} ---\n")
            f.write(traceback.format_exc())
            f.write("\n")
    except Exception:
        pass  # Le journal est une aide au diagnostic, jamais bloquant


def _show_error(title, text):
    """Affiche l'erreur dans une boîte de dialogue Qt si possible, sinon sur la console."""
    shown = False
    try:
        from qgis.PyQt.QtWidgets import QMessageBox, QApplication
        if QApplication.instance() is not None:
            QMessageBox.critical(None, title, text)
            shown = True
    except Exception:
        pass
    if not shown:
        print(f"\n{title}\n{'-' * len(title)}\n{text}\n", file=sys.stderr)


def main():
    from qgis.PyQt.QtWidgets import QFileDialog, QMessageBox

    qgs_app = None
    try:
        # 0. Initialisation de QGIS (headless)
        qgs_app = demarrer_qgis()

        # 1. Import du dialogue (APRÈS initialisation de QGIS et mise à jour de sys.path)
        dialog_module = importlib.import_module(f"{PACKAGE_NAME}.plugin_sites_cen_dialog")
        AttributeEditorSitesCENDialog = dialog_module.AttributeEditorSitesCENDialog

        # 2. Sélection du GeoPackage
        chemin_gpkg, _ = QFileDialog.getOpenFileName(
            None,
            "Sélectionner le GeoPackage",
            "",
            "GeoPackage (*.gpkg)")

        if not chemin_gpkg:
            return

        # 3. Chargement des couches
        layer, parcelles_layer = charger_couches(chemin_gpkg)

        if not layer.isValid():
            QMessageBox.critical(
                None, "Erreur",
                "La couche 'sites_cen' est introuvable dans ce GeoPackage.\n\n"
                f"Fichier sélectionné :\n{chemin_gpkg}")
            return

        if parcelles_layer is None:
            QMessageBox.warning(
                None, "Attention",
                "Couche 'parcelles_cen' introuvable : "
                "le sous-formulaire des parcelles sera désactivé.")

        # 4. Ouverture du formulaire (sans iface, puisqu'il n'y a pas de QGIS visible)
        dlg = AttributeEditorSitesCENDialog(iface=None)
        dlg.populate_list(layer, parcelles_layer)

        dlg.show()
        # Force la fenêtre au premier plan (utile si elle s'ouvre derrière une autre fenêtre)
        dlg.raise_()
        dlg.activateWindow()

        # 5. Boucle d'événements Qt (QgsApplication hérite de QApplication)
        # PyQt6 (QGIS 4) a supprimé exec_() au profit de exec() ; PyQt5 (QGIS 3)
        # conserve les deux. On utilise donc exec() s'il existe, exec_() sinon.
        if hasattr(qgs_app, "exec"):
            qgs_app.exec()
        else:
            qgs_app.exec_()

    except Exception:
        _log_error()
        _show_error(
            "Erreur au lancement du plugin",
            "Une erreur inattendue a empêché l'ouverture du formulaire.\n\n"
            f"Le détail technique a été enregistré dans :\n{LOG_PATH}\n\n"
            "Merci de transmettre ce fichier si le problème persiste.\n\n"
            f"Résumé :\n{traceback.format_exc(limit=2)}"
        )
        # Sous Windows, garde la fenêtre console ouverte le temps de lire l'erreur
        if os.name == "nt":
            try:
                input("\nAppuyez sur Entrée pour fermer cette fenêtre...")
            except Exception:
                pass

    finally:
        if qgs_app is not None:
            try:
                qgs_app.exitQgis()
            except Exception:
                pass


if __name__ == "__main__":
    main()
