from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPainter, QColor, QPen, QFont, QPixmap
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QDialog,
    QDialogButtonBox, QSpinBox, QGroupBox, QRadioButton
)

from reportlab.pdfgen import canvas
from reportlab.lib import colors

from config import PDF_STYLES, PDF_LAYOUTS
from utils import reportlab_color_to_qcolor


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


class PdfPreviewWidget(QWidget):
    """Швидкодіючий віджет для динамічного показу попереднього перегляду 1-ї сторінки."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout_key = "a4_cards"
        self.style_key = "slate"
        self.phone_card_height = 150
        self.records = []
        self.setMinimumSize(280, 400)
        self.setStyleSheet("background-color: #F1F5F9; border: 1px solid #CBD5E1; border-radius: 4px;")

    def set_preview_data(self, layout_key: str, style_key: str, phone_card_height: int, records: list):
        self.layout_key = layout_key
        self.style_key = style_key
        self.phone_card_height = phone_card_height
        self.records = records or []
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        w = self.width()
        h = self.height()
        painter.fillRect(0, 0, w, h, QColor("#F1F5F9"))

        style_cfg = PDF_STYLES.get(self.style_key, PDF_STYLES["slate"])
        c_head = reportlab_color_to_qcolor(style_cfg["header_bg"])
        c_title = reportlab_color_to_qcolor(style_cfg["title_color"])
        c_card_bg = reportlab_color_to_qcolor(style_cfg["card_bg"])
        c_border = reportlab_color_to_qcolor(style_cfg["card_border"])
        c_filter = reportlab_color_to_qcolor(style_cfg["filter_box_bg"])

        margin = 12
        avail_w = w - 2 * margin
        avail_h = h - 2 * margin

        # Розрахунок геометрії «аркуша» згідно з форматом
        if self.layout_key == "phone":
            # Фіксований формат А5 (148 x 210 мм, співвідношення ~ 1 : 1.414)
            aspect = 1.414
        else:
            # Формат А4 (210 x 297 мм, співвідношення ~ 1 : 1.414)
            aspect = 1.414

        page_h = avail_h
        page_w = page_h / aspect
        if page_w > avail_w:
            page_w = avail_w
            page_h = page_w * aspect

        page_x = (w - page_w) / 2
        page_y = (h - page_h) / 2
        page_rect = QRectF(page_x, page_y, page_w, page_h)

        # Тінь та аркуш
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 30))
        painter.drawRoundedRect(page_rect.translated(2.5, 3.5), 3, 3)

        painter.setPen(QPen(QColor("#CBD5E1"), 1))
        painter.setBrush(QColor("#FFFFFF"))
        painter.drawRoundedRect(page_rect, 3, 3)

        # Заголовок сторінки
        painter.setPen(c_title)
        title_font = QFont("Arial", 8)
        title_font.setBold(True)
        painter.setFont(title_font)
        painter.drawText(QRectF(page_x, page_y + 6, page_w, 14), Qt.AlignmentFlag.AlignCenter, "Звіт списку громади")

        # Блок активних фільтрів
        f_rect = QRectF(page_x + 10, page_y + 22, page_w - 20, 10)
        painter.setPen(QPen(c_border, 0.5))
        painter.setBrush(c_filter)
        painter.drawRoundedRect(f_rect, 1.5, 1.5)

        cnt_left = page_x + 10
        cnt_top = page_y + 36
        cnt_w = page_w - 20
        cnt_h = page_h - 48

        # --- 1. А4: по 2 картки в рядку ---
        if self.layout_key == "a4_cards":
            col_gap = 6
            c_w = (cnt_w - col_gap) / 2
            c_h = min(62.0, (cnt_h - 12) / 3.1)

            card_idx = 0
            for r in range(3):
                y_c = cnt_top + r * (c_h + 4)
                if y_c + c_h > page_y + page_h - 12:
                    break
                for c in range(2):
                    x_c = cnt_left + c * (c_w + col_gap)
                    c_rect = QRectF(x_c, y_c, c_w, c_h)
                    painter.setPen(QPen(c_border, 0.5))
                    painter.setBrush(c_card_bg)
                    painter.drawRoundedRect(c_rect, 2, 2)

                    # Фото картки
                    ph_w = c_w * 0.36
                    ph_h = c_h - 6
                    ph_rect = QRectF(x_c + 3, y_c + 3, ph_w, ph_h)
                    painter.fillRect(ph_rect, QColor("#E2E8F0"))

                    rec_name = f"#{card_idx+1} Парафіянин"
                    if card_idx < len(self.records):
                        rec_name = f"#{card_idx+1} {self.records[card_idx].get('name', '')}"
                        p_bytes = self.records[card_idx].get("photo_bytes")
                        if p_bytes:
                            px = QPixmap()
                            if px.loadFromData(p_bytes):
                                s_px = px.scaled(int(ph_w), int(ph_h), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                                painter.drawPixmap(int(x_c + 3 + (ph_w - s_px.width())/2), int(y_c + 3 + (ph_h - s_px.height())/2), s_px)

                    # Текстова частина картки
                    tx = x_c + ph_w + 6
                    tw = c_w - ph_w - 9
                    painter.setPen(c_title)
                    card_title_font = QFont("Arial", 5)
                    card_title_font.setBold(True)
                    painter.setFont(card_title_font)
                    painter.drawText(QRectF(tx, y_c + 3, tw, 8), Qt.AlignmentFlag.AlignLeft, rec_name[:22])

                    painter.setPen(Qt.PenStyle.NoPen)
                    painter.setBrush(QColor("#94A3B8"))
                    painter.drawRect(QRectF(tx, y_c + 13, tw * 0.9, 1.8))
                    painter.drawRect(QRectF(tx, y_c + 18, tw * 0.75, 1.8))
                    painter.drawRect(QRectF(tx, y_c + 23, tw * 0.85, 1.8))
                    painter.drawRect(QRectF(tx, y_c + 28, tw * 0.5, 1.8))

                    card_idx += 1

        # --- 2. Для телефону (формат А5, 3 плитки, динамічне фото від висоти) ---
        elif self.layout_key == "phone":
            scale_factor = self.phone_card_height / 150.0
            card_h = min(66.0 * scale_factor, (cnt_h - 12) / 3.1)
            c_w = cnt_w

            ph_h = max(25.0, card_h - 6)
            ph_w = min(c_w * 0.45, ph_h * 0.78)

            for i in range(3):
                y_c = cnt_top + i * (card_h + 5)
                if y_c + card_h > page_y + page_h - 12:
                    break
                c_rect = QRectF(cnt_left, y_c, c_w, card_h)
                painter.setPen(QPen(c_border, 0.5))
                painter.setBrush(c_card_bg)
                painter.drawRoundedRect(c_rect, 2.5, 2.5)

                ph_rect = QRectF(cnt_left + 3, y_c + 3, ph_w, ph_h)
                painter.fillRect(ph_rect, QColor("#E2E8F0"))

                rec_name = f"#{i+1} Парафіянин"
                if i < len(self.records):
                    rec_name = f"#{i+1} {self.records[i].get('name', '')}"
                    p_bytes = self.records[i].get("photo_bytes")
                    if p_bytes:
                        px = QPixmap()
                        if px.loadFromData(p_bytes):
                            s_px = px.scaled(int(ph_w), int(ph_h), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                            painter.drawPixmap(int(cnt_left + 3 + (ph_w - s_px.width())/2), int(y_c + 3 + (ph_h - s_px.height())/2), s_px)

                tx = cnt_left + ph_w + 6
                tw = c_w - ph_w - 9
                painter.setPen(c_title)
                phone_title_font = QFont("Arial", 6)
                phone_title_font.setBold(True)
                painter.setFont(phone_title_font)
                painter.drawText(QRectF(tx, y_c + 3, tw, 9), Qt.AlignmentFlag.AlignLeft, rec_name[:24])

                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(QColor("#64748B"))
                painter.drawRect(QRectF(tx, y_c + 14, tw * 0.85, 2.0))
                painter.drawRect(QRectF(tx, y_c + 19, tw * 0.95, 2.0))
                painter.drawRect(QRectF(tx, y_c + 24, tw * 0.7, 2.0))
                painter.drawRect(QRectF(tx, y_c + 29, tw * 0.5, 2.0))

        # --- 3. Компактний (таблиця без фото) ---
        else:
            tbl_h = cnt_h - 4
            tbl_rect = QRectF(cnt_left, cnt_top, cnt_w, tbl_h)

            row_h = 13.0
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(c_head)
            painter.drawRect(QRectF(cnt_left, cnt_top, cnt_w, row_h))

            c_r1 = reportlab_color_to_qcolor(style_cfg["row_bg1"])
            c_r2 = reportlab_color_to_qcolor(style_cfg["row_bg2"])
            num_rows = int((tbl_h - row_h) / row_h)

            for r in range(min(num_rows, 16)):
                ry = cnt_top + row_h + r * row_h
                painter.setBrush(c_r1 if r % 2 == 0 else c_r2)
                painter.drawRect(QRectF(cnt_left, ry, cnt_w, row_h))

            painter.setPen(QPen(reportlab_color_to_qcolor(style_cfg["grid_color"]), 0.5))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRect(tbl_rect)

            col_splits = [0.06, 0.30, 0.52, 0.74, 0.86]
            for frac in col_splits:
                sx = cnt_left + cnt_w * frac
                painter.drawLine(int(sx), int(cnt_top), int(sx), int(cnt_top + tbl_h))

        # Нижня мітка формату і сторінки
        fmt_label = "Формат: A5" if self.layout_key == "phone" else "Формат: A4"
        painter.setPen(QColor("#94A3B8"))
        painter.setFont(QFont("Arial", 5))
        painter.drawText(QRectF(page_x + 10, page_y + page_h - 11, 80, 8), Qt.AlignmentFlag.AlignLeft, fmt_label)
        painter.drawText(QRectF(page_x + page_w - 70, page_y + page_h - 11, 60, 8), Qt.AlignmentFlag.AlignRight, "Стор. 1 з 3")


class PdfExportStyleDialog(QDialog):
    """Діалогове вікно вибору лейауту та стилю для експорту в PDF з інтерактивним прев'ю."""
    def __init__(self, parent=None, current_layout="a4_cards", current_style="slate", current_card_h=150, app_instance=None):
        super().__init__(parent)
        self.app = app_instance
        self.setWindowTitle("Параметри експорту в PDF")
        self.resize(860, 560)
        self.selected_layout_key = current_layout if current_layout in PDF_LAYOUTS else "a4_cards"
        self.selected_style_key = current_style if current_style in PDF_STYLES else "slate"
        self.phone_card_height = current_card_h
        self.preview_records = []
        if self.app:
            self.preview_records = self.app._get_records_for_export(limit=6)
        self.init_ui()

    def init_ui(self):
        root_layout = QHBoxLayout(self)

        # Ліва панель із фіксованою шириною
        left_widget = QWidget()
        left_widget.setFixedWidth(380)
        left_panel = QVBoxLayout(left_widget)
        left_panel.setContentsMargins(0, 0, 0, 0)

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

        root_layout.addWidget(left_widget, 0)

        # Права колонка — попередній перегляд (розтягується автоматично)
        gb_preview = QGroupBox("Попередній перегляд 1-ї сторінки")
        preview_vbox = QVBoxLayout(gb_preview)
        self.preview_widget = PdfPreviewWidget()
        preview_vbox.addWidget(self.preview_widget)
        root_layout.addWidget(gb_preview, 1)

        self._on_options_changed()

    def _on_options_changed(self):
        curr_layout = self.get_selected_layout()
        curr_style = self.get_selected_style()
        curr_height = self.spin_card_height.value()

        self.card_h_container.setEnabled(curr_layout == "phone")
        self.preview_widget.set_preview_data(curr_layout, curr_style, curr_height, self.preview_records)

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
