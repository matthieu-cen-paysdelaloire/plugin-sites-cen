# -*- coding: utf-8 -*-
"""
shortcut_creator.py
====================

Génère un raccourci sur le Bureau de l'utilisateur, permettant d'ouvrir le
formulaire "MAJ des sites CEN" directement (double-clic), sans passer par
l'interface complète de QGIS.

Ce module est totalement indépendant du formulaire d'édition (fichier .ui) :
il est appelé depuis un bouton dédié du menu du plugin (voir
plugin_sites_cen.py) et n'a aucun effet sur le reste de l'interface.

Fonctionnement par système d'exploitation :
    - Windows : raccourci .lnk (icône personnalisée incluse), créé via un
      script VBScript temporaire (WScript.Shell), sans dépendance externe
      (pas besoin de pywin32).
    - macOS   : script .command exécutable, pointant vers le Python fourni
      par QGIS.app.
    - Linux   : fichier .desktop standard (icône incluse), pointant vers
      python3.

Le raccourci pointe vers 'lancer_plugin.py', qui
initialise QGIS en mode autonome et ouvre directement le formulaire.
"""
import os
import platform
import subprocess
import tempfile

from qgis.core import QgsApplication


PLUGIN_TITLE = "MAJ des sites CEN"


def _plugin_dir():
    return os.path.dirname(os.path.abspath(__file__))


def _desktop_dir():
    """Retourne le chemin du Bureau de l'utilisateur (Windows/macOS/Linux, FR/EN)."""
    home = os.path.expanduser("~")
    for name in ("Desktop", "Bureau"):
        candidate = os.path.join(home, name)
        if os.path.isdir(candidate):
            return candidate
    # Repli : dossier personnel si aucun dossier "Bureau"/"Desktop" trouvé
    return home


def _to_portable_windows_path(path):
    """
    Remplace, dans un chemin Windows résolu, le préfixe correspondant au profil de
    l'utilisateur COURANT (celui qui crée le raccourci) par la variable d'environnement
    littérale %APPDATA% ou %USERPROFILE%.
    """
    appdata = os.environ.get("APPDATA")
    userprofile = os.environ.get("USERPROFILE")

    normalized = os.path.normpath(path)

    if appdata and normalized.lower().startswith(os.path.normpath(appdata).lower()):
        return "%APPDATA%" + normalized[len(os.path.normpath(appdata)):]
    if userprofile and normalized.lower().startswith(os.path.normpath(userprofile).lower()):
        return "%USERPROFILE%" + normalized[len(os.path.normpath(userprofile)):]

    # Chemin hors du profil utilisateur standard (ex: installation QGIS portable,
    # profil personnalisé...) : on le laisse tel quel, en absolu, faute de mieux.
    return normalized


def _find_windows_python_qgis(prefix_path):
    """
    A partir du prefixPath de QGIS (ex: 'C:/Program Files/QGIS 3.34/apps/qgis'),
    retrouve le script Python fourni par l'installation QGIS (habituellement
    'bin/python-qgis.bat', mais le nom exact et l'arborescence varient selon les
    versions/distributions de QGIS : on élargit donc la recherche plutôt que de ne
    tester qu'un seul nom figé).
    """
    if not prefix_path:
        return None
    install_dir = os.path.dirname(os.path.dirname(prefix_path))

    search_dirs = [
        os.path.join(install_dir, "bin"),
        os.path.normpath(os.path.join(install_dir, "..", "bin")),
        install_dir,
    ]

    # Noms connus, du plus courant (versions LTR classiques) aux variantes
    # rencontrées sur certaines installations (OSGeo4W, versions récentes...).
    known_names = [
        "python-qgis.bat", "python-qgis-ltr.bat", "python-qgis-dev.bat",
        "python-qgis.cmd",
    ]

    for directory in search_dirs:
        for name in known_names:
            candidate = os.path.join(directory, name)
            if os.path.isfile(candidate):
                return candidate

    # Repli : n'importe quel .bat/.cmd du dossier 'bin' dont le nom contient à la
    # fois "python" et "qgis" (insensible à la casse), pour couvrir les variantes
    # de nommage qu'on n'aurait pas anticipées.
    for directory in search_dirs:
        if not os.path.isdir(directory):
            continue
        try:
            entries = os.listdir(directory)
        except OSError:
            continue
        for entry in entries:
            lower = entry.lower()
            if lower.endswith((".bat", ".cmd")) and "python" in lower and "qgis" in lower:
                return os.path.join(directory, entry)

    return None


def _prompt_for_python_qgis(parent):
    """
    Repli manuel : si la détection automatique échoue (nouvelle version de QGIS,
    installation non standard...), on demande à l'utilisateur de sélectionner
    lui-même le script de lancement Python de QGIS, plutôt que d'abandonner.
    """
    from qgis.PyQt.QtWidgets import QFileDialog

    path, _ = QFileDialog.getOpenFileName(
        parent,
        "Sélectionner le script Python de QGIS (ex : python-qgis.bat, dans le "
        "dossier 'bin' de l'installation QGIS)",
        "C:\\Program Files\\",
        "Scripts (*.bat *.cmd);;Tous les fichiers (*.*)")
    return path or None


def create_desktop_shortcut(parent=None):
    """
    Crée un raccourci sur le Bureau qui lance lancer_plugin.py avec le Python
    fourni par QGIS.

    :param parent: widget parent optionnel, utilisé uniquement si une boîte de
        dialogue de sélection manuelle du script Python de QGIS doit s'afficher
        (repli en cas d'échec de la détection automatique sur Windows).
    :return: tuple (succes: bool, message: str)
    """
    system = platform.system()
    plugin_dir = _plugin_dir()
    launcher_script = os.path.join(plugin_dir, "lancer_plugin.py")
    icon_dir = os.path.join(plugin_dir, "resources")
    desktop = _desktop_dir()

    if not os.path.isfile(launcher_script):
        return False, (
            "Fichier 'lancer_plugin.py' introuvable dans le dossier du plugin.\n"
            "Le raccourci n'a pas pu être créé."
        )

    prefix_path = QgsApplication.prefixPath()

    if system == "Windows":
        return _create_windows_shortcut(launcher_script, plugin_dir, icon_dir, desktop, prefix_path, parent)
    elif system == "Darwin":
        return _create_macos_shortcut(launcher_script, icon_dir, desktop, prefix_path)
    else:
        return _create_linux_shortcut(launcher_script, icon_dir, desktop)


def _create_windows_shortcut(launcher_script, plugin_dir, icon_dir, desktop, prefix_path, parent=None):
    """ Crée sur le Bureau un raccourci **`MAJ des sites CEN.lnk`** qui lance `lancer_plugin.py` avec le Python fourni par QGIS. """
    python_qgis = _find_windows_python_qgis(prefix_path)

    if python_qgis is None:
        # La détection automatique a échoué (nouvelle version de QGIS, arborescence
        # non standard...) : on demande à l'utilisateur de localiser lui-même le
        # script, au lieu d'abandonner directement.
        python_qgis = _prompt_for_python_qgis(parent)

    # Icône dédiée au raccourci (fond marron clair), différente de celle du
    # plugin dans QGIS (fond vert), afin de pouvoir distinguer les deux
    # icônes lorsqu'elles apparaissent côte à côte (barre d'outils QGIS /
    # Bureau).
    icon_path = os.path.join(icon_dir, "icon_shortcut.ico")

    if python_qgis is None:
        return False, (
            "Impossible de localiser automatiquement le script Python de QGIS "
            "(ex : 'python-qgis.bat') à partir de l'installation actuelle, et "
            "aucun fichier n'a été sélectionné manuellement.\n"
            "Le raccourci n'a pas pu être créé.\n\n"
            "Astuce : ce fichier se trouve normalement dans le dossier 'bin' de "
            "votre installation QGIS (ex : C:\\Program Files\\QGIS 4.2.0\\bin)."
        )

    shortcut_path = os.path.join(desktop, f"{PLUGIN_TITLE}.lnk")

    # IMPORTANT : on n'écrit PAS les chemins du plugin (script, dossier de travail,
    # icône) en absolu résolu pour l'utilisateur courant, car cela figerait le
    # raccourci sur le compte de la personne qui le crée. On les rend "portables"
    # via %APPDATA%/%USERPROFILE% (cf. _to_portable_windows_path) afin que le
    # raccourci fonctionne aussi pour un collègue qui a installé le plugin dans son
    # propre profil QGIS. python-qgis.bat, lui, est sous Program Files (commun à
    # tous les comptes) : pas besoin de le rendre portable.
    portable_launcher_script = _to_portable_windows_path(launcher_script)
    portable_plugin_dir = _to_portable_windows_path(plugin_dir)
    portable_icon_path = _to_portable_windows_path(icon_path)

    # Création du raccourci .lnk via un script VBScript temporaire (WScript.Shell) :
    # aucune dépendance externe (pywin32) n'est nécessaire.
    vbs_content = (
        'Set oWS = WScript.CreateObject("WScript.Shell")\n'
        f'sLinkFile = "{shortcut_path}"\n'
        'Set oLink = oWS.CreateShortcut(sLinkFile)\n'
        f'oLink.TargetPath = "{python_qgis}"\n'
        f'oLink.Arguments = """{portable_launcher_script}"""\n'
        f'oLink.WorkingDirectory = "{portable_plugin_dir}"\n'
        'oLink.WindowStyle = 1\n'
        f'oLink.IconLocation = "{portable_icon_path}"\n'
        f'oLink.Description = "{PLUGIN_TITLE}"\n'
        'oLink.Save\n'
    )

    fd, vbs_path = tempfile.mkstemp(suffix=".vbs")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(vbs_content)
        result = subprocess.run(
            ["cscript", "//nologo", vbs_path],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            return False, f"Erreur lors de la création du raccourci :\n{result.stderr}"
    finally:
        try:
            os.remove(vbs_path)
        except OSError:
            pass

    return True, (
        f"Raccourci créé dans votre dossier d'utilisateur, retrouvable en suivant le chemin d'acès suivant :\n{shortcut_path}\n\n"
        "Note : si ce raccourci est partagé avec un(e) collègue, il ne fonctionnera "
        "que si cette personne a elle aussi installé le plugin dans son propre profil "
        "QGIS (chaque compte Windows a son propre dossier de plugins)."
    )


def _create_macos_shortcut(launcher_script, icon_dir, desktop, prefix_path):
    """ Crée sur le Bureau un script bash exécutable **`MAJ des sites CEN.command`**.   """
    # Pour QGIS.app, prefixPath() pointe généralement vers .../QGIS.app/Contents/MacOS
    qgis_python = os.path.join(prefix_path or "", "bin", "python3")
    if not os.path.isfile(qgis_python):
        qgis_python = "python3"  # repli si non trouvé (environnement QGIS via Homebrew, etc.)

    shortcut_path = os.path.join(desktop, f"{PLUGIN_TITLE}.command")

    script_content = (
        "#!/bin/bash\n"
        f'export QGIS_PREFIX_PATH="{prefix_path or ""}"\n'
        f'"{qgis_python}" "{launcher_script}"\n'
    )
    with open(shortcut_path, "w", encoding="utf-8") as f:
        f.write(script_content)
    os.chmod(shortcut_path, 0o755)

    return True, (
        f"Raccourci créé sur le Bureau :\n{shortcut_path}\n\n"
        "Astuce : lors du tout premier double-clic, macOS peut demander une "
        "confirmation (clic droit > Ouvrir, puis confirmer)."
    )


def _create_linux_shortcut(launcher_script, icon_dir, desktop):
    """ Crée sur le Bureau un fichier **`MAJ_des_sites_CEN.desktop`** (espaces remplacés par des `_`). """
    # Icône dédiée au raccourci (fond marron clair), différente de celle du
    # plugin dans QGIS (fond vert), afin de pouvoir distinguer les deux
    # icônes lorsqu'elles apparaissent côte à côte (barre d'outils QGIS /
    # Bureau).
    icon_path = os.path.join(icon_dir, "icon_shortcut.png")
    shortcut_path = os.path.join(desktop, f"{PLUGIN_TITLE.replace(' ', '_')}.desktop")

    desktop_entry = (
        "[Desktop Entry]\n"
        "Type=Application\n"
        f"Name={PLUGIN_TITLE}\n"
        "Comment=Ouvrir le formulaire d'édition des sites CEN sans ouvrir QGIS\n"
        f'Exec=python3 "{launcher_script}"\n'
        f"Icon={icon_path}\n"
        "Terminal=false\n"
        "Categories=Office;GIS;\n"
    )
    with open(shortcut_path, "w", encoding="utf-8") as f:
        f.write(desktop_entry)
    os.chmod(shortcut_path, 0o755)

    return True, (
        f"Raccourci créé sur le Bureau :\n{shortcut_path}\n\n"
        "Selon votre environnement de bureau, un clic droit puis "
        "'Autoriser le lancement' (ou 'Faire confiance') peut être nécessaire "
        "au premier lancement."
    )
