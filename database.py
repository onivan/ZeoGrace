import sqlite3
from utils import ukrainian_sort_key


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
