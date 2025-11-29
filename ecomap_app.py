import sys
import math
import sqlite3
import json
import copy
from datetime import datetime
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QLineEdit, QComboBox, 
                             QPushButton, QListWidget, QGraphicsScene, 
                             QGraphicsView, QGraphicsItem, QGraphicsEllipseItem, 
                             QGraphicsPathItem, QGraphicsTextItem, QMessageBox,
                             QFileDialog, QFrame, QSplitter)
from PyQt6.QtCore import Qt, QPointF, QRectF, QLineF, pyqtSignal, QObject
from PyQt6.QtGui import (QPen, QBrush, QColor, QPainter, QPainterPath, 
                         QFont, QPolygonF, QTransform, QImage)

# --- 설정 및 상수 (디자인 테마) ---
CONSTANTS = {
    'PRIMARY_COLOR': '#4285F4',    # 구글 블루
    'SECONDARY_COLOR': '#fbbc05',  # 구글 옐로우
    'DANGER_COLOR': '#ea4335',     # 구글 레드
    'SUCCESS_COLOR': '#28a745',    # 그린
    'TEXT_COLOR': '#333333',
    'BG_COLOR': '#f8f9fa',
    'CARD_BG': '#ffffff',
    'NODE_RADIUS': 40,
    'FONT_FAMILY': 'Malgun Gothic', # 윈도우 기본 한글 폰트
}

# --- 데이터베이스 관리 클래스 (SQLite) ---
class EcomapDB:
    def __init__(self, db_name="ecomap_local.db"):
        self.conn = sqlite3.connect(db_name)
        self.create_tables()

    def create_tables(self):
        cursor = self.conn.cursor()
        # 생태도 메타 정보 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS maps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE,
                updated_at TEXT
            )
        ''')
        # 노드 및 관계 데이터 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS nodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                map_id INTEGER,
                type TEXT,  -- 'Client' or 'Person'
                name TEXT,
                relationship TEXT,
                direction TEXT,
                x REAL,
                y REAL,
                FOREIGN KEY(map_id) REFERENCES maps(id) ON DELETE CASCADE
            )
        ''')
        self.conn.commit()

    def save_map(self, map_name, client_data, people_data):
        cursor = self.conn.cursor()
        try:
            # 기존 동일 이름 맵 삭제 (덮어쓰기 로직)
            cursor.execute("DELETE FROM maps WHERE name = ?", (map_name,))
            
            # 맵 생성
            cursor.execute("INSERT INTO maps (name, updated_at) VALUES (?, ?)", 
                           (map_name, datetime.now().isoformat()))
            map_id = cursor.lastrowid

            # Client 저장
            cursor.execute('''
                INSERT INTO nodes (map_id, type, name, x, y) 
                VALUES (?, 'Client', ?, ?, ?)
            ''', (map_id, client_data['name'], client_data['x'], client_data['y']))

            # People 저장
            for p in people_data:
                cursor.execute('''
                    INSERT INTO nodes (map_id, type, name, relationship, direction, x, y) 
                    VALUES (?, 'Person', ?, ?, ?, ?, ?)
                ''', (map_id, p['name'], p['relationship'], p['direction'], p['x'], p['y']))
            
            self.conn.commit()
            return True, "저장되었습니다."
        except Exception as e:
            return False, str(e)

    def get_map_list(self):
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM maps ORDER BY updated_at DESC")
        return [row[0] for row in cursor.fetchall()]

    def load_map(self, map_name):
        cursor = self.conn.cursor()
        cursor.execute("SELECT id FROM maps WHERE name = ?", (map_name,))
        row = cursor.fetchone()
        if not row:
            return None
        
        map_id = row[0]
        cursor.execute("SELECT type, name, relationship, direction, x, y FROM nodes WHERE map_id = ?", (map_id,))
        nodes = cursor.fetchall()
        
        result = {'client': None, 'people': []}
        for n in nodes:
            node_data = {'name': n[1], 'x': n[4], 'y': n[5]}
            if n[0] == 'Client':
                result['client'] = node_data
            else:
                node_data['relationship'] = n[2]
                node_data['direction'] = n[3]
                result['people'].append(node_data)
        return result

    def delete_map(self, map_name):
        cursor = self.conn.cursor()
        cursor.execute("DELETE FROM maps WHERE name = ?", (map_name,))
        self.conn.commit()

# --- 그래픽 아이템: 노드 (원) ---
class NodeItem(QGraphicsEllipseItem):
    def __init__(self, x, y, name, node_type, parent_scene, app_ref=None):
        r = CONSTANTS['NODE_RADIUS']
        super().__init__(-r, -r, r*2, r*2) # 중심을 (0,0)으로 설정
        
        self.name = name
        self.node_type = node_type # 'Client' or 'Person'
        self.scene_ref = parent_scene
        self.app_ref = app_ref # Undo/Redo를 위해 앱 참조
        
        # 위치 설정
        self.setPos(x, y)
        
        # 스타일 설정
        self.setBrush(QBrush(QColor("white")))
        self.default_pen = QPen(QColor(CONSTANTS['TEXT_COLOR']))
        self.default_pen.setWidth(2)
        
        if node_type == 'Client':
            self.default_pen.setColor(QColor(CONSTANTS['PRIMARY_COLOR']))
            self.default_pen.setWidth(3)
            
        self.setPen(self.default_pen)
        
        # 플래그 설정 (드래그 가능, 위치 변경 감지)
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsMovable | 
                      QGraphicsItem.GraphicsItemFlag.ItemSendsScenePositionChanges |
                      QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        
        # 텍스트 라벨 추가
        self.text_item = QGraphicsTextItem(name, self)
        font = QFont(CONSTANTS['FONT_FAMILY'], 10)
        font.setBold(True)
        self.text_item.setFont(font)
        
        # 텍스트 중앙 정렬
        self.center_text()

        self.links = [] # 연결된 링크들

    def center_text(self):
        text_rect = self.text_item.boundingRect()
        self.text_item.setPos(-text_rect.width()/2, -text_rect.height()/2)

    def itemChange(self, change, value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionChange:
            # 노드가 움직일 때 연결된 링크들도 업데이트
            for link in self.links:
                link.update_position()
        
        if change == QGraphicsItem.GraphicsItemChange.ItemSelectedChange:
            if value: # 선택됨
                pen = QPen(QColor(CONSTANTS['DANGER_COLOR']))
                pen.setWidth(4)
                pen.setStyle(Qt.PenStyle.DashLine)
                self.setPen(pen)
            else: # 선택 해제됨
                self.setPen(self.default_pen)

        return super().itemChange(change, value)

    def mouseReleaseEvent(self, event):
        # 드래그가 끝났을 때 상태 저장 (위치 변경 시)
        super().mouseReleaseEvent(event)
        if self.app_ref:
            self.app_ref.save_state_to_history()

    def add_link(self, link):
        self.links.append(link)

# --- 그래픽 아이템: 링크 (선) ---
class LinkItem(QGraphicsPathItem):
    def __init__(self, source_node, target_node, relationship, direction):
        super().__init__()
        self.source = source_node
        self.target = target_node
        self.relationship = relationship
        self.direction = direction
        
        # 화살표 아이템 (자식 아이템으로 관리)
        self.arrow_start = QGraphicsPathItem(self)
        self.arrow_end = QGraphicsPathItem(self)
        
        # Z-Index를 낮게 설정하여 노드 뒤로 가게 함
        self.setZValue(-1)
        self.update_style()
        self.update_position()

    def update_style(self):
        pen = QPen()
        pen.setWidth(2)
        
        color = QColor(CONSTANTS['TEXT_COLOR'])
        if self.relationship == 'good':
            color = QColor(CONSTANTS['SUCCESS_COLOR'])
            pen.setStyle(Qt.PenStyle.SolidLine)
        elif self.relationship == 'distant':
            color = QColor(CONSTANTS['SECONDARY_COLOR'])
            pen.setStyle(Qt.PenStyle.DashLine)
        elif self.relationship == 'conflict':
            color = QColor(CONSTANTS['DANGER_COLOR'])
            pen.setStyle(Qt.PenStyle.SolidLine) 
            
        pen.setColor(color)
        self.setPen(pen)
        
        # 화살표 스타일
        arrow_pen = QPen(color)
        arrow_pen.setWidth(1)
        arrow_brush = QBrush(color)
        
        self.arrow_start.setPen(arrow_pen)
        self.arrow_start.setBrush(arrow_brush)
        self.arrow_end.setPen(arrow_pen)
        self.arrow_end.setBrush(arrow_brush)

    def update_position(self):
        src_pos = self.source.pos()
        tgt_pos = self.target.pos()
        
        path = QPainterPath()
        
        # 노드 반지름만큼 띄우기
        offset = CONSTANTS['NODE_RADIUS'] + 5
        
        line = QLineF(src_pos, tgt_pos)
        length = line.length()
        
        if length <= offset * 2:
            # 너무 가까우면 그리지 않음
            self.setPath(path)
            self.arrow_start.setPath(QPainterPath())
            self.arrow_end.setPath(QPainterPath())
            return

        # 시작점과 끝점 조정 (원 테두리)
        vec = (tgt_pos - src_pos) / length if length > 0 else QPointF(0,0)
        start_p = src_pos + vec * offset
        end_p = tgt_pos - vec * offset
        
        # 경로 그리기
        if self.relationship == 'conflict':
            # 지그재그 생성 (양 끝에 직선 구간 추가)
            straight_len = 20 # 직선 구간 길이
            
            dist = QLineF(start_p, end_p).length()
            
            if dist > straight_len * 2:
                # 직선 구간을 제외한 지그재그 구간 계산
                zigzag_start = start_p + vec * straight_len
                zigzag_end = end_p - vec * straight_len
                
                path.moveTo(start_p)
                path.lineTo(zigzag_start) # 시작 직선
                
                # 지그재그 그리기
                zz_len = dist - (straight_len * 2)
                segments = max(4, int(zz_len / 15)) # 세그먼트 길이 조정
                amplitude = 6
                
                dx = (zigzag_end.x() - zigzag_start.x()) / segments
                dy = (zigzag_end.y() - zigzag_start.y()) / segments
                
                # 수직 벡터 계산
                perp_dx, perp_dy = -dy, dx
                norm_perp = math.sqrt(perp_dx**2 + perp_dy**2)
                if norm_perp == 0: norm_perp = 1
                
                for i in range(1, segments + 1):
                    mid_x = zigzag_start.x() + dx * (i - 0.5)
                    mid_y = zigzag_start.y() + dy * (i - 0.5)
                    
                    sign = 1 if i % 2 == 0 else -1
                    peak_x = mid_x + (amplitude * perp_dx / norm_perp) * sign
                    peak_y = mid_y + (amplitude * perp_dy / norm_perp) * sign
                    
                    path.lineTo(peak_x, peak_y)
                    path.lineTo(zigzag_start.x() + dx * i, zigzag_start.y() + dy * i)
                    
                path.lineTo(end_p) # 끝 직선
            else:
                # 거리가 너무 짧으면 그냥 직선
                path.moveTo(start_p)
                path.lineTo(end_p)
        else:
            # 직선
            path.moveTo(start_p)
            path.lineTo(end_p)

        self.setPath(path)
        
        # 화살표 그리기
        self.update_arrowheads(start_p, end_p, vec)

    def update_arrowheads(self, start_p, end_p, vec):
        # 화살표 크기 및 각도
        arrow_size = 10
        angle = math.atan2(vec.y(), vec.x())
        
        # Start Arrow (To Client) - 역방향
        if self.direction in ['to', 'both']:
            p1 = start_p + QPointF(math.cos(angle + math.pi/6) * arrow_size, 
                                   math.sin(angle + math.pi/6) * arrow_size)
            p2 = start_p + QPointF(math.cos(angle - math.pi/6) * arrow_size, 
                                   math.sin(angle - math.pi/6) * arrow_size)
            arrow_path = QPainterPath()
            arrow_path.moveTo(start_p)
            arrow_path.lineTo(p1)
            arrow_path.lineTo(p2)
            arrow_path.closeSubpath()
            self.arrow_start.setPath(arrow_path)
        else:
            self.arrow_start.setPath(QPainterPath())

        # End Arrow (From Client) - 정방향
        if self.direction in ['from', 'both']:
            # 끝점에서는 벡터 반대 방향으로 화살표가 그려져야 함
            rev_angle = angle + math.pi 
            p1 = end_p + QPointF(math.cos(rev_angle + math.pi/6) * arrow_size, 
                                 math.sin(rev_angle + math.pi/6) * arrow_size)
            p2 = end_p + QPointF(math.cos(rev_angle - math.pi/6) * arrow_size, 
                                 math.sin(rev_angle - math.pi/6) * arrow_size)
            arrow_path = QPainterPath()
            arrow_path.moveTo(end_p)
            arrow_path.lineTo(p1)
            arrow_path.lineTo(p2)
            arrow_path.closeSubpath()
            self.arrow_end.setPath(arrow_path)
        else:
            self.arrow_end.setPath(QPainterPath())

# --- 메인 윈도우 ---
class EcomapApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.db = EcomapDB()
        self.setWindowTitle("생태도 그리기 (Desktop Version)")
        self.resize(1200, 800)
        self.setStyleSheet(f"background-color: {CONSTANTS['BG_COLOR']}; font-family: {CONSTANTS['FONT_FAMILY']};")

        self.client_node = None
        self.people_nodes = []
        self.link_items = []
        
        # Undo/Redo 관련
        self.history = []
        self.history_index = -1
        self.is_undoing = False # Undo/Redo 중 이벤트 루프 방지

        self.init_ui()

    def init_ui(self):
        # 메인 위젯 및 레이아웃
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget) # 수직 레이아웃으로 변경

        # 컨텐츠 영역 (기존 좌우 패널)
        content_layout = QHBoxLayout()
        main_layout.addLayout(content_layout)

        # --- 왼쪽 패널 (컨트롤) ---
        left_panel = QFrame()
        left_panel.setFixedWidth(350)
        left_panel.setStyleSheet(f"background-color: {CONSTANTS['CARD_BG']}; border-radius: 8px; border: 1px solid #ddd;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(15)

        # 1. 정보 입력 영역
        title_label = QLabel("생태도 정보 입력")
        title_label.setStyleSheet(f"font-size: 18px; font-weight: bold; color: {CONSTANTS['PRIMARY_COLOR']};")
        left_layout.addWidget(title_label)

        self.map_title_input = QLineEdit()
        self.map_title_input.setPlaceholderText("예: 우리 가족 생태도")
        self.style_input(self.map_title_input)
        left_layout.addWidget(QLabel("생태도 제목"))
        left_layout.addWidget(self.map_title_input)

        self.client_name_input = QLineEdit()
        self.client_name_input.setPlaceholderText("중심 인물 이름")
        self.style_input(self.client_name_input)
        self.client_name_input.textChanged.connect(self.update_client_name)
        left_layout.addWidget(QLabel("중심 인물(Client) 이름"))
        left_layout.addWidget(self.client_name_input)

        left_layout.addWidget(self.create_h_line())

        # 2. 인물 추가 폼
        form_title = QLabel("주변 인물/조직 추가")
        form_title.setStyleSheet("font-size: 14px; font-weight: bold;")
        left_layout.addWidget(form_title)

        self.person_name_input = QLineEdit()
        self.person_name_input.setPlaceholderText("이름")
        self.style_input(self.person_name_input)
        left_layout.addWidget(self.person_name_input)

        self.rel_combo = QComboBox()
        self.rel_combo.addItems(["좋은 관계 (good)", "소원한 관계 (distant)", "갈등 관계 (conflict)"])
        self.style_input(self.rel_combo)
        left_layout.addWidget(self.rel_combo)

        self.dir_combo = QComboBox()
        self.dir_combo.addItems(["↔ 양방향 (both)", "→ Client로부터 나감 (from)", "← Client에게로 들어옴 (to)"])
        self.style_input(self.dir_combo)
        left_layout.addWidget(self.dir_combo)

        add_btn = QPushButton("인물 추가")
        self.style_button(add_btn, "primary")
        add_btn.clicked.connect(self.add_person)
        left_layout.addWidget(add_btn)

        # 3. 생태도 목록
        list_label = QLabel("내 생태도 목록")
        list_label.setStyleSheet("font-size: 14px; font-weight: bold; margin-top: 10px;")
        left_layout.addWidget(list_label)

        self.map_list_widget = QListWidget()
        self.map_list_widget.setStyleSheet("border: 1px solid #ddd; border-radius: 4px;")
        self.map_list_widget.itemClicked.connect(self.on_list_item_clicked)
        left_layout.addWidget(self.map_list_widget)

        # 목록 제어 버튼
        list_btn_layout = QHBoxLayout()
        load_btn = QPushButton("불러오기")
        self.style_button(load_btn, "primary")
        load_btn.clicked.connect(self.load_selected_map)
        
        del_btn = QPushButton("삭제")
        self.style_button(del_btn, "danger")
        del_btn.clicked.connect(self.delete_selected_map)
        
        list_btn_layout.addWidget(load_btn)
        list_btn_layout.addWidget(del_btn)
        left_layout.addLayout(list_btn_layout)

        left_layout.addStretch() # 아래 여백 채우기

        # --- 오른쪽 패널 (캔버스) ---
        right_panel = QFrame()
        right_panel.setStyleSheet(f"background-color: {CONSTANTS['CARD_BG']}; border-radius: 8px; border: 1px solid #ddd;")
        right_layout = QVBoxLayout(right_panel)

        # 상단 툴바
        toolbar = QHBoxLayout()
        new_btn = QPushButton("새로 만들기")
        self.style_button(new_btn, "secondary")
        new_btn.clicked.connect(self.reset_canvas_with_confirm)
        
        save_btn = QPushButton("DB에 저장")
        self.style_button(save_btn, "primary")
        save_btn.clicked.connect(self.save_to_db)

        export_btn = QPushButton("이미지 저장(PNG)")
        self.style_button(export_btn, "secondary")
        export_btn.clicked.connect(self.export_image)

        # Undo/Redo 버튼
        self.undo_btn = QPushButton("실행 취소")
        self.style_button(self.undo_btn, "secondary")
        self.undo_btn.clicked.connect(self.undo)
        self.undo_btn.setEnabled(False)

        self.redo_btn = QPushButton("다시 실행")
        self.style_button(self.redo_btn, "secondary")
        self.redo_btn.clicked.connect(self.redo)
        self.redo_btn.setEnabled(False)

        toolbar.addWidget(new_btn)
        toolbar.addWidget(save_btn)
        toolbar.addWidget(self.undo_btn)
        toolbar.addWidget(self.redo_btn)
        toolbar.addWidget(export_btn)
        toolbar.addStretch()
        right_layout.addLayout(toolbar)

        # 그래픽 뷰 (캔버스)
        self.scene = QGraphicsScene()
        self.scene.setSceneRect(0, 0, 800, 600) # 초기 크기
        
        self.view = QGraphicsView(self.scene)
        self.view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.view.setDragMode(QGraphicsView.DragMode.NoDrag) # 아이템 드래그를 위해 뷰 드래그 꺼둠
        self.view.setStyleSheet("border: none;")
        right_layout.addWidget(self.view)
        
        # 캔버스 하단 설명
        help_label = QLabel("노드를 드래그하여 이동 | Delete 키로 선택 노드 삭제")
        help_label.setStyleSheet("color: #777; font-size: 12px; margin-top: 5px;")
        help_label.setAlignment(Qt.AlignmentFlag.AlignRight)
        right_layout.addWidget(help_label)

        # 메인 레이아웃에 패널 추가 (컨텐츠 레이아웃에 추가)
        content_layout.addWidget(left_panel)
        content_layout.addWidget(right_panel)

        # 하단 푸터 추가
        footer_label = QLabel("welfareact.net에서 제작·배포합니다.")
        footer_label.setStyleSheet("color: #888; font-size: 11px; margin-top: 5px;")
        footer_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(footer_label)

        # 초기 로드
        self.refresh_map_list()
        self.reset_canvas() # 초기 캔버스 설정 (Client 생성 등)
        self.save_state_to_history() # 초기 상태 저장

    # --- 스타일 헬퍼 함수 ---
    def style_input(self, widget):
        widget.setStyleSheet(f"""
            padding: 8px; border: 1px solid #ddd; border-radius: 4px; font-size: 12px;
            selection-background-color: {CONSTANTS['PRIMARY_COLOR']};
        """)

    def style_button(self, btn, btn_type):
        bg = "#f1f3f4"
        fg = "#3c4043"
        hover = "#e8eaed"
        
        if btn_type == "primary":
            bg = CONSTANTS['PRIMARY_COLOR']
            fg = "white"
            hover = "#3367d6"
        elif btn_type == "danger":
            bg = CONSTANTS['DANGER_COLOR']
            fg = "white"
            hover = "#c53929"
            
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg}; color: {fg}; border: none; 
                padding: 8px 16px; border-radius: 4px; font-weight: bold;
            }}
            QPushButton:hover {{ background-color: {hover}; }}
            QPushButton:disabled {{ background-color: #f1f3f4; color: #9aa0a6; }}
        """)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

    def create_h_line(self):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("border: none; border-top: 1px solid #eee; margin: 10px 0;")
        return line

    # --- Undo/Redo 로직 ---
    def save_state_to_history(self):
        if self.is_undoing: return

        # 현재 상태 스냅샷 생성
        state = {
            'client': {
                'name': self.client_node.name if self.client_node else "",
                'x': self.client_node.pos().x() if self.client_node else 0,
                'y': self.client_node.pos().y() if self.client_node else 0
            },
            'people': []
        }
        
        for p_node in self.people_nodes:
            # 해당 노드와 Client를 잇는 링크 찾기
            related_link = None
            for link in p_node.links:
                if link.source == self.client_node or link.target == self.client_node:
                    related_link = link
                    break
            
            if related_link:
                state['people'].append({
                    'name': p_node.name,
                    'x': p_node.pos().x(),
                    'y': p_node.pos().y(),
                    'relationship': related_link.relationship,
                    'direction': related_link.direction
                })

        # 히스토리 관리 (현재 인덱스 뒤의 기록은 날림)
        self.history = self.history[:self.history_index + 1]
        self.history.append(state)
        self.history_index += 1
        
        self.update_undo_redo_buttons()

    def update_undo_redo_buttons(self):
        self.undo_btn.setEnabled(self.history_index > 0)
        self.redo_btn.setEnabled(self.history_index < len(self.history) - 1)

    def undo(self):
        if self.history_index > 0:
            self.history_index -= 1
            self.restore_state(self.history[self.history_index])
            self.update_undo_redo_buttons()

    def redo(self):
        if self.history_index < len(self.history) - 1:
            self.history_index += 1
            self.restore_state(self.history[self.history_index])
            self.update_undo_redo_buttons()

    def restore_state(self, state):
        self.is_undoing = True
        
        self.scene.clear()
        self.people_nodes = []
        self.link_items = []
        
        # Client 복원
        c_data = state['client']
        self.client_name_input.blockSignals(True) # 시그널 차단하여 무한 루프 방지
        self.client_name_input.setText(c_data['name'])
        self.client_name_input.blockSignals(False)
        
        self.client_node = NodeItem(c_data['x'], c_data['y'], c_data['name'], 'Client', self.scene, self)
        self.scene.addItem(self.client_node)
        
        # People 복원
        for p_data in state['people']:
            p_node = NodeItem(p_data['x'], p_data['y'], p_data['name'], 'Person', self.scene, self)
            self.scene.addItem(p_node)
            self.people_nodes.append(p_node)
            
            link = LinkItem(self.client_node, p_node, p_data['relationship'], p_data['direction'])
            self.scene.addItem(link)
            self.link_items.append(link)
            
            self.client_node.add_link(link)
            p_node.add_link(link)
            
        self.is_undoing = False

    # --- 기능 로직 ---

    def reset_canvas_with_confirm(self):
        if QMessageBox.question(self, "확인", "현재 작업 내용을 지우고 새로 시작하시겠습니까?", 
                                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) == QMessageBox.StandardButton.Yes:
            self.reset_canvas()
            self.save_state_to_history()

    def reset_canvas(self):
        self.scene.clear()
        self.client_node = None
        self.people_nodes = []
        self.link_items = []
        self.history = []
        self.history_index = -1
        
        # 기본 Client 생성 (화면 중앙)
        rect = self.view.rect()
        cx, cy = 400, 300 # 기본값
        if rect.width() > 0: cx, cy = rect.width()/2, rect.height()/2
        
        initial_name = self.client_name_input.text() if self.client_name_input.text() else "Client"
        self.client_node = NodeItem(cx, cy, initial_name, 'Client', self.scene, self)
        self.scene.addItem(self.client_node)

    def update_client_name(self, text):
        if self.client_node and hasattr(self.client_node, 'text_item'):
            try:
                self.client_node.name = text  # name 속성도 업데이트
                self.client_node.text_item.setPlainText(text)
                self.client_node.center_text()
            except RuntimeError:
                # text_item이 이미 삭제된 경우 (scene.clear() 후 등)
                pass
            if not self.is_undoing:
                # 타이핑할 때마다 저장하면 너무 많으므로, 포커스 아웃이나 엔터 처리 등이 좋지만
                # 여기서는 간단히 처리 (실제로는 타이머 등을 사용해 디바운싱 권장)
                pass 

    def add_person(self):
        name = self.person_name_input.text()
        if not name:
            QMessageBox.warning(self, "경고", "이름을 입력해주세요.")
            return

        if not self.client_node:
            QMessageBox.warning(self, "경고", "중심 인물이 없습니다.")
            return

        # 데이터 추출
        rel_text = self.rel_combo.currentText()
        if "good" in rel_text: rel = "good"
        elif "distant" in rel_text: rel = "distant"
        else: rel = "conflict"

        dir_text = self.dir_combo.currentText()
        if "both" in dir_text: direction = "both"
        elif "from" in dir_text: direction = "from"
        else: direction = "to"

        # 위치 계산 (원형 배치)
        count = len(self.people_nodes)
        angle = count * 0.9  # 약간씩 각도를 틈
        radius = 200
        cx, cy = self.client_node.pos().x(), self.client_node.pos().y()
        nx = cx + math.cos(angle) * radius
        ny = cy + math.sin(angle) * radius

        # 노드 생성
        person_node = NodeItem(nx, ny, name, 'Person', self.scene, self)
        self.scene.addItem(person_node)
        self.people_nodes.append(person_node)

        # 링크 생성
        link = LinkItem(self.client_node, person_node, rel, direction)
        self.scene.addItem(link)
        self.link_items.append(link)
        
        # 노드에 링크 정보 등록 (움직일 때 업데이트용)
        self.client_node.add_link(link)
        person_node.add_link(link)

        # 입력 초기화
        self.person_name_input.clear()
        
        # 상태 저장
        self.save_state_to_history()

    def delete_selected_node(self):
        selected_items = self.scene.selectedItems()
        if not selected_items:
            return
            
        changed = False
        for item in selected_items:
            if isinstance(item, NodeItem):
                if item.node_type == 'Client':
                    QMessageBox.warning(self, "불가", "중심 인물은 삭제할 수 없습니다.")
                    continue
                
                # 연결된 링크 삭제
                for link in item.links[:]: # 복사본으로 순회
                    self.scene.removeItem(link)
                    if link in self.link_items:
                        self.link_items.remove(link)
                    # 반대편 노드의 링크 목록에서도 제거
                    other = link.source if link.target == item else link.target
                    if link in other.links:
                        other.links.remove(link)
                        
                # 리스트에서 제거
                if item in self.people_nodes:
                    self.people_nodes.remove(item)
                
                self.scene.removeItem(item)
                changed = True
        
        if changed:
            self.save_state_to_history()

    def keyPressEvent(self, event):
        # Delete 키로 삭제 기능
        if event.key() == Qt.Key.Key_Delete:
            self.delete_selected_node()
        # Undo/Redo 단축키 (Ctrl+Z, Ctrl+Y)
        elif event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_Z:
                self.undo()
            elif event.key() == Qt.Key.Key_Y:
                self.redo()
        super().keyPressEvent(event)

    def closeEvent(self, event):
        reply = QMessageBox.question(self, '종료 확인',
                                     "변경사항을 저장하시겠습니까?",
                                     QMessageBox.StandardButton.Yes | 
                                     QMessageBox.StandardButton.No | 
                                     QMessageBox.StandardButton.Cancel,
                                     QMessageBox.StandardButton.Yes)

        if reply == QMessageBox.StandardButton.Yes:
            if self.save_to_db():
                event.accept()
            else:
                event.ignore()
        elif reply == QMessageBox.StandardButton.No:
            event.accept()
        else:
            event.ignore()

    # --- 데이터베이스 연동 ---
    def save_to_db(self):
        title = self.map_title_input.text()
        if not title:
            QMessageBox.warning(self, "필수", "생태도 제목을 입력해주세요.")
            return False

        client_data = {
            'name': self.client_node.name if hasattr(self.client_node, 'name') else self.client_name_input.text(),
            'x': self.client_node.pos().x(),
            'y': self.client_node.pos().y()
        }

        people_data = []
        # 링크 정보를 기반으로 관계 데이터 찾기 (약간 비효율적이지만 정확함)
        for p_node in self.people_nodes:
            # 해당 노드와 Client를 잇는 링크 찾기
            related_link = None
            for link in p_node.links:
                if link.source == self.client_node or link.target == self.client_node:
                    related_link = link
                    break
            
            if related_link:
                people_data.append({
                    'name': p_node.name,
                    'x': p_node.pos().x(),
                    'y': p_node.pos().y(),
                    'relationship': related_link.relationship,
                    'direction': related_link.direction
                })

        success, msg = self.db.save_map(title, client_data, people_data)
        if success:
            QMessageBox.information(self, "성공", msg)
            self.refresh_map_list()
            return True
        else:
            QMessageBox.critical(self, "오류", f"저장 실패: {msg}")
            return False

    def refresh_map_list(self):
        self.map_list_widget.clear()
        maps = self.db.get_map_list()
        self.map_list_widget.addItems(maps)

    def on_list_item_clicked(self, item):
        self.map_title_input.setText(item.text())

    def load_selected_map(self):
        current_item = self.map_list_widget.currentItem()
        if not current_item:
            QMessageBox.warning(self, "선택", "불러올 생태도를 목록에서 선택해주세요.")
            return
        
        map_name = current_item.text()
        data = self.db.load_map(map_name)
        
        if not data:
            QMessageBox.critical(self, "오류", "데이터를 불러오지 못했습니다.")
            return

        # Client 데이터 확인
        c_data = data['client']
        if not c_data:
            QMessageBox.critical(self, "오류", "생태도에 중심 인물 데이터가 없습니다.")
            return

        # 캔버스 리셋 및 데이터 적용
        self.scene.clear()
        self.people_nodes = []
        self.link_items = []
        self.history = []
        self.history_index = -1
        
        # Client 생성 (시그널 차단하여 update_client_name 호출 방지)
        self.client_name_input.blockSignals(True)
        self.client_name_input.setText(c_data['name'])
        self.map_title_input.setText(map_name)
        self.client_name_input.blockSignals(False)
        
        self.client_node = NodeItem(c_data['x'], c_data['y'], c_data['name'], 'Client', self.scene, self)
        self.scene.addItem(self.client_node)
        
        # People 생성
        for p_data in data['people']:
            p_node = NodeItem(p_data['x'], p_data['y'], p_data['name'], 'Person', self.scene, self)
            self.scene.addItem(p_node)
            self.people_nodes.append(p_node)
            
            link = LinkItem(self.client_node, p_node, p_data['relationship'], p_data['direction'])
            self.scene.addItem(link)
            self.link_items.append(link)
            
            self.client_node.add_link(link)
            p_node.add_link(link)
            
        self.save_state_to_history() # 로드 후 초기 상태 저장
        QMessageBox.information(self, "완료", f"'{map_name}'을(를) 불러왔습니다.")

    def delete_selected_map(self):
        current_item = self.map_list_widget.currentItem()
        if not current_item:
            return
        
        ret = QMessageBox.question(self, "확인", f"정말 '{current_item.text()}'을(를) 삭제하시겠습니까?",
                                   QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        
        if ret == QMessageBox.StandardButton.Yes:
            self.db.delete_map(current_item.text())
            self.refresh_map_list()
            self.map_title_input.clear()

    def export_image(self):
        file_path, _ = QFileDialog.getSaveFileName(self, "이미지 저장", "ecomap.png", "PNG Files (*.png)")
        if file_path:
            # Scene 영역 계산
            rect = self.scene.itemsBoundingRect()
            rect.adjust(-50, -50, 50, 50) # 여백 추가
            
            image = QImage(rect.size().toSize(), QImage.Format.Format_ARGB32)
            image.fill(Qt.GlobalColor.white)
            
            painter = QPainter(image)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            self.scene.render(painter, target=QRectF(image.rect()), source=rect)
            painter.end()
            
            image.save(file_path)
            QMessageBox.information(self, "저장 완료", "이미지가 저장되었습니다.")

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = EcomapApp()
    window.show()
    sys.exit(app.exec())
