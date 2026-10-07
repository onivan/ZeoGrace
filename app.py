import io
import os
import shutil
import sqlite3
import sys
from datetime import datetime
from PIL import Image

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtGui import QPixmap, QAction
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QLineEdit, QLabel,
    QFileDialog, QMessageBox, QHeaderView, QSplitter, QDialog,
    QFormLayout, QTextEdit, QDateEdit, QDialogButtonBox
)

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


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


class NumberedCanvas(canvas.Canvas):
    """Канвас із нумерацією сторінок (X із Y)."""
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
        self.setFont(self.font_name, 9)
        self.drawRightString(200 * 2.834, 15 * 2.834, f"Сторінка {self._pageNumber} з {page_count}")


class PersonDialog(QDialog):
    """Діалогове вікно для додавання або редагування запису парафіянина."""
    def __init__(self, parent=None, person_data=None):
        super().__init__(parent)
        self.person_data = person_data
        self.setWindowTitle("Редагувати запис" if person_data else "Додати запис")
        self.resize(450, 420)
        self.init_ui()

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

        self.edit_phone = QLineEdit()
        self.edit_email = QLineEdit()
        self.edit_notes = QTextEdit()
        self.edit_notes.setMaximumHeight(80)

        form_layout.addRow("П.І.Б. (*):", self.edit_name)
        form_layout.addRow("Адреса:", self.edit_address)
        form_layout.addRow("Дата народження:", dob_box)
        form_layout.addRow("Дата хрещення:", self.edit_bapt)
        form_layout.addRow("Мобільний телефон:", self.edit_phone)
        form_layout.addRow("Email:", self.edit_email)
        form_layout.addRow("Примітки:", self.edit_notes)

        layout.addLayout(form_layout)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept_data)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

        if self.person_data:
            self.edit_name.setText(self.person_data.get("name", ""))
            self.edit_address.setText(self.person_data.get("address", ""))
            dob_val = self.person_data.get("Date_of_Birth", "")
            if dob_val:
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

            self.edit_bapt.setText(self.person_data.get("Date_of_Bapt", "") or "")
            self.edit_phone.setText(str(self.person_data.get("Mobile_Phone", "") or ""))
            self.edit_email.setText(self.person_data.get("email", "") or "")
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
            "Date_of_Birth": dob_str,
            "Date_of_Bapt": self.edit_bapt.text().strip(),
            "Mobile_Phone": self.edit_phone.text().strip(),
            "email": self.edit_email.text().strip(),
            "notes": self.edit_notes.toPlainText().strip()
        }


class ZeoGraceApp(QMainWindow):
    def __init__(self, db_path=None):
        super().__init__()
        if db_path is None:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            self.db_path = os.path.join(base_dir, "zeograce.db")
        else:
            self.db_path = db_path

        self.selected_person_id = None
        self.current_photo_id = None
        self.pdf_font = register_unicode_font()

        self.init_db()
        self.backup_database()
        self.init_ui()
        self.load_people()

    # --- База даних і бекап ---

    def init_db(self):
        """Ініціалізація структури БД."""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute("""
                CREATE TABLE IF NOT EXISTS people (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    address TEXT,
                    Date_of_Birth TEXT,
                    Date_of_Bapt TEXT,
                    Mobile_Phone TEXT,
                    email TEXT,
                    notes TEXT
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS photos (
                    photo_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    people_id INTEGER,
                    photo BLOB,
                    descr TEXT,
                    FOREIGN KEY (people_id) REFERENCES people(id) ON DELETE CASCADE
                )
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
        self.search_edit.textChanged.connect(self.load_people)
        top_bar.addWidget(self.search_edit)

        btn_this_week = QPushButton("ДН цього тижня")
        btn_this_week.clicked.connect(self.filter_bd_this_week)
        top_bar.addWidget(btn_this_week)

        btn_reset = QPushButton("Скинути")
        btn_reset.clicked.connect(self.reset_filter)
        top_bar.addWidget(btn_reset)

        btn_export = QPushButton("Експорт PDF")
        btn_export.clicked.connect(self.export_to_pdf)
        top_bar.addWidget(btn_export)

        main_layout.addLayout(top_bar)

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
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Таблиця парафіян
        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels(["ID", "Ім'я", "Адреса", "Дата нар.", "Хрещення", "Мобільний", "Email"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.itemSelectionChanged.connect(self.on_person_selected)
        self.table.itemDoubleClicked.connect(lambda: self.edit_person())
        splitter.addWidget(self.table)

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
        splitter.addWidget(photo_panel)

        splitter.setSizes([800, 350])
        main_layout.addWidget(splitter)

        # Статус-бар
        self.status_label = QLabel("Готово")
        self.statusBar().addWidget(self.status_label)

    # --- Логіка CRUD для people ---

    def load_people(self, query_filter=None, params=None):
        """Завантаження та фільтрація списку людей."""
        self.table.setRowCount(0)
        sql = "SELECT id, name, address, Date_of_Birth, Date_of_Bapt, Mobile_Phone, email FROM people"
        sql_params = []

        search_text = self.search_edit.text().strip()
        conditions = []

        if search_text:
            conditions.append("(name LIKE ? OR address LIKE ? OR Mobile_Phone LIKE ?)")
            p = f"%{search_text}%"
            sql_params.extend([p, p, p])

        if query_filter:
            conditions.append(query_filter)
            if params:
                sql_params.extend(params)

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        sql += " ORDER BY name ASC"

        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute(sql, sql_params)
            rows = cur.fetchall()

        self.table.setRowCount(len(rows))
        for row_idx, row in enumerate(rows):
            for col_idx, val in enumerate(row):
                if col_idx == 5:
                    val = format_phone(val)
                item = QTableWidgetItem(str(val) if val is not None else "")
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(row_idx, col_idx, item)

        self.status_label.setText(f"БД: {os.path.basename(self.db_path)} | Записів знайдено: {len(rows)}")

    def add_person(self):
        """Створення нового запису (Create)."""
        dlg = PersonDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("""
                    INSERT INTO people (name, address, Date_of_Birth, Date_of_Bapt, Mobile_Phone, email, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    data["name"], data["address"], data["Date_of_Birth"],
                    data["Date_of_Bapt"], data["Mobile_Phone"], data["email"], data["notes"]
                ))
                conn.commit()
                new_id = cur.lastrowid

            self.load_people()
            # Вибір щойно створеного
            for r in range(self.table.rowCount()):
                if self.table.item(r, 0).text() == str(new_id):
                    self.table.selectRow(r)
                    break

    def edit_person(self):
        """Редагування вибраного запису (Update)."""
        if not self.selected_person_id:
            QMessageBox.warning(self, "Увага", "Оберіть запис для редагування!")
            return

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.cursor()
            cur.execute("SELECT * FROM people WHERE id = ?", (self.selected_person_id,))
            row = cur.fetchone()

        if not row:
            return

        person_dict = dict(row)
        dlg = PersonDialog(self, person_data=person_dict)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("""
                    UPDATE people
                    SET name = ?, address = ?, Date_of_Birth = ?, Date_of_Bapt = ?,
                        Mobile_Phone = ?, email = ?, notes = ?
                    WHERE id = ?
                """, (
                    data["name"], data["address"], data["Date_of_Birth"],
                    data["Date_of_Bapt"], data["Mobile_Phone"], data["email"],
                    data["notes"], self.selected_person_id
                ))
                conn.commit()

            curr_id = self.selected_person_id
            self.load_people()
            for r in range(self.table.rowCount()):
                if self.table.item(r, 0).text() == str(curr_id):
                    self.table.selectRow(r)
                    break

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
            "Усі пов'язані фотографії також буде видалено.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("PRAGMA foreign_keys = ON")
                cur.execute("DELETE FROM photos WHERE people_id = ?", (self.selected_person_id,))
                cur.execute("DELETE FROM people WHERE id = ?", (self.selected_person_id,))
                conn.commit()

            self.selected_person_id = None
            self.current_photo_id = None
            self.photo_label.clear()
            self.photo_label.setText("Немає фото")
            self.load_people()

    def filter_bd_this_week(self):
        """Фільтр днів народження поточного тижня."""
        condition = "strftime('%W', Date_of_Birth) = strftime('%W', 'now')"
        self.load_people(query_filter=condition)

    def reset_filter(self):
        self.search_edit.clear()
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
        self.display_photo(self.selected_person_id)

    # --- Робота із зображеннями (CRUD для photos) ---

    def display_photo(self, people_id):
        with sqlite3.connect(self.db_path) as conn:
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

            with sqlite3.connect(self.db_path) as conn:
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
            with sqlite3.connect(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM photos WHERE photo_id = ?", (self.current_photo_id,))
                conn.commit()

            self.display_photo(self.selected_person_id)

    def save_photo_as(self):
        if not self.selected_person_id:
            return

        with sqlite3.connect(self.db_path) as conn:
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
        save_path, _ = QFileDialog.getSaveFileName(self, "Зберегти PDF-звіт", "report.pdf", "PDF файли (*.pdf)")
        if not save_path:
            return

        doc = SimpleDocTemplate(
            save_path,
            pagesize=A4,
            leftMargin=30,
            rightMargin=30,
            topMargin=30,
            bottomMargin=35
        )

        elements = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            name="ReportTitle",
            parent=styles["Heading1"],
            fontName=self.pdf_font,
            fontSize=16,
            leading=20,
            spaceAfter=14,
            alignment=1
        )
        body_style = ParagraphStyle(
            name="ReportCell",
            parent=styles["Normal"],
            fontName=self.pdf_font,
            fontSize=8,
            leading=10
        )
        header_style = ParagraphStyle(
            name="ReportHeaderCell",
            parent=body_style,
            textColor=colors.white
        )

        elements.append(Paragraph("Звіт списку громади", title_style))

        headers = ["Фото", "Ім'я", "Адреса", "Дата нар.", "Мобільний", "Email"]
        table_data = [[Paragraph(h, header_style) for h in headers]]

        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            for row_idx in range(self.table.rowCount()):
                p_id = int(self.table.item(row_idx, 0).text())
                name = self.table.item(row_idx, 1).text()
                address = self.table.item(row_idx, 2).text()
                dob = self.table.item(row_idx, 3).text()
                phone = self.table.item(row_idx, 5).text()
                email = self.table.item(row_idx, 6).text()

                cur.execute("SELECT photo FROM photos WHERE people_id = ? ORDER BY photo_id DESC LIMIT 1", (p_id,))
                photo_row = cur.fetchone()

                img_flowable = ""
                if photo_row and photo_row[0]:
                    img_stream = io.BytesIO(photo_row[0])
                    img_flowable = RLImage(img_stream, width=35, height=45)

                table_data.append([
                    img_flowable,
                    Paragraph(name, body_style),
                    Paragraph(address, body_style),
                    Paragraph(dob, body_style),
                    Paragraph(phone, body_style),
                    Paragraph(email, body_style)
                ])

        col_widths = [45, 125, 135, 60, 85, 85]
        t = Table(table_data, colWidths=col_widths, repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#334155")),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
        ]))

        elements.append(t)

        def canvas_factory(*args, **kwargs):
            return NumberedCanvas(*args, font_name=self.pdf_font, **kwargs)

        try:
            doc.build(elements, canvasmaker=canvas_factory)
            QMessageBox.information(self, "Успіх", f"Звіт успішно збережено:\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося створити PDF:\n{str(e)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ZeoGraceApp()
    window.show()
    sys.exit(app.exec())
