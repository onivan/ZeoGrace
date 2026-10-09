import io
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from PIL import Image

from PyQt6.QtCore import Qt, QSettings
from PyQt6.QtGui import QPixmap, QAction
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLineEdit, QLabel,
    QFileDialog, QMessageBox, QHeaderView, QSplitter,
    QFrame, QProgressDialog
)

from reportlab.lib.pagesizes import A4, A5
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

from config import ALL_COLUMNS, DEFAULT_VISIBLE_COLUMNS, PDF_STYLES, PDF_LAYOUTS
from utils import ukrainian_sort_key, format_phone, register_unicode_font, get_proportional_image
from database import get_db_connection
from pdf_components import NumberedCanvas, PdfExportStyleDialog
from dialogs import ColumnSelectionDialog, ModalStatusFilterDialog, EventDialog, PersonDialog


class ZeoGraceApp(QMainWindow):
    def __init__(self, db_path=None):
        super().__init__()
        self.settings = QSettings("ZeoGrace", "ZeoGraceApp")

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

        self.init_db()
        self.backup_database()
        self.init_ui()
        self.restore_ui_state()
        self.load_people()

    def prompt_startup_action(self):
        """
        Запитує користувача при першому запуску (або якщо базу не знайдено),
        чи він хоче відкрити існуючу базу, чи створити нову.
        """
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
        """Допоміжний метод для відкриття БД до ініціалізації UI."""
        if getattr(sys, 'frozen', False):
            base_dir = os.path.dirname(sys.executable)
        else:
            base_dir = os.path.dirname(os.path.abspath(__file__))

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Обрати файл бази даних SQLite",
            base_dir,
            "Бази даних SQLite (*.db *.sqlite *.sqlite3);;Всі файли (*.*)"
        )

        if file_path:
            self.db_path = file_path
            self.settings.setValue("last_db_path", self.db_path)

    def prompt_create_new_database(self):
        """
        Пропонує користувачеві вибрати місце та ім'я для нової бази даних.
        Створює нову базу шляхом копіювання файлу-шаблону _blank.db.
        """
        def get_resource_path(relative_path):
            if hasattr(sys, '_MEIPASS'):
                return os.path.join(sys._MEIPASS, relative_path)
            return os.path.join(os.path.dirname(os.path.abspath(__file__)), relative_path)

        blank_db_path = get_resource_path("_blank.db")

        if getattr(sys, 'frozen', False):
            exe_dir = os.path.dirname(sys.executable)
        else:
            exe_dir = os.path.dirname(os.path.abspath(__file__))

        if not os.path.exists(blank_db_path):
            QMessageBox.critical(
                self,
                "Помилка",
                f"Не знайдено файл-шаблон бази даних:\n{blank_db_path}\n\nНеможливо створити нову базу."
            )
            return

        QMessageBox.information(
            self,
            "Створення бази",
            "Зараз буде створено нову базу даних на основі шаблону. Будь ласка, вкажіть місце та назву для нового файлу."
        )

        default_path = os.path.join(exe_dir, "нова_база.db")

        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Зберегти нову базу даних як...",
            default_path,
            "Бази даних SQLite (*.db *.sqlite *.sqlite3);;Всі файли (*.*)"
        )

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

    # --- База даних і бекап ---

    def init_db(self, is_new=False):
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
                    id        INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
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

        view_menu = menu_bar.addMenu("&Вигляд")
        act_columns = QAction("Налаштувати &колонки...", self)
        act_columns.triggered.connect(self.select_columns)
        view_menu.addAction(act_columns)

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
                new_id = cur.lastrowid

                # Збереження доданих подій
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

                # Видалення позначених подій
                for ev_id in data.get("events_to_delete", []):
                    cur.execute("DELETE FROM p_events WHERE id = ?", (ev_id,))

                # Оновлення або вставка подій
                for ev in data.get("events", []):
                    if ev["id"]:
                        cur.execute("""
                            UPDATE p_events
                            SET eventdate = ?, eventtype = ?, descr = ?
                            WHERE id = ?
                        """, (ev["eventdate"], ev["eventtype"], ev["descr"], ev["id"]))
                    else:
                        cur.execute("""
                            INSERT INTO p_events (people_id, eventdate, eventtype, descr)
                            VALUES (?, ?, ?, ?)
                        """, (self.selected_person_id, ev["eventdate"], ev["eventtype"], ev["descr"]))

                conn.commit()

            self.load_people()

    def delete_person(self):
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

    # --- Робота із зображеннями ---

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

    # --- Генерація PDF ---

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
        return records

    def build_pdf_document(self, output_dest, layout_key, style_key, phone_card_height=150, records=None, first_page_only=False):
        style_cfg = PDF_STYLES.get(style_key, PDF_STYLES["slate"])

        if records is None:
            limit = 6 if layout_key == "a4_cards" else (3 if layout_key == "phone" else 20)
            records = self._get_records_for_export(limit=limit if first_page_only else None)

        total_records_count = len(records)
        styles = getSampleStyleSheet()

        # Фіксований формат А5 для варіанта "Для телефону", А4 для інших
        if layout_key == "phone":
            page_size = A5
            left_margin = right_margin = 16
            top_margin = 16
            bottomMargin = 18
            doc_width = page_size[0] - (left_margin + right_margin)
        else:
            page_size = A4
            left_margin = right_margin = 25
            top_margin = 25
            bottomMargin = 25
            doc_width = 545

        doc = SimpleDocTemplate(
            output_dest,
            pagesize=page_size,
            leftMargin=left_margin,
            rightMargin=right_margin,
            topMargin=top_margin,
            bottomMargin=bottomMargin
        )

        elements = []

        title_font_size = 14 if layout_key == "phone" else 15
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
        filter_parts.append(f"<b>Всього записів:</b> {self.table.rowCount()}")
        filter_full_text = " | ".join(filter_parts)

        filter_style = ParagraphStyle(
            name="ReportFilter",
            parent=styles["Normal"],
            fontName=self.pdf_font,
            fontSize=6.8 if layout_key == "phone" else 7.5,
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

        # 1. Варіант "А4"
        if layout_key == "a4_cards":
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

        # 2. Варіант "Для телефону" (фіксований формат А5, ширина фото від висоти)
        elif layout_key == "phone":
            card_w = doc_width
            card_photo_max_h = max(60, phone_card_height - 14)
            card_photo_max_w = min(card_w * 0.48, card_photo_max_h * 0.78)
            info_w = card_w - card_photo_max_w - 8

            font_scale = max(0.85, min(1.30, phone_card_height / 150.0))
            base_font_sz = 7.0 * font_scale
            title_font_sz = 8.6 * font_scale

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
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                    ("LEFTPADDING", (0, 0), (-1, -1), 4),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ]))

                elements.append(card_table)
                elements.append(Spacer(1, 4))

                if idx % 3 == 0 and idx < len(records):
                    elements.append(PageBreak())

        # 3. Варіант "Компактний"
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

        def canvas_factory(*args, **kwargs):
            return NumberedCanvas(*args, font_name=self.pdf_font, **kwargs)

        doc.build(elements, canvasmaker=canvas_factory)

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
        layout_name_slug = {
            "a4_cards": "A4",
            "phone": "Phone_A5",
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

        progress = QProgressDialog("Створення PDF-звіту...", "Скасувати", 0, 100, self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(150)
        progress.setValue(20)
        QApplication.processEvents()

        try:
            records = self._get_records_for_export()
            progress.setValue(50)
            QApplication.processEvents()

            self.build_pdf_document(
                save_path,
                layout_key=chosen_layout_key,
                style_key=chosen_style_key,
                phone_card_height=phone_card_height,
                records=records,
                first_page_only=False
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
