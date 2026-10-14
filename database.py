import os
import shutil
import sqlite3
from datetime import datetime
from utils import ukrainian_sort_key


def ukrainian_collation(str1: str, str2: str) -> int:
    k1 = ukrainian_sort_key(str1)
    k2 = ukrainian_sort_key(str2)
    if k1 < k2:
        return -1
    elif k1 > k2:
        return 1
    return 0


def get_db_connection(db_path: str) -> sqlite3.Connection:
    abs_path = os.path.abspath(db_path)
    conn = sqlite3.connect(abs_path)
    conn.create_collation("UKRAINIAN", ukrainian_collation)
    return conn


def init_db(db_path: str):
    """Створення повного каркасу таблиць бази даних та заповнення базових класифікаторів."""
    with get_db_connection(db_path) as conn:
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

            CREATE TABLE IF NOT EXISTS list_kinship_types (
                id         INTEGER   PRIMARY KEY AUTOINCREMENT UNIQUE NOT NULL,
                list_name  CHAR (50) NOT NULL,
                opposite_m INTEGER   DEFAULT (0),
                opposite_f INTEGER   DEFAULT (0)
            );

            CREATE TABLE IF NOT EXISTS p_kinship (
                id          INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
                person1_id  INTEGER NOT NULL REFERENCES people (id) ON DELETE CASCADE,
                person2_id  INTEGER NOT NULL REFERENCES people (id) ON DELETE CASCADE,
                kin_type_id INTEGER NOT NULL REFERENCES list_kinship_types (id) ON DELETE CASCADE,
                descr       TEXT,
                UNIQUE(person1_id, person2_id) ON CONFLICT REPLACE
            );
        """)

        cur.execute("SELECT COUNT(*) FROM list_kinship_types")
        if cur.fetchone()[0] == 0:
            kinship_defaults = [
                (1, "Чоловік", 0, 2),
                (2, "Дружина", 1, 0),
                (3, "Батько", 5, 6),
                (4, "Мати", 5, 6),
                (5, "Син", 3, 4),
                (6, "Донька", 3, 4),
                (7, "Брат", 7, 8),
                (8, "Сестра", 7, 8),
                (9, "Дядько", 11, 12),
                (10, "Тітка", 11, 12),
                (11, "Племінник", 9, 10),
                (12, "Племінниця", 9, 10),
                (13, "Дідусь", 15, 16),
                (14, "Бабуся", 15, 16),
                (15, "Онук", 13, 14),
                (16, "Онука", 13, 14)
            ]
            cur.executemany(
                "INSERT INTO list_kinship_types (id, list_name, opposite_m, opposite_f) VALUES (?, ?, ?, ?)",
                kinship_defaults
            )

        conn.commit()


import glob

def backup_database(db_path, prefix="backup", max_files=20):
    """
    Створює резервну копію бази даних та видаляє найстаріші копії,
    якщо їх кількість перевищує max_files.
    """
    if not db_path or not os.path.exists(db_path):
        return None

    try:
        backup_dir = os.path.join(os.path.dirname(os.path.abspath(db_path)), "backups")
        os.makedirs(backup_dir, exist_ok=True)

        db_name = os.path.splitext(os.path.basename(db_path))[0]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{db_name}_{prefix}_{timestamp}.db"
        backup_path = os.path.join(backup_dir, backup_filename)

        # Копіювання файлу
        shutil.copy2(db_path, backup_path)

        # Ротація старих файлів
        pattern = os.path.join(backup_dir, f"{db_name}_*.db")
        existing_backups = sorted(glob.glob(pattern), key=os.path.getmtime)

        if len(existing_backups) > max_files:
            files_to_delete = existing_backups[:-max_files]
            for f in files_to_delete:
                try:
                    os.remove(f)
                except Exception:
                    pass

        return backup_path
    except Exception as e:
        print(f"Помилка створення резервної копії: {e}")
        return None


def _get_person_gender(conn, person_id: int) -> int:
    cur = conn.cursor()
    cur.execute("SELECT gender FROM people WHERE id = ?", (person_id,))
    row = cur.fetchone()
    return row[0] if row and row[0] else 0


def _get_opposite_kin_type(conn, kin_type_id: int, source_person_id: int) -> int:
    gender = _get_person_gender(conn, source_person_id)
    cur = conn.cursor()
    cur.execute("SELECT opposite_m, opposite_f FROM list_kinship_types WHERE id = ?", (kin_type_id,))
    opp_row = cur.fetchone()
    if not opp_row:
        return None
    opp_m, opp_f = opp_row
    return opp_m if gender == 1 else (opp_f if opp_f else opp_m)


def set_kinship_relation(db_path: str, person1_id: int, person2_id: int, kin_type_id: int, descr: str = "", conn=None):
    """
    Встановлює родинний зв'язок person1 -> person2,
    автоматично створює зворотний зв'язок person2 -> person1,
    а також каскадно виводить непрямі зв'язки.
    """
    if person1_id == person2_id:
        return

    should_close = False
    if conn is None:
        conn = get_db_connection(db_path)
        should_close = True

    try:
        cur = conn.cursor()

        # 1. Прямий зв'язок p1 -> p2
        cur.execute("""
            INSERT OR REPLACE INTO p_kinship (person1_id, person2_id, kin_type_id, descr)
            VALUES (?, ?, ?, ?)
        """, (person1_id, person2_id, kin_type_id, descr))

        # 2. Зворотний зв'язок p2 -> p1
        opp_type = _get_opposite_kin_type(conn, kin_type_id, person1_id)
        if opp_type:
            cur.execute("""
                INSERT OR REPLACE INTO p_kinship (person1_id, person2_id, kin_type_id, descr)
                VALUES (?, ?, ?, ?)
            """, (person2_id, person1_id, opp_type, descr))

        # 3. КАСКАДНЕ ВИВЕДЕННЯ НЕПРЯМИХ ЗВ'ЯЗКІВ
        if kin_type_id in (3, 4):
            parent_id = person2_id
            child_id = person1_id

            cur.execute("SELECT person2_id, kin_type_id FROM p_kinship WHERE person1_id = ?", (parent_id,))
            parent_relatives = cur.fetchall()

            for rel_id, rel_kin_type in parent_relatives:
                if rel_id == child_id:
                    continue

                if rel_kin_type in (3, 4):
                    grandparent_id = rel_id
                    gp_gender = _get_person_gender(conn, grandparent_id)
                    gp_kin_type = 13 if gp_gender == 1 else 14

                    cur.execute("INSERT OR IGNORE INTO p_kinship (person1_id, person2_id, kin_type_id, descr) VALUES (?, ?, ?, ?)",
                                (child_id, grandparent_id, gp_kin_type, "Автоматично через батьків"))

                    ch_gender = _get_person_gender(conn, child_id)
                    gc_kin_type = 15 if ch_gender == 1 else 16
                    cur.execute("INSERT OR IGNORE INTO p_kinship (person1_id, person2_id, kin_type_id, descr) VALUES (?, ?, ?, ?)",
                                (grandparent_id, child_id, gc_kin_type, "Автоматично через онуків"))

                elif rel_kin_type in (7, 8):
                    uncle_aunt_id = rel_id
                    ua_gender = _get_person_gender(conn, uncle_aunt_id)
                    ua_kin_type = 9 if ua_gender == 1 else 10

                    cur.execute("INSERT OR IGNORE INTO p_kinship (person1_id, person2_id, kin_type_id, descr) VALUES (?, ?, ?, ?)",
                                (child_id, uncle_aunt_id, ua_kin_type, "Автоматично через батьків"))

                    ch_gender = _get_person_gender(conn, child_id)
                    nib_kin_type = 11 if ch_gender == 1 else 12
                    cur.execute("INSERT OR IGNORE INTO p_kinship (person1_id, person2_id, kin_type_id, descr) VALUES (?, ?, ?, ?)",
                                (uncle_aunt_id, child_id, nib_kin_type, "Автоматично через брата/сестру"))

                elif rel_kin_type in (5, 6):
                    sibling_id = rel_id
                    sib_gender = _get_person_gender(conn, sibling_id)
                    sib_kin_type = 7 if sib_gender == 1 else 8

                    cur.execute("INSERT OR IGNORE INTO p_kinship (person1_id, person2_id, kin_type_id, descr) VALUES (?, ?, ?, ?)",
                                (child_id, sibling_id, sib_kin_type, "Спільні батьки"))

                    ch_gender = _get_person_gender(conn, child_id)
                    my_sib_kin_type = 7 if ch_gender == 1 else 8
                    cur.execute("INSERT OR IGNORE INTO p_kinship (person1_id, person2_id, kin_type_id, descr) VALUES (?, ?, ?, ?)",
                                (sibling_id, child_id, my_sib_kin_type, "Спільні батьки"))

        elif kin_type_id in (5, 6):
            child_id = person2_id
            parent_id = person1_id
            p_gender = _get_person_gender(conn, parent_id)
            p_kin_type = 3 if p_gender == 1 else 4

            cur.execute("SELECT COUNT(*) FROM p_kinship WHERE person1_id = ? AND person2_id = ?", (child_id, parent_id))
            if cur.fetchone()[0] == 0:
                conn.commit()
                # Передаємо існуюче з'єднання `conn` у рекурсивний виклик
                set_kinship_relation(db_path, child_id, parent_id, p_kin_type, descr, conn=conn)
                return

        conn.commit()
    finally:
        if should_close:
            conn.close()


def remove_kinship_relation(db_path: str, person1_id: int, person2_id: int):
    """Видаляє взаємний родинний зв'язок між двома людьми."""
    with get_db_connection(db_path) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM p_kinship WHERE person1_id = ? AND person2_id = ?", (person1_id, person2_id))
        cur.execute("DELETE FROM p_kinship WHERE person1_id = ? AND person2_id = ?", (person2_id, person1_id))
        conn.commit()


def find_potential_marriages(db_path: str):
    """
    Аналізує базу даних та шукає потенційні шлюбні пари за критеріями:
    1. Різна стать (чоловік та жінка).
    2. Однакові або узгоджені за статтю прізвища, але різні по батькові.
    3. Однакова дата події типу 'Шлюб' або 'Весілля'.
    4. Враховує сімейний статус (розведений/розлучена).
    """
    candidates = []

    with get_db_connection(db_path) as conn:
        cur = conn.cursor()

        # 1. Знаходимо ID типів подій "Шлюб" або "Весілля"
        cur.execute("SELECT id FROM list_event_type WHERE LOWER(list_name) LIKE '%шлюб%' OR LOWER(list_name) LIKE '%весілля%'")
        marriage_event_rows = cur.fetchall()
        if not marriage_event_rows:
            return []
        marriage_event_type_ids = [r[0] for r in marriage_event_rows]
        placeholders_ev = ",".join("?" * len(marriage_event_type_ids))

        # 2. Отримуємо чоловіків (gender=1) та жінок (gender=2) разом із сімейним статусом
        query_men = f"""
            SELECT p.id, p.name, e.eventdate, e.descr, fs.list_name
            FROM people p
            JOIN p_events e ON p.id = e.people_id
            LEFT JOIN list_family_status fs ON p.fam_status = fs.id
            WHERE p.gender = 1 AND e.eventtype IN ({placeholders_ev})
        """
        cur.execute(query_men, marriage_event_type_ids)
        men_events = cur.fetchall()

        query_women = f"""
            SELECT p.id, p.name, e.eventdate, e.descr, fs.list_name
            FROM people p
            JOIN p_events e ON p.id = e.people_id
            LEFT JOIN list_family_status fs ON p.fam_status = fs.id
            WHERE p.gender = 2 AND e.eventtype IN ({placeholders_ev})
        """
        cur.execute(query_women, marriage_event_type_ids)
        women_events = cur.fetchall()

        def parse_full_name(full_name: str):
            parts = (full_name or "").strip().split()
            surname = parts[0] if len(parts) > 0 else ""
            firstname = parts[1] if len(parts) > 1 else ""
            patronymic = parts[2] if len(parts) > 2 else ""
            return surname, firstname, patronymic

        # 3. Порівнюємо записи
        for m_id, m_name, m_date, m_descr, m_fam_name in men_events:
            m_surname, m_first, m_patronymic = parse_full_name(m_name)
            if not m_surname:
                continue

            for w_id, w_name, w_date, w_descr, w_fam_name in women_events:
                if m_id == w_id:
                    continue

                if m_date != w_date or not m_date or m_date == "1900-01-01":
                    continue

                w_surname, w_first, w_patronymic = parse_full_name(w_name)

                surname_match = (
                    m_surname.lower() == w_surname.lower() or
                    _adapt_surname_for_gender(m_surname, 2).lower() == w_surname.lower() or
                    _adapt_surname_for_gender(w_surname, 1).lower() == m_surname.lower()
                )

                if not surname_match:
                    continue

                if m_patronymic and w_patronymic and m_patronymic.lower() == w_patronymic.lower():
                    continue

                cur.execute("""
                    SELECT k.kin_type_id, t.list_name 
                    FROM p_kinship k
                    JOIN list_kinship_types t ON k.kin_type_id = t.id
                    WHERE k.person1_id = ? AND k.person2_id = ?
                """, (m_id, w_id))
                existing = cur.fetchone()

                # Перевіряємо, чи вказано статус "розведений" / "розлучений"
                m_div = ("розвед" in (m_fam_name or "").lower()) or ("розлуч" in (m_fam_name or "").lower())
                w_div = ("розвед" in (w_fam_name or "").lower()) or ("розлуч" in (w_fam_name or "").lower())
                is_divorced = m_div or w_div

                candidates.append({
                    "m_id": m_id,
                    "m_name": m_name,
                    "m_fam_name": m_fam_name or "",
                    "w_id": w_id,
                    "w_name": w_name,
                    "w_fam_name": w_fam_name or "",
                    "date": m_date,
                    "is_divorced": is_divorced,
                    "existing_kin_id": existing[0] if existing else None,
                    "existing_kin_name": existing[1] if existing else None
                })

    return candidates


def auto_detect_marriages(db_path: str) -> int:
    """
    Аналізує базу даних і автоматично створює родинні зв'язки "Чоловік" / "Дружина"
    для пар чоловік-жінка.
    """
    candidates = find_potential_marriages(db_path)
    created_count = 0

    wife_kin_id = 2
    if db_path and os.path.exists(db_path):
        try:
            with get_db_connection(db_path) as conn:
                cur = conn.cursor()
                cur.execute("SELECT id FROM list_kinship_types WHERE LOWER(list_name) = 'дружина'")
                row = cur.fetchone()
                if row and row[0]:
                    wife_kin_id = row[0]
        except Exception:
            pass

    for cand in candidates:
        if cand["existing_kin_id"] is None:
            # Передаємо wife_kin_id (2) від чоловіка do дружини
            set_kinship_relation(
                db_path,
                cand["m_id"],
                cand["w_id"],
                wife_kin_id,
                f"Автоматично за подією шлюбу від {cand['date']}"
            )
            created_count += 1

    return created_count


def _parse_full_name(full_name: str):
    parts = (full_name or "").strip().split()
    surname = parts[0] if len(parts) > 0 else ""
    firstname = parts[1] if len(parts) > 1 else ""
    patronymic = parts[2] if len(parts) > 2 else ""
    return surname, firstname, patronymic


MALE_NAME_EXCEPTIONS = {
    "микола", "ілля", "микита", "сава", "кузьма", "ярема", 
    "хома", "фома", "лука", "льова", "паша", "саша", "женя", "ваня"
}


def _determine_gender_by_name_and_text(firstname: str, descr_text: str) -> int:
    """Визначає стать дитини (1 - чоловік, 2 - жінка) за ім'ям та текстом події."""
    text_lower = (descr_text or "").lower()
    first_lower = (firstname or "").lower()

    # 1. Перевірка за ключовими словами в описі події
    if any(w in text_lower for w in ["донька", "дочка", "доня", "дівчинка", "народилася", "народилась"]):
        return 2
    if any(w in text_lower for w in ["син", "хлопчик", "народився"]):
        return 1

    # 2. Перевірка за ім'ям дитини
    if first_lower in MALE_NAME_EXCEPTIONS:
        return 1
    if first_lower in {"любов", "нінель", "жанет"}:
        return 2
    if first_lower.endswith("а") or first_lower.endswith("я"):
        return 2

    return 1


def _infer_child_info_from_event(descr: str):
    """Визначає ім'я та стать дитини з опису події."""
    text = (descr or "").strip()
    words = text.split()
    stop_words = {
        "народився", "народилась", "народилася", "родився", "родилась", "родилася",
        "син", "донька", "дочка", "доня", "дівчинка", "дитина", "в", "на", "року", "р.",
        "день", "народження"
    }
    clean_words = [w.strip(".,!?:;\"'()") for w in words if w.lower().strip(".,!?:;\"'()") not in stop_words]

    child_firstname = clean_words[0].capitalize() if clean_words else "Дитина"
    gender = _determine_gender_by_name_and_text(child_firstname, text)

    return child_firstname, gender


def _infer_patronymic_from_father(father_firstname: str, child_gender: int) -> str:
    """Генерує по-батькові на основі імені батька та статі дитини (1 - чоловік, 2 - жінка)."""
    name = (father_firstname or "").strip()
    if not name:
        return ""

    name_lower = name.lower()

    # Винятки правил утворення по-батькові
    if name_lower == "ілля":
        return "Ілліч" if child_gender == 1 else "Іллівна"
    if name_lower == "кузьма":
        return "Кузьмич" if child_gender == 1 else "Кузьмівна"
    if name_lower in ("хома", "лука", "сава"):
        return (name[:-1] + ("ич" if name_lower != "сава" else "ч")) if child_gender == 1 else (name[:-1] + "вівна" if name_lower == "сава" else name[:-1] + "івна")
    if name_lower == "микола":
        return "Миколайович" if child_gender == 1 else "Миколаївна"
    if name_lower == "яків":
        return "Якович" if child_gender == 1 else "Яківна"
    if name_lower == "ігор":
        return "Ігорович" if child_gender == 1 else "Ігорівна"

    # Чоловіче по-батькові (child_gender == 1)
    if child_gender == 1:
        if name_lower.endswith("ій"):
            return name[:-2] + "ійович"
        elif name_lower.endswith("й"):
            return name[:-1] + "йович"
        elif name_lower.endswith("а") or name_lower.endswith("я"):
            return name[:-1] + "ович"
        elif name_lower.endswith("о"):
            return name[:-1] + "ович"
        elif name_lower.endswith("ь"):
            return name[:-1] + "ьович"
        else:
            return name + "ович"

    # Жіноче по-батькові (child_gender == 2)
    else:
        if name_lower.endswith("ій"):
            return name[:-2] + "іївна"
        elif name_lower.endswith("й"):
            return name[:-1] + "ївна"
        elif name_lower.endswith("а") or name_lower.endswith("я"):
            return name[:-1] + "івна"
        elif name_lower.endswith("о"):
            return name[:-1] + "івна"
        elif name_lower.endswith("ь"):
            return name[:-1] + "івна"
        else:
            return name + "івна"


def _adapt_surname_for_gender(surname: str, target_gender: int) -> str:
    """Адаптує закінчення прізвища за статтю (наприклад: Ковальський <-> Ковальська)."""
    s = (surname or "").strip()
    if not s:
        return ""
    if target_gender == 2:  # Жіноча стать
        if s.endswith("ський"): return s[:-5] + "ська"
        if s.endswith("цький"): return s[:-5] + "цька"
        if s.endswith("зький"): return s[:-5] + "зька"
        if s.endswith("ий"): return s[:-2] + "а"
        if s.endswith(("ов", "ев", "єв", "ін", "ін")): return s + "а"
    elif target_gender == 1:  # Чоловіча стать
        if s.endswith("ська"): return s[:-4] + "ський"
        if s.endswith("цька"): return s[:-4] + "цький"
        if s.endswith("зька"): return s[:-4] + "зький"
        if s.endswith(("ова", "ева", "єва", "іна")): return s[:-1]
    return s




def find_potential_children(db_path: str):
    """
    Аналізує базу даних і шукає потенційних дітей для існуючих осіб або пар батьків.
    Враховує ТІЛЬКИ події типу 'дитина' та виключає власні Дні народження осіб.
    """
    candidates_map = {}

    with get_db_connection(db_path) as conn:
        cur = conn.cursor()

        # 1. Отримуємо всі існуючі шлюбні зв'язки (чоловік <-> дружина)
        spouses = {}
        cur.execute("SELECT person1_id, person2_id FROM p_kinship WHERE kin_type_id IN (1, 2)")
        for p1, p2 in cur.fetchall():
            spouses[p1] = p2

        # 1. ВРАХОВУЄМО ТІЛЬКИ ТИПИ ПОДІЙ, ЩО МІСТЯТЬ 'дитин' (без персональних ДН)
        cur.execute("""
            SELECT id FROM list_event_type 
            WHERE LOWER(list_name) LIKE '%дитин%'
        """)
        event_type_ids = [r[0] for r in cur.fetchall()]

        # 3. Зчитуємо список усіх людей
        cur.execute("SELECT id, name, gender, address, Date_of_Birth FROM people")
        all_people = cur.fetchall()
        people_dict = {p[0]: p for p in all_people}

        # А. Збираємо всі події про дітей та групуємо їх за ключем дитини: (child_first_lower, child_gender, event_date)
        event_groups = {}

        if event_type_ids:
            placeholders = ",".join("?" * len(event_type_ids))
            cur.execute(f"""
                SELECT e.people_id, e.eventdate, e.descr
                FROM p_events e
                WHERE e.eventtype IN ({placeholders})
            """, event_type_ids)
            child_events = cur.fetchall()

            for parent_id, event_date, descr in child_events:
                if not parent_id or parent_id not in people_dict:
                    continue

                # Додатковий захист від опису "День народження"
                descr_clean = (descr or "").lower()
                if "день народження" in descr_clean or descr_clean.strip() == "народження":
                    continue

                child_first, child_gender = _infer_child_info_from_event(descr)
                date_str = (event_date[:10] if event_date else "").strip()

                if date_str and date_str != "1900-01-01" and child_first and child_first not in ("Дитина", "День"):
                    group_key = (child_first.lower(), child_gender, date_str)
                else:
                    group_key = (parent_id, child_first.lower(), child_gender, descr)

                if group_key not in event_groups:
                    event_groups[group_key] = []
                event_groups[group_key].append((parent_id, event_date, descr, child_first, child_gender))

        # Обробляємо кожну згруповану дитячу подію
        for group_key, ev_list in event_groups.items():
            parent_ids_set = set()
            for pid, edate, descr, c_first, c_gender in ev_list:
                parent_ids_set.add(pid)
                if pid in spouses:
                    parent_ids_set.add(spouses[pid])

            parent_ids = list(parent_ids_set)

            fathers = [people_dict[pid] for pid in parent_ids if people_dict[pid][2] == 1]
            mothers = [people_dict[pid] for pid in parent_ids if people_dict[pid][2] == 2]

            father_info = fathers[0] if fathers else None
            mother_info = mothers[0] if mothers else None

            # Формуємо відображення імен батьків
            if father_info and mother_info:
                parents_display = f"{father_info[1]} та {mother_info[1]}"
            elif father_info:
                parents_display = father_info[1]
            elif mother_info:
                parents_display = mother_info[1]
            else:
                parents_display = people_dict[parent_ids[0]][1]

            # Перевіряємо, чи є офіційний шлюбний зв'язок між батьками
            parents_married = False
            if father_info and mother_info:
                parents_married = (spouses.get(father_info[0]) == mother_info[0])

            _, event_date, descr, child_first, child_gender = ev_list[0]

            ref_parent = father_info if father_info else (mother_info if mother_info else people_dict[parent_ids[0]])
            ref_surname, _, _ = _parse_full_name(ref_parent[1])

            matched_person_id = None
            matched_person_name = None

            # Перевіряємо, чи існує така дитина серед записів людей
            for target_id, t_name, t_gender, t_address, t_dob in all_people:
                if target_id in parent_ids:
                    continue

                t_surname, t_first, t_patronymic = _parse_full_name(t_name)
                surname_match = (
                    t_surname.lower() == ref_surname.lower() or
                    _adapt_surname_for_gender(t_surname, ref_parent[2]).lower() == ref_surname.lower()
                )
                firstname_match = (child_first.lower() in t_first.lower() or t_first.lower() in child_first.lower())

                date_match = False
                if event_date and t_dob and event_date != "1900-01-01" and t_dob != "1900-01-01":
                    date_match = (event_date[:10] == t_dob[:10])

                if surname_match and (firstname_match or date_match):
                    matched_person_id = target_id
                    matched_person_name = t_name
                    child_gender = t_gender or child_gender
                    break

            if matched_person_id:
                dedup_key = ("existing", matched_person_id)
                if dedup_key not in candidates_map:
                    existing_kin_id, existing_kin_name = None, None
                    for pid in parent_ids:
                        cur.execute("""
                            SELECT k.kin_type_id, t.list_name 
                            FROM p_kinship k
                            JOIN list_kinship_types t ON k.kin_type_id = t.id
                            WHERE k.person1_id = ? AND k.person2_id = ?
                        """, (pid, matched_person_id))
                        row = cur.fetchone()
                        if row:
                            existing_kin_id, existing_kin_name = row[0], row[1]
                            break

                    candidates_map[dedup_key] = {
                        "type": "existing",
                        "parent_ids": parent_ids,
                        "parent_name": parents_display,
                        "parents_married": parents_married,
                        "child_id": matched_person_id,
                        "child_name": matched_person_name,
                        "child_gender": child_gender,
                        "date": event_date,
                        "existing_kin_id": existing_kin_id,
                        "existing_kin_name": existing_kin_name
                    }
            else:
                fam_key = tuple(sorted(parent_ids))
                date_str = event_date if event_date != "1900-01-01" else ""
                dedup_key = ("new", fam_key, child_first.lower(), child_gender, date_str[:10])

                if dedup_key not in candidates_map:
                    child_surname = _adapt_surname_for_gender(ref_surname, child_gender)
                    if father_info:
                        _, f_first, _ = _parse_full_name(father_info[1])
                        child_patronymic = _infer_patronymic_from_father(f_first, child_gender)
                    else:
                        child_patronymic = ""

                    full_new_name = f"{child_surname} {child_first} {child_patronymic}".strip()
                    address = ref_parent[3] or ""

                    candidates_map[dedup_key] = {
                        "type": "new_person",
                        "parent_ids": parent_ids,
                        "parent_name": parents_display,
                        "parents_married": parents_married,
                        "child_id": None,
                        "child_name": full_new_name,
                        "child_firstname": child_first,
                        "child_surname": child_surname,
                        "child_patronymic": child_patronymic,
                        "child_gender": child_gender,
                        "date": date_str,
                        "address": address,
                        "existing_kin_id": None,
                        "existing_kin_name": None
                    }

        # 2. АНАЛІЗ ЗА ПРІЗВИЩЕМ ТА ПО БАТЬКОВІ (ДЛЯ ІСНУЮЧИХ ЗАПИСІВ В БАЗІ)
        for p_id, p_name, p_gender, p_address, p_dob in all_people:
            if p_gender != 1 or not p_dob or p_dob == "1900-01-01":
                continue
            p_surname, p_first, _ = _parse_full_name(p_name)
            try:
                p_year = int(p_dob[:4])
            except ValueError:
                continue

            spouse_id = spouses.get(p_id)
            parent_ids = [p_id]
            if spouse_id:
                parent_ids.append(spouse_id)

            father_info = people_dict.get(p_id)
            mother_info = people_dict.get(spouse_id) if spouse_id else None

            if father_info and mother_info:
                parents_display = f"{father_info[1]} та {mother_info[1]}"
                parents_married = True
            else:
                parents_display = father_info[1]
                parents_married = False

            for c_id, c_name, c_gender, c_address, c_dob in all_people:
                if c_id in parent_ids or not c_dob or c_dob == "1900-01-01":
                    continue
                try:
                    c_year = int(c_dob[:4])
                except ValueError:
                    continue

                if not (15 <= c_year - p_year <= 60):
                    continue

                c_surname, c_first, c_patronymic = _parse_full_name(c_name)
                stem = _infer_patronymic_from_father(p_first, 1)[:4].lower()

                if (c_surname.lower() == p_surname.lower() or _adapt_surname_for_gender(c_surname, 1).lower() == p_surname.lower()) and (stem in c_patronymic.lower()):
                    dedup_key = ("existing", c_id)
                    if dedup_key not in candidates_map:
                        existing_kin_id, existing_kin_name = None, None
                        for pid in parent_ids:
                            cur.execute("""
                                SELECT k.kin_type_id, t.list_name 
                                FROM p_kinship k
                                JOIN list_kinship_types t ON k.kin_type_id = t.id
                                WHERE k.person1_id = ? AND k.person2_id = ?
                            """, (pid, c_id))
                            row = cur.fetchone()
                            if row:
                                existing_kin_id, existing_kin_name = row[0], row[1]
                                break

                        candidates_map[dedup_key] = {
                            "type": "existing",
                            "parent_ids": parent_ids,
                            "parent_name": parents_display,
                            "parents_married": parents_married,
                            "child_id": c_id,
                            "child_name": c_name,
                            "child_gender": c_gender,
                            "date": c_dob,
                            "existing_kin_id": existing_kin_id,
                            "existing_kin_name": existing_kin_name
                        }

    return list(candidates_map.values())


def create_person_record(db_path: str, name: str, gender: int, dob: str, address: str) -> int:
    """Створює новий запис особи в базі даних та повертає її новий ID."""
    with get_db_connection(db_path) as conn:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO people (name, gender, Date_of_Birth, address)
            VALUES (?, ?, ?, ?)
        """, (name, gender, dob or "1900-01-01", address or ""))
        new_id = cur.lastrowid

        # Автоматично додаємо подію "Народження"
        if dob and dob != "1900-01-01":
            cur.execute("SELECT id FROM list_event_type WHERE LOWER(list_name) LIKE '%народжен%' LIMIT 1")
            row = cur.fetchone()
            ev_type_id = row[0] if row else 0
            cur.execute("""
                INSERT INTO p_events (people_id, eventdate, eventtype, descr)
                VALUES (?, ?, ?, ?)
            """, (new_id, dob, ev_type_id, "День народження"))

        conn.commit()
        return new_id


def find_extended_kinship_candidates(db_path):
    """
    Аналізує базу даних для виявлення потенційних родинних зв'язків:
    - Дідусі / Бабусі
    - Брати / Сестри
    - Дядьки / Тітки
    - Двоюрідні брати / сестри
    
    Повертає список словників з кандидатами.
    """
    if not db_path or not os.path.exists(db_path):
        return []

    candidates = []

    with get_db_connection(db_path) as conn:
        cur = conn.cursor()

        # 1. Завантажуємо всіх людей
        cur.execute("SELECT id, name, gender, Date_of_Birth, address FROM people")
        people = {}
        for pid, name, gender, dob, addr in cur.fetchall():
            sname, fname, pat = _parse_full_name(name or "")
            people[pid] = {
                "id": pid,
                "name": name or "",
                "gender": gender or 0,
                "dob": str(dob or "").strip(),
                "address": (addr or "").strip(),
                "surname": sname,
                "firstname": fname,
                "patronymic": pat
            }

        # 2. Завантажуємо існуючі родинні зв'язки з p_kinship
        cur.execute("SELECT person1_id, person2_id, kin_type_id FROM p_kinship")
        existing_kin = {}
        for p1, p2, ktype in cur.fetchall():
            existing_kin[(p1, p2)] = ktype

        # Картування батьків для кожної особи: pid -> set(parent_ids)
        # kin_type_id: 3 (батько), 4 (мати). Також від kin_type_id 5, 6 (син/донька) навпаки
        parents_of = {pid: set() for pid in people}
        children_of = {pid: set() for pid in people}

        for (p1, p2), ktype in existing_kin.items():
            if ktype in (3, 4):  # p2 є батьком/матір'ю для p1
                parents_of[p1].add(p2)
                children_of[p2].add(p1)
            elif ktype in (5, 6):  # p2 є дитиною для p1
                children_of[p1].add(p2)
                parents_of[p2].add(p1)

        # 3. Визначення типів зв'язків у довіднику
        cur.execute("SELECT id, LOWER(list_name) FROM list_kinship_types")
        kin_type_lookup = {}
        for kt_id, kt_name in cur.fetchall():
            kin_type_lookup[kt_id] = kt_name

        def get_kin_id_by_name(target_name):
            for kt_id, kt_name in kin_type_lookup.items():
                if target_name in kt_name:
                    return kt_id
            return None

        id_grandpa = get_kin_id_by_name("дідусь") or 13
        id_grandma = get_kin_id_by_name("бабуся") or 14
        id_brother = get_kin_id_by_name("брат") or 7
        id_sister = get_kin_id_by_name("сестра") or 8
        id_uncle = get_kin_id_by_name("дядько") or 9
        id_aunt = get_kin_id_by_name("тітка") or 10
        id_cousin_m = get_kin_id_by_name("двоюрідний брат") or 11
        id_cousin_f = get_kin_id_by_name("двоюрідна сестра") or 12

        visited_pairs = set()

        def add_candidate(p1_id, p2_id, target_kin_id, target_kin_name, reason):
            pair_key = (p1_id, p2_id, target_kin_id)
            if pair_key in visited_pairs:
                return
            visited_pairs.add(pair_key)

            exist_k = existing_kin.get((p1_id, p2_id))
            exist_k_name = kin_type_lookup.get(exist_k, "") if exist_k else None

            candidates.append({
                "person1_id": p1_id,
                "person1_name": people[p1_id]["name"],
                "person2_id": p2_id,
                "person2_name": people[p2_id]["name"],
                "target_kin_id": target_kin_id,
                "target_kin_name": target_kin_name,
                "existing_kin_id": exist_k,
                "existing_kin_name": exist_k_name,
                "reason": reason
            })

        # --- АНАЛІЗ 1: Брати та сестри (спільні батьки) ---
        siblings_map = {pid: set() for pid in people}
        for pid, p_parents in parents_of.items():
            if not p_parents:
                continue
            for other_id, o_parents in parents_of.items():
                if pid >= other_id:
                    continue
                shared = p_parents.intersection(o_parents)
                if shared:
                    siblings_map[pid].add(other_id)
                    siblings_map[other_id].add(pid)

                    # Для p1 людина p2 є...
                    gender2 = people[other_id]["gender"]
                    k_id = id_brother if gender2 == 1 else id_sister
                    k_name = "Брат" if gender2 == 1 else "Сестра"
                    add_candidate(pid, other_id, k_id, k_name, "Спільні батьки у базі")

                    gender1 = people[pid]["gender"]
                    k_id1 = id_brother if gender1 == 1 else id_sister
                    k_name1 = "Брат" if gender1 == 1 else "Сестра"
                    add_candidate(other_id, pid, k_id1, k_name1, "Спільні батьки у базі")

        # --- АНАЛІЗ 2: Брати та сестри за по батькові та прізвищем (якщо батьки ще не вказані) ---
        for pid1, p1 in people.items():
            for pid2, p2 in people.items():
                if pid1 >= pid2:
                    continue
                if pid2 in siblings_map[pid1]:
                    continue  # вже знайдені через прямих батьків

                if p1["patronymic"] and p2["patronymic"] and p1["patronymic"].lower() == p2["patronymic"].lower():
                    # Перевірка прізвища з урахуванням роду
                    sn1 = p1["surname"]
                    sn2 = p2["surname"]
                    if sn1 and sn2:
                        match_sn = (
                            sn1.lower() == sn2.lower() or
                            _adapt_surname_for_gender(sn1, p2["gender"]).lower() == sn2.lower() or
                            _adapt_surname_for_gender(sn2, p1["gender"]).lower() == sn1.lower()
                        )
                        if match_sn:
                            siblings_map[pid1].add(pid2)
                            siblings_map[pid2].add(pid1)

                            k_id = id_brother if p2["gender"] == 1 else id_sister
                            k_name = "Брат" if p2["gender"] == 1 else "Сестра"
                            add_candidate(pid1, pid2, k_id, k_name, f"Збіг по батькові ('{p1['patronymic']}') та прізвища")

                            k_id1 = id_brother if p1["gender"] == 1 else id_sister
                            k_name1 = "Брат" if p1["gender"] == 1 else "Сестра"
                            add_candidate(pid2, pid1, k_id1, k_name1, f"Збіг по батькові ('{p2['patronymic']}') та прізвища")

        # --- АНАЛІЗ 3: Дідусі та бабусі ---
        for child_id, p_set in parents_of.items():
            for parent_id in p_set:
                grandparents = parents_of.get(parent_id, set())
                for gp_id in grandparents:
                    gp_gender = people[gp_id]["gender"]
                    k_id = id_grandpa if gp_gender == 1 else id_grandma
                    k_name = "Дідусь" if gp_gender == 1 else "Бабуся"
                    add_candidate(child_id, gp_id, k_id, k_name, f"Батько/Мати для {people[parent_id]['name']}")

        # --- АНАЛІЗ 4: Дядьки та тітки (брати/сестри батьків) ---
        for child_id, p_set in parents_of.items():
            for parent_id in p_set:
                p_siblings = siblings_map.get(parent_id, set())
                for sib_id in p_siblings:
                    sib_gender = people[sib_id]["gender"]
                    k_id = id_uncle if sib_gender == 1 else id_aunt
                    k_name = "Дядько" if sib_gender == 1 else "Тітка"
                    add_candidate(child_id, sib_id, k_id, k_name, f"Рідний брат/сестра для {people[parent_id]['name']}")

        # --- АНАЛІЗ 5: Двоюрідні брати та сестри (діти дядьків/тіток) ---
        for child_id, p_set in parents_of.items():
            for parent_id in p_set:
                p_siblings = siblings_map.get(parent_id, set())
                for sib_id in p_siblings:
                    cousins = children_of.get(sib_id, set())
                    for cousin_id in cousins:
                        if cousin_id == child_id:
                            continue
                        c_gender = people[cousin_id]["gender"]
                        k_id = id_cousin_m if c_gender == 1 else id_cousin_f
                        k_name = "Двоюрідний брат" if c_gender == 1 else "Двоюрідна сестра"
                        add_candidate(child_id, cousin_id, k_id, k_name, f"Дитина {people[sib_id]['name']} (дядька/тітки)")

    return candidates
