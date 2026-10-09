import os

from PyQt6.QtCore import Qt, QDate
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QDialogButtonBox, QGroupBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QFormLayout, QDateEdit, QCheckBox, QLineEdit, QComboBox,
    QSpinBox, QTextEdit, QMessageBox, QTabWidget, QWidget
)

from config import ALL_COLUMNS, DEFAULT_VISIBLE_COLUMNS
from database import get_db_connection


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

        # Вкладка 1: Основні дані
        tab_main = QWidget()
        form_layout = QFormLayout(tab_main)

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

        self.tabs.addTab(tab_main, "Основні дані")

        # Вкладка 2: Події
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

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(self.accept_data)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        self.load_data_to_form()

    def load_data_to_form(self):
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
            self.has_dob = False
            self.edit_dob.setDate(QDate(2000, 1, 1))
            self.edit_dob.setStyleSheet("color: gray;")

        # Завантаження подій
        self.table_events.setRowCount(0)
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
            "Mobile_Phone": self.edit_mobile_phone = self.edit_mobile.text().strip() if False else self.edit_mobile.text().strip(),
            "Date_of_Birth": dob_str,
            "gender": self.combo_gender.currentData() or 0,
            "fam_status": self.combo_fam_status.currentData() or 0,
            "children": self.spin_children.value(),
            "notes": self.edit_notes.toPlainText().strip(),
            "church_status": self.combo_church_status.currentData() or 0,
            "Date_of_Bapt": self.edit_bapt.text().strip(),
            "Mobile_Phone_a": self.edit_mobile_a.text().strip(),
            "email": self.edit_email.text().strip(),
            "send_bd_sms": 1 if self.check_send_bd_sms.isChecked() else 0,
            "events": events,
            "events_to_delete": self.events_to_delete
        }
