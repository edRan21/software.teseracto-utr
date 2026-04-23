# TESERACTO-UTR/GUI/Windows/ErrorConsoleWindow.py
import os
import time
import shutil
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem, 
    QPushButton, QComboBox, QLabel, QHeaderView, QAbstractItemView, QLineEdit
)
from PyQt5.QtCore import Qt, QTimer, QDate
from PyQt5.QtGui import QColor, QFont, QBrush

class ErrorConsoleWindow(QWidget):
    def __init__(self, error_handler):
        super().__init__()
        self.error_handler = error_handler
        
        from Core.System.PathManager import path_manager
        self.log_file = str(path_manager.get_db_path("errores.log"))
        
        # APORTACIONES PARA OPTIMIZACIÓN
        self.last_modified = 0
        self.last_file_pos = 0            # Solo leeremos las líneas nuevas
        self.MAX_VISIBLE_ERRORS = 1000    # Evitar saturación visual en la tabla
        self.all_errors = []              # Caché interna de errores procesados
        
        self.setup_ui()
        self.load_errors()
        
    def setup_ui(self):
        # (El código de la interfaz gráfica es el mismo, solo lo abrevio un poco para el copiado,
        # pero asegúrate de mantener tus estilos CSS intactos)
        main_layout = QVBoxLayout()
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        control_layout = QHBoxLayout()
        label_style = "color: white; font-weight: bold;"

        lbl_level = QLabel("Nivel:")
        lbl_level.setStyleSheet(label_style)
        control_layout.addWidget(lbl_level)

        self.cmb_level = QComboBox()
        self.cmb_level.addItems(["TODOS", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"])
        self.cmb_level.currentIndexChanged.connect(self.filter_errors)
        self.cmb_level.setStyleSheet("QComboBox { background-color: #3b3b3b; color: white; border: 1px solid #555; padding: 3px; }")
        control_layout.addWidget(self.cmb_level)

        lbl_date = QLabel("Fecha:")
        lbl_date.setStyleSheet(label_style)
        control_layout.addWidget(lbl_date)

        self.txt_date = QLineEdit()
        self.txt_date.setPlaceholderText("YYYY-MM-DD")
        self.txt_date.setMaximumWidth(100)
        self.txt_date.textChanged.connect(self.filter_errors)
        self.txt_date.setStyleSheet("QLineEdit { background-color: #3b3b3b; color: white; border: 1px solid #555; padding: 3px; }")
        control_layout.addWidget(self.txt_date)

        lbl_search = QLabel("Buscar:")
        lbl_search.setStyleSheet(label_style)
        control_layout.addWidget(lbl_search)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("Código o texto")
        self.txt_search.textChanged.connect(self.filter_errors)
        self.txt_search.setStyleSheet("QLineEdit { background-color: #3b3b3b; color: white; border: 1px solid #555; padding: 3px; }")
        control_layout.addWidget(self.txt_search)

        self.btn_clear = QPushButton("Limpiar Log")
        self.btn_clear.setStyleSheet("QPushButton { background-color: #E74C3C; color: white; font-weight: bold; padding: 5px; border: none; } QPushButton:hover { background-color: #C0392B; }")
        self.btn_clear.clicked.connect(self.clear_log)
        control_layout.addWidget(self.btn_clear)

        self.btn_refresh = QPushButton("Actualizar")
        self.btn_refresh.setStyleSheet("QPushButton { background-color: #2E86C1; color: white; font-weight: bold; padding: 5px; border: none; } QPushButton:hover { background-color: #2874A6; }")
        self.btn_refresh.clicked.connect(self.force_load_errors)
        control_layout.addWidget(self.btn_refresh)

        control_layout.addStretch()
        main_layout.addLayout(control_layout)
        
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Fecha/Hora", "Nivel", "Código", "Descripción", "Origen"])
        
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setSortingEnabled(True)
        
        self.level_colors = {
            "DEBUG": QColor(144, 144, 144),
            "INFO": QColor(52, 152, 219),
            "WARNING": QColor(243, 156, 18),
            "ERROR": QColor(231, 76, 60),
            "CRITICAL": QColor(155, 89, 182)
        }
        
        self.table.setStyleSheet("""
            QTableWidget { gridline-color: #555; background-color: #2b2b2b; color: white; border: 1px solid #555; font-size: 10pt; }
            QTableWidget::item { border-bottom: 1px solid #555; padding: 5px; }
            QTableWidget::item:selected { background-color: #0078d7; color: white; }
            QHeaderView::section { background-color: #3b3b3b; color: white; padding: 5px; border: 0px; font-weight: bold; }
        """)
        
        main_layout.addWidget(self.table)
        
        self.lbl_count = QLabel("0 errores mostrados")
        self.lbl_count.setFont(QFont("Arial", 9))
        self.lbl_count.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.lbl_count.setStyleSheet("color: white;")
        main_layout.addWidget(self.lbl_count)
        
        self.setLayout(main_layout)
        
        self.update_timer = QTimer()
        self.update_timer.setInterval(5000)
        self.update_timer.timeout.connect(self.check_log_changes)
        self.update_timer.start()

    def force_load_errors(self):
        """Fuerza la recarga del log ignorando el puntero actual"""
        self.last_file_pos = 0
        self.all_errors = []
        self.load_errors()

    def check_log_changes(self):
        if not os.path.exists(self.log_file):
            return
            
        current_modified = os.path.getmtime(self.log_file)
        if current_modified > self.last_modified:
            self.last_modified = current_modified
            self.load_errors()

    def load_errors(self):
        if not os.path.exists(self.log_file):
            self.table.setRowCount(0)
            self.lbl_count.setText("Archivo de log no encontrado")
            return
            
        try:
            # APORTACIÓN: Verificar si el archivo fue rotado o limpiado
            file_size = os.path.getsize(self.log_file)
            if file_size < self.last_file_pos:
                self.last_file_pos = 0
                self.all_errors = []

            if file_size == self.last_file_pos:
                return # No hay datos nuevos
                
            new_lines = []
            with open(self.log_file, 'r', encoding='utf-8', errors='replace') as f:
                f.seek(self.last_file_pos) # Saltamos a donde nos quedamos la última vez
                new_lines = f.readlines()
                self.last_file_pos = f.tell() # Guardamos la nueva posición
                
            if not new_lines:
                return

            new_errors = []
            for line in new_lines:
                if not line.strip() or not line.startswith('['):
                    continue
                    
                parts = line.split("]", 1)
                if len(parts) < 2: continue
                    
                timestamp = parts[0][1:].strip()
                rest = parts[1].strip()
                
                level_end = rest.find(':')
                if level_end == -1: continue
                    
                level = rest[:level_end].strip().upper()
                if "ERROR" in level: level = "ERROR"
                elif "WARN" in level: level = "WARNING"
                elif "INFO" in level: level = "INFO"
                elif "DEBUG" in level: level = "DEBUG"
                elif "CRIT" in level: level = "CRITICAL"
                
                message = rest[level_end+1:].strip()
                
                code = ""
                ker_pos = message.find("KER-")
                if ker_pos != -1:
                    code_end = message.find(":", ker_pos)
                    if code_end != -1: code = message[ker_pos+4:code_end].strip()
                    else:
                        space_pos = message.find(" ", ker_pos)
                        if space_pos != -1: code = message[ker_pos+4:space_pos].strip()
                        else: code = message[ker_pos+4:].strip()
                
                origin = "Sistema"
                if "Modbus" in message: origin = "Modbus"
                elif "Medidor" in message: origin = "Medidor"
                elif "Conexión" in message: origin = "Conexión"
                elif "Reporte" in message: origin = "Reportes"
                    
                new_errors.append({
                    "timestamp": timestamp,
                    "level": level,
                    "code": code,
                    "description": message,
                    "origin": origin
                })
                
            # Agregamos los nuevos errores y mantenemos solo los últimos MAX_VISIBLE_ERRORS
            self.all_errors.extend(new_errors)
            if len(self.all_errors) > self.MAX_VISIBLE_ERRORS:
                self.all_errors = self.all_errors[-self.MAX_VISIBLE_ERRORS:]
                
            self.filter_errors()
            
        except Exception as e:
            print(f"Error cargando log de forma incremental: {e}")

    def filter_errors(self):
        if not hasattr(self, 'all_errors'):
            return
            
        level_filter = self.cmb_level.currentText()
        date_filter = self.txt_date.text().strip()
        text_filter = self.txt_search.text().strip().lower()
        
        filtered = []
        for error in self.all_errors:
            if level_filter != "TODOS" and level_filter != error["level"]: continue
            if date_filter and not error["timestamp"].startswith(date_filter): continue
            
            if text_filter:
                text_match = (text_filter in error["code"].lower() or 
                              text_filter in error["description"].lower() or 
                              text_filter in error["origin"].lower())
                if not text_match: continue
                    
            filtered.append(error)
            
        # APORTACIÓN: Desactivar ordenamiento temporal para insertar filas rapidísimo
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(filtered))
        
        for row, error in enumerate(filtered):
            item_time = QTableWidgetItem(error["timestamp"])
            item_time.setData(Qt.UserRole, error["timestamp"]) 
            
            item_level = QTableWidgetItem(error["level"])
            if error["level"] in self.level_colors:
                item_level.setForeground(QBrush(self.level_colors[error["level"]]))
                item_level.setFont(QFont("Arial", 9, QFont.Bold))
                
            item_code = QTableWidgetItem(error["code"])
            item_desc = QTableWidgetItem(error["description"])
            item_origin = QTableWidgetItem(error["origin"])
            
            self.table.setItem(row, 0, item_time)
            self.table.setItem(row, 1, item_level)
            self.table.setItem(row, 2, item_code)
            self.table.setItem(row, 3, item_desc)
            self.table.setItem(row, 4, item_origin)
            
        self.table.sortItems(0, Qt.DescendingOrder)
        self.table.setSortingEnabled(True) # Volver a activar ordenamiento
        
        self.lbl_count.setText(f"{len(filtered)} de {len(self.all_errors)} errores mostrados (Límite visual: {self.MAX_VISIBLE_ERRORS})")

    def clear_log(self):
        try:
            backup_path = f"{self.log_file}.backup.{int(time.time())}"
            if os.path.exists(self.log_file):
                shutil.copy2(self.log_file, backup_path)
                
            open(self.log_file, "w").close()
            
            # Resetear variables
            self.last_modified = os.path.getmtime(self.log_file) if os.path.exists(self.log_file) else 0
            self.last_file_pos = 0
            self.all_errors = []
            
            self.force_load_errors()
            
            if hasattr(self, 'error_handler'):
                self.error_handler.log_evento("Log de errores limpiado manualmente", "300")
            else:
                print("Log de errores limpiado manualmente")
                
        except Exception as e:
            print(f"Error clearing log: {e}")

    def closeEvent(self, event):
        self.update_timer.stop()
        super().closeEvent(event)