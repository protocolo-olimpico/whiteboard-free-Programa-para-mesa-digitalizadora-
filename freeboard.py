import sys
import os
import json
import math

os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

import fitz  # PyMuPDF
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QSlider, QSpinBox, QDoubleSpinBox, QComboBox, QAbstractSpinBox,
    QColorDialog, QFileDialog, QMessageBox, QDialog, QLabel, QCheckBox,
    QTextEdit, QTabWidget, QMenu, QFrame, QLineEdit, QGraphicsDropShadowEffect
)
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QImage, QFont, QPainterPath,
    QKeySequence, QShortcut, QAction, QTabletEvent, QPolygonF
)
from PyQt6.QtCore import Qt, QPointF, QRectF, QTimer, QByteArray, QBuffer, QIODevice, QPoint


# ================= FUNÇÕES MATEMÁTICAS E RECONHECIMENTO DE FORMAS =================
def rotate_point(px, py, cx, cy, angle_rad):
    cos_a = math.cos(angle_rad)
    sin_a = math.sin(angle_rad)
    dx = px - cx
    dy = py - cy
    return cx + dx * cos_a - dy * sin_a, cy + dx * sin_a + dy * cos_a


def dist_to_segment(p, v, w):
    l2 = (w.x() - v.x()) ** 2 + (w.y() - v.y()) ** 2
    if l2 == 0:
        return math.hypot(p.x() - v.x(), p.y() - v.y())
    t = ((p.x() - v.x()) * (w.x() - v.x()) + (p.y() - v.y()) * (w.y() - v.y())) / l2
    t = max(0.0, min(1.0, t))
    proj_x = v.x() + t * (w.x() - v.x())
    proj_y = v.y() + t * (w.y() - v.y())
    return math.hypot(p.x() - proj_x, p.y() - proj_y)


def simplify_rdp(points, epsilon):
    if len(points) < 3:
        return points
    max_dist = 0.0
    index = 0
    start = points[0]
    end = points[-1]
    for i in range(1, len(points) - 1):
        d = dist_to_segment(points[i], start, end)
        if d > max_dist:
            index = i
            max_dist = d
    if max_dist > epsilon:
        left = simplify_rdp(points[:index + 1], epsilon)
        right = simplify_rdp(points[index:], epsilon)
        return left[:-1] + right
    else:
        return [start, end]


def filter_collinear(verts, angle_thresh_deg=26.0):
    if len(verts) <= 3:
        return verts
    filtered = []
    n = len(verts)
    for i in range(n):
        prev_pt = verts[(i - 1 + n) % n]
        curr_pt = verts[i]
        next_pt = verts[(i + 1) % n]
        a1 = math.atan2(curr_pt.y() - prev_pt.y(), curr_pt.x() - prev_pt.x())
        a2 = math.atan2(next_pt.y() - curr_pt.y(), next_pt.x() - curr_pt.x())
        diff = abs(a2 - a1) * (180.0 / math.pi)
        if diff > 180.0:
            diff = 360.0 - diff
        if diff >= angle_thresh_deg:
            filtered.append(curr_pt)
    return filtered


def circle_from_3_points(p1, p2, p3):
    x1, y1 = p1.x(), p1.y()
    x2, y2 = p2.x(), p2.y()
    x3, y3 = p3.x(), p3.y()
    d = 2 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    if abs(d) < 1e-5:
        return None
    ux = ((x1**2 + y1**2) * (y2 - y3) + (x2**2 + y2**2) * (y3 - y1) + (x3**2 + y3**2) * (y1 - y2)) / d
    uy = ((x1**2 + y1**2) * (x3 - x2) + (x2**2 + y2**2) * (x1 - x3) + (x3**2 + y3**2) * (x2 - x1)) / d
    r = math.hypot(x1 - ux, y1 - uy)
    return ux, uy, r


def recognize_shape(pts_dicts, zoom):
    if len(pts_dicts) < 6:
        return None
    pts = [QPointF(p['x'], p['y']) for p in pts_dicts]
    min_x = min(p.x() for p in pts)
    min_y = min(p.y() for p in pts)
    max_x = max(p.x() for p in pts)
    max_y = max(p.y() for p in pts)
    w = max_x - min_x
    h = max_y - min_y
    diag = math.hypot(w, h)
    if diag < 22.0 / zoom:
        return None

    path_len = sum(math.hypot(pts[i].x() - pts[i-1].x(), pts[i].y() - pts[i-1].y()) for i in range(1, len(pts)))
    first_pt, last_pt = pts[0], pts[-1]
    start_end_dist = math.hypot(last_pt.x() - first_pt.x(), last_pt.y() - first_pt.y())

    is_closed = (start_end_dist < max(diag * 0.36, 34.0 / zoom)) and (path_len > diag * 1.65)
    if not is_closed:
        max_sagitta = 0.0
        mid_idx = len(pts) // 2
        for i in range(1, len(pts) - 1):
            d = dist_to_segment(pts[i], first_pt, last_pt)
            if d > max_sagitta:
                max_sagitta = d
                mid_idx = i

        if start_end_dist > 25.0 / zoom and (start_end_dist * 0.13 < max_sagitta < start_end_dist * 1.8):
            mid_pt = pts[mid_idx]
            circ = circle_from_3_points(first_pt, mid_pt, last_pt)
            if circ:
                cx, cy, r = circ
                if 15.0 / zoom < r < 3000.0 / zoom:
                    err_sum = sum(abs(math.hypot(p.x() - cx, p.y() - cy) - r) for p in pts)
                    mean_err = (err_sum / len(pts)) / r
                    if mean_err < 0.16:
                        a1 = math.atan2(first_pt.y() - cy, first_pt.x() - cx)
                        amid = math.atan2(mid_pt.y() - cy, mid_pt.x() - cx)
                        a2 = math.atan2(last_pt.y() - cy, last_pt.x() - cx)
                        norm = lambda a: (a % (2 * math.pi) + 2 * math.pi) % (2 * math.pi)
                        na1, namid, na2 = norm(a1), norm(amid), norm(a2)
                        ccw_span = norm(na2 - na1)
                        mid_in_ccw = norm(namid - na1) <= ccw_span
                        total_span = ccw_span if mid_in_ccw else -(2 * math.pi - ccw_span)

                        arc_pts = []
                        steps = 40
                        for s in range(steps + 1):
                            ang = a1 + total_span * (s / steps)
                            arc_pts.append({'x': cx + r * math.cos(ang), 'y': cy + r * math.sin(ang), 'pressure': 0.65})
                        return {'kind': 'recognized-arc', 'arc_points': arc_pts}

        return {'kind': 'line', 'start': first_pt, 'end': last_pt}

    cx = min_x + w / 2.0
    cy = min_y + h / 2.0
    rx = max(w / 2.0, 1.0)
    ry = max(h / 2.0, 1.0)
    radial_err = sum(abs(math.hypot((p.x() - cx) / rx, (p.y() - cy) / ry) - 1.0) for p in pts) / len(pts)

    simplified = simplify_rdp(pts, diag * 0.075)
    if len(simplified) > 2:
        if math.hypot(simplified[0].x() - simplified[-1].x(), simplified[0].y() - simplified[-1].y()) < diag * 0.25:
            simplified.pop()
    corners = filter_collinear(simplified, 28.0)
    num_corners = len(corners)

    if radial_err < 0.135 and num_corners != 3:
        if abs(w - h) / max(w, h) < 0.18:
            r = (w + h) / 4.0
            min_x, max_x = cx - r, cx + r
            min_y, max_y = cy - r, cy + r
        return {'kind': 'circle', 'min_x': min_x, 'min_y': min_y, 'max_x': max_x, 'max_y': max_y}

    if num_corners == 3:
        return {'kind': 'triangle', 'min_x': min_x, 'min_y': min_y, 'max_x': max_x, 'max_y': max_y}

    if num_corners == 4:
        mid_sides = [QPointF(cx, min_y), QPointF(max_x, cy), QPointF(cx, max_y), QPointF(min_x, cy)]
        box_corners = [QPointF(min_x, min_y), QPointF(max_x, min_y), QPointF(max_x, max_y), QPointF(min_x, max_y)]
        d_mid = sum(min(math.hypot(c.x() - m.x(), c.y() - m.y()) for m in mid_sides) for c in corners)
        d_box = sum(min(math.hypot(c.x() - b.x(), c.y() - b.y()) for b in box_corners) for c in corners)
        if d_mid < d_box * 0.78:
            return {'kind': 'diamond', 'min_x': min_x, 'min_y': min_y, 'max_x': max_x, 'max_y': max_y}
        if abs(w - h) / max(w, h) < 0.16:
            hs = (w + h) / 4.0
            min_x, max_x = cx - hs, cx + hs
            min_y, max_y = cy - hs, cy + hs
        return {'kind': 'rect', 'min_x': min_x, 'min_y': min_y, 'max_x': max_x, 'max_y': max_y}

    if num_corners == 5 and radial_err > 0.15:
        return {'kind': 'pentagon', 'min_x': min_x, 'min_y': min_y, 'max_x': max_x, 'max_y': max_y}

    kind = 'circle' if radial_err < 0.20 else 'rect'
    return {'kind': kind, 'min_x': min_x, 'min_y': min_y, 'max_x': max_x, 'max_y': max_y}


# ================= BOTÃO ESTILO HTML ALINHADO E COMPATÍVEL COM CANETA XP-PEN =================
class HtmlToolButton(QPushButton):
    def __init__(self, icon_str, label_str, badge_str="", parent=None):
        super().__init__(parent)
        self.icon_str = icon_str
        self.label_str = label_str
        self.badge_str = badge_str
        self.compact_mode = False
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.vbox = QVBoxLayout(self)
        self.vbox.setContentsMargins(2, 4, 2, 3)
        self.vbox.setSpacing(0)

        self.icon_lbl = QLabel(icon_str, self)
        self.icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.icon_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self.text_lbl = QLabel(label_str, self)
        self.text_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self.vbox.addWidget(self.icon_lbl)
        self.vbox.addWidget(self.text_lbl)

        self.badge_lbl = QLabel(badge_str.upper(), self)
        self.badge_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.badge_lbl.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self.toggled.connect(self.update_visual_style)
        self.update_size()
        self.update_visual_style()

    def set_compact(self, compact: bool):
        self.compact_mode = compact
        self.text_lbl.setVisible(not compact)
        self.update_size()
        self.update_visual_style()

    def set_badge(self, badge_str: str):
        self.badge_str = badge_str.upper()
        self.badge_lbl.setText(self.badge_str)
        self.badge_lbl.setVisible(bool(self.badge_str))
        self.update_badge_pos()

    def set_icon_and_label(self, icon_str: str, label_str: str = None):
        self.icon_str = icon_str
        self.icon_lbl.setText(icon_str)
        if label_str is not None:
            self.label_str = label_str
            self.text_lbl.setText(label_str)

    def update_size(self):
        if self.compact_mode:
            self.setFixedSize(42, 38)
        else:
            self.setFixedSize(52, 46)
        self.update_badge_pos()

    def update_badge_pos(self):
        self.badge_lbl.setVisible(bool(self.badge_str))
        self.badge_lbl.setGeometry(self.width() - 15, 2, 13, 12)

    def update_visual_style(self):
        checked = self.isChecked()
        bg = "rgba(0, 103, 192, 0.16)" if checked else "transparent"
        border = "1.5px solid #0067c0" if checked else "1px solid transparent"
        txt_col = "#0067c0" if checked else "#202124"
        fw = "700" if checked else "600"

        self.setStyleSheet(f"""
            HtmlToolButton {{
                background-color: {bg};
                border: {border};
                border-radius: 10px;
            }}
            HtmlToolButton:hover {{
                background-color: rgba(0, 103, 192, 0.10);
            }}
        """)
        self.icon_lbl.setStyleSheet(f"color: {txt_col}; font-size: 16px; background: transparent; border: none;")
        self.text_lbl.setStyleSheet(f"color: {txt_col}; font-size: 9.5px; font-weight: {fw}; background: transparent; border: none;")
        self.badge_lbl.setStyleSheet("""
            background-color: rgba(100, 116, 139, 0.20);
            color: #334155;
            border-radius: 3px;
            font-size: 7.5px;
            font-weight: bold;
        """)

    def tabletEvent(self, event: QTabletEvent):
        if event.type() == QTabletEvent.Type.TabletPress:
            self.click()
            event.accept()
        elif event.type() == QTabletEvent.Type.TabletRelease:
            event.accept()
        else:
            event.ignore()


# ================= CALCULADORA FLUTUANTE ARRASTÁVEL (4 OPERAÇÕES) =================
class FloatingCalculator(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(225, 300)
        self.dragging = False
        self.drag_offset = QPoint(0, 0)
        self.expression = ""

        self.setStyleSheet("""
            FloatingCalculator {
                background-color: rgba(255, 255, 255, 0.98);
                border: 1.5px solid #cbd5e1;
                border-radius: 16px;
            }
            QLabel#CalcTitle {
                color: #202124;
                font-weight: bold;
                font-size: 12.5px;
            }
            QPushButton#CloseCalcBtn {
                background-color: transparent;
                color: #64748b;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 13px;
            }
            QPushButton#CloseCalcBtn:hover {
                background-color: #fee2e2;
                color: #dc2626;
            }
            QLineEdit#CalcDisplay {
                background-color: #f8fafc;
                color: #0f172a;
                border: 1px solid #cbd5e1;
                border-radius: 9px;
                padding: 6px 8px;
                font-size: 18px;
                font-weight: bold;
            }
            QPushButton.calcBtn {
                background-color: #f1f5f9;
                color: #1e293b;
                border: 1px solid #e2e8f0;
                border-radius: 9px;
                font-size: 14px;
                font-weight: bold;
                min-height: 34px;
            }
            QPushButton.calcBtn:hover { background-color: #e2e8f0; }
            QPushButton.calcOpBtn {
                background-color: #e0f2fe;
                color: #0284c7;
                border: 1px solid #bae6fd;
                border-radius: 9px;
                font-size: 15px;
                font-weight: bold;
                min-height: 34px;
            }
            QPushButton.calcOpBtn:hover { background-color: #bae6fd; }
            QPushButton.calcEqBtn {
                background-color: #0067c0;
                color: #ffffff;
                border: none;
                border-radius: 9px;
                font-size: 15px;
                font-weight: bold;
                min-height: 34px;
            }
            QPushButton.calcEqBtn:hover { background-color: #005299; }
        """)

        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(24)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 45))
        self.setGraphicsEffect(shadow)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        title = QLabel("🧮 Calculadora")
        title.setObjectName("CalcTitle")
        header.addWidget(title)
        header.addStretch()

        close_btn = QPushButton("✕")
        close_btn.setObjectName("CloseCalcBtn")
        close_btn.setFixedSize(24, 24)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.clicked.connect(self.hide)
        header.addWidget(close_btn)
        layout.addLayout(header)

        self.display = QLineEdit("0")
        self.display.setObjectName("CalcDisplay")
        self.display.setReadOnly(True)
        self.display.setAlignment(Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.display)

        grid = QGridLayout()
        grid.setSpacing(5)
        buttons = [
            ('C', 0, 0, 'op'), ('⌫', 0, 1, 'op'), ('÷', 0, 2, 'op'), ('×', 0, 3, 'op'),
            ('7', 1, 0, 'num'), ('8', 1, 1, 'num'), ('9', 1, 2, 'num'), ('-', 1, 3, 'op'),
            ('4', 2, 0, 'num'), ('5', 2, 1, 'num'), ('6', 2, 2, 'num'), ('+', 2, 3, 'op'),
            ('1', 3, 0, 'num'), ('2', 3, 1, 'num'), ('3', 3, 2, 'num'), ('=', 3, 3, 'eq'),
            ('0', 4, 0, 'num', 1, 2), ('.', 4, 2, 'num', 1, 1)
        ]

        for btn_data in buttons:
            text, r, c, btype = btn_data[0], btn_data[1], btn_data[2], btn_data[3]
            row_span = btn_data[4] if len(btn_data) > 4 else 1
            col_span = btn_data[5] if len(btn_data) > 5 else 1

            btn = QPushButton(text)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            if btype == 'num':
                btn.setProperty("class", "calcBtn")
            elif btype == 'op':
                btn.setProperty("class", "calcOpBtn")
            else:
                btn.setProperty("class", "calcEqBtn")
                row_span = 2

            btn.clicked.connect(lambda checked, ch=text: self.on_btn_click(ch))
            grid.addWidget(btn, r, c, row_span, col_span)

        layout.addLayout(grid)

    def on_btn_click(self, ch):
        if ch == 'C':
            self.expression = ""
            self.display.setText("0")
        elif ch == '⌫':
            self.expression = self.expression[:-1]
            self.display.setText(self.expression if self.expression else "0")
        elif ch == '=':
            if not self.expression:
                return
            try:
                safe_expr = self.expression.replace('×', '*').replace('÷', '/')
                res = eval(safe_expr, {"__builtins__": None}, {})
                if isinstance(res, float):
                    res = round(res, 8)
                    if res.is_integer():
                        res = int(res)
                self.expression = str(res)
                self.display.setText(self.expression)
            except Exception:
                self.display.setText("Erro")
                self.expression = ""
        else:
            if self.display.text() == "Erro":
                self.expression = ""
            self.expression += ch
            self.display.setText(self.expression)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragging = True
            self.drag_offset = event.pos()
            self.raise_()
            event.accept()

    def mouseMoveEvent(self, event):
        if self.dragging and self.parent():
            new_pos = self.mapToParent(event.pos() - self.drag_offset)
            max_x = max(0, self.parent().width() - self.width())
            max_y = max(0, self.parent().height() - self.height())
            self.move(max(0, min(max_x, new_pos.x())), max(0, min(max_y, new_pos.y())))
            event.accept()

    def mouseReleaseEvent(self, event):
        self.dragging = False
        event.accept()


# ================= CAIXINHA POPOVER EM GRADE (LINHAS, FORMAS E SÍMBOLOS) =================
class GridPopover(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.hide()
        self.setStyleSheet("""
            GridPopover {
                background-color: rgba(255, 255, 255, 0.98);
                border: 1.5px solid #cbd5e1;
                border-radius: 14px;
            }
            QLabel.popTitle {
                color: #64748b;
                font-size: 10px;
                font-weight: bold;
                text-transform: uppercase;
                padding-top: 4px;
            }
            QPushButton.popItem {
                background-color: #f1f5f9;
                color: #202124;
                border: 1px solid transparent;
                border-radius: 8px;
                padding: 6px 4px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton.popItem:hover {
                background-color: #e0f2fe;
                border-color: #0067c0;
            }
        """)
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(22)
        shadow.setOffset(0, 5)
        shadow.setColor(QColor(0, 0, 0, 40))
        self.setGraphicsEffect(shadow)

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(10, 10, 10, 10)
        self.main_layout.setSpacing(6)

    def add_section(self, title_str, items, cols, callback):
        lbl = QLabel(title_str)
        lbl.setProperty("class", "popTitle")
        self.main_layout.addWidget(lbl)

        grid = QGridLayout()
        grid.setSpacing(5)
        for idx, (code, icon_txt, name_txt) in enumerate(items):
            btn = QPushButton(f"{icon_txt}\n{name_txt}" if name_txt else icon_txt)
            btn.setProperty("class", "popItem")
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, c=code, ic=icon_txt, nm=name_txt: (self.hide(), callback(c, ic, nm)))
            grid.addWidget(btn, idx // cols, idx % cols)
        self.main_layout.addLayout(grid)
        self.adjustSize()


# ================= QUADRO BRANCO INTERATIVO (CANVAS NATIVO) =================
class WhiteboardCanvas(QWidget):
    def __init__(self, main_win):
        super().__init__(main_win)
        self.main_win = main_win
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAcceptDrops(True)

        self.current_tool = 'pen'
        self.current_line_variant = 'line-solid'
        self.current_shape_variant = 'rect'
        self.current_color = '#1e1e1e'
        self.eraser_color = '#ffffff'
        self.eraser_mode = 'stroke'  # 'stroke', 'pixel', 'color'
        self.base_size = 5
        self.eraser_radius = 24
        self.use_pressure = True
        self.shape_recognition = True
        self.show_hover_tooltips = True

        self.tablet_active = False

        # Fontes e Texto
        self.font_family = 'Segoe UI'
        self.font_size = 24
        self.text_bold = False
        self.text_italic = False

        # Fundo e Escalas
        self.bg_pattern = 'dots'
        self.is_dark_mode = False
        self.grid_spacing = 28
        self.zoom_step_percent = 12

        # Câmera
        self.cam_x = 0.0
        self.cam_y = 0.0
        self.cam_zoom = 1.0
        self.is_panning = False
        self.space_pressed = False
        self.start_pan = QPointF(0, 0)
        self.pointer_screen_pos = QPointF(-100, -100)

        # Régua Virtual
        self.ruler_visible = False
        self.ruler_x = 550.0
        self.ruler_y = 360.0
        self.ruler_angle = 0.0
        self.ruler_length = 760.0
        self.ruler_height = 86.0
        self.dragging_ruler = False
        self.ruler_drag_offset = QPointF(0, 0)
        self.snapped_ruler_edge = None

        # Elementos e Histórico
        self.elements = []
        self.undo_history = []
        self.redo_stack = []
        self.current_element = None
        self.is_drawing = False
        self.has_unsaved_changes = False
        self.image_cache = {}
        self.erased_in_current_drag = False
        self.snapshot_before_erase = None

        # Laço e Rotação
        self.lasso_mode = 'none'
        self.lasso_points = []
        self.selected_indices = []
        self.selection_bounds = None
        self.selection_angle = 0.0
        self.active_handle = None
        self.drag_start_world = None
        self.initial_bounds = None
        self.initial_elements_snapshot = None
        self.rotate_start_angle = 0.0

        self.hold_timer = QTimer(self)
        self.hold_timer.setSingleShot(True)
        self.hold_timer.timeout.connect(self.on_hold_timeout)

        self.text_editor = QTextEdit(self)
        self.text_editor.hide()
        self.active_text_world_pos = QPointF(0, 0)
        self.editing_text_index = -1

        self.init_ruler_hud()

        self.calculator = FloatingCalculator(self)
        self.calculator.move(960, 80)
        self.calculator.hide()

    def init_ruler_hud(self):
        self.ruler_hud = QFrame(self)
        self.ruler_hud.hide()
        self.ruler_hud.setStyleSheet("""
            QFrame {
                background-color: #0067c0;
                border-radius: 14px;
                padding: 2px 6px;
            }
            QPushButton {
                background-color: rgba(0, 0, 0, 0.22);
                color: #ffffff;
                border: none;
                border-radius: 4px;
                padding: 2px 6px;
                font-size: 11px;
                font-weight: bold;
            }
            QPushButton:hover { background-color: rgba(0, 0, 0, 0.42); }
            QDoubleSpinBox {
                background-color: rgba(255, 255, 255, 0.2);
                color: #ffffff;
                border: 1px solid rgba(255, 255, 255, 0.45);
                border-radius: 4px;
                padding: 1px 4px;
                font-weight: bold;
                font-size: 11.5px;
            }
        """)
        rl = QHBoxLayout(self.ruler_hud)
        rl.setContentsMargins(4, 2, 4, 2)
        rl.setSpacing(4)

        for lbl, delta in [("-15°", -15.0), ("-1°", -1.0), ("-0.1°", -0.1)]:
            b = QPushButton(lbl)
            b.clicked.connect(lambda checked, d=delta: self.rotate_ruler_by(d))
            rl.addWidget(b)

        self.ruler_spin = QDoubleSpinBox()
        self.ruler_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.ruler_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.ruler_spin.setFixedWidth(56)
        self.ruler_spin.setRange(-360.0, 360.0)
        self.ruler_spin.setDecimals(1)
        self.ruler_spin.setSingleStep(0.1)
        self.ruler_spin.setSuffix("°")
        self.ruler_spin.valueChanged.connect(self.set_ruler_exact_angle)
        rl.addWidget(self.ruler_spin)

        for lbl, delta in [("+0.1°", 0.1), ("+1°", 1.0), ("+15°", 15.0)]:
            b = QPushButton(lbl)
            b.clicked.connect(lambda checked, d=delta: self.rotate_ruler_by(d))
            rl.addWidget(b)

        b_zero = QPushButton("0°")
        b_zero.clicked.connect(lambda: self.set_ruler_exact_angle(0.0))
        rl.addWidget(b_zero)

        b_90 = QPushButton("90°")
        b_90.clicked.connect(lambda: self.set_ruler_exact_angle(90.0))
        rl.addWidget(b_90)

        self.ruler_hud.adjustSize()

    def update_ruler_hud_pos(self):
        if not self.ruler_visible:
            self.ruler_hud.hide()
            return
        self.ruler_hud.show()
        self.ruler_hud.adjustSize()
        hw = self.ruler_hud.width() / 2
        hh = self.ruler_hud.height() / 2
        self.ruler_hud.move(int(self.ruler_x - hw), int(self.ruler_y - hh))
        norm_ang = round(((self.ruler_angle % 360.0) + 360.0) % 360.0, 1)
        self.ruler_spin.blockSignals(True)
        self.ruler_spin.setValue(norm_ang)
        self.ruler_spin.blockSignals(False)

    def rotate_ruler_by(self, delta):
        self.ruler_angle = round(self.ruler_angle + delta, 1)
        self.update_ruler_hud_pos()
        self.update()

    def set_ruler_exact_angle(self, val):
        self.ruler_angle = round(float(val), 1)
        self.update_ruler_hud_pos()
        self.update()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.main_win.position_floating_dock()

    def screen_to_world(self, sx, sy):
        return QPointF((sx - self.cam_x) / self.cam_zoom, (sy - self.cam_y) / self.cam_zoom)

    def world_to_screen(self, wx, wy):
        return QPointF(wx * self.cam_zoom + self.cam_x, wy * self.cam_zoom + self.cam_y)

    def push_undo(self):
        self.has_unsaved_changes = True
        self.undo_history.append(json.loads(json.dumps(self.elements)))
        if len(self.undo_history) > 40:
            self.undo_history.pop(0)

    def get_qimage(self, b64_str):
        if b64_str not in self.image_cache:
            ba = QByteArray.fromBase64(b64_str.encode('utf-8'))
            img = QImage.fromData(ba)
            self.image_cache[b64_str] = img
        return self.image_cache[b64_str]

    def qimage_to_b64(self, qimg, fmt="JPEG"):
        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        qimg.save(buf, fmt, 92)
        return ba.toBase64().data().decode('utf-8')

    # ================= TEXTO DIRETO =================
    def open_text_editor(self, world_pos, existing_idx=-1):
        if self.text_editor.isVisible():
            self.commit_text_editor()
        self.active_text_world_pos = world_pos
        self.editing_text_index = existing_idx

        if existing_idx != -1 and 0 <= existing_idx < len(self.elements):
            el = self.elements[existing_idx]
            self.text_editor.setPlainText(el['text'])
            self.current_color = el['color']
            self.font_size = el.get('fontSize', 24)
            self.font_family = el.get('fontFamily', 'Segoe UI')
            self.text_bold = el.get('bold', False)
            self.text_italic = el.get('italic', False)
        else:
            self.text_editor.clear()

        self.update_text_editor_style()
        self.text_editor.show()
        self.text_editor.setFocus()
        self.update()

    def update_text_editor_style(self):
        if not self.text_editor.isVisible():
            return
        scr = self.world_to_screen(self.active_text_world_pos.x(), self.active_text_world_pos.y())
        font = QFont(self.font_family, max(8, int(self.font_size * self.cam_zoom)))
        font.setBold(self.text_bold)
        font.setItalic(self.text_italic)
        self.text_editor.setFont(font)

        bg_rgba = "rgba(30, 30, 30, 0.85)" if self.current_color.lower() == "#ffffff" and not self.is_dark_mode else "rgba(255, 255, 255, 0.88)" if not self.is_dark_mode else "rgba(40, 42, 46, 0.90)"
        self.text_editor.setStyleSheet(f"""
            QTextEdit {{
                background-color: {bg_rgba};
                border: 2px dashed #0067c0;
                border-radius: 6px;
                padding: 4px;
                color: {self.current_color};
                selection-background-color: #0067c0;
                selection-color: #ffffff;
            }}
        """)
        self.text_editor.move(int(scr.x()), int(scr.y()))
        self.text_editor.resize(300, 115)

    def commit_text_editor(self):
        if not self.text_editor.isVisible():
            return
        txt = self.text_editor.toPlainText().strip()
        idx = self.editing_text_index
        self.text_editor.hide()
        self.editing_text_index = -1

        if txt:
            self.push_undo()
            self.redo_stack.clear()
            lines = txt.split('\n')
            w = max(len(l) for l in lines) * self.font_size * 0.6 + 20
            h = len(lines) * self.font_size * 1.35
            prev_rot = self.elements[idx].get('rotation', 0.0) if (idx != -1 and idx < len(self.elements)) else 0.0
            obj = {
                'type': 'text',
                'text': txt,
                'x': self.active_text_world_pos.x(),
                'y': self.active_text_world_pos.y(),
                'fontSize': self.font_size,
                'fontFamily': self.font_family,
                'bold': self.text_bold,
                'italic': self.text_italic,
                'color': self.current_color,
                'w': w,
                'h': h,
                'rotation': prev_rot
            }
            if idx != -1 and idx < len(self.elements):
                self.elements[idx] = obj
            else:
                self.elements.append(obj)
        elif idx != -1 and idx < len(self.elements):
            self.push_undo()
            self.elements.pop(idx)
        self.update()

    def insert_symbol(self, sym):
        if not self.text_editor.isVisible():
            center_w = self.screen_to_world(self.width() / 2 - 60, self.height() / 2 - 30)
            self.open_text_editor(center_w, -1)
        self.text_editor.insertPlainText(sym)
        self.text_editor.setFocus()

    # ================= CHECAGEM SE A CANETA ESTÁ SOBRE A BARRA OU PAINÉIS =================
    def is_over_ui_widget(self, px, py):
        pt = QPoint(int(px), int(py))
        ui_panels = [
            getattr(self.main_win, 'dock_frame', None),
            getattr(self.main_win, 'zoom_hud', None),
            getattr(self.main_win, 'lines_pop', None),
            getattr(self.main_win, 'shapes_pop', None),
            getattr(self.main_win, 'symbols_pop', None),
            self.calculator,
            self.ruler_hud,
            self.text_editor
        ]
        for w in ui_panels:
            if w is not None and w.isVisible() and w.geometry().contains(pt):
                return True
        return False

    # ================= BLINDAGEM PARA MESA DIGITALIZADORA XP-PEN =================
    def tabletEvent(self, event: QTabletEvent):
        try:
            pos = event.position()
            px, py = float(pos.x()), float(pos.y())
            if math.isnan(px) or math.isnan(py) or math.isinf(px) or math.isinf(py):
                event.ignore()
                return

            if not self.is_drawing and self.is_over_ui_widget(px, py):
                self.tablet_active = False
                event.ignore()
                return

            raw_p = float(event.pressure())
            pressure = max(0.05, min(1.0, raw_p)) if (self.use_pressure and raw_p > 0.0) else 0.5

            is_eraser_tip = False
            if hasattr(event, 'pointingDevice') and event.pointingDevice():
                dev_ptr = event.pointingDevice().pointerType()
                if hasattr(dev_ptr, 'name') and 'Eraser' in dev_ptr.name:
                    is_eraser_tip = True

            ev_type = event.type()
            if ev_type == QTabletEvent.Type.TabletPress:
                self.tablet_active = True
                self.handle_pointer_down(px, py, Qt.MouseButton.LeftButton, pressure, is_pen=True, is_eraser_tip=is_eraser_tip)
                event.accept()
            elif ev_type == QTabletEvent.Type.TabletMove:
                if self.tablet_active or raw_p > 0.0:
                    self.handle_pointer_move(px, py, pressure, is_pen=True, is_eraser_tip=is_eraser_tip)
                else:
                    self.pointer_screen_pos = QPointF(px, py)
                    if self.current_tool == 'eraser':
                        self.update()
                event.accept()
            elif ev_type == QTabletEvent.Type.TabletRelease:
                self.tablet_active = False
                self.handle_pointer_up()
                event.accept()
            else:
                event.ignore()
        except Exception:
            self.tablet_active = False
            event.ignore()

    def mousePressEvent(self, event):
        if self.tablet_active:
            return
        pos = event.position()
        self.handle_pointer_down(pos.x(), pos.y(), event.button(), 0.5, is_pen=False)

    def mouseMoveEvent(self, event):
        if self.tablet_active:
            return
        pos = event.position()
        self.handle_pointer_move(pos.x(), pos.y(), 0.5, is_pen=False)

    def mouseReleaseEvent(self, event):
        if self.tablet_active:
            self.tablet_active = False
            return
        self.handle_pointer_up()

    def mouseDoubleClickEvent(self, event):
        wpos = self.screen_to_world(event.position().x(), event.position().y())
        idx = self.find_topmost_object(wpos, only_text=True)
        if idx != -1:
            el = self.elements[idx]
            self.clear_selection()
            self.open_text_editor(QPointF(el['x'], el['y']), idx)

    # ================= RÉGUA VIRTUAL E ROTAÇÃO DE SELEÇÃO =================
    def hit_test_ruler(self, sx, sy):
        if not self.ruler_visible:
            return False
        rad = math.radians(self.ruler_angle)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        dx, dy = sx - self.ruler_x, sy - self.ruler_y
        lx = dx * cos_a + dy * sin_a
        ly = -dx * sin_a + dy * cos_a
        return abs(lx) <= self.ruler_length / 2.0 and abs(ly) <= self.ruler_height / 2.0

    def get_snapped_screen_point(self, sx, sy, is_initial=False):
        if not self.ruler_visible or self.current_tool not in ('pen', 'highlighter'):
            return sx, sy
        rad = math.radians(self.ruler_angle)
        cos_a, sin_a = math.cos(rad), math.sin(rad)
        dx, dy = sx - self.ruler_x, sy - self.ruler_y
        lx = dx * cos_a + dy * sin_a
        ly = -dx * sin_a + dy * cos_a
        half_h = self.ruler_height / 2.0
        half_w = self.ruler_length / 2.0 + 20.0

        if is_initial:
            if abs(lx) <= half_w:
                if abs(ly - (-half_h)) < 34.0:
                    self.snapped_ruler_edge = -1
                elif abs(ly - half_h) < 34.0:
                    self.snapped_ruler_edge = 1
                else:
                    self.snapped_ruler_edge = None
        if self.snapped_ruler_edge is not None:
            target_ly = self.snapped_ruler_edge * (half_h + 2.0)
            return (self.ruler_x + lx * cos_a - target_ly * sin_a,
                    self.ruler_y + lx * sin_a + target_ly * cos_a)
        return sx, sy

    def get_rotation_handle_pos(self, b: QRectF):
        return QPointF(b.center().x(), b.top() - 28.0 / self.cam_zoom)

    def hit_test_rotation_handle(self, wpos):
        if not self.selection_bounds:
            return False
        rot_pt = self.get_rotation_handle_pos(self.selection_bounds)
        return math.hypot(wpos.x() - rot_pt.x(), wpos.y() - rot_pt.y()) <= 13.0 / self.cam_zoom

    def rotate_selected_elements(self, delta_deg, snapshot_els, center_pt: QPointF):
        rad = math.radians(delta_deg)
        cx, cy = center_pt.x(), center_pt.y()
        for idx in self.selected_indices:
            if idx >= len(self.elements) or idx >= len(snapshot_els):
                continue
            orig = snapshot_els[idx]
            curr = self.elements[idx]
            if curr['type'] == 'stroke':
                for i, pt in enumerate(orig['points']):
                    rx, ry = rotate_point(pt['x'], pt['y'], cx, cy, rad)
                    curr['points'][i]['x'] = rx
                    curr['points'][i]['y'] = ry
            elif curr['type'] == 'shape':
                tool = curr['tool']
                if tool.startswith('line') or tool.startswith('arrow'):
                    sx, sy = rotate_point(orig['startX'], orig['startY'], cx, cy, rad)
                    ex, ey = rotate_point(orig['endX'], orig['endY'], cx, cy, rad)
                    curr['startX'], curr['startY'] = sx, sy
                    curr['endX'], curr['endY'] = ex, ey
                else:
                    ob = self.get_element_bbox(orig)
                    ocx, ocy = ob.center().x(), ob.center().y()
                    ncx, ncy = rotate_point(ocx, ocy, cx, cy, rad)
                    dx, dy = ncx - ocx, ncy - ocy
                    curr['startX'] = orig['startX'] + dx
                    curr['startY'] = orig['startY'] + dy
                    curr['endX'] = orig['endX'] + dx
                    curr['endY'] = orig['endY'] + dy
                    curr['rotation'] = round((orig.get('rotation', 0.0) + delta_deg) % 360.0, 1)
            elif curr['type'] in ('text', 'image'):
                ob = self.get_element_bbox(orig)
                ocx, ocy = ob.center().x(), ob.center().y()
                ncx, ncy = rotate_point(ocx, ocy, cx, cy, rad)
                curr['x'] = orig['x'] + (ncx - ocx)
                curr['y'] = orig['y'] + (ncy - ocy)
                curr['rotation'] = round((orig.get('rotation', 0.0) + delta_deg) % 360.0, 1)

    def handle_pointer_down(self, sx, sy, button, pressure, is_pen=False, is_eraser_tip=False):
        try:
            self.main_win.hide_all_popovers()
            if self.text_editor.isVisible():
                self.commit_text_editor()
                if self.current_tool == 'text':
                    return

            if self.hit_test_ruler(sx, sy):
                self.dragging_ruler = True
                self.ruler_drag_offset = QPointF(sx - self.ruler_x, sy - self.ruler_y)
                return

            if button == Qt.MouseButton.MiddleButton or self.space_pressed or self.current_tool == 'pan':
                self.is_panning = True
                self.start_pan = QPointF(sx - self.cam_x, sy - self.cam_y)
                self.setCursor(Qt.CursorShape.ClosedHandCursor)
                return

            active_tool = 'eraser' if is_eraser_tip else self.current_tool
            wpos = self.screen_to_world(sx, sy)

            if active_tool == 'text':
                idx = self.find_topmost_object(wpos, only_text=True)
                if idx != -1:
                    el = self.elements[idx]
                    self.open_text_editor(QPointF(el['x'], el['y']), idx)
                else:
                    self.open_text_editor(wpos, -1)
                return

            if self.selection_bounds and self.selected_indices:
                if self.hit_test_rotation_handle(wpos):
                    self.push_undo()
                    self.lasso_mode = 'rotating'
                    self.initial_bounds = QRectF(self.selection_bounds)
                    self.initial_elements_snapshot = json.loads(json.dumps(self.elements))
                    c = self.selection_bounds.center()
                    self.rotate_start_angle = math.degrees(math.atan2(wpos.y() - c.y(), wpos.x() - c.x()))
                    return

                h_name = self.hit_test_handles(wpos)
                if h_name:
                    self.push_undo()
                    self.lasso_mode = 'resizing'
                    self.active_handle = h_name
                    self.drag_start_world = wpos
                    self.initial_bounds = QRectF(self.selection_bounds)
                    self.initial_elements_snapshot = json.loads(json.dumps(self.elements))
                    return

                if self.selection_bounds.contains(wpos):
                    self.push_undo()
                    self.lasso_mode = 'moving'
                    self.drag_start_world = wpos
                    self.initial_bounds = QRectF(self.selection_bounds)
                    self.initial_elements_snapshot = json.loads(json.dumps(self.elements))
                    return
                if active_tool != 'lasso':
                    self.clear_selection()

            if active_tool == 'lasso':
                clicked_idx = self.find_topmost_object(wpos, only_text=False)
                if clicked_idx != -1:
                    self.push_undo()
                    self.selected_indices = [clicked_idx]
                    self.compute_selection_bounds()
                    self.main_win.update_contextual_bar()
                    self.lasso_mode = 'moving'
                    self.drag_start_world = wpos
                    self.initial_bounds = QRectF(self.selection_bounds)
                    self.initial_elements_snapshot = json.loads(json.dumps(self.elements))
                    self.update()
                    return
                self.clear_selection()
                self.lasso_mode = 'drawing'
                self.lasso_points = [wpos]
                self.update()
                return

            self.is_drawing = True
            self.redo_stack.clear()
            snapped_sx, snapped_sy = self.get_snapped_screen_point(sx, sy, is_initial=True)
            pos = self.screen_to_world(snapped_sx, snapped_sy)

            if active_tool == 'eraser' and self.eraser_mode == 'stroke':
                self.snapshot_before_erase = json.loads(json.dumps(self.elements))
                self.erased_in_current_drag = False
                self.erase_whole_strokes_at(pos)
                return

            if active_tool in ('pen', 'highlighter', 'eraser'):
                is_color_eraser = (active_tool == 'eraser' and self.eraser_mode == 'color')
                size = self.base_size * 3.8 if active_tool == 'highlighter' else (self.eraser_radius if active_tool == 'eraser' else self.base_size)
                self.current_element = {
                    'type': 'stroke',
                    'tool': 'color-eraser' if is_color_eraser else active_tool,
                    'color': self.eraser_color if is_color_eraser else self.current_color,
                    'size': size,
                    'points': [{'x': pos.x(), 'y': pos.y(), 'pressure': pressure}],
                    'snappedToLine': False,
                    'snappedToArc': False
                }
            elif active_tool == 'line-tool':
                self.current_element = {
                    'type': 'shape',
                    'tool': self.current_line_variant,
                    'color': self.current_color,
                    'size': self.base_size,
                    'startX': pos.x(), 'startY': pos.y(),
                    'endX': pos.x(), 'endY': pos.y(),
                    'rotation': 0.0
                }
            elif active_tool == 'shape-tool':
                self.current_element = {
                    'type': 'shape',
                    'tool': self.current_shape_variant,
                    'color': self.current_color,
                    'size': self.base_size,
                    'startX': pos.x(), 'startY': pos.y(),
                    'endX': pos.x(), 'endY': pos.y(),
                    'rotation': 0.0
                }
        except Exception:
            pass

    def handle_pointer_move(self, sx, sy, pressure, is_pen=False, is_eraser_tip=False):
        try:
            self.pointer_screen_pos = QPointF(sx, sy)
            wpos = self.screen_to_world(sx, sy)

            if self.dragging_ruler:
                self.ruler_x = sx - self.ruler_drag_offset.x()
                self.ruler_y = sy - self.ruler_drag_offset.y()
                self.update_ruler_hud_pos()
                self.update()
                return

            if self.is_panning:
                self.cam_x = sx - self.start_pan.x()
                self.cam_y = sy - self.start_pan.y()
                self.update_text_editor_style()
                self.update()
                return

            if self.lasso_mode == 'drawing':
                self.lasso_points.append(wpos)
                self.update()
                return

            if self.lasso_mode == 'rotating':
                c = self.initial_bounds.center()
                curr_ang = math.degrees(math.atan2(wpos.y() - c.y(), wpos.x() - c.x()))
                delta_deg = curr_ang - self.rotate_start_angle
                self.selection_angle = round(delta_deg, 1)
                self.rotate_selected_elements(delta_deg, self.initial_elements_snapshot, c)
                self.main_win.rot_spin.blockSignals(True)
                self.main_win.rot_spin.setValue(self.selection_angle)
                self.main_win.rot_spin.blockSignals(False)
                self.update()
                return

            if self.lasso_mode == 'moving':
                dx = wpos.x() - self.drag_start_world.x()
                dy = wpos.y() - self.drag_start_world.y()
                for idx in self.selected_indices:
                    if idx >= len(self.elements) or idx >= len(self.initial_elements_snapshot):
                        continue
                    orig = self.initial_elements_snapshot[idx]
                    curr = self.elements[idx]
                    if curr['type'] == 'stroke':
                        for i in range(len(curr['points'])):
                            curr['points'][i]['x'] = orig['points'][i]['x'] + dx
                            curr['points'][i]['y'] = orig['points'][i]['y'] + dy
                    elif curr['type'] == 'shape':
                        curr['startX'] = orig['startX'] + dx
                        curr['startY'] = orig['startY'] + dy
                        curr['endX'] = orig['endX'] + dx
                        curr['endY'] = orig['endY'] + dy
                    elif curr['type'] in ('image', 'text'):
                        curr['x'] = orig['x'] + dx
                        curr['y'] = orig['y'] + dy
                self.selection_bounds = QRectF(
                    self.initial_bounds.x() + dx, self.initial_bounds.y() + dy,
                    self.initial_bounds.width(), self.initial_bounds.height()
                )
                self.update()
                return

            if self.lasso_mode == 'resizing':
                ib = self.initial_bounds
                nx, ny, nw, nh = ib.x(), ib.y(), ib.width(), ib.height()
                dx = wpos.x() - self.drag_start_world.x()
                dy = wpos.y() - self.drag_start_world.y()
                h = self.active_handle
                min_dim = 12.0 / self.cam_zoom

                if 'e' in h:
                    nw = max(min_dim, ib.width() + dx)
                if 's' in h:
                    nh = max(min_dim, ib.height() + dy)
                if 'w' in h and ib.width() - dx > min_dim:
                    nx = ib.x() + dx
                    nw = ib.width() - dx
                if 'n' in h and ib.height() - dy > min_dim:
                    ny = ib.y() + dy
                    nh = ib.height() - dy

                sx_factor = nw / max(ib.width(), 1.0)
                sy_factor = nh / max(ib.height(), 1.0)
                avg_s = (sx_factor + sy_factor) / 2.0

                for idx in self.selected_indices:
                    if idx >= len(self.elements) or idx >= len(self.initial_elements_snapshot):
                        continue
                    orig = self.initial_elements_snapshot[idx]
                    curr = self.elements[idx]
                    if curr['type'] == 'stroke':
                        curr['size'] = max(1.0, orig['size'] * avg_s)
                        for i in range(len(curr['points'])):
                            curr['points'][i]['x'] = nx + (orig['points'][i]['x'] - ib.x()) * sx_factor
                            curr['points'][i]['y'] = ny + (orig['points'][i]['y'] - ib.y()) * sy_factor
                    elif curr['type'] == 'shape':
                        curr['startX'] = nx + (orig['startX'] - ib.x()) * sx_factor
                        curr['startY'] = ny + (orig['startY'] - ib.y()) * sy_factor
                        curr['endX'] = nx + (orig['endX'] - ib.x()) * sx_factor
                        curr['endY'] = ny + (orig['endY'] - ib.y()) * sy_factor
                    elif curr['type'] == 'image':
                        curr['x'] = nx + (orig['x'] - ib.x()) * sx_factor
                        curr['y'] = ny + (orig['y'] - ib.y()) * sy_factor
                        curr['w'] = max(10.0, orig['w'] * sx_factor)
                        curr['h'] = max(10.0, orig['h'] * sy_factor)
                    elif curr['type'] == 'text':
                        curr['x'] = nx + (orig['x'] - ib.x()) * sx_factor
                        curr['y'] = ny + (orig['y'] - ib.y()) * sy_factor
                        curr['fontSize'] = max(8, int(orig['fontSize'] * avg_s))
                        curr['w'] = orig['w'] * sx_factor
                        curr['h'] = orig['h'] * sy_factor

                self.selection_bounds = QRectF(nx, ny, nw, nh)
                self.update()
                return

            if not self.is_drawing:
                if self.selection_bounds and self.selected_indices:
                    if self.hit_test_rotation_handle(wpos):
                        self.setCursor(Qt.CursorShape.PointingHandCursor)
                        return
                    if self.hit_test_handles(wpos):
                        self.setCursor(Qt.CursorShape.SizeAllCursor)
                        return
                    if self.selection_bounds.contains(wpos):
                        self.setCursor(Qt.CursorShape.SizeAllCursor)
                        return
                if self.current_tool == 'eraser':
                    self.update()
                self.setCursor(Qt.CursorShape.OpenHandCursor if self.current_tool == 'pan' else Qt.CursorShape.CrossCursor)
                return

            active_tool = 'eraser' if is_eraser_tip else self.current_tool
            if active_tool == 'eraser' and self.eraser_mode == 'stroke':
                self.erase_whole_strokes_at(wpos)
                return

            if not self.current_element:
                return

            if self.current_element.get('snappedToLine'):
                snapped_sx, snapped_sy = self.get_snapped_screen_point(sx, sy, is_initial=False)
                pos = self.screen_to_world(snapped_sx, snapped_sy)
                self.current_element['points'][1] = {'x': pos.x(), 'y': pos.y(), 'pressure': 0.6}
                self.update()
                return

            if self.current_element.get('snappedToArc'):
                self.update()
                return

            if self.current_element.get('recognizedFromStroke'):
                self.current_element['endX'] = wpos.x()
                self.current_element['endY'] = wpos.y()
                self.update()
                return

            snapped_sx, snapped_sy = self.get_snapped_screen_point(sx, sy, is_initial=False)
            pos = self.screen_to_world(snapped_sx, snapped_sy)

            last_dist = 999.0
            if self.current_element['type'] == 'stroke' and self.current_element['points']:
                lp = self.current_element['points'][-1]
                last_dist = math.hypot(pos.x() - lp['x'], pos.y() - lp['y'])
                self.current_element['points'].append({'x': pos.x(), 'y': pos.y(), 'pressure': pressure})
            elif self.current_element['type'] == 'shape':
                self.current_element['endX'] = pos.x()
                self.current_element['endY'] = pos.y()

            if self.shape_recognition and self.current_element['type'] == 'stroke' and self.current_element['tool'] in ('pen', 'highlighter') and self.snapped_ruler_edge is None:
                if last_dist > 1.5 / self.cam_zoom or not self.hold_timer.isActive():
                    self.hold_timer.start(420)

            self.update()
        except Exception:
            pass

    def on_hold_timeout(self):
        if not self.shape_recognition:
            return
        if not self.is_drawing or not self.current_element or self.current_element['type'] != 'stroke':
            return
        res = recognize_shape(self.current_element['points'], self.cam_zoom)
        if not res:
            return
        if res['kind'] == 'line':
            self.current_element['snappedToLine'] = True
            self.current_element['points'] = [
                {'x': res['start'].x(), 'y': res['start'].y(), 'pressure': 0.6},
                {'x': res['end'].x(), 'y': res['end'].y(), 'pressure': 0.6}
            ]
        elif res['kind'] == 'recognized-arc':
            self.current_element['snappedToArc'] = True
            self.current_element['points'] = res['arc_points']
        else:
            is_hl = (self.current_element['tool'] == 'highlighter')
            self.current_element = {
                'type': 'shape',
                'tool': res['kind'],
                'color': self.current_element['color'],
                'size': max(4, int(self.current_element['size'] * 0.45)) if is_hl else self.current_element['size'],
                'isHighlighterShape': is_hl,
                'recognizedFromStroke': True,
                'startX': res['min_x'], 'startY': res['min_y'],
                'endX': res['max_x'], 'endY': res['max_y'],
                'rotation': 0.0
            }
        self.update()

    def handle_pointer_up(self):
        try:
            self.hold_timer.stop()
            if self.dragging_ruler:
                self.dragging_ruler = False
                return
            if self.is_panning:
                self.is_panning = False
                self.setCursor(Qt.CursorShape.OpenHandCursor if self.current_tool == 'pan' else Qt.CursorShape.CrossCursor)
                return
            if self.lasso_mode == 'drawing':
                self.finalize_lasso()
                return
            if self.lasso_mode in ('moving', 'resizing', 'rotating'):
                self.lasso_mode = 'none'
                self.active_handle = None
                self.compute_selection_bounds()
                self.update()
                return

            if self.is_drawing:
                if self.erased_in_current_drag and self.snapshot_before_erase is not None:
                    self.undo_history.append(self.snapshot_before_erase)
                    self.snapshot_before_erase = None
                    self.erased_in_current_drag = False
                    self.has_unsaved_changes = True
                elif self.current_element:
                    is_shape = (self.current_element['type'] == 'shape')
                    auto_select = is_shape or self.current_element.get('snappedToArc', False)
                    self.push_undo()
                    self.current_element.pop('recognizedFromStroke', None)
                    self.elements.append(self.current_element)
                    if auto_select:
                        self.selected_indices = [len(self.elements) - 1]
                        self.compute_selection_bounds()
                        self.main_win.update_contextual_bar()
                    self.current_element = None
                self.is_drawing = False
                self.snapped_ruler_edge = None
                self.update()
        except Exception:
            self.is_drawing = False

    # ================= ZOOM E RODA DO MOUSE =================
    def wheelEvent(self, event):
        pos = event.position()
        delta = event.angleDelta().y()
        if self.hit_test_ruler(pos.x(), pos.y()):
            step = 15.0 if (event.modifiers() & Qt.KeyboardModifier.ShiftModifier) else (0.1 if (event.modifiers() & Qt.KeyboardModifier.AltModifier) else 1.0)
            self.rotate_ruler_by(step if delta > 0 else -step)
            return

        step_pct = self.zoom_step_percent / 100.0
        factor = (1.0 + step_pct) if delta > 0 else (1.0 / (1.0 + step_pct))
        self.apply_zoom_at(self.cam_zoom * factor, pos.x(), pos.y())

    def apply_zoom_at(self, new_zoom, cx, cy):
        new_zoom = max(0.05, min(50.0, new_zoom))
        self.cam_x = cx - (cx - self.cam_x) * (new_zoom / self.cam_zoom)
        self.cam_y = cy - (cy - self.cam_y) * (new_zoom / self.cam_zoom)
        self.cam_zoom = new_zoom
        self.main_win.zoom_spin.blockSignals(True)
        self.main_win.zoom_spin.setValue(int(self.cam_zoom * 100))
        self.main_win.zoom_spin.blockSignals(False)
        self.update_text_editor_style()
        self.update()

    # ================= LAÇO E SELEÇÃO =================
    def clear_selection(self):
        self.lasso_mode = 'none'
        self.lasso_points.clear()
        self.selected_indices.clear()
        self.selection_bounds = None
        self.selection_angle = 0.0
        self.active_handle = None
        self.main_win.update_contextual_bar()
        self.update()

    def get_element_bbox(self, el):
        if el['type'] == 'stroke':
            xs = [p['x'] for p in el['points']]
            ys = [p['y'] for p in el['points']]
            pad = el.get('size', 4) / 2.0
            return QRectF(min(xs) - pad, min(ys) - pad, max(max(xs) - min(xs), 1.0) + pad*2, max(max(ys) - min(ys), 1.0) + pad*2)
        elif el['type'] == 'shape':
            x1, y1, x2, y2 = el['startX'], el['startY'], el['endX'], el['endY']
            pad = el.get('size', 4) / 2.0
            return QRectF(min(x1, x2) - pad, min(y1, y2) - pad, max(abs(x2 - x1), 1.0) + pad*2, max(abs(y2 - y1), 1.0) + pad*2)
        elif el['type'] in ('image', 'text'):
            return QRectF(el['x'], el['y'], el.get('w', 100), el.get('h', 40))
        return QRectF(0, 0, 10, 10)

    def compute_selection_bounds(self):
        if not self.selected_indices:
            self.selection_bounds = None
            return
        rects = [self.get_element_bbox(self.elements[i]) for i in self.selected_indices if i < len(self.elements)]
        if not rects:
            self.selection_bounds = None
            return
        min_x = min(r.left() for r in rects)
        min_y = min(r.top() for r in rects)
        max_x = max(r.right() for r in rects)
        max_y = max(r.bottom() for r in rects)
        m = 8.0 / self.cam_zoom
        self.selection_bounds = QRectF(min_x - m, min_y - m, max(max_x - min_x, 10.0) + m*2, max(max_y - min_y, 10.0) + m*2)
        self.selection_angle = 0.0
        if hasattr(self.main_win, 'rot_spin'):
            self.main_win.rot_spin.blockSignals(True)
            self.main_win.rot_spin.setValue(0.0)
            self.main_win.rot_spin.blockSignals(False)

    def get_handles(self, b: QRectF):
        cx, cy = b.center().x(), b.center().y()
        return {
            'nw': QPointF(b.left(), b.top()), 'n': QPointF(cx, b.top()), 'ne': QPointF(b.right(), b.top()),
            'e': QPointF(b.right(), cy), 'se': QPointF(b.right(), b.bottom()), 's': QPointF(cx, b.bottom()),
            'sw': QPointF(b.left(), b.bottom()), 'w': QPointF(b.left(), cy)
        }

    def hit_test_handles(self, wpos):
        if not self.selection_bounds:
            return None
        r = 11.0 / self.cam_zoom
        for name, pt in self.get_handles(self.selection_bounds).items():
            if math.hypot(wpos.x() - pt.x(), wpos.y() - pt.y()) <= r:
                return name
        return None

    def find_topmost_object(self, wpos, only_text=False):
        for i in range(len(self.elements) - 1, -1, -1):
            el = self.elements[i]
            if el['type'] == 'text':
                if self.get_element_bbox(el).contains(wpos):
                    return i
            elif not only_text and el['type'] in ('image', 'shape'):
                if self.get_element_bbox(el).contains(wpos):
                    return i
        return -1

    def finalize_lasso(self):
        if len(self.lasso_points) < 3:
            self.clear_selection()
            return
        poly = QPolygonF(self.lasso_points)
        self.selected_indices = []
        for idx, el in enumerate(self.elements):
            if el.get('tool') == 'eraser' or (el['type'] == 'image' and el.get('isPdfPage')):
                continue
            if el['type'] == 'stroke':
                if any(poly.containsPoint(QPointF(p['x'], p['y']), Qt.FillRule.OddEvenFill) for p in el['points']):
                    self.selected_indices.append(idx)
            else:
                b = self.get_element_bbox(el)
                pts = [b.topLeft(), b.topRight(), b.bottomLeft(), b.bottomRight(), b.center()]
                if any(poly.containsPoint(pt, Qt.FillRule.OddEvenFill) for pt in pts):
                    self.selected_indices.append(idx)
        self.lasso_points.clear()
        self.lasso_mode = 'none'
        self.compute_selection_bounds()
        self.main_win.update_contextual_bar()
        self.update()

    # ================= BORRACHA DE TRAÇO INTEIRO =================
    def erase_whole_strokes_at(self, wpos):
        rad_w = (self.eraser_radius / 2.0) / self.cam_zoom
        remaining = []
        removed = False
        for el in self.elements:
            if el['type'] == 'image' or el.get('tool') == 'eraser':
                remaining.append(el)
                continue
            b = self.get_element_bbox(el).adjusted(-rad_w, -rad_w, rad_w, rad_w)
            if not b.contains(wpos):
                remaining.append(el)
                continue
            if el['type'] == 'stroke':
                pts = [QPointF(p['x'], p['y']) for p in el['points']]
                thresh = rad_w + el.get('size', 4) / 2.0
                hit = (len(pts) == 1 and math.hypot(wpos.x() - pts[0].x(), wpos.y() - pts[0].y()) <= thresh) or \
                      any(dist_to_segment(wpos, pts[i-1], pts[i]) <= thresh for i in range(1, len(pts)))
                if hit:
                    removed = True
                else:
                    remaining.append(el)
            else:
                removed = True
        if removed:
            self.erased_in_current_drag = True
            self.elements = remaining
            self.update()

    # ================= PINTURA E RENDERIZAÇÃO =================
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        bg_col = QColor('#18191a') if self.is_dark_mode else QColor('#f8f9fa')
        grid_col = QColor('#333639') if self.is_dark_mode else QColor('#cbd5e1')
        painter.fillRect(self.rect(), bg_col)
        self.draw_background_grid(painter, grid_col)

        all_els = self.elements + ([self.current_element] if self.current_element else [])

        # Camada de Imagens e Páginas PDF
        painter.save()
        painter.translate(self.cam_x, self.cam_y)
        painter.scale(self.cam_zoom, self.cam_zoom)
        for el in all_els:
            if el['type'] == 'image':
                qimg = self.get_qimage(el['src'])
                if not qimg.isNull():
                    painter.save()
                    rot = el.get('rotation', 0.0)
                    if rot != 0.0:
                        cx = el['x'] + el['w'] / 2.0
                        cy = el['y'] + el['h'] / 2.0
                        painter.translate(cx, cy)
                        painter.rotate(rot)
                        painter.translate(-cx, -cy)
                    painter.drawImage(QRectF(el['x'], el['y'], el['w'], el['h']), qimg)
                    painter.restore()
        painter.restore()

        # Camada de Tinta Independente
        ink_img = QImage(self.size(), QImage.Format.Format_ARGB32_Premultiplied)
        ink_img.fill(Qt.GlobalColor.transparent)
        ink_p = QPainter(ink_img)
        ink_p.setRenderHint(QPainter.RenderHint.Antialiasing)
        ink_p.translate(self.cam_x, self.cam_y)
        ink_p.scale(self.cam_zoom, self.cam_zoom)

        for idx, el in enumerate(all_els):
            if el['type'] == 'image':
                continue
            if self.text_editor.isVisible() and idx == self.editing_text_index:
                continue
            self.draw_vector_element(ink_p, el)
        ink_p.end()

        painter.drawImage(0, 0, ink_img)

        if self.ruler_visible:
            self.draw_virtual_ruler(painter)

        painter.save()
        painter.translate(self.cam_x, self.cam_y)
        painter.scale(self.cam_zoom, self.cam_zoom)

        if self.lasso_mode == 'drawing' and len(self.lasso_points) > 1:
            pen = QPen(QColor('#0067c0'), 1.8 / self.cam_zoom, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QColor(0, 103, 192, 22))
            painter.drawPolygon(QPolygonF(self.lasso_points))

        if self.selection_bounds and self.selected_indices:
            b = self.selection_bounds
            pen = QPen(QColor('#0067c0'), 1.6 / self.cam_zoom, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(QColor(0, 103, 192, 12))
            painter.drawRect(b)

            rot_pt = self.get_rotation_handle_pos(b)
            top_mid = QPointF(b.center().x(), b.top())
            painter.setPen(QPen(QColor('#2f9e44'), 1.8 / self.cam_zoom))
            painter.drawLine(top_mid, rot_pt)
            r_rad = 6.5 / self.cam_zoom
            painter.setBrush(QColor('#2f9e44'))
            painter.drawEllipse(rot_pt, r_rad, r_rad)

            hs = 9.0 / self.cam_zoom
            painter.setPen(QPen(QColor('#0067c0'), 2.0 / self.cam_zoom))
            painter.setBrush(QColor('#ffffff'))
            for pt in self.get_handles(b).values():
                painter.drawRect(QRectF(pt.x() - hs/2, pt.y() - hs/2, hs, hs))
        painter.restore()

        if self.current_tool == 'eraser' and self.pointer_screen_pos.x() > 0:
            r = (self.eraser_radius / 2.0) if self.eraser_mode == 'stroke' else (self.eraser_radius * self.cam_zoom / 2.0)
            painter.setPen(QPen(QColor('#e03131' if self.eraser_mode == 'stroke' else '#0067c0'), 1.5))
            if self.eraser_mode == 'color':
                c = QColor(self.eraser_color)
                c.setAlpha(180)
                painter.setBrush(c)
            else:
                painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(self.pointer_screen_pos, max(r, 4.0), max(r, 4.0))

    def draw_background_grid(self, painter: QPainter, grid_col: QColor):
        if self.bg_pattern == 'blank':
            return
        step = self.grid_spacing * self.cam_zoom
        if step < 6:
            return
        ox = ((self.cam_x % step) + step) % step
        oy = ((self.cam_y % step) + step) % step
        w, h = self.width(), self.height()

        if self.bg_pattern == 'dots':
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(grid_col)
            x = ox
            while x < w:
                y = oy
                while y < h:
                    painter.drawEllipse(QPointF(x, y), 1.5, 1.5)
                    y += step
                x += step
        else:
            painter.setPen(QPen(grid_col, 1.0))
            if self.bg_pattern == 'grid':
                x = ox
                while x < w:
                    painter.drawLine(QPointF(x, 0), QPointF(x, h))
                    x += step
            y = oy
            while y < h:
                painter.drawLine(QPointF(0, y), QPointF(w, y))
                y += step

    def draw_virtual_ruler(self, painter: QPainter):
        painter.save()
        painter.translate(self.ruler_x, self.ruler_y)
        painter.rotate(self.ruler_angle)
        rect = QRectF(-self.ruler_length / 2, -self.ruler_height / 2, self.ruler_length, self.ruler_height)
        painter.setPen(QPen(QColor('#0067c0'), 2.5))
        painter.setBrush(QColor(45, 47, 52, 215) if self.is_dark_mode else QColor(255, 255, 255, 215))
        painter.drawRoundedRect(rect, 6, 6)

        painter.setPen(QPen(QColor('#ffffff' if self.is_dark_mode else '#202124'), 1.2))
        start_x = -int(self.ruler_length / 2) + 10
        end_x = int(self.ruler_length / 2) - 10
        top_y = -self.ruler_height / 2
        for x in range(start_x, end_x, 10):
            tick_h = 18 if x % 50 == 0 else 10
            painter.drawLine(QPointF(x, top_y), QPointF(x, top_y + tick_h))
        painter.restore()

    def draw_vector_element(self, painter: QPainter, el):
        painter.save()
        rot = el.get('rotation', 0.0)
        if rot != 0.0 and el['type'] in ('text', 'shape'):
            b = self.get_element_bbox(el)
            cx, cy = b.center().x(), b.center().y()
            painter.translate(cx, cy)
            painter.rotate(rot)
            painter.translate(-cx, -cy)

        if el['type'] == 'text':
            font = QFont(el.get('fontFamily', 'Segoe UI'), int(el.get('fontSize', 24)))
            font.setBold(el.get('bold', False))
            font.setItalic(el.get('italic', False))
            painter.setFont(font)
            painter.setPen(QColor(el['color']))
            lines = el['text'].split('\n')
            lh = el.get('fontSize', 24) * 1.3
            for i, line in enumerate(lines):
                painter.drawText(QPointF(el['x'], el['y'] + (i + 0.85) * lh), line)

        elif el['type'] == 'stroke':
            if el['tool'] == 'eraser':
                painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            col = QColor(el['color'])
            if el['tool'] == 'highlighter':
                col.setAlphaF(0.32)

            pts = el['points']
            if el['tool'] in ('highlighter', 'eraser', 'color-eraser') or el.get('snappedToLine') or el.get('snappedToArc'):
                pen = QPen(col, el['size'], Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
                painter.setPen(pen)
                if len(pts) == 1:
                    painter.drawPoint(QPointF(pts[0]['x'], pts[0]['y']))
                elif len(pts) == 2:
                    painter.drawLine(QPointF(pts[0]['x'], pts[0]['y']), QPointF(pts[1]['x'], pts[1]['y']))
                else:
                    path = QPainterPath(QPointF(pts[0]['x'], pts[0]['y']))
                    for i in range(1, len(pts) - 1):
                        mid_x = (pts[i]['x'] + pts[i+1]['x']) / 2.0
                        mid_y = (pts[i]['y'] + pts[i+1]['y']) / 2.0
                        path.quadTo(QPointF(pts[i]['x'], pts[i]['y']), QPointF(mid_x, mid_y))
                    path.lineTo(QPointF(pts[-1]['x'], pts[-1]['y']))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawPath(path)
            else:
                for i in range(1, len(pts)):
                    p_factor = pts[i].get('pressure', 0.5) * 1.8
                    w = max(1.0, el['size'] * p_factor)
                    painter.setPen(QPen(col, w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
                    painter.drawLine(QPointF(pts[i-1]['x'], pts[i-1]['y']), QPointF(pts[i]['x'], pts[i]['y']))

        elif el['type'] == 'shape':
            self.draw_shape_2d_3d_physics(painter, el)

        painter.restore()

    def draw_shape_2d_3d_physics(self, painter: QPainter, el):
        x1, y1, x2, y2 = el['startX'], el['startY'], el['endX'], el['endY']
        min_x, min_y = min(x1, x2), min(y1, y2)
        w, h = max(abs(x2 - x1), 2.0), max(abs(y2 - y1), 2.0)
        cx, cy = min_x + w / 2.0, min_y + h / 2.0
        s = el['size']
        col = QColor(el['color'])
        if el.get('isHighlighterShape'):
            col.setAlphaF(0.35)

        pen = QPen(col, s, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        tool = el['tool']

        if 'dashed' in tool:
            pen.setStyle(Qt.PenStyle.DashLine)
        elif 'dotted' in tool:
            pen.setStyle(Qt.PenStyle.DotLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if tool.startswith('line') or tool.startswith('arrow'):
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
            if tool.startswith('arrow'):
                ang = math.atan2(y2 - y1, x2 - x1)
                hlen = max(s * 3.6, 12.0)
                pen.setStyle(Qt.PenStyle.SolidLine)
                painter.setPen(pen)
                painter.drawLine(QPointF(x2, y2), QPointF(x2 - hlen * math.cos(ang - math.pi/6), y2 - hlen * math.sin(ang - math.pi/6)))
                painter.drawLine(QPointF(x2, y2), QPointF(x2 - hlen * math.cos(ang + math.pi/6), y2 - hlen * math.sin(ang + math.pi/6)))
            return

        if tool == 'rect':
            painter.drawRect(QRectF(min_x, min_y, w, h))
        elif tool == 'circle':
            painter.drawEllipse(QRectF(min_x, min_y, w, h))
        elif tool == 'arc':
            painter.drawArc(QRectF(min_x, min_y, w, h * 2), 0, 180 * 16)
        elif tool == 'triangle':
            painter.drawPolygon(QPolygonF([QPointF(cx, min_y), QPointF(min_x + w, min_y + h), QPointF(min_x, min_y + h)]))
        elif tool == 'diamond':
            painter.drawPolygon(QPolygonF([QPointF(cx, min_y), QPointF(min_x + w, cy), QPointF(cx, min_y + h), QPointF(min_x, cy)]))
        elif tool == 'pentagon':
            pts = [QPointF(cx + (w/2)*math.cos(i*2*math.pi/5 - math.pi/2), cy + (h/2)*math.sin(i*2*math.pi/5 - math.pi/2)) for i in range(5)]
            painter.drawPolygon(QPolygonF(pts))
        elif tool == 'star':
            pts = []
            for i in range(10):
                rx = w/2 if i % 2 == 0 else w*0.2
                ry = h/2 if i % 2 == 0 else h*0.2
                ang = i * math.pi / 5 - math.pi / 2
                pts.append(QPointF(cx + rx*math.cos(ang), cy + ry*math.sin(ang)))
            painter.drawPolygon(QPolygonF(pts))
        elif tool == 'sphere':
            painter.drawEllipse(QRectF(min_x, min_y, w, h))
            eq_h = max(h * 0.32, 8.0)
            eq_rect = QRectF(min_x, cy - eq_h/2, w, eq_h)
            painter.drawArc(eq_rect, 180 * 16, 180 * 16)
            painter.setPen(QPen(col, s, Qt.PenStyle.DashLine))
            painter.drawArc(eq_rect, 0, 180 * 16)
        elif tool == 'cube':
            dx, dy = w * 0.28, h * 0.28
            fw, fh = w - dx, h - dy
            fx, fy = min_x, min_y + dy
            bx, by = min_x + dx, min_y
            painter.drawRect(QRectF(fx, fy, fw, fh))
            painter.drawLine(QPointF(fx, fy), QPointF(bx, by))
            painter.drawLine(QPointF(bx, by), QPointF(bx + fw, by))
            painter.drawLine(QPointF(bx + fw, by), QPointF(fx + fw, fy))
            painter.drawLine(QPointF(bx + fw, by), QPointF(bx + fw, by + fh))
            painter.drawLine(QPointF(bx + fw, by + fh), QPointF(fx + fw, fy + fh))
            painter.setPen(QPen(col, s, Qt.PenStyle.DashLine))
            painter.drawLine(QPointF(bx, by), QPointF(bx, by + fh))
            painter.drawLine(QPointF(bx, by + fh), QPointF(fx, fy + fh))
            painter.drawLine(QPointF(bx, by + fh), QPointF(bx + fw, by + fh))
        elif tool == 'cylinder':
            eh = min(h * 0.28, 60.0)
            painter.drawEllipse(QRectF(min_x, min_y, w, eh))
            painter.drawLine(QPointF(min_x, min_y + eh/2), QPointF(min_x, min_y + h - eh/2))
            painter.drawLine(QPointF(min_x + w, min_y + eh/2), QPointF(min_x + w, min_y + h - eh/2))
            bot_rect = QRectF(min_x, min_y + h - eh, w, eh)
            painter.drawArc(bot_rect, 180 * 16, 180 * 16)
            painter.setPen(QPen(col, s, Qt.PenStyle.DashLine))
            painter.drawArc(bot_rect, 0, 180 * 16)
        elif tool == 'pyramid':
            apex = QPointF(cx, min_y)
            pl = QPointF(min_x, min_y + h * 0.82)
            pf = QPointF(min_x + w * 0.56, min_y + h)
            pr = QPointF(min_x + w, min_y + h * 0.72)
            pb = QPointF(min_x + w * 0.44, min_y + h * 0.56)
            painter.drawPolygon(QPolygonF([apex, pl, pf]))
            painter.drawPolygon(QPolygonF([apex, pf, pr]))
            painter.setPen(QPen(col, s, Qt.PenStyle.DashLine))
            painter.drawLine(pl, pb)
            painter.drawLine(pb, pr)
            painter.drawLine(apex, pb)
        elif tool == 'cone':
            eh = min(h * 0.26, 56.0)
            bot_rect = QRectF(min_x, min_y + h - eh, w, eh)
            painter.drawLine(QPointF(cx, min_y), QPointF(min_x, min_y + h - eh/2))
            painter.drawLine(QPointF(cx, min_y), QPointF(min_x + w, min_y + h - eh/2))
            painter.drawArc(bot_rect, 180 * 16, 180 * 16)
            painter.setPen(QPen(col, s, Qt.PenStyle.DashLine))
            painter.drawArc(bot_rect, 0, 180 * 16)
        elif tool == 'phys-car':
            wr = min(w * 0.13, h * 0.24)
            wy = min_y + h - wr
            bbot = wy - wr * 0.2
            hood_y = min_y + h * 0.42
            poly = QPolygonF([
                QPointF(min_x, bbot), QPointF(min_x, hood_y), QPointF(min_x + w*0.2, hood_y),
                QPointF(min_x + w*0.32, min_y), QPointF(min_x + w*0.68, min_y),
                QPointF(min_x + w*0.82, hood_y), QPointF(min_x + w, hood_y), QPointF(min_x + w, bbot)
            ])
            painter.drawPolygon(poly)
            painter.drawEllipse(QPointF(min_x + w*0.25, wy), wr, wr)
            painter.drawEllipse(QPointF(min_x + w*0.75, wy), wr, wr)
        elif tool == 'phys-bike':
            r = min(w * 0.18, h * 0.30)
            wy = min_y + h - r
            wx1, wx2 = min_x + r, min_x + w - r
            crank = QPointF(min_x + w*0.46, wy)
            seat = QPointF(min_x + w*0.35, min_y + h*0.32)
            head = QPointF(min_x + w*0.72, min_y + h*0.28)
            painter.drawEllipse(QPointF(wx1, wy), r, r)
            painter.drawEllipse(QPointF(wx2, wy), r, r)
            painter.drawPolyline(QPolygonF([QPointF(wx1, wy), seat, head, crank, QPointF(wx1, wy)]))
            painter.drawLine(seat, crank)
            painter.drawLine(QPointF(wx2, wy), head)
            painter.drawLine(head, QPointF(head.x() - w*0.05, min_y + h*0.12))
        elif tool == 'phys-person':
            hr = min(w * 0.22, h * 0.14)
            hy = min_y + hr
            painter.drawEllipse(QPointF(cx, hy), hr, hr)
            painter.drawLine(QPointF(cx, hy + hr), QPointF(cx, min_y + h*0.62))
            painter.drawLine(QPointF(min_x + w*0.15, min_y + h*0.38), QPointF(min_x + w*0.85, min_y + h*0.38))
            painter.drawLine(QPointF(cx, min_y + h*0.62), QPointF(min_x + w*0.18, min_y + h))
            painter.drawLine(QPointF(cx, min_y + h*0.62), QPointF(min_x + w*0.82, min_y + h))
        elif tool == 'phys-top':
            rim_y = min_y + h * 0.34
            rim_h = min(h * 0.22, 40.0)
            painter.drawLine(QPointF(cx, min_y), QPointF(cx, rim_y))
            painter.drawEllipse(QRectF(min_x, rim_y - rim_h/2, w, rim_h))
            painter.drawLine(QPointF(min_x, rim_y), QPointF(cx, min_y + h))
            painter.drawLine(QPointF(min_x + w, rim_y), QPointF(cx, min_y + h))
        elif tool == 'phys-incline':
            painter.drawPolygon(QPolygonF([QPointF(min_x, min_y + h), QPointF(min_x + w, min_y + h), QPointF(min_x, min_y)]))
        elif tool == 'phys-spring':
            coils = 6
            pad_x = w * 0.1
            step_x = (w - pad_x * 2) / (coils * 2)
            pts = [QPointF(min_x, cy), QPointF(min_x + pad_x, cy)]
            for i in range(coils * 2):
                px = min_x + pad_x + (i + 0.5) * step_x
                py = min_y if i % 2 == 0 else (min_y + h)
                pts.append(QPointF(px, py))
            pts.extend([QPointF(min_x + w - pad_x, cy), QPointF(min_x + w, cy)])
            painter.drawPolyline(QPolygonF(pts))
        elif tool == 'phys-pulley':
            r = min(w * 0.30, h * 0.26)
            wy = min_y + h * 0.42
            painter.drawLine(QPointF(cx - r, min_y), QPointF(cx + r, min_y))
            painter.drawLine(QPointF(cx, min_y), QPointF(cx, wy))
            painter.drawEllipse(QPointF(cx, wy), r, r)
            painter.drawLine(QPointF(cx - r, wy), QPointF(cx - r, min_y + h))
            painter.drawLine(QPointF(cx + r, wy), QPointF(cx + r, min_y + h))
        elif tool == 'phys-block':
            painter.drawRect(QRectF(min_x, min_y, w, h))
            painter.setFont(QFont('Cambria Math', max(10, int(min(w, h) * 0.35)), QFont.Weight.Bold, True))
            painter.drawText(QRectF(min_x, min_y, w, h), Qt.AlignmentFlag.AlignCenter, "m")


# ================= JANELA PRINCIPAL COM BARRA ENXUTA E ESCALAS SEM CORTE =================
class FreeBoardWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("FreeBoard Pro - Quadro Branco e Física")
        self.resize(1366, 768)

        self.dock_pos_index = 0  # 0: Inferior, 1: Superior, 2: Esquerda, 3: Direita
        self.tooltip_widgets = []

        self.shortcuts_map = {
            'pen': 'P', 'highlighter': 'M', 'eraser': 'E', 'text': 'T',
            'lasso': 'S', 'ruler': 'G', 'line': 'L', 'shape': 'R',
            'pan': 'H', 'calc': 'K', 'image': 'I', 'pdf': 'D', 'undo': 'Z', 'redo': 'Y'
        }
        self.qshortcuts = {}

        self.canvas = WhiteboardCanvas(self)
        self.setCentralWidget(self.canvas)

        self.init_popovers()
        self.init_floating_dock()
        self.init_zoom_hud()
        self.bind_shortcuts()
        self.update_contextual_bar()

    def create_divider(self, vertical_dock=False):
        div = QFrame()
        if vertical_dock:
            div.setFixedSize(36, 1)
        else:
            div.setFixedSize(1, 30)
        div.setStyleSheet("background-color: #cbd5e1;")
        return div

    def register_tooltip(self, widget, text):
        widget.setProperty("custom_tooltip", text)
        widget.setToolTip(text if self.canvas.show_hover_tooltips else "")
        if widget not in self.tooltip_widgets:
            self.tooltip_widgets.append(widget)

    def apply_tooltips_visibility(self, enabled: bool):
        self.canvas.show_hover_tooltips = enabled
        for w in self.tooltip_widgets:
            w.setToolTip(w.property("custom_tooltip") if enabled else "")

    def hide_all_popovers(self):
        self.lines_pop.hide()
        self.shapes_pop.hide()
        self.symbols_pop.hide()

    def position_popover_near(self, pop: QWidget, btn: QWidget):
        pop.adjustSize()
        btn_pos = btn.mapTo(self.canvas, QPoint(0, 0))
        pw, ph = pop.width(), pop.height()
        bw, bh = btn.width(), btn.height()

        if self.dock_pos_index == 0:
            x = btn_pos.x() + bw // 2 - pw // 2
            y = btn_pos.y() - ph - 10
        elif self.dock_pos_index == 1:
            x = btn_pos.x() + bw // 2 - pw // 2
            y = btn_pos.y() + bh + 10
        elif self.dock_pos_index == 2:
            x = btn_pos.x() + bw + 10
            y = btn_pos.y() + bh // 2 - ph // 2
        else:
            x = btn_pos.x() - pw - 10
            y = btn_pos.y() + bh // 2 - ph // 2

        x = max(8, min(self.canvas.width() - pw - 8, x))
        y = max(8, min(self.canvas.height() - ph - 8, y))
        pop.move(x, y)
        pop.show()
        pop.raise_()

    def init_popovers(self):
        self.lines_pop = GridPopover(self.canvas)
        self.lines_pop.add_section("Linhas Retas", [
            ('line-solid', '📏', 'Normal'),
            ('line-dashed', '➖', 'Tracejada'),
            ('line-dotted', '•••', 'Pontilhada')
        ], 3, self.on_line_picked)
        self.lines_pop.add_section("Setas / Vetores", [
            ('arrow-solid', '↗️', 'Seta Normal'),
            ('arrow-dashed', '⇢', 'Tracejada'),
            ('arrow-dotted', '••▸', 'Pontilhada')
        ], 3, self.on_line_picked)

        self.shapes_pop = GridPopover(self.canvas)
        self.shapes_pop.add_section("Figuras 2D e Arco", [
            ('rect', '⬜', 'Retângulo'), ('circle', '⭕', 'Círculo'),
            ('arc', '⌒', 'Arco'), ('triangle', '🔺', 'Triângulo'),
            ('diamond', '🔶', 'Losango'), ('pentagon', '⬠', 'Pentágono'),
            ('star', '⭐', 'Estrela')
        ], 4, self.on_shape_picked)
        self.shapes_pop.add_section("Figuras 3D", [
            ('sphere', '🌐', 'Esfera 3D'), ('cube', '🧊', 'Cubo 3D'),
            ('cylinder', '🛢️', 'Cilindro'), ('pyramid', '⛰️', 'Pirâmide'),
            ('cone', '🎉', 'Cone 3D')
        ], 4, self.on_shape_picked)
        self.shapes_pop.add_section("Kit Aula de Física", [
            ('phys-car', '🚗', 'Carro'), ('phys-bike', '🚲', 'Bicicleta'),
            ('phys-person', '🧍', 'Observador'), ('phys-top', '🪀', 'Peão'),
            ('phys-incline', '📐', 'Plano Incl.'), ('phys-spring', '🌀', 'Mola'),
            ('phys-pulley', '⚙️', 'Polia'), ('phys-block', '⚖️', 'Bloco (m)')
        ], 4, self.on_shape_picked)

        self.symbols_pop = GridPopover(self.canvas)
        syms = [(s, s, '') for s in ['α', 'β', 'γ', 'Δ', 'δ', 'ε', 'θ', 'λ', 'μ', 'π', 'ρ', 'σ', 'Σ', 'τ', 'φ', 'ω', 'Ω', '°', '±', '≈', '≠', '≤', '≥', '√', '∞', '∫', '→', '²', '³']]
        self.symbols_pop.add_section("Alfabeto Grego e Operadores", syms, 6, lambda c, ic, nm: self.canvas.insert_symbol(c))

    def init_zoom_hud(self):
        self.zoom_hud = QFrame(self.canvas)
        self.zoom_hud.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0.96);
                border: 1.5px solid #cbd5e1;
                border-radius: 12px;
            }
            QPushButton {
                background-color: #f1f5f9;
                color: #202124;
                border: none;
                border-radius: 6px;
                padding: 3px 8px;
                font-weight: bold;
                font-size: 12px;
            }
            QPushButton:hover { background-color: #e2e8f0; }
            QSpinBox {
                background-color: #f8fafc;
                color: #202124;
                border: 1px solid #cbd5e1;
                border-radius: 6px;
                padding: 2px 4px;
                font-weight: bold;
                font-size: 11.5px;
            }
        """)
        zl = QHBoxLayout(self.zoom_hud)
        zl.setContentsMargins(6, 4, 6, 4)
        zl.setSpacing(4)

        b_minus = QPushButton("-")
        self.register_tooltip(b_minus, "Diminuir Zoom")
        b_minus.clicked.connect(lambda: self.step_zoom(-1))
        zl.addWidget(b_minus)

        self.zoom_spin = QSpinBox()
        self.zoom_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.zoom_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.zoom_spin.setFixedWidth(56)
        self.zoom_spin.setRange(5, 5000)
        self.zoom_spin.setSuffix("%")
        self.zoom_spin.setValue(100)
        self.register_tooltip(self.zoom_spin, "Escala de Zoom Livre (5% a 5000%)")
        self.zoom_spin.valueChanged.connect(lambda v: self.canvas.apply_zoom_at(v / 100.0, self.canvas.width()/2, self.canvas.height()/2))
        zl.addWidget(self.zoom_spin)

        b_plus = QPushButton("+")
        self.register_tooltip(b_plus, "Aumentar Zoom")
        b_plus.clicked.connect(lambda: self.step_zoom(1))
        zl.addWidget(b_plus)

        b_reset = QPushButton("100%")
        self.register_tooltip(b_reset, "Resetar Zoom para 100%")
        b_reset.clicked.connect(self.reset_camera)
        zl.addWidget(b_reset)

        self.zoom_hud.adjustSize()

    def step_zoom(self, direction):
        factor = 1.0 + (self.canvas.zoom_step_percent / 100.0) * direction
        self.canvas.apply_zoom_at(self.canvas.cam_zoom * factor, self.canvas.width()/2, self.canvas.height()/2)

    def reset_camera(self):
        self.canvas.cam_x = 0.0
        self.canvas.cam_y = 0.0
        self.canvas.cam_zoom = 1.0
        self.zoom_spin.blockSignals(True)
        self.zoom_spin.setValue(100)
        self.zoom_spin.blockSignals(False)
        self.canvas.update()

    def init_floating_dock(self):
        self.dock_frame = QFrame(self.canvas)
        self.dock_frame.setObjectName("FloatingDock")
        self.dock_frame.setStyleSheet("""
            QFrame#FloatingDock {
                background-color: rgba(255, 255, 255, 0.96);
                border: 1.5px solid #cbd5e1;
                border-radius: 18px;
            }
            QFrame#FloatingDock QLabel {
                color: #202124;
                font-weight: 600;
                font-size: 11px;
            }
            QPushButton.modePill {
                background-color: #f1f5f9;
                color: #202124;
                border: 1px solid #cbd5e1;
                border-radius: 8px;
                padding: 4px 8px;
                font-size: 11px;
                font-weight: 600;
            }
            QPushButton.modePill:hover { background-color: #e2e8f0; }
            QPushButton.modePill:checked {
                background-color: #0067c0;
                color: #ffffff;
                border-color: #0067c0;
            }
            QSpinBox, QDoubleSpinBox, QComboBox {
                background-color: #ffffff;
                color: #202124;
                border: 1.5px solid #cbd5e1;
                border-radius: 7px;
                padding: 3px 4px;
                font-weight: bold;
                font-size: 11.5px;
            }
        """)

        shadow = QGraphicsDropShadowEffect(self.dock_frame)
        shadow.setBlurRadius(26)
        shadow.setOffset(0, 6)
        shadow.setColor(QColor(0, 0, 0, 38))
        self.dock_frame.setGraphicsEffect(shadow)

        self.dock_layout = QGridLayout(self.dock_frame)
        self.dock_layout.setContentsMargins(10, 6, 10, 6)
        self.dock_layout.setSpacing(4)

        self.tool_buttons = {}
        main_tools_spec = [
            ('pen', '✏️', 'Caneta', 'P', 'Caneta com Pressão e Reconhecimento de Formas'),
            ('highlighter', '🖍️', 'Marca', 'M', 'Marca-texto Suave'),
            ('eraser', '🧹', 'Borracha', 'E', 'Borracha (Traço Inteiro, Transparente ou Com Cor)'),
            ('text', '🔤', 'Texto', 'T', 'Texto Direto no Quadro'),
            ('lasso', '➰', 'Laço', 'S', 'Laço de Seleção (Mover, Redimensionar e Rotacionar)')
        ]
        for key, ic, lbl, badge, tip in main_tools_spec:
            btn = HtmlToolButton(ic, lbl, badge)
            self.register_tooltip(btn, tip)
            btn.clicked.connect(lambda checked, t=key: self.select_tool(t))
            self.tool_buttons[key] = btn

        self.ruler_btn = HtmlToolButton('📐', 'Régua', 'G')
        self.register_tooltip(self.ruler_btn, "Mostrar/Ocultar Régua Virtual")
        self.ruler_btn.clicked.connect(self.toggle_ruler)

        self.line_btn = HtmlToolButton('📏', 'Linhas▾', 'L')
        self.register_tooltip(self.line_btn, "Abrir Caixinha de Linhas e Setas")
        self.line_btn.clicked.connect(self.toggle_lines_popover)
        self.tool_buttons['line-tool'] = self.line_btn

        self.shape_btn = HtmlToolButton('⬜', 'Formas▾', 'R')
        self.register_tooltip(self.shape_btn, "Abrir Caixinha de Figuras 2D, 3D e Física")
        self.shape_btn.clicked.connect(self.toggle_shapes_popover)
        self.tool_buttons['shape-tool'] = self.shape_btn

        self.pan_btn = HtmlToolButton('✋', 'Mover', 'H')
        self.register_tooltip(self.pan_btn, "Mover Tela (Pan)")
        self.pan_btn.clicked.connect(lambda: self.select_tool('pan'))
        self.tool_buttons['pan'] = self.pan_btn

        # ================= GRUPOS CONTEXTUAIS COMPACTOS (SEM ESCALAS CORTADAS!) =================
        self.stroke_group = QWidget()
        self.sg_layout = QGridLayout(self.stroke_group)
        self.sg_layout.setContentsMargins(4, 0, 4, 0)
        self.sg_layout.setSpacing(5)

        self.color_btns = []
        for hex_col, c_tip in [
            ('#1e1e1e', 'Preto'), ('#ffffff', 'Branco'), ('#e03131', 'Vermelho'),
            ('#1971c2', 'Azul'), ('#2f9e44', 'Verde'), ('#f08c00', 'Laranja')
        ]:
            c_btn = QPushButton()
            c_btn.setFixedSize(20, 20)
            c_btn.setCursor(Qt.CursorShape.PointingHandCursor)
            c_btn.setStyleSheet(f"background-color: {hex_col}; border: 1.5px solid #64748b; border-radius: 10px;")
            self.register_tooltip(c_btn, f"Cor: {c_tip}")
            c_btn.clicked.connect(lambda checked, h=hex_col: self.set_ink_color(h))
            self.color_btns.append(c_btn)

        self.custom_c_btn = QPushButton("🎨")
        self.custom_c_btn.setFixedSize(26, 24)
        self.custom_c_btn.setProperty("class", "modePill")
        self.register_tooltip(self.custom_c_btn, "Escolher Cor Personalizada")
        self.custom_c_btn.clicked.connect(self.pick_custom_color)

        self.size_slider = QSlider(Qt.Orientation.Horizontal)
        self.size_slider.setRange(1, 80)
        self.size_slider.setValue(5)
        self.size_slider.setFixedWidth(72)
        self.register_tooltip(self.size_slider, "Ajustar Espessura")

        # CORRIGIDO: Sem setinhas internas gigantes que cortavam o número!
        self.size_spin = QSpinBox()
        self.size_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.size_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.size_spin.setRange(1, 200)
        self.size_spin.setSuffix("px")
        self.size_spin.setValue(5)
        self.size_spin.setFixedWidth(50)
        self.register_tooltip(self.size_spin, "Espessura do Traço (Digite ou gire o scroll)")

        self.size_slider.valueChanged.connect(lambda v: self.size_spin.setValue(v))
        self.size_spin.valueChanged.connect(self.on_size_changed)

        # Opções de Texto
        self.text_group = QWidget()
        self.tg_layout = QGridLayout(self.text_group)
        self.tg_layout.setContentsMargins(4, 0, 4, 0)
        self.tg_layout.setSpacing(4)

        self.font_combo = QComboBox()
        self.font_combo.addItems(["Segoe UI", "Cambria Math", "Comic Sans MS", "Consolas"])
        self.font_combo.setFixedWidth(102)
        self.register_tooltip(self.font_combo, "Escolher Fonte")
        self.font_combo.currentTextChanged.connect(self.on_font_changed)

        self.bold_btn = QPushButton("B")
        self.bold_btn.setProperty("class", "modePill")
        self.bold_btn.setCheckable(True)
        self.register_tooltip(self.bold_btn, "Negrito")
        self.bold_btn.clicked.connect(self.on_bold_toggled)

        self.italic_btn = QPushButton("I")
        self.italic_btn.setProperty("class", "modePill")
        self.italic_btn.setCheckable(True)
        self.register_tooltip(self.italic_btn, "Itálico")
        self.italic_btn.clicked.connect(self.on_italic_toggled)

        self.sym_btn = QPushButton("Ω Símbolos▾")
        self.sym_btn.setProperty("class", "modePill")
        self.register_tooltip(self.sym_btn, "Abrir Caixinha de Símbolos Gregos e Matemáticos")
        self.sym_btn.clicked.connect(self.toggle_symbols_popover)

        # Opções da Borracha
        self.eraser_group = QWidget()
        self.eg_layout = QGridLayout(self.eraser_group)
        self.eg_layout.setContentsMargins(4, 0, 4, 0)
        self.eg_layout.setSpacing(4)

        self.er_btn_stroke = QPushButton("✂️ Traço")
        self.er_btn_stroke.setProperty("class", "modePill")
        self.er_btn_stroke.setCheckable(True)
        self.er_btn_stroke.setChecked(True)
        self.register_tooltip(self.er_btn_stroke, "Apagar o Traço ou Figura Inteira ao Encostar")
        self.er_btn_stroke.clicked.connect(lambda: self.set_eraser_mode('stroke'))

        self.er_btn_pixel = QPushButton("🧽 Transp.")
        self.er_btn_pixel.setProperty("class", "modePill")
        self.er_btn_pixel.setCheckable(True)
        self.register_tooltip(self.er_btn_pixel, "Borracha Transparente (Não apaga o PDF ao fundo)")
        self.er_btn_pixel.clicked.connect(lambda: self.set_eraser_mode('pixel'))

        self.er_btn_color = QPushButton("🎨 Cor")
        self.er_btn_color.setProperty("class", "modePill")
        self.er_btn_color.setCheckable(True)
        self.register_tooltip(self.er_btn_color, "Borracha que Pinta com a Cor Escolhida ao Lado")
        self.er_btn_color.clicked.connect(lambda: self.set_eraser_mode('color'))

        self.er_color_dots = []
        for e_hex, e_tip in [('#ffffff', 'Branco'), ('#f8f9fa', 'Gelo'), ('#18191a', 'Escuro'), ('#e03131', 'Vermelho')]:
            eb = QPushButton()
            eb.setFixedSize(19, 19)
            eb.setCursor(Qt.CursorShape.PointingHandCursor)
            eb.setStyleSheet(f"background-color: {e_hex}; border: 1.5px solid #64748b; border-radius: 9px;")
            self.register_tooltip(eb, f"Cor da Borracha: {e_tip}")
            eb.clicked.connect(lambda checked, h=e_hex: self.set_eraser_dot_color(h))
            self.er_color_dots.append(eb)

        self.er_custom_btn = QPushButton("🎨")
        self.er_custom_btn.setFixedSize(25, 23)
        self.er_custom_btn.setProperty("class", "modePill")
        self.register_tooltip(self.er_custom_btn, "Outra Cor para a Borracha")
        self.er_custom_btn.clicked.connect(self.pick_eraser_color)

        self.er_slider = QSlider(Qt.Orientation.Horizontal)
        self.er_slider.setRange(4, 120)
        self.er_slider.setValue(24)
        self.er_slider.setFixedWidth(64)
        self.register_tooltip(self.er_slider, "Tamanho/Raio da Borracha")

        self.er_val_lbl = QLabel("24px")
        self.er_val_lbl.setFixedWidth(34)
        self.er_slider.valueChanged.connect(lambda v: (setattr(self.canvas, 'eraser_radius', v), self.er_val_lbl.setText(f"{v}px")))

        # Opções do Laço / Rotação (Sem corte numérico!)
        self.lasso_group = QWidget()
        self.lg_layout = QGridLayout(self.lasso_group)
        self.lg_layout.setContentsMargins(4, 0, 4, 0)
        self.lg_layout.setSpacing(4)

        self.lbl_rot = QLabel("🔄")
        self.rot_spin = QDoubleSpinBox()
        self.rot_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self.rot_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rot_spin.setRange(-360.0, 360.0)
        self.rot_spin.setDecimals(1)
        self.rot_spin.setSingleStep(5.0)
        self.rot_spin.setSuffix("°")
        self.rot_spin.setFixedWidth(54)
        self.register_tooltip(self.rot_spin, "Ângulo de Rotação da Seleção")
        self.rot_spin.valueChanged.connect(self.on_rot_spin_changed)

        self.dup_btn = QPushButton("📑 Duplicar")
        self.dup_btn.setProperty("class", "modePill")
        self.register_tooltip(self.dup_btn, "Duplicar Seleção")
        self.dup_btn.clicked.connect(self.duplicate_selected)

        self.del_btn = QPushButton("🗑️ Excluir")
        self.del_btn.setProperty("class", "modePill")
        self.register_tooltip(self.del_btn, "Excluir Seleção")
        self.del_btn.clicked.connect(self.delete_selected)

        # Botões Finais: Desfazer, Refazer e Config
        self.undo_btn = HtmlToolButton('↩️', 'Desfazer', 'Z')
        self.undo_btn.setCheckable(False)
        self.register_tooltip(self.undo_btn, "Desfazer (Atalho: Z)")
        self.undo_btn.clicked.connect(self.undo)

        self.redo_btn = HtmlToolButton('↪️', 'Refazer', 'Y')
        self.redo_btn.setCheckable(False)
        self.register_tooltip(self.redo_btn, "Refazer (Atalho: Y)")
        self.redo_btn.clicked.connect(self.redo)

        self.cfg_btn = HtmlToolButton('⚙️', 'Config.', '')
        self.cfg_btn.setCheckable(False)
        self.register_tooltip(self.cfg_btn, "Calculadora, Foto, Abrir PDF, Salvar e Configurações")
        self.cfg_btn.clicked.connect(self.open_settings_dialog)

        self.rebuild_dock_layout(vertical=False)
        self.tool_buttons['pen'].setChecked(True)

    def rebuild_dock_layout(self, vertical=False):
        for lay in (self.dock_layout, self.sg_layout, self.tg_layout, self.eg_layout, self.lg_layout):
            while lay.count():
                item = lay.takeAt(0)
                w = item.widget()
                if w and isinstance(w, QFrame) and w not in (self.stroke_group, self.text_group, self.eraser_group, self.lasso_group):
                    w.deleteLater()

        # Calc, Foto e PDF agora moram dentro de Config., deixando a barra principal limpa!
        ordered_main_btns = [
            self.tool_buttons['pen'], self.tool_buttons['highlighter'],
            self.tool_buttons['eraser'], self.tool_buttons['text'],
            self.tool_buttons['lasso'], self.ruler_btn, self.line_btn,
            self.shape_btn, self.pan_btn
        ]
        for b in ordered_main_btns + [self.undo_btn, self.redo_btn, self.cfg_btn]:
            b.set_compact(vertical)

        if vertical:
            for i, b in enumerate(ordered_main_btns):
                self.dock_layout.addWidget(b, i // 2, i % 2)

            for idx, b in enumerate(self.color_btns):
                self.sg_layout.addWidget(b, idx // 3, idx % 3)
            self.sg_layout.addWidget(self.custom_c_btn, 2, 0)
            self.sg_layout.addWidget(self.size_spin, 2, 1, 1, 2)

            self.tg_layout.addWidget(self.font_combo, 0, 0, 1, 2)
            self.tg_layout.addWidget(self.bold_btn, 1, 0)
            self.tg_layout.addWidget(self.italic_btn, 1, 1)
            self.tg_layout.addWidget(self.sym_btn, 2, 0, 1, 2)

            self.eg_layout.addWidget(self.er_btn_stroke, 0, 0, 1, 2)
            self.eg_layout.addWidget(self.er_btn_pixel, 1, 0)
            self.eg_layout.addWidget(self.er_btn_color, 1, 1)
            for idx, eb in enumerate(self.er_color_dots):
                self.eg_layout.addWidget(eb, 2 + idx // 2, idx % 2)
            self.eg_layout.addWidget(self.er_slider, 4, 0, 1, 2)

            self.lg_layout.addWidget(self.rot_spin, 0, 0, 1, 2)
            self.lg_layout.addWidget(self.dup_btn, 1, 0, 1, 2)
            self.lg_layout.addWidget(self.del_btn, 2, 0, 1, 2)

            base_r = (len(ordered_main_btns) + 1) // 2
            self.dock_layout.addWidget(self.create_divider(True), base_r, 0, 1, 2, Qt.AlignmentFlag.AlignCenter)
            self.dock_layout.addWidget(self.stroke_group, base_r + 1, 0, 1, 2)
            self.dock_layout.addWidget(self.text_group, base_r + 2, 0, 1, 2)
            self.dock_layout.addWidget(self.eraser_group, base_r + 3, 0, 1, 2)
            self.dock_layout.addWidget(self.lasso_group, base_r + 4, 0, 1, 2)
            self.dock_layout.addWidget(self.create_divider(True), base_r + 5, 0, 1, 2, Qt.AlignmentFlag.AlignCenter)
            self.dock_layout.addWidget(self.undo_btn, base_r + 6, 0)
            self.dock_layout.addWidget(self.redo_btn, base_r + 6, 1)
            self.dock_layout.addWidget(self.cfg_btn, base_r + 7, 0, 1, 2, Qt.AlignmentFlag.AlignCenter)
        else:
            col = 0
            for idx_b, b in enumerate(ordered_main_btns):
                self.dock_layout.addWidget(b, 0, col)
                col += 1
                if idx_b == 4:
                    self.dock_layout.addWidget(self.create_divider(False), 0, col)
                    col += 1

            self.dock_layout.addWidget(self.create_divider(False), 0, col)
            col += 1

            for idx, b in enumerate(self.color_btns):
                self.sg_layout.addWidget(b, 0, idx)
            self.sg_layout.addWidget(self.custom_c_btn, 0, 6)
            self.sg_layout.addWidget(self.size_slider, 0, 7)
            self.sg_layout.addWidget(self.size_spin, 0, 8)

            self.tg_layout.addWidget(self.font_combo, 0, 0)
            self.tg_layout.addWidget(self.bold_btn, 0, 1)
            self.tg_layout.addWidget(self.italic_btn, 0, 2)
            self.tg_layout.addWidget(self.sym_btn, 0, 3)

            self.eg_layout.addWidget(self.er_btn_stroke, 0, 0)
            self.eg_layout.addWidget(self.er_btn_pixel, 0, 1)
            self.eg_layout.addWidget(self.er_btn_color, 0, 2)
            for idx, eb in enumerate(self.er_color_dots):
                self.eg_layout.addWidget(eb, 0, 3 + idx)
            self.eg_layout.addWidget(self.er_custom_btn, 0, 7)
            self.eg_layout.addWidget(self.er_slider, 0, 8)
            self.eg_layout.addWidget(self.er_val_lbl, 0, 9)

            self.lg_layout.addWidget(self.lbl_rot, 0, 0)
            self.lg_layout.addWidget(self.rot_spin, 0, 1)
            self.lg_layout.addWidget(self.dup_btn, 0, 2)
            self.lg_layout.addWidget(self.del_btn, 0, 3)

            self.dock_layout.addWidget(self.stroke_group, 0, col); col += 1
            self.dock_layout.addWidget(self.text_group, 0, col); col += 1
            self.dock_layout.addWidget(self.eraser_group, 0, col); col += 1
            self.dock_layout.addWidget(self.lasso_group, 0, col); col += 1

            self.dock_layout.addWidget(self.create_divider(False), 0, col); col += 1
            self.dock_layout.addWidget(self.undo_btn, 0, col); col += 1
            self.dock_layout.addWidget(self.redo_btn, 0, col); col += 1
            self.dock_layout.addWidget(self.cfg_btn, 0, col)

        self.position_floating_dock()

    def position_floating_dock(self):
        if not hasattr(self, 'dock_frame'):
            return
        self.dock_frame.adjustSize()
        cw, ch = self.canvas.width(), self.canvas.height()
        dw, dh = self.dock_frame.width(), self.dock_frame.height()
        margin = 14

        if self.dock_pos_index == 0:
            self.dock_frame.move(max(6, (cw - dw) // 2), max(6, ch - dh - margin))
        elif self.dock_pos_index == 1:
            self.dock_frame.move(max(6, (cw - dw) // 2), margin)
        elif self.dock_pos_index == 2:
            self.dock_frame.move(margin, max(6, (ch - dh) // 2))
        elif self.dock_pos_index == 3:
            self.dock_frame.move(max(6, cw - dw - margin), max(6, (ch - dh) // 2))

        if hasattr(self, 'zoom_hud'):
            self.zoom_hud.adjustSize()
            zw, zh = self.zoom_hud.width(), self.zoom_hud.height()
            zy = ch - zh - 14
            if self.dock_pos_index == 0 and (cw - dw) // 2 + dw > cw - zw - 20:
                zy = ch - dh - zh - 22
            self.zoom_hud.move(max(6, cw - zw - 14), max(6, zy))

    # ================= AÇÕES DAS CAIXINHAS POPOVER E FERRAMENTAS =================
    def toggle_lines_popover(self):
        vis = self.lines_pop.isVisible()
        self.hide_all_popovers()
        self.select_tool('line-tool')
        if not vis:
            self.position_popover_near(self.lines_pop, self.line_btn)

    def toggle_shapes_popover(self):
        vis = self.shapes_pop.isVisible()
        self.hide_all_popovers()
        self.select_tool('shape-tool')
        if not vis:
            self.position_popover_near(self.shapes_pop, self.shape_btn)

    def toggle_symbols_popover(self):
        vis = self.symbols_pop.isVisible()
        self.hide_all_popovers()
        if not vis:
            self.position_popover_near(self.symbols_pop, self.sym_btn)

    def on_line_picked(self, code, icon_txt, name_txt):
        self.canvas.current_line_variant = code
        self.line_btn.set_icon_and_label(icon_txt, "Linhas▾")
        self.select_tool('line-tool')

    def on_shape_picked(self, code, icon_txt, name_txt):
        self.canvas.current_shape_variant = code
        self.shape_btn.set_icon_and_label(icon_txt, "Formas▾")
        self.select_tool('shape-tool')

    def toggle_calculator(self):
        vis = not self.canvas.calculator.isVisible()
        self.canvas.calculator.setVisible(vis)
        if vis:
            self.canvas.calculator.raise_()

    def select_tool(self, tool):
        if self.canvas.text_editor.isVisible() and tool != 'text':
            self.canvas.commit_text_editor()
        if tool != 'lasso':
            self.canvas.clear_selection()
        self.canvas.current_tool = tool
        for k, btn in self.tool_buttons.items():
            btn.blockSignals(True)
            btn.setChecked(k == tool)
            btn.update_visual_style()
            btn.blockSignals(False)
        self.update_contextual_bar()
        self.canvas.update()

    def toggle_ruler(self):
        self.canvas.ruler_visible = not self.canvas.ruler_visible
        self.ruler_btn.blockSignals(True)
        self.ruler_btn.setChecked(self.canvas.ruler_visible)
        self.ruler_btn.update_visual_style()
        self.ruler_btn.blockSignals(False)
        self.canvas.update_ruler_hud_pos()
        self.canvas.update()

    def set_eraser_mode(self, mode):
        self.canvas.eraser_mode = mode
        self.er_btn_stroke.setChecked(mode == 'stroke')
        self.er_btn_pixel.setChecked(mode == 'pixel')
        self.er_btn_color.setChecked(mode == 'color')
        self.canvas.update()

    def set_eraser_dot_color(self, hex_col):
        self.canvas.eraser_color = hex_col
        self.set_eraser_mode('color')

    def update_contextual_bar(self):
        t = self.canvas.current_tool
        has_sel = len(self.canvas.selected_indices) > 0
        self.stroke_group.setVisible(t not in ('eraser', 'lasso') or has_sel)
        self.text_group.setVisible(t == 'text')
        self.eraser_group.setVisible(t == 'eraser')
        self.lasso_group.setVisible(t == 'lasso' or has_sel)
        QTimer.singleShot(0, self.position_floating_dock)

    def on_rot_spin_changed(self, new_ang):
        if not self.canvas.selected_indices or not self.canvas.selection_bounds:
            return
        delta = new_ang - self.canvas.selection_angle
        self.canvas.selection_angle = new_ang
        snap = json.loads(json.dumps(self.canvas.elements))
        self.canvas.rotate_selected_elements(delta, snap, self.canvas.selection_bounds.center())
        self.canvas.update()

    def set_ink_color(self, hex_col):
        self.canvas.current_color = hex_col
        if self.canvas.selected_indices:
            self.canvas.push_undo()
            for idx in self.canvas.selected_indices:
                if idx < len(self.canvas.elements) and self.canvas.elements[idx]['type'] != 'image':
                    self.canvas.elements[idx]['color'] = hex_col
        self.canvas.update_text_editor_style()
        self.canvas.update()

    def pick_custom_color(self):
        col = QColorDialog.getColor(QColor(self.canvas.current_color), self, "Escolher Cor")
        if col.isValid():
            self.set_ink_color(col.name())

    def pick_eraser_color(self):
        col = QColorDialog.getColor(QColor(self.canvas.eraser_color), self, "Cor da Borracha")
        if col.isValid():
            self.canvas.eraser_color = col.name()
            self.set_eraser_mode('color')

    def on_size_changed(self, val):
        self.canvas.base_size = val
        self.size_slider.blockSignals(True)
        self.size_slider.setValue(min(80, val))
        self.size_slider.blockSignals(False)
        if self.canvas.selected_indices:
            for idx in self.canvas.selected_indices:
                if idx < len(self.canvas.elements) and self.canvas.elements[idx]['type'] in ('shape', 'stroke'):
                    self.canvas.elements[idx]['size'] = val
            self.canvas.compute_selection_bounds()
            self.canvas.update()

    def on_font_changed(self, fam):
        self.canvas.font_family = fam
        self.canvas.update_text_editor_style()

    def on_bold_toggled(self, checked):
        self.canvas.text_bold = checked
        self.canvas.update_text_editor_style()

    def on_italic_toggled(self, checked):
        self.canvas.text_italic = checked
        self.canvas.update_text_editor_style()

    def delete_selected(self):
        if not self.canvas.selected_indices:
            return
        self.canvas.push_undo()
        rem = set(self.canvas.selected_indices)
        self.canvas.elements = [el for i, el in enumerate(self.canvas.elements) if i not in rem]
        self.canvas.clear_selection()

    def duplicate_selected(self):
        if not self.canvas.selected_indices:
            return
        self.canvas.push_undo()
        offset = 25.0 / self.canvas.cam_zoom
        new_idxs = []
        for idx in self.canvas.selected_indices:
            if idx >= len(self.canvas.elements):
                continue
            cp = json.loads(json.dumps(self.canvas.elements[idx]))
            if cp['type'] == 'stroke':
                for p in cp['points']:
                    p['x'] += offset
                    p['y'] += offset
            elif cp['type'] == 'shape':
                cp['startX'] += offset
                cp['startY'] += offset
                cp['endX'] += offset
                cp['endY'] += offset
            else:
                cp['x'] += offset
                cp['y'] += offset
            self.canvas.elements.append(cp)
            new_idxs.append(len(self.canvas.elements) - 1)
        self.canvas.selected_indices = new_idxs
        self.canvas.compute_selection_bounds()
        self.canvas.update()

    def undo(self):
        if self.canvas.undo_history:
            self.canvas.clear_selection()
            self.canvas.redo_stack.append(json.loads(json.dumps(self.canvas.elements)))
            self.canvas.elements = self.canvas.undo_history.pop()
            self.canvas.update()

    def redo(self):
        if self.canvas.redo_stack:
            self.canvas.clear_selection()
            self.canvas.undo_history.append(json.loads(json.dumps(self.canvas.elements)))
            self.canvas.elements = self.canvas.redo_stack.pop()
            self.canvas.update()

    # ================= IMPORTAR E EXPORTAR =================
    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self.canvas.space_pressed = True
            self.canvas.setCursor(Qt.CursorShape.OpenHandCursor)
        elif event.matches(QKeySequence.StandardKey.Paste):
            clip = QApplication.clipboard()
            img = clip.image()
            if not img.isNull():
                self.insert_qimage(img)
        elif event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and self.canvas.selected_indices:
            self.delete_selected()

    def keyReleaseEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self.canvas.space_pressed = False
            self.canvas.setCursor(Qt.CursorShape.CrossCursor)

    def insert_qimage(self, qimg: QImage):
        b64 = self.canvas.qimage_to_b64(qimg, "PNG")
        self.canvas.image_cache[b64] = qimg
        w = min(420.0, qimg.width()) / self.canvas.cam_zoom
        h = (qimg.height() / max(qimg.width(), 1)) * w
        c = self.canvas.screen_to_world(self.canvas.width() / 2, self.canvas.height() / 2)
        self.canvas.push_undo()
        self.canvas.elements.append({
            'type': 'image', 'src': b64,
            'x': c.x() - w/2, 'y': c.y() - h/2, 'w': w, 'h': h, 'rotation': 0.0
        })
        self.select_tool('lasso')
        self.canvas.selected_indices = [len(self.canvas.elements) - 1]
        self.canvas.compute_selection_bounds()
        self.update_contextual_bar()
        self.canvas.update()

    def import_image_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Inserir Imagem", "", "Imagens (*.png *.jpg *.jpeg *.bmp *.webp)")
        if path:
            img = QImage(path)
            if not img.isNull():
                self.insert_qimage(img)

    def import_pdf_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Abrir PDF para Riscar", "", "Arquivos PDF (*.pdf)")
        if not path:
            return
        doc = fitz.open(path)
        self.canvas.push_undo()
        cur_y = 60.0
        new_pages = []
        for page_index in range(len(doc)):
            page = doc[page_index]
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0))
            qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888).copy()
            b64 = self.canvas.qimage_to_b64(qimg, "JPEG")
            self.canvas.image_cache[b64] = qimg
            disp_w = 794.0
            disp_h = (pix.height / pix.width) * disp_w
            new_pages.append({
                'type': 'image', 'isPdfPage': True, 'src': b64,
                'x': 120.0, 'y': cur_y, 'w': disp_w, 'h': disp_h, 'rotation': 0.0
            })
            cur_y += disp_h + 36.0
        self.canvas.elements = new_pages + self.canvas.elements
        self.canvas.update()

    def export_pdf_dialog(self):
        path, _ = QFileDialog.getSaveFileName(self, "Salvar em PDF", "quadro-anotado.pdf", "PDF (*.pdf)")
        if not path:
            return
        self.dock_frame.hide()
        self.zoom_hud.hide()
        calc_vis = self.canvas.calculator.isVisible()
        self.canvas.calculator.hide()
        img = QImage(self.canvas.size(), QImage.Format.Format_RGB32)
        p = QPainter(img)
        self.canvas.render(p)
        p.end()
        self.dock_frame.show()
        self.zoom_hud.show()
        if calc_vis:
            self.canvas.calculator.show()

        ba = QByteArray()
        buf = QBuffer(ba)
        buf.open(QIODevice.OpenModeFlag.WriteOnly)
        img.save(buf, "JPEG", 95)

        pdf_doc = fitz.open()
        page = pdf_doc.new_page(width=img.width(), height=img.height())
        page.insert_image(fitz.Rect(0, 0, img.width(), img.height()), stream=ba.data())
        pdf_doc.save(path)
        pdf_doc.close()
        self.canvas.has_unsaved_changes = False
        QMessageBox.information(self, "Sucesso", "Arquivo PDF salvo com sucesso!")

    def export_png_dialog(self):
        path, _ = QFileDialog.getSaveFileName(self, "Exportar PNG", "quadro-branco.png", "PNG (*.png)")
        if path:
            self.dock_frame.hide()
            self.zoom_hud.hide()
            calc_vis = self.canvas.calculator.isVisible()
            self.canvas.calculator.hide()
            pix = self.canvas.grab()
            self.dock_frame.show()
            self.zoom_hud.show()
            if calc_vis:
                self.canvas.calculator.show()
            pix.save(path, "PNG")
            self.canvas.has_unsaved_changes = False

    def save_json_dialog(self):
        path, _ = QFileDialog.getSaveFileName(self, "Salvar Projeto", "meu-quadro.json", "JSON (*.json)")
        if path:
            data = {'elements': self.canvas.elements}
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f)
            self.canvas.has_unsaved_changes = False

    def load_json_dialog(self):
        path, _ = QFileDialog.getOpenFileName(self, "Abrir Projeto", "", "JSON (*.json)")
        if path:
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.canvas.elements = data.get('elements', [])
            self.canvas.has_unsaved_changes = False
            self.canvas.update()

    def bind_shortcuts(self):
        for sc in self.qshortcuts.values():
            sc.setEnabled(False)
        self.qshortcuts.clear()

        actions = {
            'pen': lambda: self.select_tool('pen'),
            'highlighter': lambda: self.select_tool('highlighter'),
            'eraser': lambda: self.select_tool('eraser'),
            'text': lambda: self.select_tool('text'),
            'lasso': lambda: self.select_tool('lasso'),
            'ruler': self.toggle_ruler,
            'line': self.toggle_lines_popover,
            'shape': self.toggle_shapes_popover,
            'pan': lambda: self.select_tool('pan'),
            'calc': self.toggle_calculator,
            'image': self.import_image_dialog,
            'pdf': self.import_pdf_dialog,
            'undo': self.undo,
            'redo': self.redo
        }
        for k, func in actions.items():
            key_str = self.shortcuts_map.get(k, '')
            if key_str:
                sc = QShortcut(QKeySequence(key_str), self)
                sc.activated.connect(func)
                self.qshortcuts[k] = sc

            if k in self.tool_buttons and isinstance(self.tool_buttons[k], HtmlToolButton):
                self.tool_buttons[k].set_badge(key_str)
            elif k == 'ruler':
                self.ruler_btn.set_badge(key_str)
            elif k == 'line':
                self.line_btn.set_badge(key_str)
            elif k == 'shape':
                self.shape_btn.set_badge(key_str)
            elif k == 'undo':
                self.undo_btn.set_badge(key_str)
            elif k == 'redo':
                self.redo_btn.set_badge(key_str)

    # ================= JANELA DE CONFIGURAÇÕES COMPLETA (AGORA COM CALC, FOTO E ABRIR PDF) =================
    def open_settings_dialog(self):
        self.hide_all_popovers()
        dlg = QDialog(self)
        dlg.setWindowTitle("⚙️ Configurações, Utilitários e Arquivos")
        dlg.setMinimumWidth(600)
        dlg.setStyleSheet("""
            QDialog { background-color: #18191a; color: #e4e6eb; }
            QLabel, QCheckBox { color: #e4e6eb; font-size: 13px; }
            QTabWidget::pane { border: 1px solid #333639; border-radius: 8px; padding: 10px; background: #18191a; }
            QTabBar::tab {
                background: #242526; color: #e4e6eb; padding: 8px 16px;
                border-radius: 8px; margin-right: 6px; font-weight: bold;
            }
            QTabBar::tab:selected { background: #0067c0; color: #ffffff; }
            QPushButton {
                background-color: #242526; color: #e4e6eb;
                border: 1px solid #3a3b3c; border-radius: 8px;
                padding: 8px 12px; font-weight: 600;
            }
            QPushButton:hover { border-color: #0067c0; background-color: #303134; }
            QComboBox, QSpinBox {
                background-color: #242526; color: #e4e6eb;
                border: 1px solid #3a3b3c; border-radius: 6px; padding: 5px 10px;
            }
        """)
        main_l = QVBoxLayout(dlg)

        # Grade Superior em 2 Linhas: Utilitários (Calc, Foto, Abrir PDF) + Exportação/Arquivos
        file_grid = QGridLayout()
        file_grid.setSpacing(8)

        btn_calc = QPushButton(f"🧮 Calculadora ({self.shortcuts_map.get('calc', 'K')})")
        btn_calc.clicked.connect(lambda: (dlg.accept(), self.toggle_calculator()))

        btn_img = QPushButton(f"🖼️ Inserir Foto ({self.shortcuts_map.get('image', 'I')})")
        btn_img.clicked.connect(lambda: (dlg.accept(), self.import_image_dialog()))

        btn_open_pdf = QPushButton(f"📄 Abrir PDF p/ Riscar ({self.shortcuts_map.get('pdf', 'D')})")
        btn_open_pdf.clicked.connect(lambda: (dlg.accept(), self.import_pdf_dialog()))

        btn_clear = QPushButton("🗑️ Limpar Tudo")
        btn_clear.setStyleSheet("QPushButton:hover { border-color: #e03131; color: #ff6b6b; }")
        btn_clear.clicked.connect(lambda: (self.canvas.elements.clear(), self.canvas.update(), dlg.accept()))

        btn_pdf = QPushButton("📕 Salvar em PDF")
        btn_pdf.clicked.connect(lambda: (dlg.accept(), self.export_pdf_dialog()))

        btn_png = QPushButton("📸 Exportar PNG")
        btn_png.clicked.connect(lambda: (dlg.accept(), self.export_png_dialog()))

        btn_save = QPushButton("💾 Salvar (.json)")
        btn_save.clicked.connect(lambda: (dlg.accept(), self.save_json_dialog()))

        btn_open = QPushButton("📂 Abrir (.json)")
        btn_open.clicked.connect(lambda: (dlg.accept(), self.load_json_dialog()))

        file_grid.addWidget(btn_calc, 0, 0)
        file_grid.addWidget(btn_img, 0, 1)
        file_grid.addWidget(btn_open_pdf, 0, 2)
        file_grid.addWidget(btn_clear, 0, 3)

        file_grid.addWidget(btn_pdf, 1, 0)
        file_grid.addWidget(btn_png, 1, 1)
        file_grid.addWidget(btn_save, 1, 2)
        file_grid.addWidget(btn_open, 1, 3)
        main_l.addLayout(file_grid)

        tabs = QTabWidget()
        main_l.addWidget(tabs)

        tab_ui = QWidget()
        ui_l = QVBoxLayout(tab_ui)
        ui_l.setSpacing(11)

        r1 = QHBoxLayout()
        r1.addWidget(QLabel("<b>Posição da Barra de Ferramentas:</b>"))
        pos_combo = QComboBox()
        pos_combo.addItems(["Inferior (Padrão)", "Superior", "Lateral Esquerda (Compacta)", "Lateral Direita (Compacta)"])
        pos_combo.setCurrentIndex(self.dock_pos_index)
        pos_combo.currentIndexChanged.connect(self.change_toolbar_pos)
        r1.addWidget(pos_combo)
        ui_l.addLayout(r1)

        r2 = QHBoxLayout()
        r2.addWidget(QLabel("<b>Reconhecimento de Formas (Segurar no final):</b>"))
        rec_chk = QCheckBox("Ativado (Reta, Arco, Círculo, Quadrado, Triângulo)")
        rec_chk.setChecked(self.canvas.shape_recognition)
        rec_chk.toggled.connect(lambda v: setattr(self.canvas, 'shape_recognition', v))
        r2.addWidget(rec_chk)
        ui_l.addLayout(r2)

        r_tip = QHBoxLayout()
        r_tip.addWidget(QLabel("<b>Mostrar nome da função ao passar o mouse:</b>"))
        tip_chk = QCheckBox("Exibir balão com o nome da ferramenta")
        tip_chk.setChecked(self.canvas.show_hover_tooltips)
        tip_chk.toggled.connect(self.apply_tooltips_visibility)
        r_tip.addWidget(tip_chk)
        ui_l.addLayout(r_tip)

        r3 = QHBoxLayout()
        r3.addWidget(QLabel("<b>Comportamento da Borracha:</b>"))
        er_combo = QComboBox()
        er_combo.addItems(["Apagar Traço Inteiro", "Transparente (Apagar por Pixel)", "Pintar com a Cor da Borracha"])
        modes = ['stroke', 'pixel', 'color']
        er_combo.setCurrentIndex(modes.index(self.canvas.eraser_mode))
        er_combo.currentIndexChanged.connect(lambda idx: self.set_eraser_mode(modes[idx]))
        r3.addWidget(er_combo)
        ui_l.addLayout(r3)

        r4 = QHBoxLayout()
        r4.addWidget(QLabel("<b>Estilo do Papel / Fundo:</b>"))
        bg_combo = QComboBox()
        bg_map = [('dots', 'Pontilhado'), ('grid', 'Quadriculado'), ('lines', 'Linhas de Caderno'), ('blank', 'Liso (Em branco)')]
        for _, label in bg_map:
            bg_combo.addItem(label)
        curr_bg_idx = [k for k, _ in bg_map].index(self.canvas.bg_pattern)
        bg_combo.setCurrentIndex(curr_bg_idx)
        bg_combo.currentIndexChanged.connect(lambda idx: (setattr(self.canvas, 'bg_pattern', bg_map[idx][0]), self.canvas.update()))
        r4.addWidget(bg_combo)
        ui_l.addLayout(r4)

        r5 = QHBoxLayout()
        r5.addWidget(QLabel("<b>Tema de Cores:</b>"))
        theme_btn = QPushButton("🌙 Alternar Modo Escuro / Claro")
        theme_btn.clicked.connect(lambda: self.toggle_dark_mode_from_cfg(not self.canvas.is_dark_mode))
        r5.addWidget(theme_btn)
        ui_l.addLayout(r5)

        r6 = QHBoxLayout()
        r6.addWidget(QLabel("<b>Escala do Quadriculado / Linhas (px):</b>"))
        grid_slider = QSlider(Qt.Orientation.Horizontal)
        grid_slider.setRange(10, 150)
        grid_slider.setValue(int(self.canvas.grid_spacing))
        grid_spin = QSpinBox()
        grid_spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        grid_spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        grid_spin.setFixedWidth(52)
        grid_spin.setRange(10, 300)
        grid_spin.setValue(int(self.canvas.grid_spacing))
        grid_slider.valueChanged.connect(lambda v: (grid_spin.setValue(v), setattr(self.canvas, 'grid_spacing', v), self.canvas.update()))
        grid_spin.valueChanged.connect(lambda v: (grid_slider.setValue(min(150, v)), setattr(self.canvas, 'grid_spacing', v), self.canvas.update()))
        r6.addWidget(grid_slider)
        r6.addWidget(grid_spin)
        ui_l.addLayout(r6)

        r7 = QHBoxLayout()
        r7.addWidget(QLabel("<b>Sensibilidade do Zoom (Roda do Mouse):</b>"))
        z_slider = QSlider(Qt.Orientation.Horizontal)
        z_slider.setRange(2, 40)
        z_slider.setValue(int(self.canvas.zoom_step_percent))
        z_lbl = QLabel(f"{self.canvas.zoom_step_percent}%")
        z_slider.valueChanged.connect(lambda v: (setattr(self.canvas, 'zoom_step_percent', v), z_lbl.setText(f"{v}%")))
        r7.addWidget(z_slider)
        r7.addWidget(z_lbl)
        ui_l.addLayout(r7)

        r8 = QHBoxLayout()
        r8.addWidget(QLabel("<b>Comprimento da Régua Virtual (px):</b>"))
        r_slider = QSlider(Qt.Orientation.Horizontal)
        r_slider.setRange(300, 1600)
        r_slider.setValue(int(self.canvas.ruler_length))
        r_lbl = QLabel(f"{int(self.canvas.ruler_length)}px")
        r_slider.valueChanged.connect(lambda v: (setattr(self.canvas, 'ruler_length', float(v)), r_lbl.setText(f"{v}px"), self.canvas.update()))
        r8.addWidget(r_slider)
        r8.addWidget(r_lbl)
        ui_l.addLayout(r8)

        tabs.addTab(tab_ui, "🎛️ Interface, Fundo e Escalas")

        tab_keys = QWidget()
        keys_l = QVBoxLayout(tab_keys)
        labels_map = [
            ('pen', 'Caneta'), ('highlighter', 'Marca-texto'), ('eraser', 'Borracha'),
            ('text', 'Texto Direto'), ('lasso', 'Laço de Seleção'), ('ruler', 'Mostrar/Ocultar Régua'),
            ('line', 'Linhas e Setas'), ('shape', 'Formas 2D/3D e Física'),
            ('calc', 'Calculadora Flutuante'), ('image', 'Inserir Foto/Imagem'),
            ('pdf', 'Abrir PDF para Riscar'), ('pan', 'Mover Tela (Pan)')
        ]
        for code, name in labels_map:
            kr = QHBoxLayout()
            kr.addWidget(QLabel(name))
            k_btn = QPushButton(self.shortcuts_map.get(code, ''))
            k_btn.clicked.connect(lambda checked, c=code, b=k_btn: self.capture_shortcut(c, b))
            kr.addWidget(k_btn)
            keys_l.addLayout(kr)

        tabs.addTab(tab_keys, "⌨️ Atalhos da Mesa / Teclado")

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("Fechar")
        close_btn.setStyleSheet("background-color: #0067c0; color: #ffffff; padding: 8px 24px;")
        close_btn.clicked.connect(dlg.accept)
        close_row.addWidget(close_btn)
        main_l.addLayout(close_row)

        dlg.exec()

    def capture_shortcut(self, code, btn):
        btn.setText("Pressione uma tecla...")
        dlg = QDialog(self)
        dlg.setWindowTitle("Definir Atalho")
        dlg.setFixedSize(260, 90)
        l = QVBoxLayout(dlg)
        l.addWidget(QLabel(f"Pressione a nova tecla para '{code}':"), alignment=Qt.AlignmentFlag.AlignCenter)

        def on_key(ev):
            txt = QKeySequence(ev.key()).toString()
            if txt:
                self.shortcuts_map[code] = txt
                btn.setText(txt)
                self.bind_shortcuts()
            dlg.accept()

        dlg.keyPressEvent = on_key
        dlg.exec()

    def toggle_dark_mode_from_cfg(self, checked):
        self.canvas.is_dark_mode = checked
        if checked and self.canvas.current_color == '#1e1e1e':
            self.set_ink_color('#ffffff')
        elif not checked and self.canvas.current_color == '#ffffff':
            self.set_ink_color('#1e1e1e')
        self.canvas.update()

    def change_toolbar_pos(self, idx):
        self.dock_pos_index = idx
        is_vertical = idx in (2, 3)
        self.rebuild_dock_layout(vertical=is_vertical)

    def closeEvent(self, event):
        if self.canvas.has_unsaved_changes or len(self.canvas.elements) > 0:
            reply = QMessageBox.warning(
                self,
                "Não esqueça de salvar!",
                "Você tem anotações no quadro. Não esqueça de salvar!\n\nDeseja realmente sair sem salvar?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = FreeBoardWindow()
    win.show()
    sys.exit(app.exec())