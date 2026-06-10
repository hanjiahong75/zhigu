import sqlite3
from typing import Dict, List, Optional


class ConceptDatabase:
    def __init__(self, db_path: str = "concepts.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS concepts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                code TEXT NOT NULL,
                category TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()

    def add_concept(self, name: str, code: str, category: str = "其他") -> bool:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO concepts (name, code, category, updated_at)
                VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ''', (name, code, category))
            conn.commit()
            conn.close()
            return True
        except Exception:
            return False

    def add_concepts_batch(self, concepts: Dict[str, str], category: str = "其他") -> int:
        count = 0
        conn = self._get_connection()
        cursor = conn.cursor()
        for name, code in concepts.items():
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO concepts (name, code, category, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                ''', (name, code, category))
                count += 1
            except Exception:
                pass
        conn.commit()
        conn.close()
        return count

    def get_code_by_name(self, name: str) -> Optional[str]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT code FROM concepts WHERE name = ?', (name,))
        row = cursor.fetchone()
        conn.close()
        return row['code'] if row else None

    def get_all_concepts(self) -> Dict[str, str]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT name, code FROM concepts')
        rows = cursor.fetchall()
        conn.close()
        return {row['name']: row['code'] for row in rows}

    def get_concepts_by_category(self, category: str) -> Dict[str, str]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT name, code FROM concepts WHERE category = ?', (category,))
        rows = cursor.fetchall()
        conn.close()
        return {row['name']: row['code'] for row in rows}

    def update_concept(self, name: str, new_code: str, new_category: Optional[str] = None) -> bool:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            if new_category:
                cursor.execute('''
                    UPDATE concepts SET code = ?, category = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE name = ?
                ''', (new_code, new_category, name))
            else:
                cursor.execute('''
                    UPDATE concepts SET code = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE name = ?
                ''', (new_code, name))
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
        except Exception:
            return False

    def delete_concept(self, name: str) -> bool:
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM concepts WHERE name = ?', (name,))
            conn.commit()
            conn.close()
            return cursor.rowcount > 0
        except Exception:
            return False

    def search_concepts(self, keyword: str) -> List[Dict]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('''
            SELECT name, code, category FROM concepts 
            WHERE name LIKE ? 
            ORDER BY name
        ''', (f'%{keyword}%',))
        rows = cursor.fetchall()
        conn.close()
        return [{'name': row['name'], 'code': row['code'], 'category': row['category']} for row in rows]

    def get_categories(self) -> List[str]:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT DISTINCT category FROM concepts ORDER BY category')
        rows = cursor.fetchall()
        conn.close()
        return [row['category'] for row in rows]

    def count_all(self) -> int:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as cnt FROM concepts')
        row = cursor.fetchone()
        conn.close()
        return row['cnt']


def init_default_concepts(db: ConceptDatabase):
    default_concepts = {
        "A股主流指数": {
            "上证指数": "sh000001",
            "深证成指": "sz399001",
            "创业板指": "sz399006",
            "科创50": "sh000688",
            "北证50": "bj899050",
            "沪深300": "sh000300",
            "中证500": "sh000905",
            "中证1000": "sh000852",
            "上证50": "sh000016",
            "中证2000": "sh000906",
            "上证综指": "sh000001",
            "深证综指": "sz399106",
        },
        "港股指数": {
            "恒生指数": "hkhsi",
            "恒生科技": "hkhstech",
            "国企指数": "hkhscei",
            "红筹指数": "hkhscci",
        },
        "美股指数": {
            "纳斯达克": "gb_ixic",
            "道琼斯": "gb_dji",
            "标普500": "gb_spx",
            "纳斯达克100": "gb_ndx",
        },
        "海外个股": {
            "英伟达": "gb_nvda",
            "苹果": "gb_aapl",
            "微软": "gb_msft",
            "谷歌": "gb_goog",
            "亚马逊": "gb_amzn",
            "特斯拉": "gb_tsla",
            "Meta": "gb_meta",
        },
        "AI科技板块": {
            "AI应用": "sz300229,sz300418,sh603019",
            "商业航天": "sz300053,sz002025,sh600118",
            "存储器": "sh600667,sz300672,sz000977",
            "可控核聚变": "sz002130,sh600875,sz000875",
            "半导体": "sh688981,sz002371,sh603501",
            "CPO": "sz002281,sz300308,sh600487",
            "PCB": "sz002916,sz002463,sz002938",
            "新能源": "sz300750,sz002594,sh601012",
            "机器人": "sz002747,sz300024,sz002979",
            "光模块": "sz002281,sz300308,sz300502",
            "算力": "sh603019,sz000977,sz300454",
            "大模型": "sz300229,sz300418,sh600588",
            "AI芯片": "sh688256,sz300458,sh603986",
            "汽车芯片": "sh688048,sz300613,sh603160",
            "消费电子": "sz002475,sz002241,sh603501",
            "医药生物": "sh600276,sz000661,sz300760",
            "创新药": "sh600276,sz300347,sh688180",
            "医疗器械": "sz300760,sz002223,sh688016",
            "白酒": "sh600519,sz000858,sz000568",
            "银行": "sh601398,sh601939,sh601288",
            "保险": "sh601318,sh601601,sh601336",
            "证券": "sh600030,sz000776,sh601211",
            "房地产": "sh600048,sz000002,sh601155",
            "基建": "sh601668,sh601390,sh600528",
            "有色": "sh601899,sz000831,sh600547",
            "煤炭": "sh601088,sh600188,sh601225",
            "钢铁": "sh600019,sz000709,sh600005",
            "石油石化": "sh601857,sh600028,sh600346",
            "电力": "sh600900,sz000883,sh601985",
            "军工": "sz002025,sh600765,sz300719",
            "传媒": "sz002607,sz300413,sz300251",
            "旅游酒店": "sz000721,sh600007,sz002033",
            "航空机场": "sh601111,sh600029,sh600009",
            "航运港口": "sh601919,sz000088,sh600018",
            "农业": "sh600108,sz000998,sz002311",
            "食品饮料": "sh600519,sz000858,sz000895",
            "家电": "sz000333,sz000651,sz002032",
            "纺织服装": "sh600398,sz002563,sz002656",
            "建筑材料": "sz000895,sh600585,sz000619",
            "建筑装饰": "sh601668,sz002789,sz002482",
            "计算机": "sh600588,sz000977,sz300454",
            "通信": "sh600050,sz000063,sh600198",
            "电子": "sz002475,sz002371,sh688981",
            "综合": "sh600648,sz000009,sh600705",
            "环保": "sh600008,sz300070,sz300137",
            "公用事业": "sh600900,sh601985,sz000883",
            "交运设备": "sz002594,sh600104,sz000625",
            "汽车整车": "sz002594,sh600104,sz000625",
            "新能源汽车": "sz002594,sh601012,sz300750",
            "光伏": "sh601012,sz002459,sz300274",
            "储能": "sz300750,sh600406,sz002121",
            "风电": "sh601615,sz002202,sz300772",
            "氢能": "sh600273,sz002211,sh600875",
            "钠离子电池": "sz300769,sh600499,sz002074",
            "钙钛矿": "sz300751,sh600620,sz000959",
            "固态电池": "sz300750,sh600438,sz002460",
            "人形机器人": "sz002747,sz300024,sz002979",
            "自动驾驶": "sz002415,sz002920,sh688256",
            "卫星互联网": "sz300053,sz002402,sh600118",
            "6G": "sh600050,sz300638,sz002281",
            "量子计算": "sh600522,sh600171,sz002156",
            "元宇宙": "sz300251,sz300229,sh600880",
            "VRAR": "sz002415,sz300081,sz300458",
            "游戏": "sz002555,sz002607,sz300413",
            "直播电商": "sz300413,sh603100,sz002027",
            "跨境电商": "sz002697,sz002154,sz300979",
            "数字货币": "sz002152,sz300099,sh600094",
            "数据要素": "sz000977,sh603881,sz300229",
            "信创": "sh600588,sz000977,sz300454",
            "鸿蒙概念": "sz002436,sz300458,sh600183",
            "华为概念": "sz002594,sh600183,sz002456",
            "苹果概念": "sz002475,sz002241,sz002456",
            "特斯拉概念": "sz002594,sz002460,sh600438",
            "ChatGPT": "sz300229,sz300418,sh603019",
            "AIGC": "sz300229,sz300251,sz300418",
            "共封装光学": "sz300308,sz300502,sz002281",
        },
        "龙头个股": {
            "寒武纪": "sh688256",
            "中际旭创": "sz300308",
            "新易盛": "sz300502",
            "贵州茅台": "sh600519",
            "工商银行": "sh601398",
            "建设银行": "sh601939",
            "农业银行": "sh601288",
            "中国银行": "sh601988",
            "腾讯": "hk0700",
            "阿里巴巴": "hk9988",
            "美团": "hk3690",
            "小米": "hk1810",
            "宁德时代": "sz300750",
            "比亚迪": "sz002594",
            "隆基绿能": "sh601012",
            "中国平安": "sh601318",
            "招商银行": "sh600036",
            "五粮液": "sz000858",
            "泸州老窖": "sz000568",
            "中国中免": "sh601888",
            "海康威视": "sz002415",
            "迈瑞医疗": "sz300760",
            "药明康德": "sh600276",
            "恒瑞医药": "sh600276",
            "宁波银行": "sz002142",
            "紫金矿业": "sh601899",
            "中国神华": "sh601088",
            "长江电力": "sh600900",
            "中国建筑": "sh601668",
            "美的集团": "sz000333",
            "格力电器": "sz000651",
            "海尔智家": "sh600690",
            "三一重工": "sh600031",
            "海螺水泥": "sh600585",
            "万科A": "sz000002",
            "保利发展": "sh600048",
            "中国中铁": "sh601390",
            "中国铁建": "sh601186",
            "中兴通讯": "sz000063",
            "中国电信": "sh601728",
            "中国联通": "sh600050",
            "中国移动": "sh600941",
            "立讯精密": "sz002475",
            "歌尔股份": "sz002241",
            "蓝思科技": "sz300433",
            "闻泰科技": "sh600745",
            "北方华创": "sz002371",
            "中芯国际": "sh688981",
            "韦尔股份": "sh603501",
            "兆易创新": "sh603986",
            "长电科技": "sh600584",
            "三安光电": "sh600703",
            "京东方A": "sz000725",
            "TCL中环": "sz002129",
            "通威股份": "sh600438",
            "阳光电源": "sz300274",
            "晶澳科技": "sz002459",
            "晶科能源": "sh688223",
            "天合光能": "sh688599",
            "东方财富": "sz300059",
            "同花顺": "sz300033",
            "指南针": "sz300803",
            "中国银河": "sh601881",
            "中信证券": "sh600030",
            "东方证券": "sh600958",
            "国泰君安": "sh601211",
            "海通证券": "sh600837",
            "广发证券": "sz000776",
            "华泰证券": "sh601688",
            "中国人寿": "sh601628",
            "中国太保": "sh601601",
            "新华保险": "sh601336",
            "中国核电": "sh601985",
            "中国广核": "sz003816",
            "国电电力": "sh600795",
            "华能国际": "sh600011",
            "大唐发电": "sh601991",
            "中国石化": "sh600028",
            "中国石油": "sh601857",
            "中国海油": "sh600938",
            "中国铝业": "sh601600",
            "江西铜业": "sh600362",
            "云南铜业": "sz000878",
            "铜陵有色": "sz000630",
            "宝钢股份": "sh600019",
            "鞍钢股份": "sz000898",
            "包钢股份": "sh600010",
            "中远海控": "sh601919",
            "中远海发": "sh601866",
            "上港集团": "sh600018",
            "宁波港": "sh601018",
            "春秋航空": "sh601021",
            "中国国航": "sh601111",
            "南方航空": "sh600029",
            "东方航空": "sh600115",
            "海航控股": "sh600221",
            "中国电影": "sh600977",
            "光线传媒": "sz300251",
            "万达电影": "sz002739",
            "芒果超媒": "sz300413",
            "分众传媒": "sz002027",
            "三七互娱": "sz002555",
            "完美世界": "sz002624",
            "巨人网络": "sz002558",
            "昆仑万维": "sz300418",
            "蓝色光标": "sz300058",
            "中文在线": "sz300364",
            "人民网": "sh603000",
            "新华网": "sh603888",
            "中科曙光": "sh603019",
            "浪潮信息": "sz000977",
            "用友网络": "sh600588",
            "金山办公": "sh688111",
            "万兴科技": "sz300624",
            "恒生电子": "sh600570",
            "科大讯飞": "sz002230",
            "四维图新": "sz002405",
            "软通动力": "sz301236",
            "中科创达": "sz300496",
            "德赛西威": "sz002920",
            "华阳集团": "sz002906",
            "北斗星通": "sz002151",
            "中国卫星": "sh600118",
            "中航西飞": "sz000768",
            "中航沈飞": "sh600760",
            "中航光电": "sz002179",
            "航发动力": "sh600893",
            "洪都航空": "sh600316",
            "中直股份": "sh600038",
            "中国重工": "sh601989",
            "中国船舶": "sh600150",
            "北方导航": "sh600435",
            "振华科技": "sz000733",
            "紫光国微": "sz002049",
            "七一二": "sh603712",
            "中国长城": "sz000066",
            "中国软件": "sh600536",
            "太极股份": "sz002368",
            "航天电子": "sh600879",
            "航天动力": "sh600343",
            "中国卫通": "sh601698",
            "铖昌科技": "sz001270",
            "海格通信": "sz002465",
            "华力创通": "sz300045",
            "振芯科技": "sz300101",
            "波导股份": "sh600130",
            "大唐电信": "sh600198",
            "烽火通信": "sh600498",
            "中天科技": "sh600522",
            "亨通光电": "sh600487",
            "通宇通讯": "sz002792",
            "盛科通信": "sh688702",
            "芯原股份": "sh688521",
            "景嘉微": "sz300474",
            "海光信息": "sh688041",
            "龙芯中科": "sh688047",
            "中核科技": "sz000777",
            "沃尔核材": "sz002130",
            "中核钛白": "sz002145",
            "宝钛股份": "sh600456",
            "西部材料": "sz002149",
            "东方锆业": "sz002167",
            "中广核技": "sz000881",
            "尚纬股份": "sh603333",
            "科新机电": "sz300092",
            "中泰股份": "sz300435",
            "深冷股份": "sz300540",
            "京城股份": "sh600860",
            "美锦能源": "sz000723",
            "潍柴动力": "sz000338",
            "亿华通": "sh688339",
            "雄韬股份": "sz002733",
            "厚普股份": "sz300471",
            "科力远": "sh600478",
            "大洋电机": "sz002249",
            "中通客车": "sz000957",
            "宇通客车": "sh600066",
            "金龙汽车": "sh600686",
            "亚星客车": "sh600213",
            "安凯客车": "sz000868",
            "福田汽车": "sh600166",
            "江淮汽车": "sh600418",
            "长安汽车": "sz000625",
            "长城汽车": "sh601633",
            "上汽集团": "sh600104",
            "广汽集团": "sh601238",
            "赛力斯": "sh601127",
            "理想汽车": "hk2015",
            "小鹏汽车": "hk9868",
            "蔚来": "hk9866",
            "吉利汽车": "hk0175",
            "国轩高科": "sz002074",
            "亿纬锂能": "sz300014",
            "欣旺达": "sz300207",
            "孚能科技": "sh688567",
            "鹏辉能源": "sz300438",
            "派能科技": "sh688063",
            "天奈科技": "sh688116",
            "容百科技": "sh688005",
            "当升科技": "sz300073",
            "贝特瑞": "bj835185",
            "璞泰来": "sh603659",
            "恩捷股份": "sz002812",
            "星源材质": "sz300568",
            "中科三环": "sz000970",
            "横店东磁": "sz002056",
            "正海磁材": "sz300224",
            "金力永磁": "sz300748",
            "宁波韵升": "sh600366",
            "英洛华": "sz000795",
            "中钢天源": "sz002057",
            "大地熊": "sh688077",
            "龙磁科技": "sz300835",
            "银河磁体": "sz300127",
        },
    }
    
    for category, concepts in default_concepts.items():
        db.add_concepts_batch(concepts, category)


if __name__ == "__main__":
    db = ConceptDatabase()
    init_default_concepts(db)
    print(f"数据库初始化完成，共导入 {db.count_all()} 条概念记录")
