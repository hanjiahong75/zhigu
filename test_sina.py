import requests

print("="*60)
print("新浪财经指数原始数据实测")
print("="*60)

# 上证指数、深证成指、创业板指标准新浪代码
codes = {
    "上证指数": "sh000001",
    "深证成指": "sz399001",
    "创业板指": "sz399006"
}

headers = {'Referer': 'https://finance.sina.com.cn'}

for name, code in codes.items():
    print(f"\n--- 正在获取: {name} (代码: {code}) ---")
    try:
        resp = requests.get(f"https://hq.sinajs.cn/list={code}", headers=headers, timeout=10)
        resp.encoding = 'gbk'
        raw_text = resp.text
        print(f"原始返回: {raw_text}")
        
        # 解析测试
        if '=' in raw_text and ';' in raw_text:
            data_part = raw_text.split('=')[1].strip('"').strip(';')
            fields = data_part.split(',')
            print(f"字段数: {len(fields)}")
            if len(fields) >= 32:
                name_real = fields[0]
                open_p = fields[1]
                pre_close = fields[2]
                current = fields[3]
                high = fields[4]
                low = fields[5]
                change_pct = (float(current) - float(pre_close)) / float(pre_close) * 100
                print(f"解析结果: 名称={name_real}, 当前={current}, 昨收={pre_close}, 涨跌幅={change_pct:.2f}%")
    except Exception as e:
        print(f"错误: {e}")

print("\n" + "="*60)
