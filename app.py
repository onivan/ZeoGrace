import io
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from PIL import Image

from PyQt6.QtCore import Qt, QDate, QSettings, QRectF
from PyQt6.QtGui import QPixmap, QAction, QPainter, QColor, QPen, QBrush, QFont
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLineEdit, QLabel,
    QFileDialog, QMessageBox, QHeaderView, QSplitter, QDialog,
    QFormLayout, QTextEdit, QDateEdit, QDialogButtonBox, QComboBox,
    QSpinBox, QCheckBox, QListWidget, QListWidgetItem, QGroupBox,
    QGridLayout, QFrame, QRadioButton, QButtonGroup, QProgressDialog
)

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Image as RLImage, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


UKRAINIAN_ALPHABET = "абвгґдеєжзиіїйклмнопрстуфхцчшщьюя"
UKRAINIAN_ORDER = {char: idx for idx, char in enumerate(UKRAINIAN_ALPHABET)}

ALL_COLUMNS = [
    ("id", "ID"),
    ("name", "Ім'я"),
    ("address", "Адреса"),
    ("Date_of_Birth", "Дата нар."),
    ("Date_of_Bapt", "Хрещення"),
    ("Mobile_Phone", "Мобільний"),
    ("Mobile_Phone_a", "Мобільний 2"),
    ("Home_phone", "Домашній"),
    ("Work_phone", "Робочий"),
    ("gender", "Стать"),
    ("fam_status", "Сімейний стан"),
    ("church_status", "Статус у церкві"),
    ("children", "Діти"),
    ("email", "Email"),
    ("send_bd_sms", "SMS"),
    ("notes", "Примітки")
]

DEFAULT_VISIBLE_COLUMNS = ["id", "name", "address", "Date_of_Birth", "Date_of_Bapt", "Mobile_Phone", "email"]

PDF_STYLES = {
    "slate": {
        "name": "Класичний строгий (Slate)",
        "desc": "Стриманий темно-сірий дизайн, універсальний для офіційних документів.",
        "header_bg": colors.HexColor("#334155"),
        "header_text": colors.white,
        "row_bg1": colors.white,
        "row_bg2": colors.HexColor("#F8FAFC"),
        "grid_color": colors.HexColor("#CBD5E1"),
        "title_color": colors.HexColor("#1E293B"),
        "card_bg": colors.HexColor("#F8FAFC"),
        "card_border": colors.HexColor("#CBD5E1"),
        "filter_box_bg": colors.HexColor("#F1F5F9"),
        "filter_box_border": colors.HexColor("#CBD5E1"),
        "filter_text_color": colors.HexColor("#475569")
    },
    "modern_blue": {
        "name": "Сучасний синій (Modern Blue)",
        "desc": "Контрастний синій стиль із насиченою шапкою та приємним відтінком смуг.",
        "header_bg": colors.HexColor("#1E40AF"),
        "header_text": colors.white,
        "row_bg1": colors.white,
        "row_bg2": colors.HexColor("#EFF6FF"),
        "grid_color": colors.HexColor("#BFDBFE"),
        "title_color": colors.HexColor("#1E3A8A"),
        "card_bg": colors.HexColor("#F0F7FF"),
        "card_border": colors.HexColor("#BFDBFE"),
        "filter_box_bg": colors.HexColor("#DBEAFE"),
        "filter_box_border": colors.HexColor("#93C5FD"),
        "filter_text_color": colors.HexColor("#1E3A8A")
    },
    "warm_amber": {
        "name": "Теплий бурштиновий (Warm Amber)",
        "desc": "М'яка тепла колірна гама для дружніх та сімейних звітів громади.",
        "header_bg": colors.HexColor("#78350F"),
        "header_text": colors.white,
        "row_bg1": colors.white,
        "row_bg2": colors.HexColor("#FEF3C7"),
        "grid_color": colors.HexColor("#FDE68A"),
        "title_color": colors.HexColor("#78350F"),
        "card_bg": colors.HexColor("#FFFDF5"),
        "card_border": colors.HexColor("#FDE68A"),
        "filter_box_bg": colors.HexColor("#FFFBEB"),
        "filter_box_border": colors.HexColor("#FCD34D"),
        "filter_text_color": colors.HexColor("#92400E")
    },
    "emerald": {
        "name": "Елегантний смарагдовий (Emerald)",
        "desc": "Гармонійний темно-зелений стиль зі свіжим світлим чергуванням рядків.",
        "header_bg": colors.HexColor("#065F46"),
        "header_text": colors.white,
        "row_bg1": colors.white,
        "row_bg2": colors.HexColor("#ECFDF5"),
        "grid_color": colors.HexColor("#A7F3D0"),
        "title_color": colors.HexColor("#064E3B"),
        "card_bg": colors.HexColor("#F4FDF8"),
        "card_border": colors.HexColor("#A7F3D0"),
        "filter_box_bg": colors.HexColor("#D1FAE5"),
        "filter_box_border": colors.HexColor("#6EE7B7"),
        "filter_text_color": colors.HexColor("#065F46")
    },
    "minimal": {
        "name": "Мінімалістичний чистий (Економний друк)",
        "desc": "Світла шапка, тонкі лінії та мінімум заливки для економії тонера й паперу.",
        "header_bg": colors.HexColor("#E2E8F0"),
        "header_text": colors.HexColor("#0F172A"),
        "row_bg1": colors.white,
        "row_bg2": colors.HexColor("#F8FAFC"),
        "grid_color": colors.HexColor("#94A3B8"),
        "title_color": colors.HexColor("#0F172A"),
        "card_bg": colors.white,
        "card_border": colors.HexColor("#CBD5E1"),
        "filter_box_bg": colors.white,
        "filter_box_border": colors.HexColor("#94A3B8"),
        "filter_text_color": colors.HexColor("#334155")
    }
}

PDF_LAYOUTS = {
    "a4_cards": {
        "name": "А4",
        "desc": "Формат А4. По 2 картки в рядку, кілька рядків на сторінці. Фотографії зберігають оригінальні пропорції."
    },
    "phone": {
        "name": "Для телефону",
        "desc": "Оптимізовано для перегляду на смартфоні. Фото займає біля 1/3 ширини, налаштовувана висота картки, мінімальні розриви."
    },
    "compact": {
        "name": "Компактний",
        "desc": "Таблиця формату А4 без фотографій. Оптимізована ширина колонок, номери телефонів без розриву, об'єднані статуси."
    }
}


def ukrainian_sort_key(s: str):
    """Генерує ключ сортування відповідно до українського алфавіту."""
    if not s:
        return []
    key = []
    for ch in str(s).lower():
        if ch in UKRAINIAN_ORDER:
            key.append((0, UKRAINIAN_ORDER[ch]))
        else:
            key.append((1, ord(ch)))
    return key


def ukrainian_collation(str1: str, str2: str) -> int:
    """Collation-функція для SQLite для українського сортування."""
    k1 = ukrainian_sort_key(str1)
    k2 = ukrainian_sort_key(str2)
    if k1 < k2:
        return -1
    elif k1 > k2:
        return 1
    return 0


def get_db_connection(db_path: str) -> sqlite3.Connection:
    """Створює підключення до SQLite з зареєстрованою функцією сортування."""
    conn = sqlite3.connect(db_path)
    conn.create_collation("UKRAINIAN", ukrainian_collation)
    return conn


def register_unicode_font() -> str:
    """Знаходить та реєструє TTF-шрифт з підтримкою кирилиці для Linux, Windows та macOS."""
    font_candidates = [
        # Windows
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
        # Linux (Ubuntu, Debian, Fedora, Arch)
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/dejavu-sans-fonts/DejaVuSans.ttf",
        # macOS
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]

    for font_path in font_candidates:
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont("ZeoUnicodeFont", font_path))
                return "ZeoUnicodeFont"
            except Exception:
                continue

    return "Helvetica"


def format_phone(phone: str) -> str:
    """Форматування номерів телефонів."""
    if not phone:
        return ""
    digits = "".join(filter(str.isdigit, str(phone)))
    if len(digits) == 10:
        return f"{digits[:3]} {digits[3:6]}-{digits[6:8]}-{digits[8:]}"
    elif len(digits) == 9:
        return f"0{digits[:2]} {digits[2:5]}-{digits[5:7]}-{digits[7:]}"
    elif len(digits) == 6:
        return f"{digits[:2]}-{digits[2:4]}-{digits[4:]}"
    return digits


def get_proportional_image(photo_bytes: bytes, max_width: float, max_height: float):
    """Створює ReportLab Image зі збереженням пропорцій оригіналу."""
    if not photo_bytes:
        return ""
    try:
        img_stream = io.BytesIO(photo_bytes)
        with Image.open(io.BytesIO(photo_bytes)) as pil_img:
            orig_w, orig_h = pil_img.size

        if orig_w <= 0 or orig_h <= 0:
            return ""

        ratio = min(max_width / orig_w, max_height / orig_h)
        target_w = orig_w * ratio
        target_h = orig_h * ratio
        return RLImage(img_stream, width=target_w, height=target_h)
    except Exception:
        return ""


def reportlab_color_to_qcolor(rl_col) -> QColor:
    """Конвертує колір ReportLab у QColor."""
    try:
        return QColor(int(rl_col.red * 255), int(rl_col.green * 255), int(rl_col.blue * 255))
    except Exception:
        return QColor("#334155")


class NumberedCanvas(canvas.Canvas):
    """Канвас із динамічною нумерацією сторінок (X із Y)."""
    def __init__(self, *args, **kwargs):
        self.font_name = kwargs.pop("font_name", "Helvetica")
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        self.setFont(self.font_name, 8)
        self.setFillColor(colors.HexColor("#64748B"))
        margin_right = 20
        margin_bottom = 12
        x = self._pagesize[0] - margin_right
        y = margin_bottom
        self.drawRightString(x, y, f"Сторінка {self._pageNumber} з {page_count}")


class ColumnSelectionDialog(QDialog):
    """Діалогове вікно вибору відображуваних колонок таблиці."""
    def __init__(self, parent=None, current_visible=None):
        super().__init__(parent)
        self.setWindowTitle("Вибір колонок для відображення")
        self.resize(320, 420)
        self.current_visible = current_visible or DEFAULT_VISIBLE_COLUMNS
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        for col_id, col_name in ALL_COLUMNS:
            item = QListWidgetItem(col_name)
            item.setData(Qt.ItemDataRole.UserRole, col_id)
            if col_id in self.current_visible:
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)
            self.list_widget.addItem(item)

        layout.addWidget(self.list_widget)

        btns_row = QHBoxLayout()
        btn_select_all = QPushButton("Вибрати всі")
        btn_select_all.clicked.connect(self.select_all)
        btns_row.addWidget(btn_select_all)

        btn_reset_def = QPushButton("За замовчуванням")
        btn_reset_def.clicked.connect(self.reset_default)
        btns_row.addWidget(btn_reset_def)
        layout.addLayout(btns_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def select_all(self):
        for idx in range(self.list_widget.count()):
            self.list_widget.item(idx).setCheckState(Qt.CheckState.Checked)

    def reset_default(self):
        for idx in range(self.list_widget.count()):
            item = self.list_widget.item(idx)
            col_id = item.data(Qt.ItemDataRole.UserRole)
            if col_id in DEFAULT_VISIBLE_COLUMNS:
                item.setCheckState(Qt.CheckState.Checked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)

    def get_selected_columns(self):
        selected = []
        for idx in range(self.list_widget.count()):
            item = self.list_widget.item(idx)
            if item.checkState() == Qt.CheckState.Checked:
                selected.append(item.data(Qt.ItemDataRole.UserRole))
        if not selected:
            selected = ["id", "name"]
        return selected


class PdfPreviewWidget(QWidget):
    """Віджет для попереднього візуального перегляду макета та колірного стилю PDF."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout_key = "a4_cards"
        self.style_key = "slate"
        self.card_height = 150
        self.setMinimumSize(230, 320)

    def update_params(self, layout_key: str, style_key: str, card_height: int):
        self.layout_key = layout_key
        self.style_key = style_key
        self.card_height = card_height
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        w = self.width()
        h = self.height()

        # Малюємо темніший фоновий контейнер прев'ю
        painter.fillRect(0, 0, w, h, QColor("#F1F5F9"))

        style_cfg = PDF_STYLES.get(self.style_key, PDF_STYLES["slate"])
        c_head = reportlab_color_to_qcolor(style_cfg["header_bg"])
        c_title = reportlab_color_to_qcolor(style_cfg["title_color"])
        c_card_bg = reportlab_color_to_qcolor(style_cfg["card_bg"])
        c_border = reportlab_color_to_qcolor(style_cfg["card_border"])
        c_filter = reportlab_color_to_qcolor(style_cfg["filter_box_bg"])

        # Визначаємо пропорції «аркуша паперу»
        margin = 12
        if self.layout_key == "phone":
            # Пропорція приблизно 9:16
            page_w = w - 2 * margin
            page_h = h - 2 * margin
            if page_h / page_w < 1.6:
                page_w = page_h / 1.65
            page_x = (w - page_w) / 2
            page_y = margin
        else:
            # Пропорція А4 (1 : 1.414)
            page_h = h - 2 * margin
            page_w = page_h / 1.414
            if page_w > (w - 2 * margin):
                page_w = w - 2 * margin
                page_h = page_w * 1.414
            page_x = (w - page_w) / 2
            page_y = (h - page_h) / 2

        page_rect = QRectF(page_x, page_y, page_w, page_h)

        # Тінь та аркуш
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 25))
        painter.drawRoundedRect(page_rect.translated(2, 3), 4, 4)

        painter.setPen(QPen(QColor("#CBD5E1"), 1))
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawRoundedRect(page_rect, 4, 4)

        # Заголовок документа
        painter.setPen(c_title)
        font = QFont("Arial", 7, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(QRectF(page_x, page_y + 6, page_w, 12), Qt.AlignmentFlag.AlignCenter, "Звіт громади")

        # Блок фільтрів
        filter_rect = QRectF(page_x + 8, page_y + 20, page_w - 16, 8)
        painter.setPen(QPen(c_border, 0.5))
        painter.setBrush(c_filter)
        painter.drawRoundedRect(filter_rect, 1.5, 1.5)

        content_top = page_y + 32
        content_w = page_w - 16
        content_left = page_x + 8

        # --- 1. А4 Картки (2 у рядку, кілька рядків) ---
        if self.layout_key == "a4_cards":
            col_gap = 5
            c_w = (content_w - col_gap) / 2
            c_h = min(42.0, (page_h - 45) / 3.3)

            for row in range(3):
                y_c = content_top + row * (c_h + 4)
                if y_c + c_h > page_y + page_h - 10:
                    break
                for col in range(2):
                    x_c = content_left + col * (c_w + col_gap)
                    c_rect = QRectF(x_c, y_c, c_w, c_h)
                    painter.setPen(QPen(c_border, 0.5))
                    painter.setBrush(c_card_bg)
                    painter.drawRoundedRect(c_rect, 2, 2)

                    # Фото
                    ph_w = c_w * 0.36
                    ph_h = c_h - 4
                    painter.fillRect(QRectF(x_c + 2, y_c + 2, ph_w, ph_h), QColor("#CBD5E1"))

                    # Текстові смужки
                    tx = x_c + ph_w + 5
                    tw = c_w - ph_w - 8
                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(c_title)
                    painter.drawRect(QRectF(tx, y_c + 4, tw * 0.75, 2.5))
                    painter.setBrush(QColor("#94A3B8"))
                    painter.drawRect(QRectF(tx, y_c + 9, tw, 2))
                    painter.drawRect(QRectF(tx, y_c + 13, tw * 0.9, 2))
                    painter.drawRect(QRectF(tx, y_c + 17, tw * 0.6, 2))

        # --- 2. Для телефону (3 плитки, регульована висота) ---
        elif self.layout_key == "phone":
            # Розрахунок висоти картки відносного масштабу (150 -> базова)
            factor = self.card_height / 150.0
            card_h = min(46.0 * factor, (page_h - 42) / 3.2)
            c_w = content_w

            for i in range(3):
                y_c = content_top + i * (card_h + 4)
                if y_c + card_h > page_y + page_h - 10:
                    break
                c_rect = QRectF(content_left, y_c, c_w, card_h)
                painter.setPen(QPen(c_border, 0.5))
                painter.setBrush(c_card_bg)
                painter.drawRoundedRect(c_rect, 2.5, 2.5)

                # Фотографія займає 1/3 ширини картки
                ph_w = c_w * 0.32
                ph_h = card_h - 4
                painter.fillRect(QRectF(content_left + 2, y_c + 2, ph_w, ph_h), QColor("#94A3B8"))

                tx = content_left + ph_w + 5
                tw = c_w - ph_w - 8
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(c_title)
                painter.drawRect(QRectF(tx, y_c + 4, tw * 0.7, 3))
                painter.setBrush(QColor("#64748B"))
                painter.drawRect(QRectF(tx, y_c + 10, tw, 2))
                painter.drawRect(QRectF(tx, y_c + 14, tw * 0.85, 2))
                painter.drawRect(QRectF(tx, y_c + 18, tw * 0.5, 2))

        # --- 3. Компактний (таблиця без фото) ---
        else:
            tbl_h = page_h - 48
            tbl_rect = QRectF(content_left, content_top, content_w, tbl_h)

            row_h = 11.0
            # Шапка
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(c_head)
            painter.drawRect(QRectF(content_left, content_top, content_w, row_h))

            # Смугасті рядки
            c_r1 = reportlab_color_to_qcolor(style_cfg["row_bg1"])
            c_r2 = reportlab_color_to_qcolor(style_cfg["row_bg2"])
            num_rows = int((tbl_h - row_h) / row_h)

            for r in range(min(num_rows, 12)):
                ry = content_top + row_h + r * row_h
                painter.setBrush(c_r1 if r % 2 == 0 else c_r2)
                painter.drawRect(QRectF(content_left, ry, content_w, row_h))

            # Сітка
            painter.setPen(QPen(reportlab_color_to_qcolor(style_cfg["grid_color"]), 0.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(tbl_rect)

            # Вертикальні розділювачі
            col_splits = [0.06, 0.32, 0.55, 0.75, 0.87]
            for frac in col_splits:
                sx = content_left + content_w * frac
                painter.drawLine(int(sx), int(content_top), int(sx), int(content_top + tbl_h))

        # Номер сторінки
        painter.setPen(QColor("#94A3B8"))
        painter.setFont(QFont("Arial", 5))
        painter.drawText(QRectF(page_x, page_y + page_h - 10, page_w - 6, 8), Qt.AlignmentFlag.AlignRight, "Стор. 1 з 3")


class PdfExportStyleDialog(QDialog):
    """Діалогове вікно вибору лейауту та стилю для експорту в PDF з інтерактивним прев'ю."""
    def __init__(self, parent=None, current_layout="a4_cards", current_style="slate", current_card_h=150):
        super().__init__(parent)
        self.setWindowTitle("Параметри експорту в PDF")
        self.resize(720, 520)
        self.selected_layout_key = current_layout if current_layout in PDF_LAYOUTS else "a4_cards"
        self.selected_style_key = current_style if current_style in PDF_STYLES else "slate"
        self.phone_card_height = current_card_h
        self.init_ui()

    def init_ui(self):
        root_layout = QHBoxLayout(self)

        # Ліва колонка з параметрами
        left_panel = QVBoxLayout()

        # 1. Вибір макета (Layout)
        gb_layout = QGroupBox("1. Оберіть макет (лейаут) сторінки")
        gb_lay_vbox = QVBoxLayout(gb_layout)

        self.layout_radios = {}
        for key, lay_info in PDF_LAYOUTS.items():
            rb = QRadioButton(lay_info["name"])
            if key == self.selected_layout_key:
                rb.setChecked(True)
            desc_lbl = QLabel(f"<span style='color: #64748B; font-size: 11px;'>{lay_info['desc']}</span>")
            desc_lbl.setWordWrap(True)
            desc_lbl.setContentsMargins(20, 0, 0, 4)
            gb_lay_vbox.addWidget(rb)
            gb_lay_vbox.addWidget(desc_lbl)
            self.layout_radios[key] = rb
            rb.toggled.connect(self._on_options_changed)

        # Налаштування висоти картки для варіанта "Для телефону"
        self.card_h_container = QWidget()
        card_h_layout = QHBoxLayout(self.card_h_container)
        card_h_layout.setContentsMargins(20, 0, 0, 0)
        lbl_card_h = QLabel("Висота картки для телефону:")
        self.spin_card_height = QSpinBox()
        self.spin_card_height.setRange(100, 300)
        self.spin_card_height.setSingleStep(10)
        self.spin_card_height.setValue(self.phone_card_height)
        self.spin_card_height.setSuffix(" pt")
        self.spin_card_height.valueChanged.connect(self._on_options_changed)
        card_h_layout.addWidget(lbl_card_h)
        card_h_layout.addWidget(self.spin_card_height)
        card_h_layout.addStretch()
        gb_lay_vbox.addWidget(self.card_h_container)

        left_panel.addWidget(gb_layout)

        # 2. Вибір кольорового стилю
        gb_style = QGroupBox("2. Оберіть колірну схему")
        gb_style_vbox = QVBoxLayout(gb_style)

        self.style_radios = {}
        for key, style_info in PDF_STYLES.items():
            rb = QRadioButton(style_info["name"])
            if key == self.selected_style_key:
                rb.setChecked(True)
            desc_lbl = QLabel(f"<span style='color: #64748B; font-size: 11px;'>{style_info['desc']}</span>")
            desc_lbl.setWordWrap(True)
            desc_lbl.setContentsMargins(20, 0, 0, 4)
            gb_style_vbox.addWidget(rb)
            gb_style_vbox.addWidget(desc_lbl)
            self.style_radios[key] = rb
            rb.toggled.connect(self._on_options_changed)

        left_panel.addWidget(gb_style)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Експортувати...")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Скасувати")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        left_panel.addWidget(buttons)

        root_layout.addLayout(left_panel, 3)

        # Права колонка — попередній перегляд макета
        gb_preview = QGroupBox("Попередній перегляд макета")
        preview_vbox = QVBoxLayout(gb_preview)
        self.preview_widget = PdfPreviewWidget()
        preview_vbox.addWidget(self.preview_widget)
        root_layout.addWidget(gb_preview, 2)

        self._on_options_changed()

    def _on_options_changed(self):
        curr_layout = self.get_selected_layout()
        curr_style = self.get_selected_style()
        curr_height = self.spin_card_height.value()

        # Активуємо спинбокс висоти тільки якщо обрано варіант "Для телефону"
        self.card_h_container.setEnabled(curr_layout == "phone")

        self.preview_widget.update_params(curr_layout, curr_style, curr_height)

    def get_selected_layout(self):
        for key, rb in self.layout_radios.items():
            if rb.isChecked():
                return key
        return "a4_cards"

    def get_selected_style(self):
        for key, rb in self.style_radios.items():
            if rb.isChecked():
                return key
        return "slate"

    def get_phone_card_height(self):
        return self.spin_card_height.value()


class ModalStatusFilterDialog(QDialog):
    """Діалогове вікно розширеного фільтра за статусами, групами та подіями (аналог TmFstatus)."""
    def __init__(self, parent=None, db_path=None, initial_state=None):
        super().__init__(parent)
        self.db_path = db_path
        self.initial_state = initial_state or {}
        self.setWindowTitle("Фільтр: Статус")
        self.resize(780, 520)
        self.init_ui()

    def _fill_checklist(self, widget, table_name, checked_ids):
        widget.clear()
        if not self.db_path or not os.path.exists(self.db_path):
            return
        try:
            with get_db_connection(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute(f"SELECT id, list_name FROM {table_name} ORDER BY id ASC")
                for row_id, name in cur.fetchall():
                    item = QListWidgetItem(name)
                    item.setData(Qt.ItemDataRole.UserRole, row_id)
                    item.setCheckState(Qt.CheckState.Checked if row_id in checked_ids else Qt.CheckState.Unchecked)
                    widget.addItem(item)
        except Exception:
            pass

    def _get_checked_ids(self, widget):
        checked = []
        for idx in range(widget.count()):
            item = widget.item(idx)
            if item.checkState() == Qt.CheckState.Checked:
                checked.append(item.data(Qt.ItemDataRole.UserRole))
        return checked

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        top_layout = QHBoxLayout()

        gb_church = QGroupBox("Церковний статус")
        gb_church_lay = QVBoxLayout(gb_church)
        self.list_church = QListWidget()
        gb_church_lay.addWidget(self.list_church)
        top_layout.addWidget(gb_church)

        gb_gender = QGroupBox("Стать")
        gb_gender_lay = QVBoxLayout(gb_gender)
        self.list_gender = QListWidget()
        gb_gender_lay.addWidget(self.list_gender)
        top_layout.addWidget(gb_gender)

        gb_fam = QGroupBox("Сімейний статус")
        gb_fam_lay = QVBoxLayout(gb_fam)
        self.list_fam = QListWidget()
        gb_fam_lay.addWidget(self.list_fam)
        top_layout.addWidget(gb_fam)

        main_layout.addLayout(top_layout)

        bottom_layout = QHBoxLayout()

        gb_group = QGroupBox("Група")
        gb_group_lay = QVBoxLayout(gb_group)

        self.list_group_status = QListWidget()
        self.list_group_status.setFixedHeight(90)
        gb_group_lay.addWidget(self.list_group_status)

        self.table_groups = QTableWidget()
        self.table_groups.setColumnCount(3)
        self.table_groups.setHorizontalHeaderLabels(["g.id", "Назва групи", "Тип групи"])
        self.table_groups.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_groups.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table_groups.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_groups.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        gb_group_lay.addWidget(self.table_groups)

        btn_clear_group = QPushButton("Очистити вибір групи")
        btn_clear_group.clicked.connect(self.table_groups.clearSelection)
        gb_group_lay.addWidget(btn_clear_group)

        bottom_layout.addWidget(gb_group, 4)

        gb_event = QGroupBox("Подія")
        gb_event_lay = QHBoxLayout(gb_event)

        self.list_event_type = QListWidget()
        gb_event_lay.addWidget(self.list_event_type, 3)

        dates_box = QVBoxLayout()
        form_dates = QFormLayout()

        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDisplayFormat("yyyy-MM-dd")
        self.date_from.setDate(QDate.currentDate().addYears(-1))

        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDisplayFormat("yyyy-MM-dd")
        self.date_to.setDate(QDate.currentDate())

        self.check_enable_dates = QCheckBox("Враховувати діапазон дат")
        self.check_enable_dates.setChecked(False)

        form_dates.addRow("з:", self.date_from)
        form_dates.addRow("до:", self.date_to)
        dates_box.addWidget(self.check_enable_dates)
        dates_box.addLayout(form_dates)
        dates_box.addStretch()

        gb_event_lay.addLayout(dates_box, 2)
        bottom_layout.addWidget(gb_event, 5)

        main_layout.addLayout(bottom_layout)

        st = self.initial_state
        self._fill_checklist(self.list_church, "list_church_status", st.get("church_status", []))
        self._fill_checklist(self.list_gender, "list_gender", st.get("gender", []))
        self._fill_checklist(self.list_fam, "list_family_status", st.get("family_status", []))
        self._fill_checklist(self.list_group_status, "list_group_status", st.get("group_status", []))
        self._fill_checklist(self.list_event_type, "list_event_type", st.get("event_type", []))

        if st.get("date_from"):
            self.date_from.setDate(QDate.fromString(st["date_from"], "yyyy-MM-dd"))
        if st.get("date_to"):
            self.date_to.setDate(QDate.fromString(st["date_to"], "yyyy-MM-dd"))
        self.check_enable_dates.setChecked(bool(st.get("enable_dates", False)))

        self._load_groups_table(st.get("group_id", None))

        btn_bar = QHBoxLayout()
        btn_clear_all = QPushButton("Скинути всі фільтри")
        btn_clear_all.clicked.connect(self.clear_all_filters)
        btn_bar.addWidget(btn_clear_all)
        btn_bar.addStretch()

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("Відмінити")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        btn_bar.addWidget(buttons)

        main_layout.addLayout(btn_bar)

    def _load_groups_table(self, selected_group_id):
        self.table_groups.setRowCount(0)
        if not self.db_path or not os.path.exists(self.db_path):
            return

        type_map = {}
        try:
            with get_db_connection(self.db_path) as conn:
                cur = conn.cursor()
                try:
                    cur.execute("SELECT id, list_name FROM list_group_type")
                    type_map = dict(cur.fetchall())
                except Exception:
                    pass

                cur.execute("SELECT group_id, group_name, group_type FROM groups ORDER BY group_name ASC")
                rows = cur.fetchall()

            self.table_groups.setRowCount(len(rows))
            sel_row = -1
            for r_idx, (gid, gname, gtype) in enumerate(rows):
                self.table_groups.setItem(r_idx, 0, QTableWidgetItem(str(gid)))
                self.table_groups.setItem(r_idx, 1, QTableWidgetItem(str(gname or "")))
                self.table_groups.setItem(r_idx, 2, QTableWidgetItem(str(type_map.get(gtype, gtype or ""))))

                for col in range(3):
                    self.table_groups.item(r_idx, col).setFlags(self.table_groups.item(r_idx, col).flags() & ~Qt.ItemFlag.ItemIsEditable)

                if selected_group_id is not None and gid == selected_group_id:
                    sel_row = r_idx

            if sel_row >= 0:
                self.table_groups.selectRow(sel_row)
        except Exception:
            pass

    def clear_all_filters(self):
        for w in [self.list_church, self.list_gender, self.list_fam, self.list_group_status, self.list_event_type]:
            for idx in range(w.count()):
                w.item(idx).setCheckState(Qt.CheckState.Unchecked)
        self.table_groups.clearSelection()
        self.check_enable_dates.setChecked(False)

    def get_filter_state(self):
        selected_gid = None
        selected_gname = ""
        sel_items = self.table_groups.selectedItems()
        if sel_items:
            row = sel_items[0].row()
            selected_gid = int(self.table_groups.item(row, 0).text())
            selected_gname = self.table_groups.item(row, 1).text()

        return {
            "church_status": self._get_checked_ids(self.list_church),
            "gender": self._get_checked_ids(self.list_gender),
            "family_status": self._get_checked_ids(self.list_fam),
            "group_status": self._get_checked_ids(self.list_group_status),
            "group_id": selected_gid,
            "group_name": selected_gname,
            "event_type": self._get_checked_ids(self.list_event_type),
            "enable_dates": self.check_enable_dates.isChecked(),
            "date_from": self.date_from.date().toString("yyyy-MM-dd"),
            "date_to": self.date_to.date().toString("yyyy-MM-dd")
        }


class PersonDialog(QDialog):
    """Діалогове вікно для додавання або редагування запису парафіянина."""
    def __init__(self, parent=None, person_data=None, db_path=None):
        super().__init__(parent)
        self.person_data = person_data
        self.db_path = db_path
        self.setWindowTitle("Редагувати запис" if person_data else "Додати запис")
        self.resize(550, 600)
        self.init_ui()

    def _load_combobox_data(self, table_name):
        items = []
        if self.db_path and os.path.exists(self.db_path):
            try:
                with get_db_connection(self.db_path) as conn:
                    cur = conn.cursor()
                    cur.execute(f"SELECT id, list_name FROM {table_name} ORDER BY id ASC")
                    items = cur.fetchall()
            except Exception:
                pass
        return items

    def init_ui(self):
        layout = QVBoxLayout(self)
        form_layout = QFormLayout()

        self.edit_name = QLineEdit()
        self.edit_address = QLineEdit()

        self.edit_dob = QDateEdit()
        self.edit_dob.setCalendarPopup(True)
        self.edit_dob.setDisplayFormat("yyyy-MM-dd")

        self.edit_dob_empty = QPushButton("Очистити дату")
        self.edit_dob_empty.setFixedWidth(120)
        self.has_dob = False

        dob_box = QHBoxLayout()
        dob_box.addWidget(self.edit_dob)
        dob_box.addWidget(self.edit_dob_empty)

        def clear_dob():
            self.has_dob = False
            self.edit_dob.setDate(QDate(2000, 1, 1))
            self.edit_dob.setStyleSheet("color: gray;")

        def set_dob():
            self.has_dob = True
            self.edit_dob.setStyleSheet("")

        self.edit_dob.dateChanged.connect(set_dob)
        self.edit_dob_empty.clicked.connect(clear_dob)

        self.edit_bapt = QLineEdit()
        self.edit_bapt.setPlaceholderText("РРРР-ММ-ДД")

        self.combo_gender = QComboBox()
        self.combo_gender.addItem("— Не вказано —", 0)
        genders = self._load_combobox_data("list_gender")
        for gid, gname in genders:
            self.combo_gender.addItem(gname, gid)

        self.combo_fam_status = QComboBox()
        self.combo_fam_status.addItem("— Не вказано —", 0)
        fam_statuses = self._load_combobox_data("list_family_status")
        for fid, fname in fam_statuses:
            self.combo_fam_status.addItem(fname, fid)

        self.combo_church_status = QComboBox()
        self.combo_church_status.addItem("— Не вказано —", 0)
        church_statuses = self._load_combobox_data("list_church_status")
        for cid, cname in church_statuses:
            self.combo_church_status.addItem(cname, cid)

        self.spin_children = QSpinBox()
        self.spin_children.setRange(0, 50)

        self.edit_mobile = QLineEdit()
        self.edit_mobile_a = QLineEdit()
        self.edit_home_phone = QLineEdit()
        self.edit_work_phone = QLineEdit()
        self.edit_email = QLineEdit()

        self.check_send_bd_sms = QCheckBox("Надсилати привітання до ДН через SMS")
        self.check_send_bd_sms.setChecked(True)

        self.edit_notes = QTextEdit()
        self.edit_notes.setMaximumHeight(80)

        form_layout.addRow("П.І.Б. (*):", self.edit_name)
        form_layout.addRow("Адреса:", self.edit_address)
        form_layout.addRow("Дата народження:", dob_box)
        form_layout.addRow("Дата хрещення:", self.edit_bapt)
        form_layout.addRow("Стать:", self.combo_gender)
        form_layout.addRow("Сімейний стан:", self.combo_fam_status)
        form_layout.addRow("Статус у церкві:", self.combo_church_status)
        form_layout.addRow("Кількість дітей:", self.spin_children)
        form_layout.addRow("Мобільний телефон:", self.edit_mobile)
        form_layout.addRow("Мобільний (додатковий):", self.edit_mobile_a)
        form_layout.addRow("Домашній телефон:", self.edit_home_phone)
        form_layout.addRow("Робочий телефон:", self.edit_work_phone)
        form_layout.addRow("Email:", self.edit_email)
        form_layout.addRow("SMS сповіщення:", self.check_send_bd_sms)
        form_layout.addRow("Примітки:", self.edit_notes)

        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept_data)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        if self.person_data:
            self.edit_name.setText(self.person_data.get("name", "") or "")
            self.edit_address.setText(self.person_data.get("address", "") or "")
            dob_val = str(self.person_data.get("Date_of_Birth", "") or "")
            if dob_val and dob_val != "1898":
                try:
                    qdate = QDate.fromString(dob_val[:10], "yyyy-MM-dd")
                    if qdate.isValid():
                        self.edit_dob.setDate(qdate)
                        self.has_dob = True
                    else:
                        clear_dob()
                except Exception:
                    clear_dob()
            else:
                clear_dob()

            self.edit_bapt.setText(str(self.person_data.get("Date_of_Bapt", "") or ""))

            gender_idx = self.combo_gender.findData(self.person_data.get("gender", 0))
            if gender_idx >= 0:
                self.combo_gender.setCurrentIndex(gender_idx)

            fam_idx = self.combo_fam_status.findData(self.person_data.get("fam_status", 0))
            if fam_idx >= 0:
                self.combo_fam_status.setCurrentIndex(fam_idx)

            church_idx = self.combo_church_status.findData(self.person_data.get("church_status", 0))
            if church_idx >= 0:
                self.combo_church_status.setCurrentIndex(church_idx)

            self.spin_children.setValue(int(self.person_data.get("children") or 0))

            self.edit_mobile.setText(str(self.person_data.get("Mobile_Phone", "") or ""))
            self.edit_mobile_a.setText(str(self.person_data.get("Mobile_Phone_a", "") or ""))
            self.edit_home_phone.setText(str(self.person_data.get("Home_phone", "") or ""))
            self.edit_work_phone.setText(str(self.person_data.get("Work_phone", "") or ""))
            self.edit_email.setText(self.person_data.get("email", "") or "")
            self.check_send_bd_sms.setChecked(bool(self.person_data.get("send_bd_sms", 1)))
            self.edit_notes.setPlainText(self.person_data.get("notes", "") or "")
        else:
            clear_dob()

    def accept_data(self):
        if not self.edit_name.text().strip():
            QMessageBox.warning(self, "Помилка валідації", "Поле 'П.І.Б.' є обов'язковим для заповнення!")
            return
        self.accept()

    def get_data(self):
        dob_str = self.edit_dob.date().toString("yyyy-MM-dd") if self.has_dob else ""
        return {
            "name": self.edit_name.text().strip(),
            "address": self.edit_address.text().strip(),
            "Home_phone": self.edit_home_phone.text().strip(),
            "Work_phone": self.edit_work_phone.text().strip(),
            "Mobile_Phone": self.edit_mobile.text().strip(),
            "Date_of_Birth": dob_str,
            "gender": self.combo_gender.currentData() or 0,
            "fam_status": self.combo_fam_status.currentData() or 0,
            "children": self.spin_children.value(),
            "notes": self.edit_notes.toPlainText().strip(),
            "church_status": self.combo_church_status.currentData() or 0,
            "Date_of_Bapt": self.edit_bapt.text().strip(),
            "Mobile_Phone_a": self.edit_mobile_a.text().strip(),
            "email": self.edit_email.text().strip(),
            "send_bd_sms": 1 if self.check_send_bd_sms.isChecked() else 0
        }


class ZeoGraceApp(QMainWindow):
    def __init__(self, db_path=None):
        super().__init__()
        self.settings = QSettings("ZeoGrace", "ZeoGraceApp")

        if db_path is None:
            saved_db = self.settings.value("last_db_path", type=str)
            if saved_db and os.path.exists(saved_db):
                self.db_path = saved_db
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
                self.db_path = os.path.join(base_dir, "zeograce.db")
        else:
            self.db_path = db_path

        saved_person_id = self.settings.value("last_selected_person_id", None)
        try:
            self.selected_person_id = int(saved_person_id) if saved_person_id is not None else None
        except (ValueError, TypeError):
            self.selected_person_id = None

        saved_cols = self.settings.value("visible_columns", None)
        if isinstance(saved_cols, list) and saved_cols:
            self.visible_columns = saved_cols
        else:
            self.visible_columns = list(DEFAULT_VISIBLE_COLUMNS)

        saved_filter_json = self.settings.value("status_filter_state", None, type=str)
        if saved_filter_json:
            try:
                self.status_filter_state = json.loads(saved_filter_json)
            except Exception:
                self.status_filter_state = {}
        else:
            self.status_filter_state = {}

        self.last_pdf_layout = self.settings.value("last_pdf_export_layout", "a4_cards", type=str)
        self.last_pdf_style = self.settings.value("last_pdf_export_style", "slate", type=str)
        self.last_phone_card_height = self.settings.value("last_pdf_phone_card_height", 150, type=int)

        self.bd_this_week_active = False
        self.current_photo_id = None
        self.pdf_font = register_unicode_font()

        self.init_db()
        self.backup_database()
        self.init_ui()
        self.restore_ui_state()
        self.load_people()

    # --- База даних і бекап ---

    def init_db(self):
        """Ініціалізація повної структури БД за schema2026-04-23v3.sql."""
        with get_db_connection(self.db_path) as conn:
            cur = conn.cursor()
            cur.executescript("""
                PRAGMA foreign_keys = ON;

                CREATE TABLE IF NOT EXISTS app_users (
                    id            INTEGER       PRIMARY KEY AUTOINCREMENT,
                    username      VARCHAR (50)  UNIQUE NOT NULL,
                    password_hash VARCHAR (255) NOT NULL,
                    role          VARCHAR (20)  DEFAULT 'editor',
                    created_at    DATETIME      DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS disabled (
                    id  INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                    num TEXT
                );

                CREATE TABLE IF NOT EXISTS fsettings_columns_titles (
                    id               INTEGER   PRIMARY KEY AUTOINCREMENT UNIQUE NOT NULL,
                    table_name       CHAR (50) NOT NULL,
                    column_name      TEXT      NOT NULL,
                    column_title     TEXT,
                    column_ods_width INTEGER   DEFAULT (20),
                    column_export    BOOLEAN   DEFAULT false,
                    list_items_blob  BLOB
                );

                CREATE TABLE IF NOT EXISTS fsettings_lists (
                    id              INTEGER   PRIMARY KEY AUTOINCREMENT UNIQUE NOT NULL,
                    list_name       CHAR (20) NOT NULL,
                    list_items      TEXT,
                    list_items_blob BLOB
                );

                CREATE TABLE IF NOT EXISTS groups (
                    group_id      INTEGER    PRIMARY KEY AUTOINCREMENT NOT NULL UNIQUE,
                    group_type    INTEGER    DEFAULT (0),
                    group_address CHAR (100),
                    group_notes   TEXT,
                    group_name    CHAR (50)
                );

                CREATE TABLE IF NOT EXISTS list_church_status (
                    id        INTEGER   PRIMARY KEY AUTOINCREMENT UNIQUE NOT NULL,
                    list_name CHAR (50) NOT NULL
                );

                CREATE TABLE IF NOT EXISTS list_event_type (
                    id                        INTEGER   PRIMARY KEY AUTOINCREMENT UNIQUE NOT NULL,
                    list_name                 CHAR (50) NOT NULL,
                    event_change_status_table CHAR (50),
                    event_change_status_id    INTEGER
                );

                CREATE TABLE IF NOT EXISTS list_family_status (
                    id        INTEGER   PRIMARY KEY AUTOINCREMENT UNIQUE NOT NULL,
                    list_name CHAR (50) NOT NULL
                );

                CREATE TABLE IF NOT EXISTS list_gender (
                    id        INTEGER   PRIMARY KEY AUTOINCREMENT UNIQUE NOT NULL,
                    list_name CHAR (50) NOT NULL
                );

                CREATE TABLE IF NOT EXISTS list_group_status (
                    id        INTEGER   PRIMARY KEY AUTOINCREMENT UNIQUE NOT NULL,
                    list_name CHAR (50) NOT NULL
                );

                CREATE TABLE IF NOT EXISTS list_group_type (
                    id        INTEGER   PRIMARY KEY AUTOINCREMENT UNIQUE NOT NULL,
                    list_name CHAR (50) NOT NULL
                );

                CREATE TABLE IF NOT EXISTS month_names (
                    id               INTEGER PRIMARY KEY NOT NULL,
                    month_name_ukr   TEXT    DEFAULT (NULL),
                    month_name_ukr_r TEXT    DEFAULT (NULL)
                );

                CREATE TABLE IF NOT EXISTS people (
                    id             INTEGER PRIMARY KEY AUTOINCREMENT,
                    name           CHAR    DEFAULT (''),
                    address        CHAR    DEFAULT (''),
                    Home_phone     INTEGER DEFAULT (''),
                    Work_phone     INTEGER DEFAULT (''),
                    Mobile_Phone   INTEGER DEFAULT (''),
                    Date_of_Birth  DATE    DEFAULT ('1900-01-01'),
                    gender         INTEGER DEFAULT (0),
                    fam_status     INTEGER DEFAULT (0),
                    children       INTEGER DEFAULT (0),
                    notes          TEXT    DEFAULT (''),
                    church_status  INTEGER DEFAULT (0),
                    Date_of_Bapt   DATE    DEFAULT (''),
                    Mobile_Phone_a INTEGER DEFAULT (''),
                    email          CHAR    NOT NULL DEFAULT (''),
                    send_bd_sms    BOOLEAN DEFAULT (1)
                );

                CREATE TABLE IF NOT EXISTS p_events (
                    id        INTEGER PRIMARY KEY NOT NULL,
                    people_id INTEGER NOT NULL REFERENCES people (id) ON DELETE CASCADE,
                    eventdate DATE    DEFAULT ('1900-01-01'),
                    eventtype INTEGER DEFAULT (0),
                    descr     CHAR
                );

                CREATE TABLE IF NOT EXISTS people_to_groups (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT UNIQUE NOT NULL,
                    people_id INTEGER NOT NULL REFERENCES people (id) ON DELETE CASCADE,
                    group_id  INTEGER NOT NULL REFERENCES groups (group_id) ON DELETE CASCADE,
                    role      INTEGER DEFAULT (0)
                );

                CREATE TABLE IF NOT EXISTS photos (
                    photo_id  INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                    people_id INTEGER NOT NULL REFERENCES people (id) ON DELETE CASCADE,
                    photo     BLOB,
                    descr     CHAR
                );

                CREATE TABLE IF NOT EXISTS user_settings (
                    user_id       INTEGER,
                    setting_key   TEXT,
                    setting_value TEXT,
                    PRIMARY KEY (user_id, setting_key),
                    FOREIGN KEY (user_id) REFERENCES app_users (id)
                );
            """)
            conn.commit()

    def backup_database(self, max_backups=5):
        """Резервне копіювання БД."""
        if not os.path.exists(self.db_path):
            return

        base_dir = os.path.dirname(os.path.abspath(self.db_path))
        base_name, ext = os.path.splitext(os.path.basename(self.db_path))
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        backup_name = os.path.join(base_dir, f"{base_name}_{timestamp}{ext}")

        try:
            shutil.copy2(self.db_path, backup_name)
        except OSError:
            return

        backups = sorted([
            os.path.join(base_dir, f) for f in os.listdir(base_dir)
            if f.startswith(f"{base_name}_") and f.endswith(ext)
        ])
        while len(backups) > max_backups:
            oldest = backups.pop(0)
            try:
                os.remove(oldest)
            except OSError:
                pass

    def open_database(self):
        """Відкриття іншого існуючого файлу БД SQLite."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Обрати файл бази даних SQLite",
            os.path.dirname(os.path.abspath(self.db_path)),
            "Бази даних SQLite (*.db *.sqlite *.sqlite3);;Всі файли (*.*)"
        )
        if not file_path:
            return

        self.db_path = file_path
        self.settings.setValue("last_db_path", self.db_path)
        self.init_db()
        self.backup_database()
        self.selected_person_id = None
        self.current_photo_id = None
        self.photo_label.clear()
        self.photo_label.setText("Немає фото")
        self.load_people()
        self.update_window_title()
        QMessageBox.information(self, "Базу відкрито", f"Базу даних успішно завантажено:\n{self.db_path}")

    def update_window_title(self):
        base_name = os.path.basename(self.db_path)
        self.setWindowTitle(f"ZeoGrace (Python Edition) — [{base_name}]")

    def restore_ui_state(self):
        """Відновлення геометрії вікна, розмірів спліттера та ширини колонок."""
        geom = self.settings.value("main_window_geometry")
        if geom:
            self.restoreGeometry(geom)

        splitter_state = self.settings.value("splitter_state")
        if splitter_state:
            self.splitter.restoreState(splitter_state)

        header_state = self.settings.value("table_header_state")
        if header_state:
            self.table.horizontalHeader().restoreState(header_state)

        vheader_state = self.settings.value("table_vheader_state")
        if vheader_state:
            self.table.verticalHeader().restoreState(vheader_state)

        self.apply_column_visibility()

    def closeEvent(self, event):
        """Збереження налаштувань, геометрії, спліттера та таблиці при закритті додатку."""
        self.settings.setValue("last_db_path", self.db_path)
        if self.selected_person_id is not None:
            self.settings.setValue("last_selected_person_id", self.selected_person_id)

        self.settings.setValue("main_window_geometry", self.saveGeometry())
        self.settings.setValue("splitter_state", self.splitter.saveState())
        self.settings.setValue("table_header_state", self.table.horizontalHeader().saveState())
        self.settings.setValue("table_vheader_state", self.table.verticalHeader().saveState())
        self.settings.setValue("visible_columns", self.visible_columns)
        self.settings.setValue("status_filter_state", json.dumps(self.status_filter_state))
        self.settings.setValue("last_pdf_export_layout", self.last_pdf_layout)
        self.settings.setValue("last_pdf_export_style", self.last_pdf_style)
        self.settings.setValue("last_pdf_phone_card_height", self.last_phone_card_height)

        super().closeEvent(event)

    # --- Інтерфейс користувача ---

    def init_ui(self):
        self.update_window_title()
        self.resize(1150, 700)

        # Меню
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&Файл")

        act_open_db = QAction("&Відкрити базу даних...", self)
        act_open_db.setShortcut("Ctrl+O")
        act_open_db.triggered.connect(self.open_database)
        file_menu.addAction(act_open_db)

        act_backup = QAction("Створити &резервну копію", self)
        act_backup.triggered.connect(lambda: self.backup_database())
        file_menu.addAction(act_backup)

        file_menu.addSeparator()

        act_export_pdf = QAction("&Експорт у PDF...", self)
        act_export_pdf.setShortcut("Ctrl+P")
        act_export_pdf.triggered.connect(self.export_to_pdf)
        file_menu.addAction(act_export_pdf)

        file_menu.addSeparator()

        act_exit = QAction("Ви&хід", self)
        act_exit.setShortcut("Ctrl+Q")
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)

        # Дії CRUD в меню
        person_menu = menu_bar.addMenu("&Парафіяни")
        act_add = QAction("&Додати нового...", self)
        act_add.setShortcut("Ctrl+N")
        act_add.triggered.connect(self.add_person)
        person_menu.addAction(act_add)

        act_edit = QAction("&Редагувати обраного...", self)
        act_edit.setShortcut("Ctrl+E")
        act_edit.triggered.connect(self.edit_person)
        person_menu.addAction(act_edit)

        act_delete = QAction("&Видалити обраного", self)
        act_delete.setShortcut("Delete")
        act_delete.triggered.connect(self.delete_person)
        person_menu.addAction(act_delete)

        person_menu.addSeparator()
        act_status_filter = QAction("Фільтр: &Статус...", self)
        act_status_filter.triggered.connect(self.open_status_filter)
        person_menu.addAction(act_status_filter)

        # Меню вигляду
        view_menu = menu_bar.addMenu("&Вигляд")
        act_columns = QAction("Налаштувати &колонки...", self)
        act_columns.triggered.connect(self.select_columns)
        view_menu.addAction(act_columns)

        # Центральний віджет
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

        # Верхня панель (пошук та фільтри)
        top_bar = QHBoxLayout()

        btn_open_db = QPushButton("Відкрити БД")
        btn_open_db.clicked.connect(self.open_database)
        top_bar.addWidget(btn_open_db)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Пошук за ім'ям, адресою або телефоном...")
        self.search_edit.textChanged.connect(lambda: self.load_people())
        top_bar.addWidget(self.search_edit)

        self.btn_this_week = QPushButton("ДН цього тижня")
        self.btn_this_week.clicked.connect(self.filter_bd_this_week)
        top_bar.addWidget(self.btn_this_week)

        btn_reset = QPushButton("Скинути")
        btn_reset.clicked.connect(self.reset_filter)
        top_bar.addWidget(btn_reset)

        btn_cols = QPushButton("Колонки...")
        btn_cols.clicked.connect(self.select_columns)
        top_bar.addWidget(btn_cols)

        btn_export = QPushButton("Експорт PDF")
        btn_export.clicked.connect(self.export_to_pdf)
        top_bar.addWidget(btn_export)

        main_layout.addLayout(top_bar)

        # Компактний постійно видимий рядок фільтрів зі статусною кнопкою на початку
        filter_box = QFrame()
        filter_box.setFrameShape(QFrame.Shape.StyledPanel)
        filter_box.setStyleSheet(
            "QFrame { background-color: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 4px; }"
        )
        filter_box_layout = QHBoxLayout(filter_box)
        filter_box_layout.setContentsMargins(4, 3, 4, 3)
        filter_box_layout.setSpacing(8)

        self.btn_filter_status = QPushButton("Фільтр: Статус...")
        self.btn_filter_status.clicked.connect(self.open_status_filter)
        filter_box_layout.addWidget(self.btn_filter_status)

        self.filter_info_label = QLabel()
        self.filter_info_label.setWordWrap(True)
        self.filter_info_label.setStyleSheet("border: none; background: transparent; font-size: 11px;")
        filter_box_layout.addWidget(self.filter_info_label, 1)
        filter_box.setFixedHeight(34)

        main_layout.addWidget(filter_box)

        # Панель дій CRUD над записами
        crud_bar = QHBoxLayout()
        btn_add_p = QPushButton("➕ Додати")
        btn_add_p.clicked.connect(self.add_person)
        crud_bar.addWidget(btn_add_p)

        btn_edit_p = QPushButton("✏️ Редагувати")
        btn_edit_p.clicked.connect(self.edit_person)
        crud_bar.addWidget(btn_edit_p)

        btn_del_p = QPushButton("🗑️ Видалити")
        btn_del_p.clicked.connect(self.delete_person)
        crud_bar.addWidget(btn_del_p)

        crud_bar.addStretch()
        main_layout.addLayout(crud_bar)

        # Основна робоча область зі спліттером
        self.splitter = QSplitter(Qt.Orientation.Horizontal)

        # Таблиця парафіян
        self.table = QTableWidget()
        self.table.setColumnCount(len(ALL_COLUMNS))
        self.table.setHorizontalHeaderLabels([col[1] for col in ALL_COLUMNS])

        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self.on_person_selected)
        self.table.itemDoubleClicked.connect(lambda: self.edit_person())
        self.splitter.addWidget(self.table)

        # Права панель для фотографії
        photo_panel = QWidget()
        photo_layout = QVBoxLayout(photo_panel)

        self.photo_label = QLabel("Немає фото")
        self.photo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.photo_label.setFixedSize(260, 320)
        self.photo_label.setStyleSheet("border: 1px solid #ccc; background-color: #f7f7f7;")
        photo_layout.addWidget(self.photo_label)

        btn_add_photo = QPushButton("Завантажити нове фото")
        btn_add_photo.clicked.connect(self.add_photo)
        photo_layout.addWidget(btn_add_photo)

        btn_save_photo = QPushButton("Зберегти фото як...")
        btn_save_photo.clicked.connect(self.save_photo_as)
        photo_layout.addWidget(btn_save_photo)

        btn_del_photo = QPushButton("Видалити фото")
        btn_del_photo.clicked.connect(self.delete_photo)
        photo_layout.addWidget(btn_del_photo)

        photo_layout.addStretch()
        self.splitter.addWidget(photo_panel)

        self.splitter.setSizes([800, 350])
        main_layout.addWidget(self.splitter)

        # Статус-бар
        self.status_label = QLabel("Готово")
        self.statusBar().addWidget(self.status_label)

    # --- Налаштування колонок ---

    def apply_column_visibility(self):
        """Встановлює видимість колонок згідно з вибором користувача."""
        for col_idx, (col_id, _) in enumerate(ALL_COLUMNS):
            is_visible = col_id in self.visible_columns
            self.table.setColumnHidden(col_idx, not is_visible)

    def select_columns(self):
        """Відкриває діалог вибору колонок."""
        dlg = ColumnSelectionDialog(self, current_visible=self.visible_columns)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.visible_columns = dlg.get_selected_columns()
            self.settings.setValue("visible_columns", self.visible_columns)
            self.apply_column_visibility()

    def open_status_filter(self):
        """Відкриває діалог фільтра статусу за зразком modalstatus."""
        dlg = ModalStatusFilterDialog(self, db_path=self.db_path, initial_state=self.status_filter_state)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.status_filter_state = dlg.get_filter_state()
            self.settings.setValue("status_filter_state", json.dumps(self.status_filter_state))
            self.load_people()

    # --- Логіка CRUD для people ---

    def _get_filter_descriptions(self):
        """Отримує людиночитабельні назви активних фільтрів."""
        desc_list = []
        st = self.status_filter_state

        lookup_queries = [
            ("church_status", "list_church_status", "Статус у церкві"),
            ("gender", "list_gender", "Стать"),
            ("family_status", "list_family_status", "Сімейний стан"),
            ("group_status", "list_group_status", "Роль/статус у групі"),
            ("event_type", "list_event_type", "Подія")
        ]

        try:
            with get_db_connection(self.db_path) as conn:
                cur = conn.cursor()
                for key, table_name, title in lookup_queries:
                    ids = st.get(key, [])
                    if ids:
                        placeholders = ",".join("?" * len(ids))
                        cur.execute(f"SELECT list_name FROM {table_name} WHERE id IN ({placeholders}) ORDER BY list_name ASC", ids)
                        names = [row[0] for row in cur.fetchall()]
                        if names:
                            desc_list.append(f"<b>{title}:</b> {', '.join(names)}")
        except Exception:
            pass

        if st.get("group_name"):
            desc_list.append(f"<b>Група:</b> {st['group_name']}")

        if st.get("enable_dates"):
            desc_list.append(f"<b>Діапазон дат події:</b> з {st.get('date_from', '')} до {st.get('date_to', '')}")

        if self.bd_this_week_active:
            desc_list.append("<b>Дні народження:</b> поточний тиждень")

        search_text = self.search_edit.text().strip()
        if search_text:
            desc_list.append(f"<b>Пошук:</b> «{search_text}»")

        return desc_list

    def load_people(self, *args, query_filter=None, params=None):
        """Завантаження та фільтрація списку людей з українським сортуванням."""
        target_person_id = self.selected_person_id

        self.table.blockSignals(True)
        self.table.setRowCount(0)

        gender_map = {}
        fam_map = {}
        church_map = {}
        with get_db_connection(self.db_path) as conn:
            cur = conn.cursor()
            try:
                cur.execute("SELECT id, list_name FROM list_gender")
                gender_map = dict(cur.fetchall())
            except Exception:
                pass
            try:
                cur.execute("SELECT id, list_name FROM list_family_status")
                fam_map = dict(cur.fetchall())
            except Exception:
                pass
            try:
                cur.execute("SELECT id, list_name FROM list_church_status")
                church_map = dict(cur.fetchall())
            except Exception:
                pass

        col_keys = [c[0] for c in ALL_COLUMNS]
        cols_sql = ", ".join(col_keys)
        sql = f"SELECT {cols_sql} FROM people"
        sql_params = []

        search_text = self.search_edit.text().strip()
        conditions = []

        if search_text:
            conditions.append("(name LIKE ? OR address LIKE ? OR Mobile_Phone LIKE ? OR Home_phone LIKE ? OR Work_phone LIKE ?)")
            p = f"%{search_text}%"
            sql_params.extend([p, p, p, p, p])

        if self.bd_this_week_active:
            conditions.append("strftime('%W', Date_of_Birth) = strftime('%W', 'now')")

        if query_filter:
            conditions.append(query_filter)
            if params:
                sql_params.extend(params)

        # Застосування статус-фільтрів (modalstatus)
        st = self.status_filter_state
        if st.get("church_status"):
            placeholders = ",".join("?" * len(st["church_status"]))
            conditions.append(f"church_status IN ({placeholders})")
            sql_params.extend(st["church_status"])

        if st.get("gender"):
            placeholders = ",".join("?" * len(st["gender"]))
            conditions.append(f"gender IN ({placeholders})")
            sql_params.extend(st["gender"])

        if st.get("family_status"):
            placeholders = ",".join("?" * len(st["family_status"]))
            conditions.append(f"fam_status IN ({placeholders})")
            sql_params.extend(st["family_status"])

        if st.get("group_id"):
            conditions.append("id IN (SELECT people_id FROM people_to_groups WHERE group_id = ?)")
            sql_params.append(st["group_id"])

        if st.get("group_status"):
            placeholders = ",".join("?" * len(st["group_status"]))
            conditions.append(f"id IN (SELECT people_id FROM people_to_groups WHERE role IN ({placeholders}))")
            sql_params.extend(st["group_status"])

        if st.get("event_type") or st.get("enable_dates"):
            event_subquery = "id IN (SELECT people_id FROM p_events WHERE 1=1"
            if st.get("event_type"):
                placeholders = ",".join("?" * len(st["event_type"]))
                event_subquery += f" AND eventtype IN ({placeholders})"
                sql_params.extend(st["event_type"])
            if st.get("enable_dates"):
                event_subquery += " AND eventdate >= ? AND eventdate <= ?"
                sql_params.extend([st.get("date_from", "1900-01-01"), st.get("date_to", "2999-12-31")])
            event_subquery += ")"
            conditions.append(event_subquery)

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        sql += " ORDER BY name COLLATE UKRAINIAN ASC"

        with get_db_connection(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(sql, sql_params)
            rows = cur.fetchall()

        rows.sort(key=lambda r: ukrainian_sort_key(r[1]))

        self.table.setRowCount(len(rows))
        target_row = None

        for row_idx, row in enumerate(rows):
            p_id = row[0]
            if target_person_id is not None and p_id == target_person_id:
                target_row = row_idx

            for col_idx, col_name in enumerate(col_keys):
                val = row[col_idx]
                if col_name in ("Mobile_Phone", "Mobile_Phone_a", "Home_phone", "Work_phone"):
                    val = format_phone(val)
                elif col_name == "gender":
                    val = gender_map.get(val, "") if val else ""
                elif col_name == "fam_status":
                    val = fam_map.get(val, "") if val else ""
                elif col_name == "church_status":
                    val = church_map.get(val, "") if val else ""
                elif col_name == "send_bd_sms":
                    val = "Так" if val else "Ні"

                item = QTableWidgetItem(str(val) if val is not None else "")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_idx, col_idx, item)

        self.apply_column_visibility()
        self.table.blockSignals(False)

        if target_row is not None and target_row < self.table.rowCount():
            self.table.selectRow(target_row)
            item = self.table.item(target_row, 0)
            if item:
                self.table.scrollToItem(item, QTableWidget.ScrollHint.EnsureVisible)
        elif self.table.rowCount() > 0:
            self.table.selectRow(0)
        else:
            self.selected_person_id = None
            self.current_photo_id = None
            self.photo_label.clear()
            self.photo_label.setText("Немає фото")

        filter_descs = self._get_filter_descriptions()
        has_status_filters = any(
            st.get(k) for k in ["church_status", "gender", "family_status", "group_status", "group_id", "event_type"]
        ) or st.get("enable_dates")

        if has_status_filters:
            self.btn_filter_status.setStyleSheet("font-weight: bold; background-color: #DBEAFE; color: #1E40AF;")
        else:
            self.btn_filter_status.setStyleSheet("")

        if self.bd_this_week_active:
            self.btn_this_week.setStyleSheet("font-weight: bold; background-color: #FEF3C7; color: #92400E;")
        else:
            self.btn_this_week.setStyleSheet("")

        if filter_descs:
            self.filter_info_label.setText("🔍 <b>Активні фільтри:</b> " + " | ".join(filter_descs))
        else:
            self.filter_info_label.setText("<span style='color: #64748B;'>Фільтри не застосовано (показано всі записи)</span>")

        plain_filter_summary = " [Фільтр активний]" if filter_descs else ""
        self.status_label.setText(f"БД: {os.path.basename(self.db_path)} | Записів знайдено: {len(rows)}{plain_filter_summary}")

    def add_person(self):
        """Створення нового запису (Create)."""
        dlg = PersonDialog(self, db_path=self.db_path)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            with get_db_connection(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO people (
                        name, address, Home_phone, Work_phone, Mobile_Phone,
                        Date_of_Birth, gender, fam_status, children, notes,
                        church_status, Date_of_Bapt, Mobile_Phone_a, email, send_bd_sms
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data["name"], data["address"], data["Home_phone"], data["Work_phone"],
                    data["Mobile_Phone"], data["Date_of_Birth"], data["gender"], data["fam_status"],
                    data["children"], data["notes"], data["church_status"], data["Date_of_Bapt"],
                    data["Mobile_Phone_a"], data["email"], data["send_bd_sms"]
                ))
                conn.commit()
                new_id = cur.lastrowid

            self.selected_person_id = new_id
            self.load_people()

    def edit_person(self):
        """Редагування вибраного запису (Update)."""
        if not self.selected_person_id:
            QMessageBox.warning(self, "Увага", "Оберіть запис для редагування!")
            return

        with get_db_connection(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM people WHERE id = ?", (self.selected_person_id,))
            row = cur.fetchone()

        if not row:
            return

        person_dict = dict(row)
        dlg = PersonDialog(self, person_data=person_dict, db_path=self.db_path)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            with get_db_connection(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE people
                    SET name = ?, address = ?, Home_phone = ?, Work_phone = ?,
                        Mobile_Phone = ?, Date_of_Birth = ?, gender = ?, fam_status = ?,
                        children = ?, notes = ?, church_status = ?, Date_of_Bapt = ?,
                        Mobile_Phone_a = ?, email = ?, send_bd_sms = ?
                    WHERE id = ?
                """, (
                    data["name"], data["address"], data["Home_phone"], data["Work_phone"],
                    data["Mobile_Phone"], data["Date_of_Birth"], data["gender"], data["fam_status"],
                    data["children"], data["notes"], data["church_status"], data["Date_of_Bapt"],
                    data["Mobile_Phone_a"], data["email"], data["send_bd_sms"], self.selected_person_id
                ))
                conn.commit()

            self.load_people()

    def delete_person(self):
        """Видалення вибраного запису (Delete)."""
        if not self.selected_person_id:
            QMessageBox.warning(self, "Увага", "Оберіть запис для видалення!")
            return

        row = self.table.currentRow()
        name = self.table.item(row, 1).text() if row >= 0 else ""

        reply = QMessageBox.question(
            self,
            "Підтвердження видалення",
            f"Ви дійсно бажаєте видалити запис '{name}' (ID: {self.selected_person_id})?\n"
            "Усі пов'язані фотографії та події також буде видалено.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            with get_db_connection(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("PRAGMA foreign_keys = ON")
                cur.execute("DELETE FROM photos WHERE people_id = ?", (self.selected_person_id,))
                cur.execute("DELETE FROM people WHERE id = ?", (self.selected_person_id,))
                conn.commit()

            self.selected_person_id = None
            self.current_photo_id = None
            self.settings.remove("last_selected_person_id")
            self.photo_label.clear()
            self.photo_label.setText("Немає фото")
            self.load_people()

    def filter_bd_this_week(self):
        """Перемикач фільтра днів народження поточного тижня."""
        self.bd_this_week_active = not self.bd_this_week_active
        self.load_people()

    def reset_filter(self):
        """Скидання всіх фільтрів (пошук, дні народження та статусні фільтри)."""
        self.search_edit.clear()
        self.bd_this_week_active = False
        self.status_filter_state = {}
        self.settings.remove("status_filter_state")
        self.load_people()

    def on_person_selected(self):
        selected = self.table.selectedItems()
        if not selected:
            self.selected_person_id = None
            self.current_photo_id = None
            self.photo_label.setText("Немає фото")
            self.photo_label.setPixmap(QPixmap())
            return

        self.selected_person_id = int(self.table.item(selected[0].row(), 0).text())
        self.settings.setValue("last_selected_person_id", self.selected_person_id)
        self.display_photo(self.selected_person_id)

    # --- Робота із зображеннями (CRUD для photos) ---

    def display_photo(self, people_id):
        with get_db_connection(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT photo_id, photo FROM photos WHERE people_id = ? ORDER BY photo_id DESC LIMIT 1", (people_id,))
            res = cur.fetchone()

        if res and res[1]:
            self.current_photo_id = res[0]
            pixmap = QPixmap()
            pixmap.loadFromData(res[1], "JPEG")
            self.photo_label.setPixmap(
                pixmap.scaled(self.photo_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            )
        else:
            self.current_photo_id = None
            self.photo_label.clear()
            self.photo_label.setText("Немає фото")

    def add_photo(self):
        if not self.selected_person_id:
            QMessageBox.warning(self, "Увага", "Оберіть запис зі списку!")
            return

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Оберіть фото", "", "Зображення (*.jpg *.jpeg *.png *.bmp)"
        )
        if not file_path:
            return

        try:
            img = Image.open(file_path).convert("RGB")
            max_size = (600, 800)
            img.thumbnail(max_size, Image.Resampling.LANCZOS)

            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=85)
            photo_bytes = buffer.getvalue()

            with get_db_connection(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("INSERT INTO photos (people_id, photo) VALUES (?, ?)", (self.selected_person_id, photo_bytes))
                conn.commit()

            self.display_photo(self.selected_person_id)
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося додати фото:\n{str(e)}")

    def delete_photo(self):
        if not self.current_photo_id:
            QMessageBox.information(self, "Інформація", "Для вибраного запису фото відсутнє.")
            return

        reply = QMessageBox.question(
            self, "Видалення фото", "Ви дійсно бажаєте видалити це фото?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            with get_db_connection(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM photos WHERE photo_id = ?", (self.current_photo_id,))
                conn.commit()

            self.display_photo(self.selected_person_id)

    def save_photo_as(self):
        if not self.selected_person_id:
            return

        with get_db_connection(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("SELECT photo FROM photos WHERE people_id = ? ORDER BY photo_id DESC LIMIT 1", (self.selected_person_id,))
            res = cur.fetchone()

        if not res or not res[0]:
            QMessageBox.information(self, "Інформація", "Фото відсутнє для збереження.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Зберегти фото", f"person_{self.selected_person_id}.jpg", "JPEG фото (*.jpg)"
        )
        if not file_path:
            return

        try:
            with open(file_path, "wb") as f:
                f.write(res[0])
            QMessageBox.information(self, "Успіх", f"Фото збережено у:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося зберегти фото:\n{str(e)}")

    # --- Прямий експорт у PDF (ReportLab) ---

    def export_to_pdf(self):
        style_dlg = PdfExportStyleDialog(
            self,
            current_layout=self.last_pdf_layout,
            current_style=self.last_pdf_style,
            current_card_h=self.last_phone_card_height
        )
        if style_dlg.exec() != QDialog.DialogCode.Accepted:
            return

        chosen_layout_key = style_dlg.get_selected_layout()
        chosen_style_key = style_dlg.get_selected_style()
        phone_card_height = style_dlg.get_phone_card_height()

        self.last_pdf_layout = chosen_layout_key
        self.last_pdf_style = chosen_style_key
        self.last_phone_card_height = phone_card_height

        self.settings.setValue("last_pdf_export_layout", chosen_layout_key)
        self.settings.setValue("last_pdf_export_style", chosen_style_key)
        self.settings.setValue("last_pdf_phone_card_height", phone_card_height)

        style_cfg = PDF_STYLES.get(chosen_style_key, PDF_STYLES["slate"])

        # Автоматичне формування назви файлу
        cur_date_str = datetime.now().strftime("%Y-%m-%d")
        db_base_name = os.path.splitext(os.path.basename(self.db_path))[0]
        layout_name_slug = {
            "a4_cards": "A4",
            "phone": "Phone",
            "compact": "Compact"
        }.get(chosen_layout_key, "Report")

        filter_slugs = []
        st = self.status_filter_state
        if st.get("group_name"):
            filter_slugs.append(f"Grp_{st['group_name'][:10]}")
        if self.bd_this_week_active:
            filter_slugs.append("BDWeek")
        if self.search_edit.text().strip():
            filter_slugs.append(f"Search_{self.search_edit.text().strip()[:8]}")
        if any(st.get(k) for k in ["church_status", "gender", "family_status", "group_status", "event_type"]):
            filter_slugs.append("Filtered")

        filter_suffix = ("_" + "_".join(filter_slugs)) if filter_slugs else ""
        clean_suffix = "".join(c for c in filter_suffix if c.isalnum() or c in ("_", "-"))
        default_file_name = f"{cur_date_str}_{db_base_name}_{layout_name_slug}{clean_suffix}.pdf"

        last_dir = self.settings.value("last_pdf_export_dir", os.path.dirname(os.path.abspath(self.db_path)), type=str)
        default_save_path = os.path.join(last_dir, default_file_name)

        save_path, _ = QFileDialog.getSaveFileName(
            self,
            "Зберегти PDF-звіт",
            default_save_path,
            "PDF файли (*.pdf)"
        )
        if not save_path:
            return

        self.settings.setValue("last_pdf_export_dir", os.path.dirname(os.path.abspath(save_path)))

        total_rows = self.table.rowCount()
        progress = QProgressDialog("Підготовка даних для звіту...", "Скасувати", 0, total_rows + 5, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(150)
        progress.setValue(0)

        records = []
        with get_db_connection(self.db_path) as conn:
            cur = conn.cursor()
            for row_idx in range(total_rows):
                if progress.wasCanceled():
                    return
                progress.setValue(row_idx)
                progress.setLabelText(f"Обробка запису {row_idx + 1} з {total_rows}...")
                QApplication.processEvents()

                p_id = int(self.table.item(row_idx, 0).text())
                cur.execute("""
                    SELECT p.id, p.name, p.address, p.Date_of_Birth, p.Date_of_Bapt,
                           p.Mobile_Phone, p.Mobile_Phone_a, p.Home_phone, p.Work_phone,
                           p.children,
                           (SELECT list_name FROM list_church_status WHERE id = p.church_status),
                           (SELECT list_name FROM list_family_status WHERE id = p.fam_status),
                           p.email
                    FROM people p
                    WHERE p.id = ?
                """, (p_id,))
                p_row = cur.fetchone()
                if not p_row:
                    continue

                cur.execute("SELECT photo FROM photos WHERE people_id = ? ORDER BY photo_id DESC LIMIT 1", (p_id,))
                photo_row = cur.fetchone()
                photo_bytes = photo_row[0] if (photo_row and photo_row[0]) else None

                raw_phones = []
                for ph in [p_row[5], p_row[6], p_row[7], p_row[8]]:
                    fph = format_phone(ph)
                    if fph and fph not in raw_phones:
                        raw_phones.append(fph)

                phone_str = ", ".join(raw_phones) if raw_phones else "—"
                nobr_phones = [ph.replace(" ", "&nbsp;").replace("-", "&#8209;") for ph in raw_phones]
                compact_phones_str = ", ".join(nobr_phones) if nobr_phones else "—"

                records.append({
                    "id": p_row[0],
                    "name": p_row[1] or "",
                    "address": p_row[2] or "—",
                    "dob": p_row[3] or "—",
                    "bapt": p_row[4] or "—",
                    "phones": phone_str,
                    "compact_phones": compact_phones_str,
                    "children": p_row[9] if p_row[9] is not None else 0,
                    "church_status": p_row[10] or "—",
                    "fam_status": p_row[11] or "—",
                    "email": p_row[12] or "",
                    "photo_bytes": photo_bytes
                })

        total_records_count = len(records)
        progress.setValue(total_rows + 1)
        progress.setLabelText("Генерація макета PDF...")
        QApplication.processEvents()

        styles = getSampleStyleSheet()

        # Формування параметрів документа та розмірів сторінки
        if chosen_layout_key == "phone":
            # Розрахунок висоти сторінки для 3 плиток з урахуванням налаштованої висоти картки
            phone_w = 108 * 2.834
            top_margin = 10
            bottomMargin = 14
            left_margin = right_margin = 10
            # 3 картки + заголовки (близько 60 pt) + відступи між картками
            phone_h = (phone_card_height * 3) + 75
            page_size = (phone_w, phone_h)
            doc_width = phone_w - (left_margin + right_margin)
        else:
            page_size = A4
            left_margin = right_margin = 25
            top_margin = 25
            bottomMargin = 25
            doc_width = 545

        doc = SimpleDocTemplate(
            save_path,
            pagesize=page_size,
            leftMargin=left_margin,
            rightMargin=right_margin,
            topMargin=top_margin,
            bottomMargin=bottomMargin
        )

        elements = []

        title_font_size = 13 if chosen_layout_key == "phone" else 15
        title_style = ParagraphStyle(
            name="ReportTitle",
            parent=styles["Heading1"],
            fontName=self.pdf_font,
            fontSize=title_font_size,
            leading=title_font_size + 3,
            spaceAfter=5,
            alignment=1,
            textColor=style_cfg["title_color"]
        )

        filter_descs = self._get_filter_descriptions()
        filter_parts = []
        if filter_descs:
            filter_parts.append("<b>Фільтри:</b> " + " | ".join(filter_descs))
        filter_parts.append(f"<b>Всього записів:</b> {total_records_count}")
        filter_full_text = " | ".join(filter_parts)

        filter_style = ParagraphStyle(
            name="ReportFilter",
            parent=styles["Normal"],
            fontName=self.pdf_font,
            fontSize=6.5 if chosen_layout_key == "phone" else 7.5,
            leading=9.5,
            textColor=style_cfg["filter_text_color"]
        )

        elements.append(Paragraph("Звіт списку громади", title_style))
        filter_table = Table([[Paragraph(filter_full_text, filter_style)]], colWidths=[doc_width])
        filter_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), style_cfg["filter_box_bg"]),
            ("BOX", (0, 0), (-1, -1), 0.5, style_cfg["filter_box_border"]),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ]))
        elements.append(filter_table)
        elements.append(Spacer(1, 5))

        # --- 1. Лейаут "А4" ---
        if chosen_layout_key == "a4_cards":
            card_w = (doc_width - 8) / 2
            card_photo_max_w = card_w * 0.38
            card_photo_max_h = 165
            info_w = card_w - card_photo_max_w - 8

            text_style = ParagraphStyle(
                name="CardTextA4",
                parent=styles["Normal"],
                fontName=self.pdf_font,
                fontSize=7.2,
                leading=9.2
            )
            title_card_style = ParagraphStyle(
                name="CardTitleA4",
                parent=styles["Normal"],
                fontName=self.pdf_font,
                fontSize=8.5,
                leading=10.5,
                textColor=style_cfg["title_color"]
            )

            cards = []
            for idx, rec in enumerate(records, start=1):
                img_widget = get_proportional_image(rec["photo_bytes"], card_photo_max_w, card_photo_max_h)

                info_lines = [
                    Paragraph(f"<b>#{idx}. {rec['name']}</b>", title_card_style),
                    Paragraph(f"<b>Тел:</b> {rec['phones']}", text_style),
                    Paragraph(f"<b>Адреса:</b> {rec['address']}", text_style),
                    Paragraph(f"<b>ДН:</b> {rec['dob']} | <b>Хрещ:</b> {rec['bapt']}", text_style),
                    Paragraph(f"<b>Статус:</b> {rec['church_status']}", text_style),
                    Paragraph(f"<b>Сім'я:</b> {rec['fam_status']} (дітей: {rec['children']})", text_style),
                ]
                if rec["email"]:
                    info_lines.append(Paragraph(f"<b>Email:</b> {rec['email']}", text_style))

                card_table = Table([[img_widget, info_lines]], colWidths=[card_photo_max_w, info_w])
                card_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), style_cfg["card_bg"]),
                    ("BOX", (0, 0), (-1, -1), 0.5, style_cfg["card_border"]),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (0, 0), (0, 0), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]))
                cards.append(card_table)

            grid_data = []
            for i in range(0, len(cards), 2):
                row_cells = [cards[i]]
                if i + 1 < len(cards):
                    row_cells.append(cards[i + 1])
                else:
                    row_cells.append("")
                grid_data.append(row_cells)

            if grid_data:
                cards_grid = Table(grid_data, colWidths=[card_w, card_w])
                cards_grid.setStyle(TableStyle([
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("LEFTPADDING", (0, 0), (-1, -1), 2),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 2),
                ]))
                elements.append(cards_grid)

        # --- 2. Лейаут "Для телефону" ---
        elif chosen_layout_key == "phone":
            card_w = doc_width
            # Фотографія займає близько 1/3 ширини картки
            card_photo_max_w = card_w * 0.33
            # Висота фотографії пропорційно масштабується відповідно до висоти картки
            card_photo_max_h = max(70, phone_card_height - 14)
            info_w = card_w - card_photo_max_w - 6

            # Пропорційне масштабування шрифту відповідно до висоти картки
            font_scale = max(0.85, min(1.35, phone_card_height / 150.0))
            base_font_sz = 6.8 * font_scale
            title_font_sz = 8.2 * font_scale

            phone_text_style = ParagraphStyle(
                name="CardPhoneText",
                parent=styles["Normal"],
                fontName=self.pdf_font,
                fontSize=base_font_sz,
                leading=base_font_sz * 1.25
            )
            phone_title_style = ParagraphStyle(
                name="CardPhoneTitle",
                parent=styles["Normal"],
                fontName=self.pdf_font,
                fontSize=title_font_sz,
                leading=title_font_sz * 1.22,
                textColor=style_cfg["title_color"]
            )

            for idx, rec in enumerate(records, start=1):
                img_widget = get_proportional_image(rec["photo_bytes"], card_photo_max_w, card_photo_max_h)

                info_lines = [
                    Paragraph(f"<b>#{idx}. {rec['name']}</b>", phone_title_style),
                    Paragraph(f"<b>Тел:</b> {rec['phones']}", phone_text_style),
                    Paragraph(f"<b>Адреса:</b> {rec['address']}", phone_text_style),
                    Paragraph(f"<b>ДН:</b> {rec['dob']} | <b>Хрещ:</b> {rec['bapt']}", phone_text_style),
                    Paragraph(f"<b>Статус:</b> {rec['church_status']} | <b>Сім:</b> {rec['fam_status']}", phone_text_style),
                    Paragraph(f"<b>Дітей:</b> {rec['children']}", phone_text_style),
                ]
                if rec["email"]:
                    info_lines.append(Paragraph(f"<b>Email:</b> {rec['email']}", phone_text_style))

                card_table = Table([[img_widget, info_lines]], colWidths=[card_photo_max_w, info_w])
                card_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, -1), style_cfg["card_bg"]),
                    ("BOX", (0, 0), (-1, -1), 0.5, style_cfg["card_border"]),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("ALIGN", (0, 0), (0, 0), "CENTER"),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("LEFTPADDING", (0, 0), (-1, -1), 3),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ]))

                elements.append(card_table)
                elements.append(Spacer(1, 3))

                # Рівно по 3 картки на сторінку
                if idx % 3 == 0 and idx < len(records):
                    elements.append(PageBreak())

        # --- 3. Лейаут "Компактний" ---
        else:
            compact_header_style = ParagraphStyle(
                name="CompactHeader",
                parent=styles["Normal"],
                fontName=self.pdf_font,
                fontSize=7.5,
                leading=9.5,
                textColor=style_cfg["header_text"]
            )
            compact_cell_style = ParagraphStyle(
                name="CompactCell",
                parent=styles["Normal"],
                fontName=self.pdf_font,
                fontSize=7.0,
                leading=8.8
            )

            col_widths = [18, 125, 110, 105, 62, 125]
            headers = [
                Paragraph("<b>№</b>", compact_header_style),
                Paragraph("<b>П.І.Б.</b>", compact_header_style),
                Paragraph("<b>Адреса</b>", compact_header_style),
                Paragraph("<b>Номери телефонів</b>", compact_header_style),
                Paragraph("<b>ДН / Хрещення</b>", compact_header_style),
                Paragraph("<b>Додаткові дані (статуси, діти)</b>", compact_header_style)
            ]
            table_data = [headers]

            for idx, rec in enumerate(records, start=1):
                dob_bapt_text = f"{rec['dob']}<br/>{rec['bapt']}" if rec['bapt'] != "—" else rec['dob']

                extras = []
                if rec['church_status'] != "—":
                    extras.append(f"Церк: {rec['church_status']}")
                if rec['fam_status'] != "—":
                    extras.append(f"Сім'я: {rec['fam_status']}")
                if rec['children']:
                    extras.append(f"Дітей: {rec['children']}")
                if rec['email']:
                    extras.append(f"{rec['email']}")
                extras_text = " | ".join(extras) if extras else "—"

                table_data.append([
                    Paragraph(str(idx), compact_cell_style),
                    Paragraph(f"<b>{rec['name']}</b>", compact_cell_style),
                    Paragraph(rec['address'], compact_cell_style),
                    Paragraph(rec['compact_phones'], compact_cell_style),
                    Paragraph(dob_bapt_text, compact_cell_style),
                    Paragraph(extras_text, compact_cell_style),
                ])

            compact_table = Table(table_data, colWidths=col_widths, repeatRows=1)
            compact_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), style_cfg["header_bg"]),
                ("ALIGN", (0, 0), (-1, -1), "LEFT"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("GRID", (0, 0), (-1, -1), 0.5, style_cfg["grid_color"]),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [style_cfg["row_bg1"], style_cfg["row_bg2"]]),
            ]))
            elements.append(compact_table)

        progress.setValue(total_rows + 3)
        progress.setLabelText("Збирання PDF-файлу...")
        QApplication.processEvents()

        def canvas_factory(*args, **kwargs):
            return NumberedCanvas(*args, font_name=self.pdf_font, **kwargs)

        try:
            doc.build(elements, canvasmaker=canvas_factory)
            progress.setValue(total_rows + 5)
            self.statusBar().showMessage(f"PDF-звіт успішно збережено: {os.path.basename(save_path)}", 8000)
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося створити PDF:\n{str(e)}")
        finally:
            progress.close()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ZeoGraceApp()
    window.show()
    sys.exit(app.exec())
