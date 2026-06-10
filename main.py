import sys
import asyncio
import aiohttp
import json
import math
import os
import markdown  # 馃専 蹇呴』瀹夎杩欎釜搴擄細pip install markdown
from datetime import datetime
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from concept_db import ConceptDatabase


# MARK: - 瀵硅瘽浼氳瘽鏁版嵁妯″瀷
class ChatSession:
    def __init__(self, session_id: str, title: str):
        self.id = session_id
        self.title = title
        self.created_at = datetime.now().isoformat()
        self.updated_at = datetime.now().isoformat()
        self.is_pinned = False
        self.messages = []

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "is_pinned": self.is_pinned,
            "messages": self.messages
        }

    @classmethod
    def from_dict(cls, data):
        session = cls(data["id"], data["title"])
        session.created_at = data["created_at"]
        session.updated_at = data["updated_at"]
        session.is_pinned = data.get("is_pinned", False)
        session.messages = data.get("messages", [])
        return session

    def get_date_group(self):
        dt = datetime.fromisoformat(self.created_at)
        today = datetime.now().date()
        if dt.date() == today:
            return "浠婂ぉ"
        elif dt.date() == today.replace(day=today.day - 1):
            return "鏄ㄥぉ"
        elif (today - dt.date()).days <= 7:
            return "7澶╁唴"
        else:
            return dt.strftime("%Y骞?m鏈?)


# MARK: - 瀵硅瘽鎸佷箙鍖栧瓨鍌ㄧ鐞嗗櫒
class ChatStorage:
    def __init__(self, filename="chat_sessions.json"):
        self.file_path = os.path.join(os.path.dirname(__file__), filename)
        self.sessions: list[ChatSession] = []
        self._load()

    def _load(self):
        if os.path.exists(self.file_path):
            try:
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    data_list = json.load(f)
                    self.sessions = [ChatSession.from_dict(d) for d in data_list]
            except Exception:
                self.sessions = []

    def _save(self):
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump([s.to_dict() for s in self.sessions], f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def create_new_session(self) -> ChatSession:
        new_id = str(int(datetime.now().timestamp() * 1000))
        session = ChatSession(new_id, "鏂板璇?)
        self.sessions.insert(0, session)
        self._save()
        return session

    def get_sorted_sessions(self):
        pinned = [s for s in self.sessions if s.is_pinned]
        unpinned = [s for s in self.sessions if not s.is_pinned]
        pinned.sort(key=lambda s: s.updated_at, reverse=True)
        unpinned.sort(key=lambda s: s.updated_at, reverse=True)
        return pinned + unpinned

    def update_session(self, session: ChatSession):
        session.updated_at = datetime.now().isoformat()
        self._save()

    def toggle_pin(self, session_id: str):
        for s in self.sessions:
            if s.id == session_id:
                s.is_pinned = not s.is_pinned
                self.update_session(s)
                return s
        return None

    def delete_session(self, session_id: str):
        self.sessions = [s for s in self.sessions if s.id != session_id]
        self._save()


# MARK: - 渚ц竟鏍忎細璇濋」鑷畾涔夋帶浠讹紙鏀寔鍙屽嚮閲嶅懡鍚嶏級
class SessionItemWidget(QWidget):
    pin_clicked = pyqtSignal(str)
    delete_clicked = pyqtSignal(str)
    clicked = pyqtSignal(str)
    rename_finished = pyqtSignal(str, str)  # 鏂颁俊鍙凤細閲嶅懡鍚嶅畬鎴愬悗 (session_id, new_title)

    def __init__(self, session: ChatSession):
        super().__init__()
        self.session = session
        self._is_editing = False
        self.setStyleSheet("background: transparent;")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(8)

        # 鏍囬鏄剧ず鏍囩
        self.title_label = QLabel(session.title)
        self.title_label.setStyleSheet("color: #E0E0E0; font-size: 14px;")
        self.title_label.setWordWrap(True)
        
        # 閲嶅懡鍚嶇紪杈戞
        self.title_edit = QLineEdit(session.title)
        self.title_edit.setStyleSheet("""
            QLineEdit { 
                background: rgba(255,255,255,0.15); 
                color: white; 
                border: 1px solid #1E88E5; 
                border-radius: 4px; 
                padding: 4px 8px; 
                font-size: 14px;
            }
        """)
        self.title_edit.hide()
        self.title_edit.editingFinished.connect(self._on_rename_finished)
        
        layout.addWidget(self.title_label, 1)
        layout.addWidget(self.title_edit, 1)

        self.pin_btn = QPushButton("馃搶")
        self.pin_btn.setFixedSize(28, 28)
        self.pin_btn.setStyleSheet("""
            QPushButton { background: transparent; border-radius: 4px; color: #90A4AE; font-size:14px; }
            QPushButton:hover { background: rgba(255,255,255,0.15); color: #FFC107; }
        """)
        self.pin_btn.clicked.connect(lambda: self.pin_clicked.emit(self.session.id))
        layout.addWidget(self.pin_btn)

        self.del_btn = QPushButton("馃棏")
        self.del_btn.setFixedSize(28, 28)
        self.del_btn.setStyleSheet("""
            QPushButton { background: transparent; border-radius: 4px; color: #90A4AE; font-size:14px; }
            QPushButton:hover { background: rgba(255,255,255,0.15); color: #EF5350; }
        """)
        self.del_btn.clicked.connect(lambda: self.delete_clicked.emit(self.session.id))
        layout.addWidget(self.del_btn)

        if session.is_pinned:
            self.title_label.setStyleSheet("color: #FFC107; font-size:14px; font-weight:bold;")

    def mouseDoubleClickEvent(self, event):
        """鍙屽嚮杩涘叆閲嶅懡鍚嶆ā寮?""
        if not self._is_editing and event.button() == Qt.MouseButton.LeftButton:
            self._start_editing()

    def mouseReleaseEvent(self, event):
        """鍗曞嚮锛堥潪鍙屽嚮锛夎Е鍙戝垏鎹細璇?""
        if not self._is_editing and event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.session.id)

    def _start_editing(self):
        """寮€濮嬬紪杈戞爣棰?""
        self._is_editing = True
        self.title_label.hide()
        self.title_edit.show()
        self.title_edit.setFocus()
        self.title_edit.selectAll()

    def _on_rename_finished(self):
        """缂栬緫瀹屾垚锛屼繚瀛樻柊鏍囬"""
        new_title = self.title_edit.text().strip()
        if not new_title:
            new_title = self.session.title
        self.session.title = new_title
        self.title_label.setText(new_title)
        self.title_edit.hide()
        self.title_label.show()
        self._is_editing = False
        self.rename_finished.emit(self.session.id, new_title)


# MARK: - 鏍稿績閫昏緫寮曟搸
class StockEngine:
    def __init__(self, api_key):
        self.api_key = api_key
        self.concept_db = ConceptDatabase()
        self.concept_dict = self.concept_db.get_all_concepts()
        
        from langchain_openai import ChatOpenAI
        self.llm = ChatOpenAI(
            model="deepseek-chat",
            base_url="https://api.deepseek.com",
            api_key=self.api_key,
            temperature=0.4,
            timeout=60
        )
        
        from langchain_core.messages import BaseMessage
        self.chat_history: list[BaseMessage] = []

    def load_history_from_list(self, msg_list):
        from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
        self.chat_history.clear()
        for m in msg_list:
            if m["type"] == "human":
                self.chat_history.append(HumanMessage(content=m["content"]))
            elif m["type"] == "ai":
                self.chat_history.append(AIMessage(content=m["content"]))

    def save_history_to_list(self):
        result = []
        for m in self.chat_history:
            if hasattr(m, 'type') and hasattr(m, 'content'):
                result.append({"type": m.type, "content": m.content})
        return result

    async def translate_code(self, keyword):
        if keyword in self.concept_dict:
            return self.concept_dict[keyword]
        url = f"https://suggest3.sinajs.cn/suggest/type=&key={keyword}"
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as resp:
                    text = await resp.text(encoding='gbk')
                    if '"' in text:
                        match_val = text.split('"')[1]
                        if match_val:
                            parts = match_val.split(',')
                            for p in parts:
                                if any(p.startswith(pre) for pre in ["sh", "sz", "gb", "hk"]):
                                    return p
            except:
                pass
        return keyword

    async def fetch_sina_data(self, code):
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(
                    f"https://hq.sinajs.cn/list={code}",
                    headers={'Referer': 'https://finance.sina.com.cn'}
                ) as resp:
                    return await resp.text(encoding='gbk')
            except Exception as e:
                return f"鎶撳彇澶辫触: {str(e)}"

    def clear_memory(self):
        self.chat_history.clear()

    async def get_analysis(self, keyword):
        try:
            from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
            
            is_new_stock_query = len(self.chat_history) == 0 or any(
                kw in keyword for kw in ["鎸囨暟", "鑲＄エ", "ETF", "涓婅瘉鎸囨暟", "鍒涗笟鏉挎寚", "绾虫柉杈惧厠", "鎭掔敓"]
            )
            
            is_market_overview = any(
                kw in keyword for kw in ["澶х洏", "A鑲℃€讳綋", "甯傚満鎬讳綋", "涓夊ぇ鎸囨暟"]
            )
            
            current_analysis_data = ""
            
            if is_new_stock_query:
                if is_market_overview:
                    sh_data = await self.fetch_sina_data("sh000001")
                    sz_data = await self.fetch_sina_data("sz399001")
                    cyb_data = await self.fetch_sina_data("sz399006")
                    current_analysis_data = f"""=== 涓婅瘉鎸囨暟瀹炴椂鏁版嵁 ===\n{sh_data}\n\n=== 娣辫瘉鎴愭寚瀹炴椂鏁版嵁 ===\n{sz_data}\n\n=== 鍒涗笟鏉挎寚瀹炴椂鏁版嵁 ===\n{cyb_data}"""
                else:
                    code = await self.translate_code(keyword)
                    market_data = await self.fetch_sina_data(code)
                    current_analysis_data = market_data
            
            system_prompt_text = """浣犵幇鍦ㄦ槸涓€浣嶈祫娣辩殑鍏嫙 FOF 鍩洪噾缁忕悊鍜岃祫浜ч厤缃笓瀹讹紝涔熸槸鐢ㄦ埛鐨勪笓灞炴櫤鑳芥姇鐮斿姪鐞嗐€?
            
浣犳嫢鏈夊畬鏁寸殑瀵硅瘽璁板繂锛岃兘璁颁綇涔嬪墠鎵€鏈夌殑鐢ㄦ埛鎻愰棶鍜屼綘鐨勫洖绛斻€傚鏋滅敤鎴烽棶鐨勯棶棰橀渶瑕佸弬鑰冧箣鍓嶇殑琛屾儏鏁版嵁鎴栧璇濆唴瀹癸紝浣犺鑷姩璋冨彇涓婁笅鏂囦俊鎭紝涓嶉渶瑕佺敤鎴烽噸澶嶈鏄庛€?

銆愬垎鏋愰€昏緫瑕佹眰銆戯細
涓€銆佸畯瑙傚ぉ姘旂爺鍒わ細鍒嗘瀽瀹藉熀鎸囨暟銆傚垽鏂綋鍓嶆槸杩涙敾锛堟垚闀?绉戞妧锛夎繕鏄槻瀹堬紙绾㈠埄/澶х洏锛夐鏍硷紵
浜屻€佸井瑙傝祫浜ч€忚锛氱偣璇勫叿浣撶殑 ETF 鎴栨澘鍧楀紓鍔ㄣ€傛槸鍚﹀瓨鍦ㄦ澘鍧楀叡鎸紵璧勯噾鎵挎帴鍔涘浣曪紵
涓夈€佸疄鎴樻搷浣滃缓璁細鍩轰簬鍦哄鍩洪噾 T+1 鎴栧満鍐?ETF T+0 鐨勭壒鎬э紝缁欏嚭鏄庣‘鐨勭敵璧庛€佸畾鎶曟垨璋冧粨寤鸿銆?

銆愭帓鐗堜弗鍘夎鍛娿€戯細
1. 鎵€鏈夌殑涓€绾ф爣棰橈紙濡傗€滀竴銆佸畯瑙傚ぉ姘旂爺鍒も€濓級蹇呴』涓ユ牸浠?### 寮€澶达紒渚嬪锛?## 涓€銆佸畯瑙傚ぉ姘旂爺鍒?
2. 缁濆绂佹浣跨敤 **, ##, #, ` 绛?Markdown 绗﹀彿锛?
3. 鏁版嵁瀵规瘮閮ㄥ垎锛氬繀椤讳娇鐢ㄦ爣鍑?Markdown 琛ㄦ牸 (鐢?| 鍒嗛殧) 杈撳嚭锛屼笖琛ㄦ牸涓婁笅蹇呴』鍚勭暀涓€涓┖琛屻€?
4. 瀛楁暟鎺у埗鍦?400 瀛椾互鍐咃紝淇濇寔涓撲笟涓ヨ皑銆?""
            
            final_messages = [SystemMessage(content=system_prompt_text)]
            final_messages.extend(self.chat_history)
            
            final_human_content = keyword
            if current_analysis_data:
                final_human_content = f"璇峰熀浜庝互涓嬪疄鏃惰鎯呮暟鎹挵鍐欐姇鐮旂畝鎶ワ細\n{current_analysis_data}"
            
            final_messages.append(HumanMessage(content=final_human_content))
            
            import asyncio
            response = await asyncio.to_thread(self.llm.invoke, final_messages)
            
            self.chat_history.append(HumanMessage(content=keyword))
            self.chat_history.append(AIMessage(content=response.content))
            
            return response.content
            
        except Exception as e:
            import traceback
            print(f"LangChain 閿欒璇︽儏: {traceback.format_exc()}")
            return f"AI 寮曟搸璋冪敤澶辫触: {str(e)}"


# MARK: - 馃寠 鐗╃悊娉㈡氮鑳屾櫙
class WaveBackground(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.phase = 0
        self.speed = 0.05
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_wave)
        self.timer.start(16)

    def update_wave(self):
        self.phase += self.speed
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        gradient = QLinearGradient(0, 0, 0, self.height())
        gradient.setColorAt(0, QColor("#E0F2F1"))
        gradient.setColorAt(1, QColor("#4FC3F7"))
        painter.fillRect(self.rect(), gradient)
        self.draw_wave(painter, self.phase, 30, "#FFFFFF", 0.4)
        self.draw_wave(painter, self.phase * 0.8 + 2, 50, "#B3E5FC", 0.3)

    def draw_wave(self, painter, phase, amp, color, opacity):
        path = QPainterPath()
        path.moveTo(0, self.height())
        for x in range(0, self.width() + 10, 10):
            t = (x / self.width()) * 2 * math.pi + phase
            y = self.height() * 0.7 + math.sin(t) * amp - math.cos(t * 2) * (amp / 4)
            path.lineTo(float(x), float(y))
        path.lineTo(self.width(), self.height())
        path.closeSubpath()
        painter.setOpacity(opacity)
        painter.fillPath(path, QColor(color))


# MARK: - 涓荤獥鍙?(DeepSeek 椋庢牸鍙屾爮鏋舵瀯)
class MainWindow(QMainWindow):
    analysis_finished = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.engine = StockEngine(os.getenv("DEEPSEEK_API_KEY", ""))
        self.storage = ChatStorage()
        self.current_session: ChatSession = None
        self.current_keyword = ""
        self.is_auto_refreshing = False

        self.setWindowTitle("鐭ヨ偂 - Windows 鎶曠爺缁堢")
        self.resize(1280, 800)

        self.analysis_finished.connect(self.update_display)
        self.central_widget = QStackedWidget()
        self.setCentralWidget(self.central_widget)

        self.auto_timer = QTimer(self)
        self.auto_timer.setInterval(300000)
        self.auto_timer.timeout.connect(self.auto_refresh_analysis)

        self.splash = QWidget()
        l = QVBoxLayout(self.splash)
        self.splash_lbl = QLabel("鐭ヨ偂锛屼綘鐨勪笓灞炴櫤鑳芥姇鐮斿姪鐞?)
        self.splash_lbl.setStyleSheet("font-size: 28px; color: #37474F; font-weight: 300;")
        self.splash_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        l.addWidget(self.splash_lbl)
        self.central_widget.addWidget(self.splash)

        self.main_ui = QWidget()
        self.main_ui.setLayout(self.main_app_content())
        self.central_widget.addWidget(self.main_ui)

        self.bg = WaveBackground(self)
        self.bg.lower()
        
        if len(self.storage.sessions) == 0:
            self.current_session = self.storage.create_new_session()
        else:
            self.current_session = self.storage.sessions[0]
            self.engine.load_history_from_list(self.current_session.messages)
        
        self.refresh_sidebar()
        QTimer.singleShot(2500, self.go_to_main)

    def main_app_content(self):
        main_hbox = QHBoxLayout()
        main_hbox.setContentsMargins(0, 0, 0, 0)
        main_hbox.setSpacing(0)

        # ===== 宸︿晶杈规爮 - DeepSeek 椋庢牸瀵硅瘽鍘嗗彶 =====
        sidebar = QWidget()
        sidebar.setFixedWidth(260)
        sidebar.setStyleSheet("background: #121212;")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 15, 12, 15)
        sidebar_layout.setSpacing(10)

        new_chat_btn = QPushButton("鉃?寮€鍚柊瀵硅瘽")
        new_chat_btn.setFixedHeight(42)
        new_chat_btn.setStyleSheet("""
            QPushButton { 
                background: #1E88E5; color: white; 
                border-radius: 21px; font-weight: bold; font-size:14px;
            }
            QPushButton:hover { background: #1976D2; }
        """)
        new_chat_btn.clicked.connect(self.create_new_session)
        sidebar_layout.addWidget(new_chat_btn)

        self.sidebar_scroll = QScrollArea()
        self.sidebar_scroll.setWidgetResizable(True)
        self.sidebar_scroll.setStyleSheet("background: transparent; border: none;")
        self.session_list_container = QWidget()
        self.session_list_layout = QVBoxLayout(self.session_list_container)
        self.session_list_layout.setContentsMargins(0,0,0,0)
        self.session_list_layout.setSpacing(2)
        self.session_list_layout.addStretch()
        self.sidebar_scroll.setWidget(self.session_list_container)
        sidebar_layout.addWidget(self.sidebar_scroll)

        main_hbox.addWidget(sidebar)

        # ===== 鍙充晶涓诲唴瀹瑰尯 =====
        right_area = QWidget()
        right_area_layout = QVBoxLayout(right_area)
        right_area_layout.setContentsMargins(40, 40, 40, 40)
        right_area_layout.setSpacing(20)

        title = QLabel("鐭ヨ偂")
        title.setStyleSheet("font-size: 65px; font-weight: bold; color: #263238; margin-bottom: 5px;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_area_layout.addWidget(title)

        search_box = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("杈撳叆闂...")
        self.input.setFixedHeight(52)
        self.input.setStyleSheet(
            "border-radius: 26px; padding: 0 24px; font-size: 16px; background: rgba(255,255,255,0.95); color: #333333; border: 1px solid #CFD8DC;")
        self.input.returnPressed.connect(self.run_analysis_task)

        self.btn = QPushButton("馃攳 鍙戦€?)
        self.btn.setFixedHeight(52)
        self.btn.setFixedWidth(110)
        self.btn.setStyleSheet("background: #0288D1; color: white; border-radius: 26px; font-weight: bold;")
        self.btn.clicked.connect(self.run_analysis_task)

        self.refresh_btn = QPushButton("馃攧 鍒锋柊")
        self.refresh_btn.setFixedHeight(52)
        self.refresh_btn.setFixedWidth(100)
        self.refresh_btn.setStyleSheet("background: #26A69A; color: white; border-radius: 26px; font-weight: bold;")
        self.refresh_btn.clicked.connect(self.manual_refresh)

        search_box.addWidget(self.input, 1)
        search_box.addWidget(self.btn)
        search_box.addWidget(self.refresh_btn)
        right_area_layout.addLayout(search_box)

        self.status_label = QLabel("馃挕 浣犵殑涓撳睘鏅鸿兘鎶曠爺鍔╃悊")
        self.status_label.setStyleSheet("color: #546E7A; font-size: 13px; padding: 5px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right_area_layout.addWidget(self.status_label)

        self.display = QTextBrowser()
        self.display.setStyleSheet("""
            QTextBrowser {
                background: rgba(255,255,255,0.88); 
                border-radius: 18px; 
                padding: 28px; 
                border: 1px solid rgba(200, 200, 200, 0.3);
                color: #222222; 
            }
        """)
        right_area_layout.addWidget(self.display)

        main_hbox.addWidget(right_area, 1)
        return main_hbox

    def refresh_sidebar(self):
        for i in reversed(range(self.session_list_layout.count() - 1)):
            item = self.session_list_layout.itemAt(i)
            if item.widget():
                item.widget().deleteLater()

        sessions = self.storage.get_sorted_sessions()
        groups = {}
        for s in sessions:
            g = s.get_date_group()
            groups.setdefault(g, []).append(s)

        order = ["缃《", "浠婂ぉ", "鏄ㄥぉ", "7澶╁唴"]
        for s in sessions:
            if s.is_pinned and "缃《" not in groups:
                groups["缃《"] = [ss for ss in sessions if ss.is_pinned]

        group_order = ["缃《", "浠婂ぉ", "鏄ㄥぉ", "7澶╁唴"]
        for g_name in group_order:
            if g_name in groups and len(groups[g_name]) > 0:
                if g_name != "缃《" or len([ss for ss in groups[g_name] if ss.is_pinned]) > 0:
                    lbl = QLabel(g_name)
                    lbl.setStyleSheet("color: #78909C; font-size:12px; font-weight:bold; margin-top:10px;")
                    self.session_list_layout.insertWidget(self.session_list_layout.count()-1, lbl)
                for s in groups[g_name]:
                    item_w = SessionItemWidget(s)
                    item_w.clicked.connect(self.on_session_click)
                    item_w.pin_clicked.connect(self.on_session_pin)
                    item_w.delete_clicked.connect(self.on_session_delete)
                    item_w.rename_finished.connect(self.on_session_rename_finished)
                    if self.current_session and self.current_session.id == s.id:
                        item_w.setStyleSheet("background: rgba(30,136,229,0.2); border-radius: 8px;")
                    self.session_list_layout.insertWidget(self.session_list_layout.count()-1, item_w)

    def on_session_rename_finished(self, session_id, new_title):
        """閲嶅懡鍚嶅畬鎴愬悗鐨勫洖璋冿紝绔嬪嵆淇濆瓨"""
        for s in self.storage.sessions:
            if s.id == session_id:
                s.title = new_title
                self.storage.update_session(s)
                break

    def create_new_session(self):
        self.current_session = self.storage.create_new_session()
        self.engine.clear_memory()
        self.display.clear()
        self.refresh_sidebar()

    def on_session_click(self, session_id):
        target = None
        for s in self.storage.sessions:
            if s.id == session_id:
                target = s
                break
        if target:
            self.current_session = target
            self.engine.load_history_from_list(target.messages)
            self.display_current_content()
            self.refresh_sidebar()

    def on_session_pin(self, session_id):
        self.storage.toggle_pin(session_id)
        self.refresh_sidebar()

    def on_session_delete(self, session_id):
        self.storage.delete_session(session_id)
        if self.current_session and self.current_session.id == session_id:
            if len(self.storage.sessions) > 0:
                self.current_session = self.storage.sessions[0]
                self.engine.load_history_from_list(self.current_session.messages)
            else:
                self.current_session = self.storage.create_new_session()
                self.engine.clear_memory()
            self.display_current_content()
        self.refresh_sidebar()

    def display_current_content(self):
        self.display.clear()
        full_text = ""
        for msg in self.current_session.messages:
            if msg["type"] == "human":
                full_text += f"鐢ㄦ埛: {msg['content']}\n\n"
            elif msg["type"] == "ai":
                full_text += f"{msg['content']}\n\n"
        if full_text.strip():
            self.update_display(full_text)

    def go_to_main(self):
        self.central_widget.setCurrentIndex(1)
        self.bg.speed = 0.01
        self.display_current_content()

    def run_analysis_task(self):
        keyword = self.input.text().strip()
        if not keyword:
            return
        # 鏅鸿兘鑷姩鐢熸垚鏍囬閫昏緫锛氬彧鏈夌涓€娆¤闂椂鎵嶈嚜鍔ㄧ敓鎴?
        if self.current_session.title == "鏂板璇?:
            # 鍘婚櫎鏍囩偣绗﹀彿鐨勫共鍑€鏍囬
            cleaned = keyword.strip()
            # 鎴彇鏈€闀?2涓腑鏂囧瓧绗︼紙淇濊瘉渚ц竟鏍忚兘瀹屾暣鏄剧ず锛?
            auto_title = cleaned[:22] if len(cleaned) > 22 else cleaned
            self.current_session.title = auto_title
        self.current_keyword = keyword
        self.display.setHtml(f"<p style='color:gray;'>鈴?姝ｅ湪浠?FOF 缁忕悊瑙嗚鎺ㄦ紨 <b>{keyword}</b> 閫昏緫...</p>")
        self.btn.setEnabled(False)
        asyncio.create_task(self.do_analysis(keyword))
        self.is_auto_refreshing = True
        self.auto_timer.start()
        self.update_status_label()
        self.refresh_sidebar()

    def auto_refresh_analysis(self):
        if not self.current_keyword:
            return
        self.status_label.setText(f"馃攧 姝ｅ湪鑷姩鍒锋柊 <b>{self.current_keyword}</b> 鍒嗘瀽...")
        asyncio.create_task(self.do_analysis(self.current_keyword))

    def manual_refresh(self):
        if not self.current_keyword:
            self.current_keyword = self.input.text().strip() or "涓婅瘉鎸囨暟"
        self.display.setHtml(f"<p style='color:gray;'>馃攧 姝ｅ湪鎵嬪姩鍒锋柊 <b>{self.current_keyword}</b> 鏈€鏂板垎鏋?..</p>")
        self.btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        asyncio.create_task(self.do_analysis(self.current_keyword))
        self.is_auto_refreshing = True
        self.auto_timer.start()
        self.update_status_label()

    def update_status_label(self):
        from datetime import datetime
        self.status_label.setText(f"鉁?瀵硅瘽宸蹭繚瀛?)

    async def do_analysis(self, keyword):
        result = await self.engine.get_analysis(keyword)
        self.current_session.messages = self.engine.save_history_to_list()
        if len(self.engine.chat_history) >= 2:
            last_user_msg = self.engine.chat_history[-2].content if hasattr(self.engine.chat_history[-2], 'content') else keyword
            if len(last_user_msg) > 0:
                self.current_session.title = last_user_msg[:25] if len(last_user_msg) > 25 else last_user_msg
        self.storage.update_session(self.current_session)
        self.analysis_finished.emit(result)
        self.refresh_sidebar()

    def update_display(self, raw_text):
        clean_text = raw_text.replace("```markdown", "").replace("```", "")
        html_body = markdown.markdown(clean_text, extensions=['tables', 'nl2br'])
        styled_html = f"""
                <style>
                    body, p, li, td {{ font-family: 'Microsoft YaHei'; color: #222222; line-height: 1.8; font-size: 15px; }}
                    p {{ text-indent: 2em; margin-top: 8px; margin-bottom: 8px; }}
                    h3 {{ 
                        color: #0277BD; 
                        font-size: 18px; 
                        font-weight: 900; 
                        border-bottom: 2px solid #E1F5FE; 
                        padding-bottom: 8px; 
                        margin-top: 20px; 
                        margin-bottom: 15px; 
                        text-indent: 0; 
                    }}
                    table {{ border-collapse: collapse; width: 100%; margin: 15px 0; border: 1px solid #ECEFF1; }}
                    th {{ background-color: #E3F2FD; color: #01579B; padding: 10px; font-weight: bold; border: 1px solid #CFD8DC; }}
                    td {{ padding: 8px; border: 1px solid #ECEFF1; text-align: center; font-family: 'Consolas'; }}
                    tr:nth-child(even) td {{ background-color: #FAFAFA; }}
                </style>
                {html_body}
                """
        self.display.setHtml(styled_html)
        self.btn.setEnabled(True)
        self.refresh_btn.setEnabled(True)
        self.input.clear()
        if self.is_auto_refreshing:
            self.update_status_label()

    def resizeEvent(self, event):
        self.bg.resize(self.size())
        super().resizeEvent(event)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()

    import threading

    def run_asyncio_loop(loop):
        asyncio.set_event_loop(loop)
        loop.run_forever()

    new_loop = asyncio.new_event_loop()
    t = threading.Thread(target=run_asyncio_loop, args=(new_loop,), daemon=True)
    t.start()
    asyncio.create_task = lambda coro: asyncio.run_coroutine_threadsafe(coro, new_loop)

    sys.exit(app.exec())
