from reportlab.lib import colors

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
        "desc": "Фіксований формат А5. 3 плитки на сторінку, ширина фотографії залежить від висоти картки."
    },
    "compact": {
        "name": "Компактний",
        "desc": "Таблиця формату А4 без фотографій. Оптимізована ширина колонок, номери телефонів без розриву, об'єднані статуси."
    }
}
