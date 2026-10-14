import io
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from PIL import Image

from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtCore import QTimer

from PyQt6.QtGui import QPixmap, QAction
from PyQt6.QtGui import QShortcut, QKeySequence
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLineEdit, QLabel,
    QFileDialog, QMessageBox, QHeaderView, QSplitter,
    QFrame, QProgressDialog, QDialog
)

from config import ALL_COLUMNS, DEFAULT_VISIBLE_COLUMNS
from utils import ukrainian_sort_key, format_phone, register_unicode_font
from database import get_db_connection, init_db, backup_database
from pdf_components import PdfExportStyleDialog
from pdf_generator import build_pdf_document
from dialogs import ColumnSelectionDialog, ModalStatusFilterDialog, PersonDialog, ListEditorDialog, FamiliesWindow, SettingsDialog

class ZeoGraceApp(QMainWindow):
    def __init__(self, db_path=None):
        super().__init__()
        self.settings = QSettings("ZeoGrace", "ZeoGraceApp")

        self.person_edit_dialog = None
        
        self.db_path = None
        if db_path is not None:
            self.db_path = db_path
        else:
            saved_db = self.settings.value("last_db_path", type=str)
            if saved_db and os.path.exists(saved_db):
                self.db_path = saved_db
            else:
                self.prompt_startup_action()

        if not self.db_path:
            if getattr(sys, 'frozen', False):
                base_dir = os.path.dirname(sys.executable)
            else:
                base_dir = os.path.dirname(os.path.abspath(__file__))
            self.db_path = os.path.join(base_dir, "zeograce.db")

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

        self.backup_timer = QTimer(self)
        self.backup_timer.timeout.connect(self.run_periodic_backup)
        
        init_db(self.db_path)
        backup_database(self.db_path, prefix="startup")
        
        self.init_ui()
        self.restore_ui_state()
        self.apply_backup_timer_settings()  # Старт таймера згідно з налаштуваннями
        self.load_people()
        

    def prompt_startup_action(self):
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("Базу даних не знайдено")
        msg_box.setText("Попередню базу даних не знайдено або програма запускається вперше.\n\nЩо ви бажаєте зробити?")
        msg_box.setIcon(QMessageBox.Icon.Question)

        btn_open = msg_box.addButton("Відкрити існуючу", QMessageBox.ButtonRole.AcceptRole)
        btn_create = msg_box.addButton("Створити нову", QMessageBox.ButtonRole.ActionRole)
        btn_cancel = msg_box.addButton("Скасувати", QMessageBox.ButtonRole.RejectRole)

        msg_box.exec()

        if msg_box.clickedButton() == btn_open:
            self._open_database_startup()
        elif msg_box.clickedButton() == btn_create:
            self.prompt_create_new_database()

    def _open_database_startup(self):
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))

        file_path, _ = QFileDialog.getOpenFileName(
            self, "Обрати файл бази даних SQLite", base_dir, "Бази даних SQLite (*.db *.sqlite *.sqlite3);;Всі файли (*.*)"
        )
        if file_path:
            self.db_path = file_path
            self.settings.setValue("last_db_path", self.db_path)

    def prompt_create_new_database(self):
        def get_resource_path(relative_path):
            if hasattr(sys, '_MEIPASS'):
                return os.path.join(sys._MEIPASS, relative_path)
            return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

        blank_db_path = get_resource_path("_blank.db")
        exe_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__))

        if not os.path.exists(blank_db_path):
            QMessageBox.critical(self, "Помилка", f"Не знайдено файл-шаблон бази даних:\n{blank_db_path}\n\nНеможливо створити нову базу.")
            return

        QMessageBox.information(self, "Створення бази", "Зараз буде створено нову базу даних на основі шаблону. Будь ласка, вкажіть місце та назву для нового файлу.")

        default_path = os.path.join(exe_dir, "нова_база.db")
        file_path, _ = QFileDialog.getSaveFileName(self, "Зберегти нову базу даних як...", default_path, "Бази даних SQLite (*.db *.sqlite *.sqlite3);;Всі файли (*.*)")

        if file_path:
            try:
                shutil.copy2(blank_db_path, file_path)
                self.db_path = file_path
                self.settings.setValue("last_db_path", self.db_path)

                if hasattr(self, 'photo_label'):
                    self.selected_person_id = None
                    self.current_photo_id = None
                    self.photo_label.clear()
                    self.photo_label.setText("Немає фото")
                    self.load_people()
                    self.update_window_title()

                QMessageBox.information(self, "Успіх", f"Нову базу успішно створено та відкрито:\n{self.db_path}")
            except Exception as e:
                QMessageBox.critical(self, "Помилка", f"Не вдалося створити базу даних:\n{str(e)}")

    def open_database(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Обрати файл бази даних SQLite", os.path.dirname(os.path.abspath(self.db_path)), "Бази даних SQLite (*.db *.sqlite *.sqlite3);;Всі файли (*.*)"
        )
        if not file_path:
            return

        self.db_path = file_path
        self.settings.setValue("last_db_path", self.db_path)
        init_db(self.db_path)
        backup_database(self.db_path)
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

    def run_auto_detect_marriages(self):
        """Запускає аналіз бази даних та відкриває вікно з переліком кандидатур і чекбоксами."""
        from database import find_potential_marriages
        from dialogs import MarriageConfirmationDialog

        candidates = find_potential_marriages(self.db_path)
        if not candidates:
            QMessageBox.information(
                self, "Інформація", "Потенційних шлюбних пар за вказаними критеріями не знайдено."
            )
            return

        # Автоматичний бэкап перед масовим застосуванням
        self.backup_before_batch_if_needed()
    
        dlg = MarriageConfirmationDialog(self, candidates=candidates, db_path=self.db_path)
        dlg.exec()

        if dlg.processed_count > 0:
            self.load_people()
            if self.person_edit_dialog and self.person_edit_dialog.isVisible():
                self.person_edit_dialog.load_kinship_data()

    def run_auto_detect_children(self):
        """Запускає пошук дітей та відкриває діалогове вікно підтвердження змін."""
        from database import find_potential_children
        from dialogs import ChildrenConfirmationDialog

        candidates = find_potential_children(self.db_path)
        if not candidates:
            QMessageBox.information(
                self, "Інформація", "Потенційних дітей за вказаними критеріями не знайдено."
            )
            return

        # Автоматичний бэкап перед масовим застосуванням
        self.backup_before_batch_if_needed()
    
        dlg = ChildrenConfirmationDialog(self, candidates=candidates, db_path=self.db_path)
        dlg.exec()

        if dlg.processed_count > 0:
            self.load_people()
            if self.person_edit_dialog and self.person_edit_dialog.isVisible():
                self.person_edit_dialog.load_kinship_data()
    
    def run_extended_kinship_search(self):
        """Запускає аналіз розширених родинних зв'язків та відкриває вікно підтвердження."""
        from database import find_extended_kinship_candidates
        from dialogs import ExtendedKinshipConfirmationDialog

        candidates = find_extended_kinship_candidates(self.db_path)
        if not candidates:
            QMessageBox.information(
                self, "Інформація", "Потенційних розширених родинних зв'язків за вказаними критеріями не знайдено."
            )
            return

        # Автоматичний бэкап перед масовим застосуванням
        self.backup_before_batch_if_needed()
    
        dlg = ExtendedKinshipConfirmationDialog(self, candidates=candidates, db_path=self.db_path)
        dlg.exec()

        if dlg.processed_count > 0:
            self.load_people()
            if self.person_edit_dialog and self.person_edit_dialog.isVisible():
                self.person_edit_dialog.load_kinship_data()
    
    def closeEvent(self, event):
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

    def open_families_window(self):
        dlg = FamiliesWindow(self, db_path=self.db_path, pdf_font=self.pdf_font)
        dlg.exec()
        
    def open_list_editor(self, table_name, title):
        dlg = ListEditorDialog(self, db_path=self.db_path, table_name=table_name, window_title=title)
        dlg.exec()
        # Оновлюємо таблицю та списки після можливих змін класифікаторів
        self.load_people()
    
    def init_ui(self):
        self.update_window_title()
        self.resize(1150, 700)

        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&Файл")

        act_open_db = QAction("&Відкрити базу даних...", self)
        act_open_db.setShortcut("Ctrl+O")
        act_open_db.triggered.connect(self.open_database)
        file_menu.addAction(act_open_db)

        act_create_db = QAction("Створити &нову базу даних...", self)
        act_create_db.triggered.connect(self.prompt_create_new_database)
        file_menu.addAction(act_create_db)

        act_backup = QAction("Створити &резервну копію", self)
        act_backup.triggered.connect(lambda: backup_database(self.db_path))
        file_menu.addAction(act_backup)

        file_menu.addSeparator()

        act_export_pdf = QAction("&Експорт у PDF...", self)
        act_export_pdf.setShortcut("Ctrl+P")
        act_export_pdf.triggered.connect(self.export_to_pdf)
        file_menu.addAction(act_export_pdf)

        file_menu.addSeparator()

        act_settings = QAction("⚙️ &Налаштування...", self)
        act_settings.triggered.connect(self.open_settings_dialog)
        file_menu.addAction(act_settings)
        
        file_menu.addSeparator()

        act_exit = QAction("Ви&хід", self)
        act_exit.setShortcut("Ctrl+Q")
        act_exit.triggered.connect(self.close)
        file_menu.addAction(act_exit)
        
        
        person_menu = menu_bar.addMenu("&Громада")
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
        
        person_menu.addSeparator()
        act_families = QAction("Перелік &родин та сімей...", self)
        act_families.triggered.connect(self.open_families_window)
        person_menu.addAction(act_families)
        

        view_menu = menu_bar.addMenu("&Вигляд")
        act_columns = QAction("Налаштувати &колонки...", self)
        act_columns.triggered.connect(self.select_columns)
        view_menu.addAction(act_columns)
        
        # Меню "Довідники"
        ref_menu = menu_bar.addMenu("&Довідники")

        act_church_status = QAction("Церковний статус", self)
        act_church_status.triggered.connect(lambda: self.open_list_editor("list_church_status", "Церковні статуси"))
        ref_menu.addAction(act_church_status)

        act_fam_status = QAction("Сімейний стан", self)
        act_fam_status.triggered.connect(lambda: self.open_list_editor("list_family_status", "Сімейний стан"))
        ref_menu.addAction(act_fam_status)

        act_gender = QAction("Стать", self)
        act_gender.triggered.connect(lambda: self.open_list_editor("list_gender", "Довідник статі"))
        ref_menu.addAction(act_gender)

        ref_menu.addSeparator()

        act_event_type = QAction("Типи подій", self)
        act_event_type.triggered.connect(lambda: self.open_list_editor("list_event_type", "Типи подій"))
        ref_menu.addAction(act_event_type)

        act_group_status = QAction("Ролі у групах", self)
        act_group_status.triggered.connect(lambda: self.open_list_editor("list_group_status", "Ролі у групах"))
        ref_menu.addAction(act_group_status)

        act_group_type = QAction("Типи груп", self)
        act_group_type.triggered.connect(lambda: self.open_list_editor("list_group_type", "Типи груп"))
        ref_menu.addAction(act_group_type)
        
        act_kinship_type = QAction("Типи родинних зв'язків", self)
        act_kinship_type.triggered.connect(lambda: self.open_list_editor("list_kinship_types", "Типи родинних зв'язків"))
        ref_menu.addAction(act_kinship_type)
        
        
        # Меню "Сервіс"
        service_menu = menu_bar.addMenu("&Сервіс")

        
        act_detect_marriages = QAction("Автоматично встановити &шлюбні зв'язки", self)
        act_detect_marriages.triggered.connect(self.run_auto_detect_marriages)
        service_menu.addAction(act_detect_marriages)

        act_detect_children = QAction("Автоматично встановити &зв'язки з дітьми", self)
        act_detect_children.triggered.connect(self.run_auto_detect_children)
        service_menu.addAction(act_detect_children)

        act_detect_ext_kinship = QAction("Автоматично шукати &розширені родинні зв'язки", self)
        act_detect_ext_kinship.triggered.connect(self.run_extended_kinship_search)
        service_menu.addAction(act_detect_ext_kinship)
        
        # ========
        
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)

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

        filter_box = QFrame()
        filter_box.setFrameShape(QFrame.Shape.StyledPanel)
        filter_box.setStyleSheet("QFrame { background-color: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 4px; }")
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

        self.splitter = QSplitter(Qt.Orientation.Horizontal)

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

        self.status_label = QLabel("Готово")
        self.statusBar().addWidget(self.status_label)
        
        

        # Створюємо гарячі клавіші з контекстом ApplicationShortcut
        shortcut_up = QShortcut(QKeySequence("Ctrl+Up"), self)
        shortcut_up.setContext(Qt.ShortcutContext.ApplicationShortcut)
        shortcut_up.activated.connect(self.select_prev_person)

        shortcut_down = QShortcut(QKeySequence("Ctrl+Down"), self)
        shortcut_down.setContext(Qt.ShortcutContext.ApplicationShortcut)
        shortcut_down.activated.connect(self.select_next_person)
        
        # Відкриття редагування при натисканні Enter або Return на вибраному рядку таблиці
        shortcut_enter = QShortcut(QKeySequence(Qt.Key.Key_Return), self.table)
        shortcut_enter.activated.connect(self.edit_person)

        shortcut_enter_num = QShortcut(QKeySequence(Qt.Key.Key_Enter), self.table)
        shortcut_enter_num.activated.connect(self.edit_person)
        
        # Встановлюємо фокус безпосередньо на таблицю
        self.table.setFocus()
        

    def select_person_by_id(self, person_id: int):
        """Шукає та виділяє запис у головній таблиці за його ID."""
        for row in range(self.table.rowCount()):
            item_id = self.table.item(row, 0)
            if item_id and int(item_id.text()) == person_id:
                self.table.selectRow(row)
                self.table.scrollToItem(item_id, QTableWidget.ScrollHint.EnsureVisible)
                break
    
    def select_prev_person(self):
        curr_row = self.table.currentRow()
        if curr_row > 0:
            self.table.selectRow(curr_row - 1)

    def select_next_person(self):
        curr_row = self.table.currentRow()
        if curr_row < self.table.rowCount() - 1:
            self.table.selectRow(curr_row + 1)
            
    def apply_column_visibility(self):
        for col_idx, (col_id, _) in enumerate(ALL_COLUMNS):
            is_visible = col_id in self.visible_columns
            self.table.setColumnHidden(col_idx, not is_visible)

    def select_columns(self):
        dlg = ColumnSelectionDialog(self, current_visible=self.visible_columns)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.visible_columns = dlg.get_selected_columns()
            self.settings.setValue("visible_columns", self.visible_columns)
            self.apply_column_visibility()

    def open_status_filter(self):
        dlg = ModalStatusFilterDialog(self, db_path=self.db_path, initial_state=self.status_filter_state)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.status_filter_state = dlg.get_filter_state()
            self.settings.setValue("status_filter_state", json.dumps(self.status_filter_state))
            self.load_people()

    def _get_filter_descriptions(self):
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
        target_person_id = self.selected_person_id

        self.table.blockSignals(True)
        self.table.setRowCount(0)

        gender_map, fam_map, church_map = {}, {}, {}
        with get_db_connection(self.db_path) as conn:
            cur = conn.cursor()
            try:
                cur.execute("SELECT id, list_name FROM list_gender")
                gender_map = dict(cur.fetchall())
                cur.execute("SELECT id, list_name FROM list_family_status")
                fam_map = dict(cur.fetchall())
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

        self.btn_filter_status.setStyleSheet("font-weight: bold; background-color: #DBEAFE; color: #1E40AF;" if has_status_filters else "")
        self.btn_this_week.setStyleSheet("font-weight: bold; background-color: #FEF3C7; color: #92400E;" if self.bd_this_week_active else "")

        if filter_descs:
            self.filter_info_label.setText("🔍 <b>Активні фільтри:</b> " + " | ".join(filter_descs))
        else:
            self.filter_info_label.setText("<span style='color: #64748B;'>Фільтри не застосовано (показано всі записи)</span>")

        plain_filter_summary = " [Фільтр активний]" if filter_descs else ""
        self.status_label.setText(f"БД: {os.path.basename(self.db_path)} | Записів знайдено: {len(rows)}{plain_filter_summary}")

    def add_person(self):
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
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    data["name"], data["address"], data["Home_phone"], data["Work_phone"],
                    data["Mobile_Phone"], data["Date_of_Birth"], data["gender"], data["fam_status"],
                    data["children"], data["notes"], data["church_status"], data["Date_of_Bapt"],
                    data["Mobile_Phone_a"], data["email"], data["send_bd_sms"]
                ))
                new_id = cur.lastrowid
                for ev in data.get("events", []):
                    cur.execute("""
                        INSERT INTO p_events (people_id, eventdate, eventtype, descr)
                        VALUES (?, ?, ?, ?)
                    """, (new_id, ev["eventdate"], ev["eventtype"], ev["descr"]))
                conn.commit()

            self.selected_person_id = new_id
            self.load_people()

    def edit_person(self):
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

        # Якщо вікно вже відкрите — оновлюємо дані у ньому
        if self.person_edit_dialog is not None and self.person_edit_dialog.isVisible():
            self.person_edit_dialog.set_person_data(person_dict)
            self.person_edit_dialog.raise_()
            self.person_edit_dialog.activateWindow()
            return

        # Створюємо немодальне вікно
        self.person_edit_dialog = PersonDialog(self, person_data=person_dict, db_path=self.db_path)
        self.person_edit_dialog.setModal(False)
        
        def save_and_refresh():
            data = self.person_edit_dialog.get_data()
            person_id = self.person_edit_dialog.person_data.get("id") if self.person_edit_dialog.person_data else None
            if person_id:
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
                        data["Mobile_Phone_a"], data["email"], data["send_bd_sms"], person_id
                    ))

                    for ev_id in data.get("events_to_delete", []):
                        cur.execute("DELETE FROM p_events WHERE id = ?", (ev_id,))

                    for ev in data.get("events", []):
                        if ev["id"]:
                            cur.execute("UPDATE p_events SET eventdate = ?, eventtype = ?, descr = ? WHERE id = ?",
                                        (ev["eventdate"], ev["eventtype"], ev["descr"], ev["id"]))
                        else:
                            cur.execute("INSERT INTO p_events (people_id, eventdate, eventtype, descr) VALUES (?, ?, ?, ?)",
                                        (person_id, ev["eventdate"], ev["eventtype"], ev["descr"]))

                    conn.commit()
                self.load_people()

        self.person_edit_dialog.accepted.connect(save_and_refresh)
        self.person_edit_dialog.show()

    def delete_person(self):
        if not self.selected_person_id:
            QMessageBox.warning(self, "Увага", "Оберіть запис для видалення!")
            return

        row = self.table.currentRow()
        name = self.table.item(row, 1).text() if row >= 0 else ""

        reply = QMessageBox.question(
            self, "Підтвердження видалення",
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
        self.bd_this_week_active = not self.bd_this_week_active
        self.load_people()

    def reset_filter(self):
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

        # Якщо вікно редагування відкрите — підтягуємо обрану людину
        if self.person_edit_dialog is not None and self.person_edit_dialog.isVisible():
            with get_db_connection(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                cur.execute("SELECT * FROM people WHERE id = ?", (self.selected_person_id,))
                row = cur.fetchone()
                if row:
                    self.person_edit_dialog.set_person_data(dict(row))

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

        file_path, _ = QFileDialog.getOpenFileName(self, "Оберіть фото", "", "Зображення (*.jpg *.jpeg *.png *.bmp)")
        if not file_path:
            return

        try:
            img = Image.open(file_path).convert("RGB")
            img.thumbnail((600, 800), Image.Resampling.LANCZOS)

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

        file_path, _ = QFileDialog.getSaveFileName(self, "Зберегти фото", f"person_{self.selected_person_id}.jpg", "JPEG фото (*.jpg)")
        if not file_path:
            return

        try:
            with open(file_path, "wb") as f:
                f.write(res[0])
            QMessageBox.information(self, "Успіх", f"Фото збережено у:\n{file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося зберегти фото:\n{str(e)}")

    def _get_records_for_export(self, limit=None):
        records = []
        total_rows = self.table.rowCount()
        count = min(total_rows, limit) if limit else total_rows

        with get_db_connection(self.db_path) as conn:
            cur = conn.cursor()
            for row_idx in range(count):
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

                records.append({
                    "id": p_row[0],
                    "name": p_row[1] or "",
                    "address": p_row[2] or "—",
                    "dob": p_row[3] or "—",
                    "bapt": p_row[4] or "—",
                    "phones": phone_str,
                    "compact_phones": ", ".join(nobr_phones) if nobr_phones else "—",
                    "children": p_row[9] if p_row[9] is not None else 0,
                    "church_status": p_row[10] or "—",
                    "fam_status": p_row[11] or "—",
                    "email": p_row[12] or "",
                    "photo_bytes": photo_bytes
                })
        return records

    # 2. Нові методи для керування резервуванням:
    def apply_backup_timer_settings(self):
        """Оновлює інтервал та стан таймера автобэкапу."""
        auto_enabled = self.settings.value("auto_backup_enabled", True, type=bool)
        interval_min = self.settings.value("auto_backup_interval", 15, type=int)

        if auto_enabled and interval_min > 0:
            interval_ms = interval_min * 60 * 1000
            self.backup_timer.start(interval_ms)
        else:
            self.backup_timer.stop()

    def run_periodic_backup(self):
        """Автоматичний бэкап за таймером."""
        max_files = self.settings.value("max_backup_files", 20, type=int)
        backup_database(self.db_path, prefix="auto", max_files=max_files)
        self.statusBar().showMessage("Створено автокопію бази даних", 3000)

    def backup_before_batch_if_needed(self):
        """Створює резервну копію безпосередньо перед пакетними операціями."""
        if self.settings.value("backup_before_batch", True, type=bool):
            max_files = self.settings.value("max_backup_files", 20, type=int)
            backup_database(self.db_path, prefix="before_batch", max_files=max_files)

    def open_settings_dialog(self):
        """Відкриває вікно налаштувань програми."""
        dlg = SettingsDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self.apply_backup_timer_settings()
            QMessageBox.information(self, "Успіх", "Налаштування збережено.")
    
    def export_to_pdf(self):
        style_dlg = PdfExportStyleDialog(
            self,
            current_layout=self.last_pdf_layout,
            current_style=self.last_pdf_style,
            current_card_h=self.last_phone_card_height,
            app_instance=self
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

        cur_date_str = datetime.now().strftime("%Y-%m-%d")
        db_base_name = os.path.splitext(os.path.basename(self.db_path))[0]
        layout_name_slug = {"a4_cards": "A4", "phone": "Phone_A5", "compact": "Compact"}.get(chosen_layout_key, "Report")

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

        save_path, _ = QFileDialog.getSaveFileName(self, "Зберегти PDF-звіт", default_save_path, "PDF файли (*.pdf)")
        if not save_path:
            return

        self.settings.setValue("last_pdf_export_dir", os.path.dirname(os.path.abspath(save_path)))

        progress = QProgressDialog("Створення PDF-звіту...", "Скасувати", 0, 100, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(150)
        progress.setValue(20)
        QApplication.processEvents()

        try:
            records = self._get_records_for_export()
            progress.setValue(50)
            QApplication.processEvents()

            filter_descs = self._get_filter_descriptions()
            filter_parts = []
            if filter_descs:
                filter_parts.append("<b>Фільтри:</b> " + " | ".join(filter_descs))
            filter_parts.append(f"<b>Всього записів:</b> {len(records)}")
            filter_text = " | ".join(filter_parts)

            build_pdf_document(
                save_path,
                layout_key=chosen_layout_key,
                style_key=chosen_style_key,
                records=records,
                filter_text=filter_text,
                font_name=self.pdf_font,
                phone_card_height=phone_card_height
            )
            progress.setValue(100)
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
