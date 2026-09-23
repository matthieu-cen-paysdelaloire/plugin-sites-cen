# -*- coding: utf-8 -*-
"""
chart_widgets.py
==================

Graphiques interactifs (barres, camembert) pour le tableau de bord "Bilan
foncier", dessinés directement au QPainter.

Pourquoi pas QtCharts (PyQtChart / PyQt6-Charts) ?
Ce module Qt n'est PAS garanti présent dans l'environnement Python de QGIS
(c'est un paquet séparé de PyQt5/PyQt6 de base, pas installé par défaut sur
toutes les distributions QGIS). Pour éviter un nouvel imprévu de compatibilité
sur ce plugin (on en a déjà eu deux : exec()/exec_(), metadata.txt...), ces
graphiques sont donc entièrement "faits maison", sur le même principe que la
barre d'échelle graphique du canevas cartographique : zéro dépendance, rendu
garanti identique sur toute installation de QGIS 3.16+ comme QGIS 4.

Interactivité : chaque widget émet un signal Qt (barClicked / sliceClicked)
avec l'index de l'élément cliqué, à connecter par l'appelant pour afficher le
détail correspondant.
"""
from qgis.PyQt import QtWidgets, QtGui, QtCore


def _event_pos(event):
    """Retourne la position (QPoint) d'un événement souris, compatible PyQt5 et PyQt6."""
    if hasattr(event, 'position'):
        return event.position().toPoint()
    return event.pos()


class InteractiveBarChart(QtWidgets.QWidget):
    """Graphique en barres verticales, avec surbrillance au survol et clic sur une barre."""

    barClicked = QtCore.pyqtSignal(int)

    DEFAULT_COLOR = QtGui.QColor(52, 152, 219)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._categories = []
        self._values = []
        self._colors = []
        self._value_suffix = ""
        self._bar_rects = []
        self._hover_index = -1
        self.setMouseTracking(True)
        self.setMinimumHeight(180)

    def set_data(self, categories, values, colors=None, value_suffix=""):
        """Définit (ou remplace) les données affichées et redessine le graphique."""
        self._categories = list(categories)
        self._values = [max(0, v or 0) for v in values]
        self._colors = colors or [self.DEFAULT_COLOR] * len(self._categories)
        self._value_suffix = value_suffix
        self._hover_index = -1
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        self._bar_rects = []
        if not self._values or max(self._values) <= 0:
            painter.setPen(QtGui.QColor(120, 120, 120))
            painter.drawText(self.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, "Aucune donnée")
            return

        margin_left, margin_right = 10, 10
        margin_top, margin_bottom = 22, 36
        plot_w = self.width() - margin_left - margin_right
        plot_h = self.height() - margin_top - margin_bottom
        if plot_w <= 0 or plot_h <= 0:
            return

        max_val = max(self._values)
        n = len(self._values)
        gap = 12
        bar_w = max((plot_w - gap * (n + 1)) / n, 4)

        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)

        x = margin_left + gap
        for i, val in enumerate(self._values):
            bar_h = 0 if max_val == 0 else (val / max_val) * plot_h
            rect = QtCore.QRectF(x, margin_top + plot_h - bar_h, bar_w, bar_h)
            self._bar_rects.append(rect)

            color = QtGui.QColor(self._colors[i % len(self._colors)])
            if i == self._hover_index:
                color = color.lighter(115)
            painter.setBrush(color)
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.drawRect(rect)

            # Valeur au-dessus de la barre
            painter.setPen(QtGui.QColor(40, 40, 40))
            painter.drawText(
                QtCore.QRectF(x - gap / 2, margin_top + plot_h - bar_h - 16, bar_w + gap, 14),
                QtCore.Qt.AlignmentFlag.AlignCenter,
                f"{val:g}{self._value_suffix}")

            # Étiquette de catégorie, sous l'axe (repliée sur plusieurs lignes si besoin)
            label_rect = QtCore.QRectF(x - gap / 2, margin_top + plot_h + 4, bar_w + gap, margin_bottom - 4)
            painter.drawText(
                label_rect,
                int(QtCore.Qt.AlignmentFlag.AlignHCenter) | int(QtCore.Qt.TextFlag.TextWordWrap),
                self._categories[i])

            x += bar_w + gap

    def mousePressEvent(self, event):
        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            return
        pos = QtCore.QPointF(_event_pos(event))
        for i, rect in enumerate(self._bar_rects):
            if rect.contains(pos):
                self.barClicked.emit(i)
                return

    def mouseMoveEvent(self, event):
        pos = QtCore.QPointF(_event_pos(event))
        new_hover = -1
        for i, rect in enumerate(self._bar_rects):
            if rect.contains(pos):
                new_hover = i
                break
        if new_hover != self._hover_index:
            self._hover_index = new_hover
            self.update()

    def leaveEvent(self, event):
        if self._hover_index != -1:
            self._hover_index = -1
            self.update()


class InteractivePieChart(QtWidgets.QWidget):
    """Camembert avec légende, surbrillance au survol et clic sur une part."""

    sliceClicked = QtCore.pyqtSignal(int)

    DEFAULT_COLORS = [
        QtGui.QColor(52, 152, 219), QtGui.QColor(230, 126, 34), QtGui.QColor(46, 204, 113),
        QtGui.QColor(155, 89, 182), QtGui.QColor(241, 196, 15), QtGui.QColor(231, 76, 60),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._labels = []
        self._values = []
        self._colors = []
        self._paths = []
        self._hover_index = -1
        self.setMouseTracking(True)
        self.setMinimumHeight(180)
        # Largeur minimale garantissant assez de place pour le camembert ET sa légende
        # (voir _LEGEND_COL_WIDTH ci-dessous, utilisée aussi pour le calcul de hauteur)
        self.setMinimumWidth(320)

    _LEGEND_COL_WIDTH = 170  # largeur de référence pour le calcul du retour à la ligne de la légende

    def set_data(self, labels, values, colors=None):
        """Définit (ou remplace) les données affichées et redessine le graphique."""
        self._labels = list(labels)
        self._values = [max(0, v or 0) for v in values]
        self._colors = colors or [
            self.DEFAULT_COLORS[i % len(self.DEFAULT_COLORS)] for i in range(len(self._labels))]
        self._hover_index = -1
        self._update_minimum_height()
        self.update()

    def _legend_font(self):
        font = QtGui.QFont()
        font.setPointSize(8)
        return font

    def _compute_legend_rows(self, legend_col_width):
        """
        Calcule, pour chaque part, le texte de légende et la hauteur de ligne nécessaire
        (avec retour à la ligne automatique) — utilisé à la fois pour dessiner la légende
        et pour garantir que le widget est assez haut pour ne jamais la couper.
        """
        fm = QtGui.QFontMetrics(self._legend_font())
        total = sum(self._values) or 1
        rows = []
        for i, label in enumerate(self._labels):
            pct = 100 * self._values[i] / total
            text = f"{label} ({pct:.0f} %)"
            bounding = fm.boundingRect(
                QtCore.QRect(0, 0, max(legend_col_width - 16, 10), 1000),
                int(QtCore.Qt.TextFlag.TextWordWrap), text)
            rows.append((text, max(bounding.height() + 6, 18)))
        return rows

    def _update_minimum_height(self):
        """
        Recalcule la hauteur minimale du widget pour que la légende (avec retour à la
        ligne) ne soit jamais coupée, quelle que soit la longueur des libellés.
        """
        rows = self._compute_legend_rows(self._LEGEND_COL_WIDTH)
        legend_h = 8 + sum(row_h + 6 for _, row_h in rows)
        self.setMinimumHeight(max(180, int(legend_h) + 16))

    def _pie_rect(self):
        side = min(self.width() * 0.42, self.height() - 10)
        side = max(side, 10)
        x = 10
        y = (self.height() - side) / 2
        return QtCore.QRectF(x, y, side, side)

    def _build_paths(self, pie_rect):
        self._paths = []
        total = sum(self._values)
        if total <= 0:
            return
        start_angle = 90.0  # démarre en haut (12h)
        for v in self._values:
            span = -360.0 * (v / total)  # sens horaire
            path = QtGui.QPainterPath()
            path.moveTo(pie_rect.center())
            path.arcTo(pie_rect, start_angle, span)
            path.closeSubpath()
            self._paths.append(path)
            start_angle += span

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        pie_rect = self._pie_rect()
        self._build_paths(pie_rect)

        total = sum(self._values)
        if total <= 0:
            painter.setPen(QtGui.QColor(120, 120, 120))
            painter.drawText(self.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, "Aucune donnée")
            return

        for i, path in enumerate(self._paths):
            color = QtGui.QColor(self._colors[i % len(self._colors)])
            if i == self._hover_index:
                color = color.lighter(115)
            painter.setBrush(color)
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 2))
            painter.drawPath(path)

        # Légende à droite du camembert, centrée verticalement au même niveau que celui-ci,
        # avec retour à la ligne pour ne jamais être coupée
        legend_x = pie_rect.right() + 16
        painter.setFont(self._legend_font())
        rows = self._compute_legend_rows(self._LEGEND_COL_WIDTH)
        legend_width = max(self._LEGEND_COL_WIDTH, self.width() - legend_x - 10)

        legend_total_h = sum(row_h + 6 for _, row_h in rows) - 6 if rows else 0
        legend_y = max((self.height() - legend_total_h) / 2, 4)
        for i, (text, row_h) in enumerate(rows):
            painter.setBrush(QtGui.QColor(self._colors[i % len(self._colors)]))
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.drawRect(QtCore.QRectF(legend_x, legend_y + 2, 10, 10))

            painter.setPen(QtGui.QColor(40, 40, 40))
            painter.drawText(
                QtCore.QRectF(legend_x + 16, legend_y, legend_width - 16, row_h),
                int(QtCore.Qt.AlignmentFlag.AlignVCenter) | int(QtCore.Qt.TextFlag.TextWordWrap),
                text)
            legend_y += row_h + 6

    def mousePressEvent(self, event):
        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            return
        pos = QtCore.QPointF(_event_pos(event))
        for i, path in enumerate(self._paths):
            if path.contains(pos):
                self.sliceClicked.emit(i)
                return

    def mouseMoveEvent(self, event):
        pos = QtCore.QPointF(_event_pos(event))
        new_hover = -1
        for i, path in enumerate(self._paths):
            if path.contains(pos):
                new_hover = i
                break
        if new_hover != self._hover_index:
            self._hover_index = new_hover
            self.update()

    def leaveEvent(self, event):
        if self._hover_index != -1:
            self._hover_index = -1
            self.update()


class InteractiveLineChart(QtWidgets.QWidget):
    """
    Graphique linéaire multi-séries (ex : évolution annuelle d'un ou plusieurs
    indicateurs), avec survol et clic sur un point pour en connaître la valeur exacte.
    Même principe "fait maison" (QPainter, zéro dépendance) que les deux autres
    graphiques de ce module.
    """

    pointClicked = QtCore.pyqtSignal(int, int)  # (index_serie, index_point)

    DEFAULT_COLORS = [QtGui.QColor(52, 152, 219), QtGui.QColor(46, 204, 113),
                       QtGui.QColor(230, 126, 34), QtGui.QColor(155, 89, 182)]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._x_labels = []
        self._series = []           # liste de dicts {"name", "values", "color"}
        self._point_positions = []  # liste (par série) de listes de QPointF
        self._hover = None          # (index_serie, index_point) ou None
        self.setMouseTracking(True)
        self.setMinimumHeight(200)

    def set_data(self, x_labels, series):
        """
        :param x_labels: labels de l'axe des X (ex : années), un par point
        :param series: liste de dicts {"name": str, "values": list[nombre], "color": QColor (optionnel)}
        """
        self._x_labels = [str(v) for v in x_labels]
        self._series = []
        for i, s in enumerate(series):
            color = s.get("color") or self.DEFAULT_COLORS[i % len(self.DEFAULT_COLORS)]
            self._series.append({
                "name": s["name"],
                "values": [(v or 0) for v in s["values"]],
                "color": QtGui.QColor(color),
            })
        self._hover = None
        self.update()

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        self._point_positions = [[] for _ in self._series]

        if not self._x_labels or not self._series:
            painter.setPen(QtGui.QColor(120, 120, 120))
            painter.drawText(self.rect(), QtCore.Qt.AlignmentFlag.AlignCenter, "Aucune donnée")
            return

        margin_left, margin_right = 46, 14
        margin_top, margin_bottom = 26, 30
        plot_w = self.width() - margin_left - margin_right
        plot_h = self.height() - margin_top - margin_bottom
        if plot_w <= 0 or plot_h <= 0:
            return

        all_values = [v for s in self._series for v in s["values"]]
        max_val = max(all_values) if all_values else 0
        if max_val <= 0:
            max_val = 1

        n = len(self._x_labels)
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)

        # Graduations Y (4 paliers) + quadrillage horizontal léger
        for step in range(5):
            y = margin_top + plot_h - (step / 4) * plot_h
            painter.setPen(QtGui.QColor(224, 227, 232))
            painter.drawLine(QtCore.QPointF(margin_left, y), QtCore.QPointF(margin_left + plot_w, y))
            painter.setPen(QtGui.QColor(120, 120, 120))
            painter.drawText(
                QtCore.QRectF(0, y - 8, margin_left - 6, 16),
                int(QtCore.Qt.AlignmentFlag.AlignRight) | int(QtCore.Qt.AlignmentFlag.AlignVCenter),
                f"{(step / 4) * max_val:.0f}")

        # Positions X (une par étiquette, régulièrement espacées)
        step_x = plot_w / max(n - 1, 1) if n > 1 else 0
        xs = [margin_left + (i * step_x if n > 1 else plot_w / 2) for i in range(n)]

        # Étiquettes X (années) : toutes si peu nombreuses, sinon on saute pour éviter le chevauchement
        label_stride = 1 if n <= 12 else (2 if n <= 24 else 3)
        painter.setPen(QtGui.QColor(90, 96, 108))
        for i, label in enumerate(self._x_labels):
            if i % label_stride != 0 and i != n - 1:
                continue
            painter.drawText(
                QtCore.QRectF(xs[i] - 20, margin_top + plot_h + 4, 40, margin_bottom - 4),
                QtCore.Qt.AlignmentFlag.AlignCenter, label)

        # Tracé des séries (ligne + points)
        for si, s in enumerate(self._series):
            color = s["color"]
            points = [QtCore.QPointF(xs[i], margin_top + plot_h - (val / max_val) * plot_h)
                      for i, val in enumerate(s["values"])]
            self._point_positions[si] = points

            painter.setPen(QtGui.QPen(color, 2))
            for i in range(len(points) - 1):
                painter.drawLine(points[i], points[i + 1])

            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            for i, pt in enumerate(points):
                is_hover = self._hover == (si, i)
                radius = 5.5 if is_hover else 3.5
                painter.setBrush(color.lighter(130) if is_hover else color)
                painter.drawEllipse(pt, radius, radius)

        # Légende (une entrée par série, en haut du graphique)
        legend_x = margin_left
        painter.setFont(font)
        for si, s in enumerate(self._series):
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(s["color"])
            painter.drawRect(QtCore.QRectF(legend_x, 6, 10, 10))
            painter.setPen(QtGui.QColor(40, 40, 40))
            text_w = painter.fontMetrics().horizontalAdvance(s["name"]) + 16
            painter.drawText(
                QtCore.QRectF(legend_x + 14, 3, text_w, 16),
                int(QtCore.Qt.AlignmentFlag.AlignLeft) | int(QtCore.Qt.AlignmentFlag.AlignVCenter),
                s["name"])
            legend_x += text_w + 18

    def _point_at(self, pos, radius=8):
        for si, points in enumerate(self._point_positions):
            for i, pt in enumerate(points):
                if QtCore.QLineF(pt, pos).length() <= radius:
                    return si, i
        return None

    def mousePressEvent(self, event):
        if event.button() != QtCore.Qt.MouseButton.LeftButton:
            return
        hit = self._point_at(QtCore.QPointF(_event_pos(event)))
        if hit is not None:
            self.pointClicked.emit(hit[0], hit[1])

    def mouseMoveEvent(self, event):
        hit = self._point_at(QtCore.QPointF(_event_pos(event)))
        if hit != self._hover:
            self._hover = hit
            self.update()

    def leaveEvent(self, event):
        if self._hover is not None:
            self._hover = None
            self.update()
