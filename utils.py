import io
import os
from PIL import Image

from PyQt6.QtGui import QColor
from reportlab.platypus import Image as RLImage
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from config import UKRAINIAN_ORDER


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
