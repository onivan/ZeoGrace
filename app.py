import io                                                                                                                                                  
import os                                                                                                                                                  
import shutil                                                                                                                                              
import sqlite3                                                                                                                                             
import sys                                                                                                                                                 
from datetime import datetime                                                                                                                              
from PIL import Image                                                                                                                                      
                                                                                                                                                           
from PyQt6.QtCore import Qt                                                                                                                                
from PyQt6.QtGui import QPixmap                                                                                                                            
from PyQt6.QtWidgets import (                                                                                                                              
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,                                                                                          
    QTableWidget, QTableWidgetItem, QPushButton, QLineEdit, QLabel,                                                                                        
    QFileDialog, QMessageBox, QHeaderView, QSplitter                                                                                                       
)                                                                                                                                                          
                                                                                                                                                           
from reportlab.lib.pagesizes import A4                                                                                                                     
from reportlab.lib import colors                                                                                                                           
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage                                                   
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle                                                                                       
from reportlab.pdfgen import canvas                                                                                                                        
                                                                                                                                                           
                                                                                                                                                           
def format_phone(phone: str) -> str:                                                                                                                       
    """Форматування номерів телефонів за прикладом оригінального коду."""                                                                                  
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
        self.setFont("Helvetica", 9)                                                                                                                       
        self.drawRightString(200 * 2.834, 15 * 2.834, f"Сторінка {self._pageNumber} з {page_count}")                                                       
                                                                                                                                                           
                                                                                                                                                           
class ZeoGraceApp(QMainWindow):                                                                                                                            
    def __init__(self, db_path="zeograce.db"):                                                                                                             
        super().__init__()                                                                                                                                 
        self.db_path = db_path                                                                                                                             
        self.selected_person_id = None                                                                                                                     
                                                                                                                                                           
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
        """Резервне копіювання БД (аналог DB_BackUpExecute)."""                                                                                            
        if not os.path.exists(self.db_path):                                                                                                               
            return                                                                                                                                         
                                                                                                                                                           
        base_dir = os.path.dirname(os.path.abspath(self.db_path))                                                                                          
        base_name, ext = os.path.splitext(os.path.basename(self.db_path))                                                                                  
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")                                                                                           
        backup_name = os.path.join(base_dir, f"{base_name}_{timestamp}{ext}")                                                                              
                                                                                                                                                           
        shutil.copy2(self.db_path, backup_name)                                                                                                            
                                                                                                                                                           
        # Ротація старих копій                                                                                                                             
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
                                                                                                                                                           
    # --- Інтерфейс користувача ---                                                                                                                        
                                                                                                                                                           
    def init_ui(self):                                                                                                                                     
        self.setWindowTitle("ZeoGrace (Python Edition)")                                                                                                   
        self.resize(1100, 650)                                                                                                                             
                                                                                                                                                           
        main_widget = QWidget()                                                                                                                            
        self.setCentralWidget(main_widget)                                                                                                                 
        main_layout = QVBoxLayout(main_widget)                                                                                                             
                                                                                                                                                           
        # Верхня панель (пошук та дії)                                                                                                                     
        top_bar = QHBoxLayout()                                                                                                                            
                                                                                                                                                           
        self.search_edit = QLineEdit()                                                                                                                     
        self.search_edit.setPlaceholderText("Пошук за ім'ям, адресою або телефоном...")                                                                    
        self.search_edit.textChanged.connect(self.load_people)                                                                                             
        top_bar.addWidget(self.search_edit)                                                                                                                
                                                                                                                                                           
        btn_this_week = QPushButton("ДН цього тижня")                                                                                                      
        btn_this_week.clicked.connect(self.filter_bd_this_week)                                                                                            
        top_bar.addWidget(btn_this_week)                                                                                                                   
                                                                                                                                                           
        btn_reset = QPushButton("Скинути фільтр")                                                                                                          
        btn_reset.clicked.connect(self.reset_filter)                                                                                                       
        top_bar.addWidget(btn_reset)                                                                                                                       
                                                                                                                                                           
        btn_export_pdf = QPushButton("Експорт у PDF")                                                                                                      
        btn_export_pdf.clicked.connect(self.export_to_pdf)                                                                                                 
        top_bar.addWidget(btn_export_pdf)                                                                                                                  
                                                                                                                                                           
        main_layout.addLayout(top_bar)                                                                                                                     
                                                                                                                                                           
        # Основна робоча область зі спліттером                                                                                                             
        splitter = QSplitter(Qt.Orientation.Horizontal)                                                                                                    
                                                                                                                                                           
        # Таблиця парафіян                                                                                                                                 
        self.table = QTableWidget()                                                                                                                        
        self.table.setColumnCount(6)                                                                                                                       
        self.table.setHorizontalHeaderLabels(["ID", "Ім'я", "Адреса", "Дата нар.", "Мобільний", "Email"])                                                  
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)                                                                 
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)                                                     
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)                                                                         
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)                                                                            
        self.table.itemSelectionChanged.connect(self.on_person_selected)                                                                                   
        splitter.addWidget(self.table)                                                                                                                     
                                                                                                                                                           
        # Права панель для фотографії                                                                                                                      
        photo_panel = QWidget()                                                                                                                            
        photo_layout = QVBoxLayout(photo_panel)                                                                                                            
                                                                                                                                                           
        self.photo_label = QLabel("Немає фото")                                                                                                            
        self.photo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)                                                                                        
        self.photo_label.setFixedSize(260, 320)                                                                                                            
        self.photo_label.setStyleSheet("border: 1px solid #ccc; background-color: #f7f7f7;")                                                               
        photo_layout.addWidget(self.photo_label)                                                                                                           
                                                                                                                                                           
        btn_add_photo = QPushButton("Завантажити фото")                                                                                                    
        btn_add_photo.clicked.connect(self.add_photo)                                                                                                      
        photo_layout.addWidget(btn_add_photo)                                                                                                              
                                                                                                                                                           
        photo_layout.addStretch()                                                                                                                          
        splitter.addWidget(photo_panel)                                                                                                                    
                                                                                                                                                           
        splitter.setSizes([750, 350])                                                                                                                      
        main_layout.addWidget(splitter)                                                                                                                    
                                                                                                                                                           
        # Статус-бар                                                                                                                                       
        self.status_label = QLabel("Готово")                                                                                                               
        self.statusBar().addWidget(self.status_label)                                                                                                      
                                                                                                                                                           
    # --- Логіка роботи з записами ---                                                                                                                     
                                                                                                                                                           
    def load_people(self, query_filter=None, params=None):                                                                                                 
        """Завантаження та фільтрація списку."""                                                                                                           
        self.table.setRowCount(0)                                                                                                                          
        sql = "SELECT id, name, address, Date_of_Birth, Mobile_Phone, email FROM people"                                                                   
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
                if col_idx == 4:  # Телефон                                                                                                                
                    val = format_phone(val)                                                                                                                
                item = QTableWidgetItem(str(val) if val is not None else "")                                                                               
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)                                                                                  
                self.table.setItem(row_idx, col_idx, item)                                                                                                 
                                                                                                                                                           
        self.status_label.setText(f"Записів знайдено: {len(rows)}")                                                                                        
                                                                                                                                                           
    def filter_bd_this_week(self):                                                                                                                         
        """Фільтр днів народження поточного тижня (strftime %W)."""                                                                                        
        condition = "strftime('%W', Date_of_Birth) = strftime('%W', 'now')"                                                                                
        self.load_people(query_filter=condition)                                                                                                           
                                                                                                                                                           
    def reset_filter(self):                                                                                                                                
        self.search_edit.clear()                                                                                                                           
        self.load_people()                                                                                                                                 
                                                                                                                                                           
    def on_person_selected(self):                                                                                                                          
        selected = self.table.selectedItems()                                                                                                              
        if not selected:                                                                                                                                   
            self.selected_person_id = None                                                                                                                 
            self.photo_label.setText("Немає фото")                                                                                                         
            self.photo_label.setPixmap(QPixmap())                                                                                                          
            return                                                                                                                                         
                                                                                                                                                           
        self.selected_person_id = int(self.table.item(selected[0].row(), 0).text())                                                                        
        self.display_photo(self.selected_person_id)                                                                                                        
                                                                                                                                                           
    # --- Робота із зображеннями ---                                                                                                                       
                                                                                                                                                           
    def display_photo(self, people_id):                                                                                                                    
        with sqlite3.connect(self.db_path) as conn:                                                                                                        
            cur = conn.cursor()                                                                                                                            
            cur.execute("SELECT photo FROM photos WHERE people_id = ? ORDER BY photo_id DESC LIMIT 1", (people_id,))                                       
            res = cur.fetchone()                                                                                                                           
                                                                                                                                                           
        if res and res[0]:                                                                                                                                 
            pixmap = QPixmap()                                                                                                                             
            pixmap.loadFromData(res[0], "JPEG")                                                                                                            
            self.photo_label.setPixmap(                                                                                                                    
                pixmap.scaled(self.photo_label.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)                     
            )                                                                                                                                              
        else:                                                                                                                                              
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
                                                                                                                                                           
        # Масштабування до базового розміру (як у оригіналі 600x800)                                                                                       
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
            fontSize=16,                                                                                                                                   
            leading=20,                                                                                                                                    
            spaceAfter=14,                                                                                                                                 
            alignment=1  # Center                                                                                                                          
        )                                                                                                                                                  
        body_style = ParagraphStyle(                                                                                                                       
            name="ReportCell",                                                                                                                             
            parent=styles["Normal"],                                                                                                                       
            fontSize=8,                                                                                                                                    
            leading=10                                                                                                                                     
        )                                                                                                                                                  
                                                                                                                                                           
        elements.append(Paragraph("Звіт списку громади", title_style))                                                                                     
                                                                                                                                                           
        # Отримуємо записи поточної вибірки                                                                                                                
        table_data = [["Фото", "Ім'я", "Адреса", "Дата нар.", "Мобільний", "Email"]]                                                                       
                                                                                                                                                           
        with sqlite3.connect(self.db_path) as conn:                                                                                                        
            cur = conn.cursor()                                                                                                                            
            for row_idx in range(self.table.rowCount()):                                                                                                   
                p_id = int(self.table.item(row_idx, 0).text())                                                                                             
                name = self.table.item(row_idx, 1).text()                                                                                                  
                address = self.table.item(row_idx, 2).text()                                                                                               
                dob = self.table.item(row_idx, 3).text()                                                                                                   
                phone = self.table.item(row_idx, 4).text()                                                                                                 
                email = self.table.item(row_idx, 5).text()                                                                                                 
                                                                                                                                                           
                # Читання фотографії для рядка                                                                                                             
                cur.execute("SELECT photo FROM photos WHERE people_id = ? ORDER BY photo_id DESC LIMIT 1", (p_id,))                                        
                photo_row = cur.fetchone()                                                                                                                 
                                                                                                                                                           
                img_flowable = ""                                                                                                                          
                if photo_row and photo_row[0]:                                                                                                             
                    img_stream = io.BytesIO(photo_row[0])                                                                                                  
                    # Фіксований міні-розмір у PDF                                                                                                         
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
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),                                                                                                  
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),                                                                                                           
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),                                                                                                        
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),                                                                                                        
            ("TOPPADDING", (0, 0), (-1, -1), 4),                                                                                                           
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),                                                                                   
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),                                                              
        ]))                                                                                                                                                
                                                                                                                                                           
        elements.append(t)                                                                                                                                 
                                                                                                                                                           
        try:                                                                                                                                               
            doc.build(elements, canvasmaker=NumberedCanvas)                                                                                                
            QMessageBox.information(self, "Успіх", f"Звіт успішно збережено:\n{save_path}")                                                                
        except Exception as e:                                                                                                                             
            QMessageBox.critical(self, "Помилка", f"Не вдалося створити PDF:\n{str(e)}")                                                                   
                                                                                                                                                           
                                                                                                                                                           
if __name__ == "__main__":                                                                                                                                 
    app = QApplication(sys.argv)                                                                                                                           
    window = ZeoGraceApp()                                                                                                                                 
    window.show()                                                                                                                                          
    sys.exit(app.exec())  
