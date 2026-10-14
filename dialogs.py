import os
from collections import deque
from datetime import datetime

from PyQt6.QtCore import Qt, QDate, QSettings
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QDialogButtonBox, QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QFormLayout, QDateEdit, QCheckBox, QLineEdit, QComboBox,
    QSpinBox, QTextEdit, QMessageBox, QTabWidget, QWidget, QInputDialog,
    QLabel, QTreeWidget, QTreeWidgetItem, QFileDialog, QProgressDialog, QApplication
)

from config import ALL_COLUMNS, DEFAULT_VISIBLE_COLUMNS
from database import get_db_connection
from utils import format_phone, ukrainian_sort_key


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


class ModalStatusFilterDialog(QDialog):
    """Діалогове вікно розширеного фільтра за статусами, групами та подіями."""
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


class EventDialog(QDialog):
    """Діалогове вікно для додавання або редагування події."""
    def __init__(self, parent=None, db_path=None, event_data=None):
        super().__init__(parent)
        self.db_path = db_path
        self.event_data = event_data
        self.setWindowTitle("Редагувати подію" if event_data else "Додати подію")
        self.resize(400, 200)
        self.init_ui()

    def init_ui(self):
        layout = QFormLayout(self)

        self.edit_date = QDateEdit()
        self.edit_date.setCalendarPopup(True)
        self.edit_date.setDisplayFormat("yyyy-MM-dd")
        self.edit_date.setDate(QDate.currentDate())

        self.combo_type = QComboBox()
        if self.db_path and os.path.exists(self.db_path):
            try:
                with get_db_connection(self.db_path) as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT id, list_name FROM list_event_type ORDER BY id ASC")
                    for eid, ename in cur.fetchall():
                        self.combo_type.addItem(ename, eid)
            except Exception:
                pass

        self.edit_descr = QLineEdit()

        layout.addRow("Дата події:", self.edit_date)
        layout.addRow("Тип події:", self.combo_type)
        layout.addRow("Опис:", self.edit_descr)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if self.event_data:
            qdate = QDate.fromString(str(self.event_data.get("eventdate", ""))[:10], "yyyy-MM-dd")
            if qdate.isValid():
                self.edit_date.setDate(qdate)

            idx = self.combo_type.findData(self.event_data.get("eventtype", 0))
            if idx >= 0:
                self.combo_type.setCurrentIndex(idx)

            self.edit_descr.setText(str(self.event_data.get("descr", "") or ""))

    def get_data(self):
        return {
            "id": self.event_data.get("id") if self.event_data else None,
            "eventdate": self.edit_date.date().toString("yyyy-MM-dd"),
            "eventtype": self.combo_type.currentData() or 0,
            "eventtype_name": self.combo_type.currentText(),
            "descr": self.edit_descr.text().strip()
        }


class PersonDialog(QDialog):
    """Діалогове вікно для додавання або редагування запису парафіянина."""
    def __init__(self, parent=None, person_data=None, db_path=None):
        super().__init__(parent)
        self.person_data = person_data
        self.db_path = db_path
        self.events_to_delete = []
        self.setWindowTitle("Редагувати запис" if person_data else "Додати запис")
        self.resize(600, 650)
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
        main_layout = QVBoxLayout(self)

        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        tab_main = QWidget()
        form_layout = QFormLayout(tab_main)

        self.edit_name = QLineEdit()
        self.edit_address = QLineEdit()

        # Дата народження
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

        # Дата хрещення
        #self.edit_bapt = QLineEdit()
        #self.edit_bapt.setPlaceholderText("РРРР-ММ-ДД")
        # --
        self.edit_bapt = QDateEdit()
        self.edit_bapt.setCalendarPopup(True)
        self.edit_bapt.setDisplayFormat("yyyy-MM-dd")

        self.edit_bapt_empty = QPushButton("Очистити дату")
        self.edit_bapt_empty.setFixedWidth(120)
        self.has_bapt = False

        bapt_box = QHBoxLayout()
        bapt_box.addWidget(self.edit_bapt)
        bapt_box.addWidget(self.edit_bapt_empty)

        def clear_bapt():
            self.has_bapt = False
            self.edit_bapt.setDate(QDate(2000, 1, 1))
            self.edit_bapt.setStyleSheet("color: gray;")

        def set_bapt():
            self.has_bapt = True
            self.edit_bapt.setStyleSheet("")

        self.edit_bapt.dateChanged.connect(set_bapt)
        self.edit_bapt_empty.clicked.connect(clear_bapt)
        
        
        # Стать
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
        form_layout.addRow("Дата хрещення:", bapt_box)
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

        self.tabs.addTab(tab_main, "Основні дані")

        tab_events = QWidget()
        events_layout = QVBoxLayout(tab_events)

        self.table_events = QTableWidget()
        self.table_events.setColumnCount(4)
        self.table_events.setHorizontalHeaderLabels(["ID", "Дата", "Тип події", "Опис"])
        self.table_events.setColumnHidden(0, True)
        self.table_events.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table_events.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_events.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table_events.itemDoubleClicked.connect(self.edit_event)
        events_layout.addWidget(self.table_events)

        btn_events_layout = QHBoxLayout()
        btn_add_event = QPushButton("Додати подію")
        btn_edit_event = QPushButton("Редагувати подію")
        btn_del_event = QPushButton("Видалити подію")

        btn_add_event.clicked.connect(self.add_event)
        btn_edit_event.clicked.connect(self.edit_event)
        btn_del_event.clicked.connect(self.delete_event)

        btn_events_layout.addWidget(btn_add_event)
        btn_events_layout.addWidget(btn_edit_event)
        btn_events_layout.addWidget(btn_del_event)
        events_layout.addLayout(btn_events_layout)

        self.tabs.addTab(tab_events, "Події")

        tab_kinship = QWidget()
        kin_layout = QVBoxLayout(tab_kinship)

        self.table_kinship = QTableWidget()
        self.table_kinship.setColumnCount(4)
        self.table_kinship.setHorizontalHeaderLabels(["ID Особи", "П.І.Б. родича", "Тип зв'язку", "Примітка"])
        self.table_kinship.setColumnHidden(0, True)

        self.table_kinship.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table_kinship.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table_kinship.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)

        settings = QSettings("ZeoGrace", "ZeoGraceApp")
        kin_header_state = settings.value("kinship_table_header_state")
        if kin_header_state:
            self.table_kinship.horizontalHeader().restoreState(kin_header_state)

        self.table_kinship.itemDoubleClicked.connect(self.on_kinship_double_clicked)

        kin_layout.addWidget(self.table_kinship)

        btn_kin_layout = QHBoxLayout()
        btn_add_kin = QPushButton("Додати родича")
        btn_del_kin = QPushButton("Видалити зв'язок")

        btn_add_kin.clicked.connect(self.add_kinship)
        btn_del_kin.clicked.connect(self.delete_kinship)

        btn_kin_layout.addWidget(btn_add_kin)
        btn_kin_layout.addWidget(btn_del_kin)
        kin_layout.addLayout(btn_kin_layout)

        self.tabs.addTab(tab_kinship, "Родичі")

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept_data)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        self.load_data_to_form()

    def on_kinship_double_clicked(self, item):
        row = item.row()
        rel_id_item = self.table_kinship.item(row, 0)
        if rel_id_item:
            relative_id = int(rel_id_item.text())
            if self.parent() and hasattr(self.parent(), "select_person_by_id"):
                self.parent().select_person_by_id(relative_id)

    def closeEvent(self, event):
        settings = QSettings("ZeoGrace", "ZeoGraceApp")
        settings.setValue("kinship_table_header_state", self.table_kinship.horizontalHeader().saveState())
        super().closeEvent(event)

    def load_data_to_form(self):
        self.table_events.setRowCount(0)

        if self.person_data:
            self.setWindowTitle(f"Редагувати запис: {self.person_data.get('name', '')}")
            self.edit_name.setText(self.person_data.get("name", "") or "")
            self.edit_address.setText(self.person_data.get("address", "") or "")
            
            # Дата народження
            dob_val = str(self.person_data.get("Date_of_Birth", "") or "")
            
            if dob_val and dob_val != "1898" and dob_val != "1900-01-01":
                try:
                    qdate = QDate.fromString(dob_val[:10], "yyyy-MM-dd")
                    if qdate.isValid():
                        self.edit_dob.setDate(qdate)
                        self.has_dob = True
                    else:
                        self.has_dob = False
                        self.edit_dob.setDate(QDate(2000, 1, 1))
                        self.edit_dob.setStyleSheet("color: gray;")
                except Exception:
                    self.has_dob = False
                    self.edit_dob.setDate(QDate(2000, 1, 1))
                    self.edit_dob.setStyleSheet("color: gray;")
            else:
                self.has_dob = False
                self.edit_dob.setDate(QDate(2000, 1, 1))
                self.edit_dob.setStyleSheet("color: gray;")
            
            # Дата хрещення
            bapt_val = str(self.person_data.get("Date_of_Bapt", "") or "")
            
            if bapt_val and bapt_val != "1898" and bapt_val != "1900-01-01":
                try:
                    qdate = QDate.fromString(bapt_val[:10], "yyyy-MM-dd")
                    if qdate.isValid():
                        self.edit_bapt.setDate(qdate)
                        self.has_bapt = True
                    else:
                        self.has_bapt = False
                        self.edit_bapt.setDate(QDate(2000, 1, 1))
                        self.edit_bapt.setStyleSheet("color: gray;")
                except Exception:
                    self.has_bapt = False
                    self.edit_bapt.setDate(QDate(2000, 1, 1))
                    self.edit_bapt.setStyleSheet("color: gray;")
            else:
                self.has_bapt = False
                self.edit_bapt.setDate(QDate(2000, 1, 1))
                self.edit_bapt.setStyleSheet("color: gray;")
            
            # Стать
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
            self.edit_email.setText(str(self.person_data.get("email", "") or ""))
            self.check_send_bd_sms.setChecked(bool(self.person_data.get("send_bd_sms", 1)))
            self.edit_notes.setPlainText(self.person_data.get("notes", "") or "")
        else:
            self.setWindowTitle("Додати новий запис")
            self.has_dob = False
            self.edit_dob.setDate(QDate(2000, 1, 1))
            self.edit_dob.setStyleSheet("color: gray;")
            
            self.has_bapt = False
            self.edit_bapt.setDate(QDate(2000, 1, 1))
            self.edit_bapt.setStyleSheet("color: gray;")

        if self.person_data and self.person_data.get("id") and self.db_path:
            try:
                with get_db_connection(self.db_path) as conn:
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT e.id, e.eventdate, e.eventtype, e.descr, t.list_name
                        FROM p_events e
                        LEFT JOIN list_event_type t ON e.eventtype = t.id
                        WHERE e.people_id = ?
                        ORDER BY e.eventdate DESC
                    """, (self.person_data["id"],))
                    for row in cur.fetchall():
                        self._add_event_row({
                            "id": row[0],
                            "eventdate": row[1],
                            "eventtype": row[2],
                            "descr": row[3],
                            "eventtype_name": row[4] or ""
                        })
            except Exception:
                pass

        self.load_kinship_data()

    def load_kinship_data(self):
        self.table_kinship.setRowCount(0)
        if self.person_data and self.person_data.get("id") and self.db_path:
            try:
                today = QDate.currentDate().toPyDate()
                with get_db_connection(self.db_path) as conn:
                    cur = conn.cursor()
                    cur.execute("""
                        SELECT 
                            k.person2_id, 
                            p.name, 
                            t.id, 
                            t.list_name, 
                            k.descr, 
                            p.Date_of_Birth, 
                            p.fam_status,
                            fs.list_name,
                            (SELECT COUNT(*) FROM p_kinship WHERE person1_id = p.id AND kin_type_id IN (1, 2)) as spouse_count
                        FROM p_kinship k
                        JOIN people p ON k.person2_id = p.id
                        JOIN list_kinship_types t ON k.kin_type_id = t.id
                        LEFT JOIN list_family_status fs ON p.fam_status = fs.id
                        WHERE k.person1_id = ?
                    """, (self.person_data["id"],))
                    rows = cur.fetchall()

                processed_rows = []

                for rel_id, rel_name, kin_id, kin_name, descr, dob, fam_status_id, fam_status_name, spouse_count in rows:
                    k_name_lower = (kin_name or "").lower()

                    # Визначення пріоритету сортування:
                    # 1: дідусі, 2: бабусі, 3: мати, 4: батько, 5: сестри, 6: брати, 7: дружина/чоловік, 8: діти, 9: інші
                    if kin_id in (13, 15) or "дідусь" in k_name_lower:
                        priority = 1
                    elif kin_id in (14, 16) or "бабуся" in k_name_lower:
                        priority = 2
                    elif kin_id == 4 or "мати" in k_name_lower or "мама" in k_name_lower:
                        priority = 3
                    elif kin_id == 3 or "батько" in k_name_lower or "тато" in k_name_lower:
                        priority = 4
                    elif kin_id == 8 or "сестра" in k_name_lower:
                        priority = 5
                    elif kin_id == 7 or "брат" in k_name_lower:
                        priority = 6
                    elif kin_id in (1, 2) or "дружина" in k_name_lower or "чоловік" in k_name_lower:
                        priority = 7
                    elif kin_id in (5, 6) or "син" in k_name_lower or "донька" in k_name_lower or "дитина" in k_name_lower:
                        priority = 8
                    else:
                        priority = 9

                    dob_str = str(dob or "").strip()
                    sub_key = ""

                    if priority == 8:
                        # Сортування дітей від найстаршого до наймолодшого (рання дата народження відображається першою)
                        if dob_str and dob_str not in ("1898", "1900-01-01"):
                            sub_key = dob_str[:10]
                        else:
                            sub_key = "9999-99-99"
                    else:
                        sub_key = ukrainian_sort_key(rel_name or "")

                    # Формування додаткової інформації для дітей (вік та стан у шлюбі)
                    final_descr = descr or ""
                    if priority == 8:
                        age_str = ""
                        if dob_str and dob_str not in ("1898", "1900-01-01"):
                            try:
                                d_obj = datetime.strptime(dob_str[:10], "%Y-%m-%d").date()
                                age = today.year - d_obj.year - ((today.month, today.day) < (d_obj.month, d_obj.day))
                                if age >= 0:
                                    age_str = f"вік: {age} р."
                            except Exception:
                                pass
                        if not age_str:
                            age_str = "вік не вказано"

                        is_married = False
                        if spouse_count and spouse_count > 0:
                            is_married = True
                        elif fam_status_name and any(w in fam_status_name.lower() for w in ["одруж", "шлюб", "заміж"]):
                            is_married = True

                        marr_str = "у шлюбі" if is_married else "не у шлюбі"

                        info_prefix = f"[{age_str}, {marr_str}]"
                        if final_descr:
                            final_descr = f"{info_prefix} {final_descr}"
                        else:
                            final_descr = info_prefix

                    processed_rows.append((priority, sub_key, rel_id, rel_name, kin_name, final_descr))

                # Сортування за пріоритетом ролей, а далі за датою народження (для дітей) або імені
                processed_rows.sort(key=lambda x: (x[0], x[1]))

                for r_idx, (_, _, rel_id, rel_name, kin_name, descr) in enumerate(processed_rows):
                    self.table_kinship.insertRow(r_idx)
                    self.table_kinship.setItem(r_idx, 0, QTableWidgetItem(str(rel_id)))
                    self.table_kinship.setItem(r_idx, 1, QTableWidgetItem(rel_name or ""))
                    self.table_kinship.setItem(r_idx, 2, QTableWidgetItem(kin_name or ""))
                    self.table_kinship.setItem(r_idx, 3, QTableWidgetItem(descr or ""))
            except Exception:
                pass

    def add_kinship(self):
        current_p_id = self.person_data.get("id") if self.person_data else None
        if not current_p_id:
            QMessageBox.information(self, "Увага", "Спочатку збережіть новий запис перед додаванням родичів.")
            return

        dlg = AddKinshipDialog(self, db_path=self.db_path, current_person_id=current_p_id)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            data = dlg.get_data()
            if data["relative_id"]:
                from database import set_kinship_relation
                set_kinship_relation(self.db_path, current_p_id, data["relative_id"], data["kin_type_id"], data["descr"])
                self.load_kinship_data()

    def delete_kinship(self):
        row = self.table_kinship.currentRow()
        if row < 0:
            return
        rel_id = int(self.table_kinship.item(row, 0).text())
        current_p_id = self.person_data.get("id")

        if current_p_id and rel_id:
            from database import remove_kinship_relation
            remove_kinship_relation(self.db_path, current_p_id, rel_id)
            self.load_kinship_data()

    def _add_event_row(self, ev):
        r = self.table_events.rowCount()
        self.table_events.insertRow(r)
        self.table_events.setItem(r, 0, QTableWidgetItem(str(ev.get("id") or "")))
        self.table_events.setItem(r, 1, QTableWidgetItem(str(ev.get("eventdate", ""))))

        type_item = QTableWidgetItem(str(ev.get("eventtype_name", "") or ""))
        type_item.setData(Qt.ItemDataRole.UserRole, ev.get("eventtype", 0))
        self.table_events.setItem(r, 2, type_item)

        self.table_events.setItem(r, 3, QTableWidgetItem(str(ev.get("descr", "") or "")))

    def add_event(self):
        dlg = EventDialog(self, self.db_path)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._add_event_row(dlg.get_data())

    def edit_event(self):
        row = self.table_events.currentRow()
        if row < 0:
            return

        ev_id = self.table_events.item(row, 0).text()
        ev_data = {
            "id": int(ev_id) if ev_id else None,
            "eventdate": self.table_events.item(row, 1).text(),
            "eventtype": self.table_events.item(row, 2).data(Qt.ItemDataRole.UserRole),
            "descr": self.table_events.item(row, 3).text()
        }

        dlg = EventDialog(self, self.db_path, ev_data)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            new_data = dlg.get_data()
            self.table_events.item(row, 1).setText(new_data["eventdate"])
            self.table_events.item(row, 2).setText(new_data["eventtype_name"])
            self.table_events.item(row, 2).setData(Qt.ItemDataRole.UserRole, new_data["eventtype"])
            self.table_events.item(row, 3).setText(new_data["descr"])

    def delete_event(self):
        row = self.table_events.currentRow()
        if row < 0:
            return
        ev_id = self.table_events.item(row, 0).text()
        if ev_id:
            self.events_to_delete.append(int(ev_id))
        self.table_events.removeRow(row)

    def accept_data(self):
        if not self.edit_name.text().strip():
            QMessageBox.warning(self, "Помилка валідації", "Поле 'П.І.Б.' є обов'язковим для заповнення!")
            return
        self.accept()

    def get_data(self):
        dob_str = self.edit_dob.date().toString("yyyy-MM-dd") if self.has_dob else ""
        bapt_str = self.edit_bapt.date().toString("yyyy-MM-dd") if self.has_bapt else ""
        events = []
        for r in range(self.table_events.rowCount()):
            ev_id = self.table_events.item(r, 0).text()
            events.append({
                "id": int(ev_id) if ev_id else None,
                "eventdate": self.table_events.item(r, 1).text(),
                "eventtype": self.table_events.item(r, 2).data(Qt.ItemDataRole.UserRole) or 0,
                "descr": self.table_events.item(r, 3).text()
            })

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
            "Date_of_Bapt": bapt_str,
            "Mobile_Phone_a": self.edit_mobile_a.text().strip(),
            "email": self.edit_email.text().strip(),
            "send_bd_sms": 1 if self.check_send_bd_sms.isChecked() else 0,
            "events": events,
            "events_to_delete": self.events_to_delete
        }

    def set_person_data(self, person_data):
        self.person_data = person_data
        self.events_to_delete = []
        self.load_data_to_form()


class ListEditorDialog(QDialog):
    """Універсальне вікно редагування довідників (класифікаторів)."""
    def __init__(self, parent=None, db_path=None, table_name="", window_title="Редагування довідника"):
        super().__init__(parent)
        self.db_path = db_path
        self.table_name = table_name
        self.setWindowTitle(window_title)
        self.resize(400, 450)
        self.init_ui()
        self.load_items()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        layout.addWidget(self.list_widget)

        btns_layout = QHBoxLayout()
        btn_add = QPushButton("➕ Додати")
        btn_edit = QPushButton("✏️ Змінити")
        btn_del = QPushButton("🗑️ Видалити")

        btn_add.clicked.connect(self.add_item)
        btn_edit.clicked.connect(self.edit_item)
        btn_del.clicked.connect(self.delete_item)

        btns_layout.addWidget(btn_add)
        btns_layout.addWidget(btn_edit)
        btns_layout.addWidget(btn_del)
        layout.addLayout(btns_layout)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Закрити")
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def load_items(self):
        self.list_widget.clear()
        if not self.db_path or not os.path.exists(self.db_path):
            return
        try:
            with get_db_connection(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute(f"SELECT id, list_name FROM {self.table_name} ORDER BY id ASC")
                for item_id, name in cur.fetchall():
                    item = QListWidgetItem(name)
                    item.setData(Qt.ItemDataRole.UserRole, item_id)
                    self.list_widget.addItem(item)
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося завантажити елементи:\n{str(e)}")

    def add_item(self):
        text, ok = QInputDialog.getText(self, "Новий елемент", "Введіть назву:")
        if ok and text.strip():
            try:
                with get_db_connection(self.db_path) as conn:
                    cur = conn.cursor()
                    cur.execute(f"INSERT INTO {self.table_name} (list_name) VALUES (?)", (text.strip(),))
                    conn.commit()
                self.load_items()
            except Exception as e:
                QMessageBox.critical(self, "Помилка", f"Не вдалося додати елемент:\n{str(e)}")

    def edit_item(self):
        curr_item = self.list_widget.currentItem()
        if not curr_item:
            QMessageBox.warning(self, "Увага", "Оберіть елемент для редагування!")
            return
        item_id = curr_item.data(Qt.ItemDataRole.UserRole)
        old_text = curr_item.text()

        text, ok = QInputDialog.getText(self, "Редагування елемента", "Назва:", text=old_text)
        if ok and text.strip():
            try:
                with get_db_connection(self.db_path) as conn:
                    cur = conn.cursor()
                    cur.execute(f"UPDATE {self.table_name} SET list_name = ? WHERE id = ?", (text.strip(), item_id))
                    conn.commit()
                self.load_items()
            except Exception as e:
                QMessageBox.critical(self, "Помилка", f"Не вдалося оновити елемент:\n{str(e)}")

    def delete_item(self):
        curr_item = self.list_widget.currentItem()
        if not curr_item:
            QMessageBox.warning(self, "Увага", "Оберіть елемент для видалення!")
            return
        item_id = curr_item.data(Qt.ItemDataRole.UserRole)

        reply = QMessageBox.question(
            self, "Підтвердження видалення",
            f"Ви дійсно бажаєте видалити елемент '{curr_item.text()}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                with get_db_connection(self.db_path) as conn:
                    cur = conn.cursor()
                    cur.execute(f"DELETE FROM {self.table_name} WHERE id = ?", (item_id,))
                    conn.commit()
                self.load_items()
            except Exception as e:
                QMessageBox.critical(self, "Помилка", f"Не вдалося видалити елемент (можливо, він використовується в базі):\n{str(e)}")


class AddKinshipDialog(QDialog):
    """Діалог додавання/редагування родинного зв'язку з фільтрацією за статтю обох осіб та автовибором за прізвищем."""
    def __init__(self, parent=None, db_path=None, current_person_id=None):
        super().__init__(parent)
        self.db_path = db_path
        self.current_person_id = current_person_id
        self.current_person_gender = 0
        self.current_person_surname = ""
        self.setWindowTitle("Додати родинний зв'язок")
        self.resize(450, 200)
        self._load_current_person_info()
        self.init_ui()

    def _load_current_person_info(self):
        if self.db_path and self.current_person_id and os.path.exists(self.db_path):
            try:
                from database import _parse_full_name
                with get_db_connection(self.db_path) as conn:
                    cur = conn.cursor()
                    cur.execute("SELECT name, gender FROM people WHERE id = ?", (self.current_person_id,))
                    row = cur.fetchone()
                    if row:
                        p_name, p_gender = row[0], row[1]
                        self.current_person_gender = p_gender or 0
                        self.current_person_surname = _parse_full_name(p_name)[0]
            except Exception:
                pass

    def init_ui(self):
        from database import _parse_full_name, _adapt_surname_for_gender

        layout = QFormLayout(self)

        self.combo_person = QComboBox()
        self.combo_kin_type = QComboBox()
        self.edit_descr = QLineEdit()

        match_idx = -1

        if self.db_path and os.path.exists(self.db_path):
            with get_db_connection(self.db_path) as conn:
                cur = conn.cursor()
                cur.execute("""
                    SELECT p.id, p.name, p.gender, g.list_name 
                    FROM people p
                    LEFT JOIN list_gender g ON p.gender = g.id
                    WHERE p.id != ? 
                    ORDER BY p.name COLLATE UKRAINIAN ASC
                """, (self.current_person_id or -1,))

                rows = cur.fetchall()
                for idx, (pid, pname, gender_id, gender_name) in enumerate(rows):
                    display_text = f"{pname} ({gender_name})" if gender_name else pname
                    self.combo_person.addItem(display_text, (pid, gender_id or 0))

                    if match_idx == -1 and self.current_person_surname:
                        c_surname, _, _ = _parse_full_name(pname)
                        if c_surname:
                            surname_match = (
                                c_surname.lower() == self.current_person_surname.lower() or
                                _adapt_surname_for_gender(c_surname, self.current_person_gender).lower() == self.current_person_surname.lower() or
                                _adapt_surname_for_gender(self.current_person_surname, gender_id or 0).lower() == c_surname.lower()
                            )
                            if surname_match:
                                match_idx = idx

        if match_idx != -1:
            self.combo_person.setCurrentIndex(match_idx)

        self.combo_person.currentIndexChanged.connect(self.update_kinship_types)

        layout.addRow("Оберіть родича:", self.combo_person)
        layout.addRow("Хто ця людина для даної особи:", self.combo_kin_type)
        layout.addRow("Примітка:", self.edit_descr)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.update_kinship_types()

    def update_kinship_types(self):
        self.combo_kin_type.clear()
        selected_data = self.combo_person.currentData()
        if not selected_data:
            return

        _, relative_gender = selected_data

        male_kin_ids = [1, 3, 5, 7, 9, 11, 13, 15]
        female_kin_ids = [2, 4, 6, 8, 10, 12, 14, 16]

        if self.current_person_gender == 1 and 1 in male_kin_ids:
            male_kin_ids.remove(1)

        if self.current_person_gender == 2 and 2 in female_kin_ids:
            female_kin_ids.remove(2)

        if not self.db_path or not os.path.exists(self.db_path):
            return

        with get_db_connection(self.db_path) as conn:
            cur = conn.cursor()

            if relative_gender == 1:
                placeholders = ",".join("?" * len(male_kin_ids))
                query = f"SELECT id, list_name FROM list_kinship_types WHERE id IN ({placeholders}) ORDER BY list_name ASC"
                cur.execute(query, male_kin_ids)
            elif relative_gender == 2:
                placeholders = ",".join("?" * len(female_kin_ids))
                query = f"SELECT id, list_name FROM list_kinship_types WHERE id IN ({placeholders}) ORDER BY list_name ASC"
                cur.execute(query, female_kin_ids)
            else:
                allowed_ids = list(set(male_kin_ids + female_kin_ids))
                placeholders = ",".join("?" * len(allowed_ids))
                query = f"SELECT id, list_name FROM list_kinship_types WHERE id IN ({placeholders}) ORDER BY list_name ASC"
                cur.execute(query, allowed_ids)

            for kid, kname in cur.fetchall():
                self.combo_kin_type.addItem(kname, kid)

    def get_data(self):
        selected_person = self.combo_person.currentData()
        relative_id = selected_person[0] if selected_person else None
        return {
            "relative_id": relative_id,
            "kin_type_id": self.combo_kin_type.currentData(),
            "descr": self.edit_descr.text().strip()
        }


class FamiliesWindow(QDialog):
    """Окреме вікно для виводу переліку родин та сімей з різними рівнями зв'язків."""
    def __init__(self, parent=None, db_path=None, pdf_font="Helvetica"):
        super().__init__(parent)
        self.db_path = db_path
        self.pdf_font = pdf_font
        self.setWindowTitle("Перелік родин та сімей громади")
        self.resize(900, 600)
        self.init_ui()
        self.load_families()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        filter_bar = QHBoxLayout()

        filter_bar.addWidget(QLabel("Режим групування:"))
        self.combo_mode = QComboBox()
        self.combo_mode.addItem("Сім'ї (Чоловік + Дружина + Діти)", "nuclear")
        self.combo_mode.addItem("Пряма лінія (Дідусі/Бабусі — Батьки — Онуки)", "direct")
        self.combo_mode.addItem("Повна родина (включно з дядьками, племінниками)", "full")
        self.combo_mode.currentIndexChanged.connect(self.load_families)
        filter_bar.addWidget(self.combo_mode)

        filter_bar.addStretch()

        btn_refresh = QPushButton("🔄 Оновити")
        btn_refresh.clicked.connect(self.load_families)
        filter_bar.addWidget(btn_refresh)

        btn_export_pdf = QPushButton("📄 Експорт у PDF")
        btn_export_pdf.clicked.connect(self.export_families_pdf)
        filter_bar.addWidget(btn_export_pdf)

        main_layout.addLayout(filter_bar)

        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Родина / Член родини", "Зв'язок / Роль", "Телефон", "Адреса"])
        self.tree.header().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.tree.header().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.tree.itemDoubleClicked.connect(self.on_item_double_clicked)

        main_layout.addWidget(self.tree)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("Закрити")
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

    def _get_allowed_kin_ids(self, mode):
        if mode == "nuclear":
            return {1, 2, 3, 4, 5, 6}
        elif mode == "direct":
            return {1, 2, 3, 4, 5, 6, 13, 14, 15, 16}
        else:
            return None

    def _order_family_members(self, family_ids, people_dict, kin_map, kin_names):
        """
        Впорядковує членів родини у послідовності:
        1. Чоловік (role = "Чоловік")
        2. Дружина (role = "Дружина")
        3. Діти від старшого до наймолодшого (role = "Син" / "Донька")
        4. Інші родичі (з відповідними назвами ролей з kin_names)
        """
        husband_id = None
        wife_id = None

        for p1 in family_ids:
            for p2 in family_ids:
                if p1 == p2:
                    continue
                k = kin_map.get((p1, p2))
                if k == 1:
                    husband_id = p1
                    wife_id = p2
                    break
                elif k == 2:
                    wife_id = p1
                    husband_id = p2
                    break
            if husband_id or wife_id:
                break

        if not husband_id:
            for p in family_ids:
                if people_dict[p]["gender"] == 1:
                    is_father = any(
                        kin_map.get((p, c)) in (5, 6) or kin_map.get((c, p)) in (3, 4)
                        for c in family_ids if c != p
                    )
                    if is_father:
                        husband_id = p
                        break

        if not wife_id:
            for p in family_ids:
                if people_dict[p]["gender"] == 2:
                    is_mother = any(
                        kin_map.get((p, c)) in (5, 6) or kin_map.get((c, p)) in (3, 4)
                        for c in family_ids if c != p
                    )
                    if is_mother:
                        wife_id = p
                        break

        parents = set(filter(None, [husband_id, wife_id]))
        remaining = [p for p in family_ids if p not in parents]

        children = []
        others = []

        for p in remaining:
            is_child = False
            for parent in parents:
                k_p_c = kin_map.get((parent, p))
                k_c_p = kin_map.get((p, parent))
                if k_p_c in (5, 6) or k_c_p in (3, 4):
                    is_child = True
                    break

            if not is_child:
                is_child = any(
                    kin_map.get((other, p)) in (5, 6) or kin_map.get((p, other)) in (3, 4)
                    for other in family_ids if other != p
                )

            if is_child:
                children.append(p)
            else:
                others.append(p)

        def get_dob_sort_key(p_id):
            dob = people_dict[p_id]["dob"]
            if dob and dob != "1900-01-01" and dob != "1898":
                return dob
            return "9999-99-99"

        children.sort(key=get_dob_sort_key)

        result = []

        if husband_id:
            result.append((husband_id, "Чоловік"))

        if wife_id:
            result.append((wife_id, "Дружина"))

        for c_id in children:
            c_gender = people_dict[c_id]["gender"]
            if c_gender == 1:
                c_role = "Син"
            elif c_gender == 2:
                c_role = "Донька"
            else:
                c_role = "Дитина"
            result.append((c_id, c_role))

        for o_id in others:
            role = "Родич"
            ref_id = husband_id or wife_id or (result[0][0] if result else None)
            if ref_id and ref_id != o_id:
                ktype = kin_map.get((ref_id, o_id))
                if ktype and ktype in kin_names:
                    role = kin_names[ktype]
            result.append((o_id, role))

        return result

    def load_families(self):
        self.tree.clear()
        if not self.db_path or not os.path.exists(self.db_path):
            return

        mode = self.combo_mode.currentData()
        allowed_kin_types = self._get_allowed_kin_ids(mode)

        with get_db_connection(self.db_path) as conn:
            cur = conn.cursor()

            cur.execute("""
                SELECT id, name, address, Mobile_Phone, gender, Date_of_Birth 
                FROM people 
                ORDER BY name COLLATE UKRAINIAN ASC
            """)
            people_dict = {}
            for row in cur.fetchall():
                pid, name, address, phone, gender, dob = row
                people_dict[pid] = {
                    "id": pid,
                    "name": name or "",
                    "address": address or "",
                    "phone": format_phone(phone),
                    "gender": gender or 0,
                    "dob": str(dob or "").strip()
                }

            query = "SELECT person1_id, person2_id, kin_type_id FROM p_kinship"
            cur.execute(query)
            kinship_rows = cur.fetchall()

            adj = {pid: [] for pid in people_dict.keys()}
            kin_map = {}

            for p1, p2, ktype in kinship_rows:
                if allowed_kin_types is None or ktype in allowed_kin_types:
                    adj[p1].append((p2, ktype))
                    kin_map[(p1, p2)] = ktype

            cur.execute("SELECT id, list_name FROM list_kinship_types")
            kin_names = dict(cur.fetchall())

            visited = set()
            families = []

            for p_id in people_dict.keys():
                if p_id not in visited:
                    family_members = []
                    queue = deque([p_id])
                    visited.add(p_id)

                    while queue:
                        curr = queue.popleft()
                        family_members.append(curr)

                        for neighbor, _ in adj[curr]:
                            if neighbor not in visited:
                                visited.add(neighbor)
                                queue.append(neighbor)

                    if len(family_members) > 1:
                        families.append(family_members)

            for f_idx, family_ids in enumerate(families, start=1):
                ordered_members = self._order_family_members(family_ids, people_dict, kin_map, kin_names)

                if not ordered_members:
                    continue

                head_id, head_role = ordered_members[0]
                head_info = people_dict[head_id]
                fam_name = head_info["name"].split()[0] if head_info["name"] else "Родина"

                fam_item = QTreeWidgetItem(self.tree)
                fam_item.setText(0, f"Родина #{f_idx} ({fam_name}) — {len(ordered_members)} осіб")
                fam_item.setText(3, head_info["address"])
                fam_item.setExpanded(True)

                for member_id, role_title in ordered_members:
                    m_info = people_dict[member_id]
                    m_item = QTreeWidgetItem(fam_item)
                    m_item.setData(0, Qt.ItemDataRole.UserRole, member_id)
                    m_item.setText(0, m_info["name"])
                    m_item.setText(1, role_title)
                    m_item.setText(2, m_info["phone"])
                    m_item.setText(3, m_info["address"])

    def on_item_double_clicked(self, item, column):
        member_id = item.data(0, Qt.ItemDataRole.UserRole)
        if member_id and self.parent() and hasattr(self.parent(), "select_person_by_id"):
            self.parent().select_person_by_id(member_id)

    def export_families_pdf(self):
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Зберегти PDF-звіт родин", "Родини_громади.pdf", "PDF файли (*.pdf)"
        )
        if not save_path:
            return

        families_data = []
        root = self.tree.invisibleRootItem()
        for i in range(root.childCount()):
            fam_item = root.child(i)
            fam_title = fam_item.text(0)
            members = []
            for j in range(fam_item.childCount()):
                m_item = fam_item.child(j)
                members.append((
                    m_item.text(0),
                    m_item.text(1),
                    m_item.text(2),
                    m_item.text(3)
                ))
            families_data.append((fam_title, members))

        filter_text = f"<b>Режим групування:</b> {self.combo_mode.currentText()} | <b>Всього родин:</b> {len(families_data)}"

        try:
            from pdf_generator import build_families_pdf_document
            build_families_pdf_document(
                save_path, families_data, filter_text=filter_text, font_name=self.pdf_font
            )
            QMessageBox.information(self, "Успіх", f"PDF-звіт родин успішно збережено у:\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Помилка", f"Не вдалося створити PDF:\n{str(e)}")


class ChildrenConfirmationDialog(QDialog):
    """Вікно перегляду та підтвердження знайдених дітей з чекбоксами та створенням нових карт."""
    def __init__(self, parent=None, candidates=None, db_path=None):
        super().__init__(parent)
        self.candidates = candidates or []
        self.db_path = db_path
        self.processed_count = 0
        self.settings = QSettings("ZeoGrace", "ZeoGraceApp")

        self.setWindowTitle("Підтвердження встановлення зв'язків з дітьми")
        self.resize(880, 540)
        self.init_ui()
        self.restore_ui_state()

    def restore_ui_state(self):
        geom = self.settings.value("children_dialog_geometry")
        if geom:
            self.restoreGeometry(geom)

        header_state = self.settings.value("children_dialog_header_state")
        if header_state:
            self.table.horizontalHeader().restoreState(header_state)

    def closeEvent(self, event):
        self.settings.setValue("children_dialog_geometry", self.saveGeometry())
        self.settings.setValue("children_dialog_header_state", self.table.horizontalHeader().saveState())
        super().closeEvent(event)

    def init_ui(self):
        layout = QVBoxLayout(self)

        lbl_info = QLabel(
            "Програма проаналізувала базу даних та знайшла потенційних дітей (у т.ч. з опису подій).\n"
            "Позначте прапорцями ті пари, для яких потрібно встановити зв'язок або створити новий запис:"
        )
        lbl_info.setWordWrap(True)
        layout.addWidget(lbl_info)

        self.table = QTableWidget()
        self.table.setColumnCount(7)
        self.table.setHorizontalHeaderLabels([
            "Застосувати", "Батько / Мати", "Дитина", "Дата нар. / події", "Тип запису", "Поточний зв'язок", "Статус"
        ])

        self.table.setWordWrap(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)

        self.table.setColumnWidth(0, 85)
        self.table.setColumnWidth(1, 220)
        self.table.setColumnWidth(2, 210)
        self.table.setColumnWidth(3, 110)
        self.table.setColumnWidth(4, 115)
        self.table.setColumnWidth(5, 130)
        self.table.setColumnWidth(6, 120)

        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        self.load_candidates()
        layout.addWidget(self.table)

        btn_bar = QHBoxLayout()

        btn_select_all = QPushButton("Вибрати всі")
        btn_select_all.clicked.connect(lambda: self.set_all_checks(True))
        btn_bar.addWidget(btn_select_all)

        btn_deselect_all = QPushButton("Скинути всі")
        btn_deselect_all.clicked.connect(lambda: self.set_all_checks(False))
        btn_bar.addWidget(btn_deselect_all)

        btn_bar.addStretch()

        self.btn_apply = QPushButton("Застосувати вибрані зміни")
        self.btn_apply.setStyleSheet("font-weight: bold; padding: 6px 14px;")
        self.btn_apply.clicked.connect(self.apply_changes)
        btn_bar.addWidget(self.btn_apply)

        btn_close = QPushButton("Закрити")
        btn_close.clicked.connect(self.accept)
        btn_bar.addWidget(btn_close)

        layout.addLayout(btn_bar)

    def load_candidates(self):
        from utils import ukrainian_sort_key

        self.candidates.sort(key=lambda cand: ukrainian_sort_key(cand.get("parent_name", "")))

        self.table.setRowCount(len(self.candidates))
        for r, cand in enumerate(self.candidates):
            exist_kin_id = cand.get("existing_kin_id")
            exist_kin_name = cand.get("existing_kin_name")
            parents_married = cand.get("parents_married", True)
            parent_ids = cand.get("parent_ids", [])

            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)

            is_warning = False
            if exist_kin_id in (5, 6):
                chk_item.setCheckState(Qt.CheckState.Unchecked)
                initial_status = "Вже є дитиною"
            elif exist_kin_id is not None:
                chk_item.setCheckState(Qt.CheckState.Unchecked)
                initial_status = "Існує інший зв'язок"
            else:
                chk_item.setCheckState(Qt.CheckState.Checked)
                if cand["type"] == "new_person":
                    initial_status = "Готово до створення"
                else:
                    initial_status = "Готово до додавання"

                if len(parent_ids) > 1 and not parents_married:
                    initial_status += " (батьки не в шлюбі)"
                    is_warning = True

            self.table.setItem(r, 0, chk_item)

            item_p = QTableWidgetItem(cand["parent_name"])
            item_p.setFlags(item_p.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, 1, item_p)

            child_label = f"✨ {cand['child_name']}" if cand["type"] == "new_person" else cand["child_name"]
            item_c = QTableWidgetItem(child_label)
            item_c.setFlags(item_c.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, 2, item_c)

            item_date = QTableWidgetItem(cand.get("date", ""))
            item_date.setFlags(item_date.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, 3, item_date)

            rec_type = "Створення особи" if cand["type"] == "new_person" else "Існуюча особа"
            item_type = QTableWidgetItem(rec_type)
            item_type.setFlags(item_type.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, 4, item_type)

            curr_kin = exist_kin_name if exist_kin_name else "— (відсутній)"
            if len(parent_ids) > 1 and not parents_married and exist_kin_id is None:
                curr_kin = "⚠️ Батьки не в шлюбі"
            item_kin = QTableWidgetItem(curr_kin)
            item_kin.setFlags(item_kin.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, 5, item_kin)

            item_status = QTableWidgetItem(initial_status)
            item_status.setFlags(item_status.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if is_warning:
                item_status.setForeground(Qt.GlobalColor.darkYellow)
            self.table.setItem(r, 6, item_status)

        self.table.resizeRowsToContents()

    def set_all_checks(self, checked: bool):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item and item.flags() & Qt.ItemFlag.ItemIsEnabled:
                item.setCheckState(state)

    def apply_changes(self):
        from database import set_kinship_relation, create_person_record, get_db_connection

        checked_rows = [
            r for r in range(self.table.rowCount())
            if self.table.item(r, 0) 
            and self.table.item(r, 0).checkState() == Qt.CheckState.Checked
            and self.table.item(r, 6)
            and self.table.item(r, 6).text() != "✓ Застосовано"
        ]

        if not checked_rows:
            return

        progress = QProgressDialog("Застосування змін до бази даних...", "Скасувати", 0, len(checked_rows), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        QApplication.processEvents()

        applied_count = 0
        conn = get_db_connection(self.db_path)

        try:
            for idx, r in enumerate(checked_rows, start=1):
                if progress.wasCanceled():
                    break

                cand = self.candidates[r]
                chk_item = self.table.item(r, 0)
                status_item = self.table.item(r, 6)

                progress.setLabelText(f"Обробка ({idx}/{len(checked_rows)}): {cand['child_name']}...")
                progress.setValue(idx - 1)
                QApplication.processEvents()

                child_id = cand.get("child_id")
                if cand["type"] == "new_person":
                    child_id = create_person_record(
                        self.db_path,
                        name=cand["child_name"],
                        gender=cand["child_gender"],
                        dob=cand.get("date", ""),
                        address=cand.get("address", "")
                    )

                kin_type_id = 6 if cand["child_gender"] == 2 else 5

                parent_ids = cand.get("parent_ids", [])
                if not parent_ids and cand.get("parent_id"):
                    parent_ids = [cand.get("parent_id")]

                for pid in parent_ids:
                    set_kinship_relation(
                        self.db_path,
                        pid,
                        child_id,
                        kin_type_id,
                        "Автоматично за аналізом дітей",
                        conn=conn
                    )

                status_item.setText("✓ Застосовано")
                status_item.setForeground(Qt.GlobalColor.darkGreen)
                chk_item.setFlags(chk_item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                applied_count += 1

                progress.setValue(idx)
                QApplication.processEvents()
        finally:
            conn.close()
            progress.close()

        self.processed_count += applied_count
        if applied_count > 0:
            QMessageBox.information(
                self, "Успіх", f"Успішно встановлено зв'язки для {applied_count} дітей!"
            )
            self.btn_apply.setEnabled(False)


class MarriageConfirmationDialog(QDialog):
    """Вікно перегляду та підтвердження знайдених шлюбних пар зі збереженням розмірів та стану колонок."""
    def __init__(self, parent=None, candidates=None, db_path=None):
        super().__init__(parent)
        self.candidates = candidates or []
        self.db_path = db_path
        self.processed_count = 0
        self.settings = QSettings("ZeoGrace", "ZeoGraceApp")

        self.setWindowTitle("Підтвердження встановлення шлюбних зв'язків")
        self.resize(800, 500)
        self.init_ui()
        self.restore_ui_state()

    def restore_ui_state(self):
        geom = self.settings.value("marriage_dialog_geometry")
        if geom:
            self.restoreGeometry(geom)

        header_state = self.settings.value("marriage_dialog_header_state")
        if header_state:
            self.table.horizontalHeader().restoreState(header_state)

    def closeEvent(self, event):
        self.settings.setValue("marriage_dialog_geometry", self.saveGeometry())
        self.settings.setValue("marriage_dialog_header_state", self.table.horizontalHeader().saveState())
        super().closeEvent(event)

    def init_ui(self):
        layout = QVBoxLayout(self)

        lbl_info = QLabel(
            "Програма проаналізувала базу даних і знайшла наступні потенційні шлюбні пари.\n"
            "Позначте прапорцями тільки ті пари, для яких дійсно потрібно встановити зв'язок «Чоловік / Дружина»:"
        )
        lbl_info.setWordWrap(True)
        layout.addWidget(lbl_info)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Застосувати", "Чоловік", "Дружина", "Дата шлюбу", "Поточний зв'язок", "Статус"
        ])

        self.table.setWordWrap(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)

        self.table.setColumnWidth(0, 85)
        self.table.setColumnWidth(1, 200)
        self.table.setColumnWidth(2, 200)
        self.table.setColumnWidth(3, 110)
        self.table.setColumnWidth(4, 130)
        self.table.setColumnWidth(5, 120)

        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        self.load_candidates()
        layout.addWidget(self.table)

        btn_bar = QHBoxLayout()

        btn_select_all = QPushButton("Вибрати всі")
        btn_select_all.clicked.connect(lambda: self.set_all_checks(True))
        btn_bar.addWidget(btn_select_all)

        btn_deselect_all = QPushButton("Скинути всі")
        btn_deselect_all.clicked.connect(lambda: self.set_all_checks(False))
        btn_bar.addWidget(btn_deselect_all)

        btn_bar.addStretch()

        self.btn_apply = QPushButton("Застосувати вибрані зміни")
        self.btn_apply.setStyleSheet("font-weight: bold; padding: 6px 14px;")
        self.btn_apply.clicked.connect(self.apply_changes)
        btn_bar.addWidget(self.btn_apply)

        btn_close = QPushButton("Закрити")
        btn_close.clicked.connect(self.accept)
        btn_bar.addWidget(btn_close)

        layout.addLayout(btn_bar)

    def load_candidates(self):
        from utils import ukrainian_sort_key
        self.candidates.sort(key=lambda cand: ukrainian_sort_key(cand.get("m_name", "")))

        self.table.setRowCount(len(self.candidates))
        for r, cand in enumerate(self.candidates):
            exist_kin_id = cand.get("existing_kin_id")
            exist_kin_name = cand.get("existing_kin_name")
            is_divorced = cand.get("is_divorced", False)

            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)

            if exist_kin_id in (1, 2):
                chk_item.setCheckState(Qt.CheckState.Unchecked)
                initial_status = "Вже встановлено"
            elif exist_kin_id is not None:
                chk_item.setCheckState(Qt.CheckState.Unchecked)
                initial_status = "Існує інший зв'язок"
            elif is_divorced:
                chk_item.setCheckState(Qt.CheckState.Unchecked)
                initial_status = "⚠️ Розведений(а)"
            else:
                chk_item.setCheckState(Qt.CheckState.Checked)
                initial_status = "Готово до додавання"

            self.table.setItem(r, 0, chk_item)

            item_m = QTableWidgetItem(cand["m_name"])
            item_m.setFlags(item_m.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, 1, item_m)

            item_w = QTableWidgetItem(cand["w_name"])
            item_w.setFlags(item_w.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, 2, item_w)

            item_date = QTableWidgetItem(cand["date"])
            item_date.setFlags(item_date.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, 3, item_date)

            curr_kin = exist_kin_name if exist_kin_name else "— (відсутній)"
            item_kin = QTableWidgetItem(curr_kin)
            item_kin.setFlags(item_kin.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, 4, item_kin)

            item_status = QTableWidgetItem(initial_status)
            item_status.setFlags(item_status.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if is_divorced and exist_kin_id is None:
                item_status.setForeground(Qt.GlobalColor.darkYellow)
            self.table.setItem(r, 5, item_status)

        self.table.resizeRowsToContents()

    def set_all_checks(self, checked: bool):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item and item.flags() & Qt.ItemFlag.ItemIsEnabled:
                item.setCheckState(state)

    def apply_changes(self):
        from database import set_kinship_relation, get_db_connection

        checked_rows = [
            r for r in range(self.table.rowCount())
            if self.table.item(r, 0)
            and self.table.item(r, 0).checkState() == Qt.CheckState.Checked
            and self.table.item(r, 5)
            and self.table.item(r, 5).text() != "✓ Застосовано"
        ]

        if not checked_rows:
            return

        progress = QProgressDialog("Застосування змін до бази даних...", "Скасувати", 0, len(checked_rows), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        QApplication.processEvents()

        wife_kin_id = 2
        if self.db_path and os.path.exists(self.db_path):
            try:
                with get_db_connection(self.db_path) as conn_tmp:
                    cur = conn_tmp.cursor()
                    cur.execute("SELECT id FROM list_kinship_types WHERE LOWER(list_name) = 'дружина'")
                    row = cur.fetchone()
                    if row and row[0]:
                        wife_kin_id = row[0]
            except Exception:
                pass

        applied_count = 0
        conn = get_db_connection(self.db_path)

        try:
            for idx, r in enumerate(checked_rows, start=1):
                if progress.wasCanceled():
                    break

                cand = self.candidates[r]
                chk_item = self.table.item(r, 0)
                status_item = self.table.item(r, 5)

                progress.setLabelText(f"Обробка ({idx}/{len(checked_rows)}): {cand['m_name']} + {cand['w_name']}...")
                progress.setValue(idx - 1)
                QApplication.processEvents()

                set_kinship_relation(
                    self.db_path,
                    cand["m_id"],
                    cand["w_id"],
                    wife_kin_id,
                    f"Автоматично за подією шлюбу від {cand['date']}",
                    conn=conn
                )

                status_item.setText("✓ Застосовано")
                status_item.setForeground(Qt.GlobalColor.darkGreen)
                chk_item.setFlags(chk_item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                applied_count += 1

                progress.setValue(idx)
                QApplication.processEvents()
        finally:
            conn.close()
            progress.close()

        self.processed_count += applied_count
        if applied_count > 0:
            QMessageBox.information(
                self, "Успіх", f"Успішно встановлено шлюбні зв'язки для {applied_count} пар(и)!"
            )
            self.btn_apply.setEnabled(False)


class ExtendedKinshipConfirmationDialog(QDialog):
    """Вікно перегляду та підтвердження знайдених розширених родинних зв'язків."""
    def __init__(self, parent=None, candidates=None, db_path=None):
        super().__init__(parent)
        self.candidates = candidates or []
        self.db_path = db_path
        self.processed_count = 0
        self.settings = QSettings("ZeoGrace", "ZeoGraceApp")

        self.setWindowTitle("Підтвердження встановлення розширених родинних зв'язків")
        self.resize(920, 560)
        self.init_ui()
        self.restore_ui_state()

    def restore_ui_state(self):
        geom = self.settings.value("ext_kinship_dialog_geometry")
        if geom:
            self.restoreGeometry(geom)
        header_state = self.settings.value("ext_kinship_dialog_header_state")
        if header_state:
            self.table.horizontalHeader().restoreState(header_state)

    def closeEvent(self, event):
        self.settings.setValue("ext_kinship_dialog_geometry", self.saveGeometry())
        self.settings.setValue("ext_kinship_dialog_header_state", self.table.horizontalHeader().saveState())
        super().closeEvent(event)

    def init_ui(self):
        layout = QVBoxLayout(self)

        lbl_info = QLabel(
            "Програма проаналізувала граф зв'язків та знайшла потенційні розширені родинні зв'язки.\n"
            "Позначте прапорцями тільки ті зв'язки, які ви бажаєте додати до бази даних:"
        )
        lbl_info.setWordWrap(True)
        layout.addWidget(lbl_info)

        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Застосувати", "Особа", "Родич", "Роль родича", "Підстава (Аналіз)", "Статус"
        ])

        self.table.setWordWrap(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)

        self.table.setColumnWidth(0, 85)
        self.table.setColumnWidth(1, 200)
        self.table.setColumnWidth(2, 200)
        self.table.setColumnWidth(3, 140)
        self.table.setColumnWidth(4, 210)
        self.table.setColumnWidth(5, 120)

        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)

        self.load_candidates()
        layout.addWidget(self.table)

        btn_bar = QHBoxLayout()

        btn_select_all = QPushButton("Вибрати всі")
        btn_select_all.clicked.connect(lambda: self.set_all_checks(True))
        btn_bar.addWidget(btn_select_all)

        btn_deselect_all = QPushButton("Скинути всі")
        btn_deselect_all.clicked.connect(lambda: self.set_all_checks(False))
        btn_bar.addWidget(btn_deselect_all)

        btn_bar.addStretch()

        self.btn_apply = QPushButton("Застосувати вибрані зміни")
        self.btn_apply.setStyleSheet("font-weight: bold; padding: 6px 14px;")
        self.btn_apply.clicked.connect(self.apply_changes)
        btn_bar.addWidget(self.btn_apply)

        btn_close = QPushButton("Закрити")
        btn_close.clicked.connect(self.accept)
        btn_bar.addWidget(btn_close)

        layout.addLayout(btn_bar)

    def load_candidates(self):
        from utils import ukrainian_sort_key
        self.candidates.sort(key=lambda c: (ukrainian_sort_key(c.get("person1_name", "")), c.get("target_kin_id", 0)))

        self.table.setRowCount(len(self.candidates))
        for r, cand in enumerate(self.candidates):
            exist_kin_id = cand.get("existing_kin_id")
            exist_kin_name = cand.get("existing_kin_name")

            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)

            if exist_kin_id is not None:
                chk_item.setCheckState(Qt.CheckState.Unchecked)
                initial_status = f"Існує ({exist_kin_name})"
            else:
                chk_item.setCheckState(Qt.CheckState.Checked)
                initial_status = "Готово до додавання"

            self.table.setItem(r, 0, chk_item)

            item_p1 = QTableWidgetItem(cand["person1_name"])
            item_p1.setFlags(item_p1.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, 1, item_p1)

            item_p2 = QTableWidgetItem(cand["person2_name"])
            item_p2.setFlags(item_p2.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, 2, item_p2)

            item_role = QTableWidgetItem(cand["target_kin_name"])
            item_role.setFlags(item_role.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, 3, item_role)

            item_reason = QTableWidgetItem(cand["reason"])
            item_reason.setFlags(item_reason.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, 4, item_reason)

            item_status = QTableWidgetItem(initial_status)
            item_status.setFlags(item_status.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if exist_kin_id is not None:
                item_status.setForeground(Qt.GlobalColor.darkGray)
            self.table.setItem(r, 5, item_status)

        self.table.resizeRowsToContents()

    def set_all_checks(self, checked: bool):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        for r in range(self.table.rowCount()):
            item = self.table.item(r, 0)
            if item and item.flags() & Qt.ItemFlag.ItemIsEnabled:
                item.setCheckState(state)

    def apply_changes(self):
        from database import set_kinship_relation, get_db_connection

        checked_rows = [
            r for r in range(self.table.rowCount())
            if self.table.item(r, 0)
            and self.table.item(r, 0).checkState() == Qt.CheckState.Checked
            and self.table.item(r, 5)
            and self.table.item(r, 5).text() != "✓ Застосовано"
        ]

        if not checked_rows:
            return

        progress = QProgressDialog("Застосування змін до бази даних...", "Скасувати", 0, len(checked_rows), self)
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(0)
        progress.setValue(0)
        QApplication.processEvents()

        applied_count = 0
        conn = get_db_connection(self.db_path)

        try:
            for idx, r in enumerate(checked_rows, start=1):
                if progress.wasCanceled():
                    break

                cand = self.candidates[r]
                chk_item = self.table.item(r, 0)
                status_item = self.table.item(r, 5)

                progress.setLabelText(f"Обробка ({idx}/{len(checked_rows)}): {cand['person1_name']} -> {cand['target_kin_name']}...")
                progress.setValue(idx - 1)
                QApplication.processEvents()

                set_kinship_relation(
                    self.db_path,
                    cand["person1_id"],
                    cand["person2_id"],
                    cand["target_kin_id"],
                    f"Автопошук: {cand['reason']}",
                    conn=conn
                )

                status_item.setText("✓ Застосовано")
                status_item.setForeground(Qt.GlobalColor.darkGreen)
                chk_item.setFlags(chk_item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                applied_count += 1

                progress.setValue(idx)
                QApplication.processEvents()
        finally:
            conn.close()
            progress.close()

        self.processed_count += applied_count
        if applied_count > 0:
            QMessageBox.information(
                self, "Успіх", f"Успішно встановлено {applied_count} родинних зв'язків!"
            )
            self.btn_apply.setEnabled(False)


class SettingsDialog(QDialog):
    """Діалогове вікно налаштувань резервного копіювання та параметрів програми."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings = QSettings("ZeoGrace", "ZeoGraceApp")
        self.setWindowTitle("Налаштування програми")
        self.resize(420, 260)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        gb_backup = QGroupBox("Параметри резервного копіювання (Backup)")
        form_lay = QFormLayout(gb_backup)

        self.chk_auto_backup = QCheckBox("Увімкнути періодичне авторезервування")
        self.spin_interval = QSpinBox()
        self.spin_interval.setRange(1, 180)
        self.spin_interval.setSuffix(" хв")

        self.chk_batch_backup = QCheckBox("Створювати бэкап перед пакетними операціями")
        
        self.spin_max_files = QSpinBox()
        self.spin_max_files.setRange(3, 100)
        self.spin_max_files.setSuffix(" файлів")

        form_lay.addRow(self.chk_auto_backup)
        form_lay.addRow("Періодичність:", self.spin_interval)
        form_lay.addRow(self.chk_batch_backup)
        form_lay.addRow("Зберігати не більше:", self.spin_max_files)

        layout.addWidget(gb_backup)

        # Завантаження збережених значень
        self.chk_auto_backup.setChecked(self.settings.value("auto_backup_enabled", True, type=bool))
        self.spin_interval.setValue(self.settings.value("auto_backup_interval", 15, type=int))
        self.chk_batch_backup.setChecked(self.settings.value("backup_before_batch", True, type=bool))
        self.spin_max_files.setValue(self.settings.value("max_backup_files", 20, type=int))

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.save_settings)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def save_settings(self):
        self.settings.setValue("auto_backup_enabled", self.chk_auto_backup.isChecked())
        self.settings.setValue("auto_backup_interval", self.spin_interval.value())
        self.settings.setValue("backup_before_batch", self.chk_batch_backup.isChecked())
        self.settings.setValue("max_backup_files", self.spin_max_files.value())
        self.accept()
