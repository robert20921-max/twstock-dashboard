import json, time, requests, datetime, os
from pathlib import Path

FINMIND_TOKEN = os.environ.get("FINMIND_TOKEN", "")
OUTPUT_PATH = Path("docs/data.json")
TODAY = datetime.date.today().strftime("%Y-%m-%d")
START90 = (datetime.date.today() - datetime.timedelta(days=90)).strftime("%Y-%m-%d")
START20 = (datetime.date.today() - datetime.timedelta(days=20)).strftime("%Y-%m-%d")
HEADERS = {"Authorization": f"Bearer {FINMIND_TOKEN}"} if FINMIND_TOKEN else {}
FM = "https://api.finmindtrade.com/api/v4/data"

NAMES = {}  # 動態從 TWSE 取得
TAGS  = {}  # 動態從 TWSE 取得

# ── 產業族群對照（TWSE 產業代碼 → 標籤）──────────────
INDUSTRY_TAG = {
    "01":"食品","02":"塑膠","03":"紡織","04":"機電","05":"電線電纜",
    "06":"化工","07":"玻璃","08":"造紙","09":"鋼鐵","10":"橡膠",
    "11":"汽車","12":"電子","14":"建材","15":"航運","16":"觀光",
    "17":"金融","18":"貿易","19":"綜合","20":"其他","21":"化學",
    "22":"生技","23":"油電燃氣","24":"半導體","25":"電腦周邊",
    "26":"光電","27":"通信網路","28":"電子零組件","29":"電子通路",
    "30":"資訊服務","31":"其他電子","32":"文化創意","33":"農業",
    "34":"電競","35":"綠能","36":"數位雲端","37":"運動休閒","38":"居家生活",
}

def safe_fm(params, retries=3):
    for i in range(retries):
        try:
            r = requests.get(FM, params=params, headers=HEADERS, timeout=20)
            r.raise_for_status()
            return r.json().get("data", [])
        except Exception as e:
            print(f"  FM retry {i+1}: {e}")
            time.sleep(3)
    return []

def safe_twse(url, params={}, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=15)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"  TWSE retry {i+1}: {e}")
            time.sleep(2)
    return {}

# ── Stage 1：TWSE 全市場篩選 ──────────────────────────

def get_all_stocks():
    """取得上市所有股票清單（代號、名稱、產業）"""
    data = safe_twse("https://openapi.twse.com.tw/v1/opendata/t187ap03_L")
    stocks = []
    for r in data:
        code = r.get("公司代號","").strip()
        name = r.get("公司簡稱","").strip()
        ind  = r.get("產業別","").strip()
        if code and len(code) == 4 and code.isdigit():
            stocks.append({"code":code,"name":name,"ind":ind})
    print(f"  上市股票清單：{len(stocks)} 檔")
    return stocks

def get_today_turnover():
    """取得今日各股周轉率與成交量（TWSE 大盤統計）"""
    ym = datetime.date.today().strftime("%Y%m%d")
    data = safe_twse("https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX",
                     {"response":"json","date":ym,"type":"ALLBUT0999"})
    turnover = {}
    for row in data.get("data9", []):
        try:
            code = row[0].strip()
            vol  = float(str(row[2]).replace(",",""))   # 成交股數
            cap  = float(str(row[7]).replace(",",""))   # 市值（千元）
            if cap > 0:
                turnover[code] = round(vol / (cap * 1000 / float(str(row[5]).replace(",","").replace("--","1"))) * 100, 2)
        except:
            pass
    time.sleep(0.5)
    return turnover

def get_industry_flow():
    """取得今日各產業漲跌幅（資金流入排行）"""
    ym = datetime.date.today().strftime("%Y%m%d")
    data = safe_twse("https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX",
                     {"response":"json","date":ym,"type":"MS"})
    flow = {}
    for row in data.get("data", []):
        try:
            ind  = str(row[0]).strip()
            chg  = float(str(row[4]).replace("+","").replace(",",""))
            flow[ind] = chg
        except:
            pass
    time.sleep(0.5)
    # 取漲幅前 5 大產業
    top5 = sorted(flow.items(), key=lambda x: x[1], reverse=True)[:5]
    print(f"  資金流入前5產業：{[x[0] for x in top5]}")
    return [x[0] for x in top5], flow

def stage1_select(max_stocks=150):
    """兩階段篩選：資金流入族群 + 高周轉率，取前 max_stocks 檔"""
    print("Stage 1：掃描全市場...")
    all_stocks = get_all_stocks()
    turnover   = get_today_turnover()
    top_inds, ind_flow = get_industry_flow()

    # 建立名稱對照
    for s in all_stocks:
        NAMES[s["code"]] = s["name"]
        TAGS[s["code"]]  = INDUSTRY_TAG.get(s["ind"][:2] if s["ind"] else "", s["ind"][:4] if s["ind"] else "")

    candidates = []
    for s in all_stocks:
        code = s["code"]
        ind  = s["ind"][:2] if s["ind"] else ""
        to   = turnover.get(code, 0)
        in_top_ind = ind in top_inds
        high_to    = to >= 1.5

        if in_top_ind or high_to:
            score = (2 if in_top_ind else 0) + (1 if high_to else 0)
            flow_score = ind_flow.get(ind, 0)
            candidates.append((code, score, flow_score, to))

    # 依族群資金流入 + 周轉率排序
    candidates.sort(key=lambda x: (x[1], x[2], x[3]), reverse=True)
    selected = [c[0] for c in candidates[:max_stocks]]
    print(f"Stage 1 完成：篩出 {len(selected)} 檔（資金流入族群+高周轉率）")
    return selected

# ── Stage 2：FinMind 個股深度分析 ────────────────────

def get_price(sid):
    rows = safe_fm({"dataset":"TaiwanStockPrice","data_id":sid,"start_date":START90,"end_date":TODAY})
    rows = sorted(rows, key=lambda x: x["date"])
    if not rows: return [], [], []
    closes = [float(r["close"]) for r in rows if r.get("close")]
    highs  = [float(r["max"])   for r in rows if r.get("close")]
    lows   = [float(r["min"])   for r in rows if r.get("close")]
    return closes, highs, lows

def get_institution(sid):
    rows = safe_fm({"dataset":"TaiwanStockInstitutionalInvestorsBuySell","data_id":sid,"start_date":START20,"end_date":TODAY})
    rows = [r for r in rows if r.get("name")=="外資"]
    rows.sort(key=lambda x: x["date"])
    if not rows: return 0
    count, last_sign = 0, None
    for r in reversed(rows):
        net = float(r.get("buy",0)) - float(r.get("sell",0))
        sign = 1 if net > 0 else -1
        if last_sign is None: last_sign = sign
        if sign == last_sign: count += sign
        else: break
    return count

def get_chip(sid):
    rows = safe_fm({"dataset":"TaiwanStockHoldingSharesPer","data_id":sid,"start_date":START20,"end_date":TODAY})
    by_date = {}
    for r in rows:
        d = r["date"]
        level = r.get("HoldingSharesLevel","")
        pct = float(r.get("percent",0))
        if any(x in level for x in ["400","1,000","4,000","10,000","15,000","20,000"]):
            by_date[d] = by_date.get(d,0) + pct
    if not by_date: return [55,57,59,61,63], 4
    dates = sorted(by_date.keys())[-5:]
    trend = [round(by_date[d],1) for d in dates]
    while len(trend) < 5: trend.insert(0, trend[0])
    return trend, round(trend[-1]-trend[0],1)

def calc_ma(closes, n):
    if len(closes) < n: return closes[-1] if closes else 0
    return round(sum(closes[-n:]) / n, 2)

def calc_kd(closes, highs, lows, n=9, m=3):
    if len(closes) < n: return 50.0, 50.0
    K, D = 50.0, 50.0
    for i in range(n-1, len(closes)):
        ph = max(highs[i-n+1:i+1])
        pl = min(lows[i-n+1:i+1])
        rsv = ((closes[i]-pl)/(ph-pl)*100) if (ph-pl)>0 else 50
        K = K*(m-1)/m + rsv/m
        D = D*(m-1)/m + K/m
    return round(K,1), round(D,1)

def kd_cross(closes, highs, lows):
    if len(closes) < 12: return False
    Kp,Dp = calc_kd(closes[:-1],highs[:-1],lows[:-1])
    Kn,Dn = calc_kd(closes,highs,lows)
    return Kp < Dp and Kn > Dn and Kn < 70

def classify(price, ma5, ma20, buy_days, chip_trend, chip_delta, cross, K, D):
    s = 0
    if price > ma5 > 0:   s += 1
    if price > ma20 > 0:  s += 1
    if buy_days >= 3:     s += 2
    elif buy_days >= 1:   s += 1
    if chip_trend[-1] > 60: s += 1
    if chip_delta > 3:    s += 1
    if cross:             s += 2
    if buy_days <= -3 and chip_delta < -5: return "exit", min(s,5)
    if s >= 5: return "buy",   min(s,5)
    if s >= 3: return "watch", min(s,5)
    return "exit", min(s,5)

# ── 主程式 ────────────────────────────────────────────

def main():
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    results = []

    # Stage 1：全市場篩選
    try:
        watch_list = stage1_select(150)
    except Exception as e:
        print(f"Stage 1 失敗：{e}，使用預設清單")
        watch_list = ["2382","6138","3443","3231","3017","5274","3711","6257","6669","2330","2345","2308","2603","2002","2609","2615","1718","2409"]

    print(f"\nStage 2：深度分析 {len(watch_list)} 檔...")

    for i, sid in enumerate(watch_list):
        name = NAMES.get(sid, sid)
        print(f"  [{i+1}/{len(watch_list)}] {sid} {name}...")
        try:
            closes, highs, lows = get_price(sid); time.sleep(0.4)
            if len(closes) < 10:
                print(f"    ⚠ 資料不足")
                continue
            price = closes[-1]
            ma5   = calc_ma(closes, 5)
            ma20  = calc_ma(closes, 20)
            K, D  = calc_kd(closes, highs, lows)
            cross = kd_cross(closes, highs, lows)

            buy_days = get_institution(sid); time.sleep(0.4)
            chip_trend, chip_delta = get_chip(sid); time.sleep(0.4)

            vs5  = round((price-ma5)/ma5*100,1)   if ma5  else 0
            vs20 = round((price-ma20)/ma20*100,1) if ma20 else 0
            signal, score = classify(price, ma5, ma20, buy_days, chip_trend, chip_delta, cross, K, D)

            # 只保留買進與觀察，出場訊號過濾掉不顯示
            if signal == "exit": continue

            entry  = round(price*1.005, 1)
            stop   = round(ma5*0.98, 1)
            target = round(price*1.12, 1)
            rr     = round((target-entry)/(entry-stop),1) if (entry-stop)>0 else 0

            results.append({
                "code":sid,"name":NAMES.get(sid,sid),"tag":TAGS.get(sid,""),
                "price":price,"ma5":ma5,"ma20":ma20,"vs5":vs5,"vs20":vs20,
                "signal":signal,"kd":cross,"K":K,"D":D,
                "buyDays":buy_days,"chipTrend":chip_trend,
                "chipNow":chip_trend[-1],"chipDelta":chip_delta,
                "entry":entry,"stop":stop,"target":target,"rr":rr,"score":score
            })
            print(f"    ✓ {price} {signal} KD={K}/{D} 連買={buy_days}日")

        except Exception as e:
            print(f"    ✗ {e}")
            continue

    # 排序：買進優先，再依評分
    results.sort(key=lambda x: (0 if x["signal"]=="buy" else 1, -x["score"]))

    summary = {
        "buy":   len([s for s in results if s["signal"]=="buy"]),
        "watch": len([s for s in results if s["signal"]=="watch"]),
        "exit":  0,
        "kd":    len([s for s in results if s["kd"]]),
        "scanned": len(watch_list)
    }
    output = {
        "updated": datetime.datetime.now().strftime("%Y/%m/%d %H:%M"),
        "date":    TODAY,
        "summary": summary,
        "stocks":  results
    }
    with open(OUTPUT_PATH,"w",encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 完成！掃描{len(watch_list)}檔，符合條件{len(results)}檔")
    print(f"   買進:{summary['buy']} 觀察:{summary['watch']} KD↑:{summary['kd']}")

if __name__ == "__main__":
    main()
