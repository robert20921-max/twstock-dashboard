import json, time, requests, datetime, os
from pathlib import Path

FINMIND_TOKEN = os.environ.get("FINMIND_TOKEN", "")
OUTPUT_PATH = Path("docs/data.json")
TODAY = datetime.date.today().strftime("%Y-%m-%d")
START90 = (datetime.date.today() - datetime.timedelta(days=90)).strftime("%Y-%m-%d")
START20 = (datetime.date.today() - datetime.timedelta(days=20)).strftime("%Y-%m-%d")
HEADERS = {"Authorization": f"Bearer {FINMIND_TOKEN}"} if FINMIND_TOKEN else {}
FM = "https://api.finmindtrade.com/api/v4/data"

WATCH = {
    "2317":"鴻海","3231":"緯創","6669":"緯穎","2382":"廣達","2356":"英業達",
    "2324":"仁寶","3706":"神達","4938":"和碩","2352":"佳世達","2395":"研華",
    "2330":"台積電","2303":"聯電","5347":"世界","6770":"力積電","3661":"世芯-KY",
    "3443":"創意","6533":"智原","6643":"M31","3529":"力旺","8027":"鈦昇",
    "3711":"日月光投控","6239":"力成","2449":"京元電子","3264":"欣銓","6223":"旺矽",
    "6515":"穎崴","6271":"同欣電","8150":"南茂","8110":"華東","3374":"精材",
    "3131":"弘塑","3583":"辛耘","6187":"萬潤","2404":"漢唐","3413":"京鼎",
    "6788":"華景電","5498":"凱崴","1815":"富喬","8021":"尖點","4755":"三福化",
    "3017":"奇鋐","3324":"雙鴻","3653":"健策","2421":"建準","6805":"富世達",
    "3023":"信邦","3338":"泰碩","6230":"超眾","1597":"直得","4545":"銘鈺",
    "2059":"川湖","8210":"勤誠","5215":"科嘉-KY","3533":"嘉澤","3005":"神基",
    "2474":"可成","6117":"迎廣","3694":"大瀚","3013":"晟銘電","5289":"宜鼎",
    "2383":"台光電","6274":"台燿","2368":"金像電","8046":"南電","3037":"欣興",
    "3189":"景碩","2316":"楠梓電","2367":"燿華","5439":"高僑","4958":"臻鼎-KY",
    "2344":"華邦電","2408":"南亞科","3006":"晶豪科","8299":"群聯","2337":"旺宏",
    "3260":"威剛","4967":"十銓","2451":"創見","8088":"品安","3051":"力特",
    "3081":"聯亞","4979":"華星光","3163":"波若威","3363":"上詮","4908":"前鼎",
    "6426":"統新","6442":"光聖","3450":"聯鈞","4977":"眾達-KY","2455":"全新",
    "2308":"台達電","2301":"光寶科","1503":"士電","1513":"中興電","1519":"華城",
    "1514":"亞力","6806":"昇陽半","3015":"全漢","2457":"飛宏","6409":"旭隼",
    "2884":"玉山金","2886":"兆豐金","2891":"中信金","2881":"富邦金","2882":"國泰金",
    "2892":"第一金","2885":"元大金","5880":"合庫金","2880":"華南金","2883":"開發金",
    "1101":"台泥","1301":"台塑","1802":"台玻","2603":"長榮","2609":"陽明",
    "2615":"萬海","3008":"大立光","3376":"新日興","2105":"正新","2201":"裕隆",
}

TAGS = {
    "2317":"AI","3231":"AI","6669":"AI","2382":"AI","2356":"AI",
    "2324":"AI","3706":"AI","4938":"AI","2352":"AI","2395":"AI",
    "2330":"晶圓","2303":"晶圓","5347":"晶圓","6770":"晶圓","3661":"ASIC",
    "3443":"ASIC","6533":"ASIC","6643":"ASIC","3529":"ASIC","8027":"設備",
    "3711":"封裝","6239":"封裝","2449":"封測","3264":"封測","6223":"封測",
    "6515":"封測","6271":"封裝","8150":"封裝","8110":"封裝","3374":"封裝",
    "3131":"設備","3583":"設備","6187":"設備","2404":"設備","3413":"設備",
    "6788":"設備","5498":"設備","1815":"材料","8021":"設備","4755":"材料",
    "3017":"散熱","3324":"散熱","3653":"散熱","2421":"散熱","6805":"散熱",
    "3023":"連接器","3338":"散熱","6230":"散熱","1597":"精密","4545":"散熱",
    "2059":"滑軌","8210":"機殼","5215":"機殼","3533":"連接器","3005":"工業電腦",
    "2474":"機殼","6117":"電源","3694":"散熱","3013":"EMS","5289":"儲存",
    "2383":"CCL","6274":"CCL","2368":"PCB","8046":"基板","3037":"PCB",
    "3189":"基板","2316":"PCB","2367":"PCB","5439":"CCL","4958":"軟板",
    "2344":"記憶體","2408":"記憶體","3006":"記憶體","8299":"NAND","2337":"記憶體",
    "3260":"記憶體","4967":"記憶體","2451":"記憶體","8088":"記憶體","3051":"記憶體",
    "3081":"光通","4979":"光通","3163":"光通","3363":"光通","4908":"光通",
    "6426":"光通","6442":"光通","3450":"光通","4977":"光通","2455":"光通",
    "2308":"電源","2301":"電源","1503":"電力","1513":"電力","1519":"電力",
    "1514":"電力","6806":"電力","3015":"電源","2457":"電源","6409":"電源",
    "2884":"金融","2886":"金融","2891":"金融","2881":"金融","2882":"金融",
    "2892":"金融","2885":"金融","5880":"金融","2880":"金融","2883":"金融",
    "1101":"傳產","1301":"傳產","1802":"傳產","2603":"航運","2609":"航運",
    "2615":"航運","3008":"光學","3376":"機構件","2105":"輪胎","2201":"汽車",
}

WATCH_LIST = list(WATCH.keys())
NAMES = dict(WATCH)

def safe_fm(params, retries=3):
    for i in range(retries):
        try:
            r = requests.get(FM, params=params, headers=HEADERS, timeout=20)
            r.raise_for_status()
            return r.json().get("data", [])
        except Exception as e:
            print(f"  retry {i+1}: {e}")
            time.sleep(3)
    return []

def get_price(sid):
    rows = safe_fm({"dataset":"TaiwanStockPrice","data_id":sid,"start_date":START90,"end_date":TODAY})
    rows = sorted(rows, key=lambda x: x["date"])
    if not rows: return [], [], []
    closes = [float(r["close"]) for r in rows if r.get("close")]
    highs  = [float(r["max"])   for r in rows if r.get("close")]
    lows   = [float(r["min"])   for r in rows if r.get("close")]
    return closes, highs, lows

def get_institution(sid):
    """外資買賣超 → 連買/連賣天數"""
    rows = safe_fm({"dataset":"TaiwanStockInstitutionalInvestorsBuySell",
                    "data_id":sid,"start_date":START20,"end_date":TODAY})
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

def get_foreign_holding(sid):
    """外資持股比例（替代籌碼集中度，免費版可用）
    回傳近5日趨勢串列 + 變化量"""
    rows = safe_fm({"dataset":"TaiwanStockInstitutionalInvestorsHolding",
                    "data_id":sid,"start_date":START20,"end_date":TODAY})
    rows = [r for r in rows if r.get("name") in ("外資及陸資","外資")]
    rows.sort(key=lambda x: x["date"])
    if not rows: return [30,30,30,30,30], 0
    # 取近5筆持股%
    recent = rows[-5:]
    trend = [round(float(r.get("percent", r.get("hold_rate", 30))), 1) for r in recent]
    while len(trend) < 5: trend.insert(0, trend[0])
    delta = round(trend[-1] - trend[0], 1)
    return trend, delta

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
    if price > ma5 > 0:     s += 1
    if price > ma20 > 0:    s += 1
    if buy_days >= 3:       s += 2
    elif buy_days >= 1:     s += 1
    if chip_trend[-1] > 40: s += 1   # 外資持股>40%為高
    if chip_delta > 1:      s += 1   # 外資持股上升
    if cross:               s += 2
    if buy_days <= -3 and chip_delta < -2: return "exit", min(s,5)
    if s >= 5: return "buy",   min(s,5)
    if s >= 3: return "watch", min(s,5)
    return "exit", min(s,5)

def main():
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    results = []
    print(f"開始掃描 {len(WATCH_LIST)} 檔，{TODAY}")

    for i, sid in enumerate(WATCH_LIST):
        name = NAMES.get(sid, sid)
        print(f"  [{i+1}/{len(WATCH_LIST)}] {sid} {name}...")
        try:
            closes, highs, lows = get_price(sid); time.sleep(0.4)
            if len(closes) < 10:
                print(f"    ⚠ 資料不足"); continue

            price = closes[-1]
            ma5   = calc_ma(closes, 5)
            ma20  = calc_ma(closes, 20)
            K, D  = calc_kd(closes, highs, lows)
            cross = kd_cross(closes, highs, lows)

            buy_days = get_institution(sid); time.sleep(0.4)
            chip_trend, chip_delta = get_foreign_holding(sid); time.sleep(0.4)

            vs5  = round((price-ma5)/ma5*100,1)   if ma5  else 0
            vs20 = round((price-ma20)/ma20*100,1) if ma20 else 0
            signal, score = classify(price, ma5, ma20, buy_days, chip_trend, chip_delta, cross, K, D)

            entry  = round(price*1.005,1) if signal!="exit" else 0
            stop   = round(ma5*0.98,1)   if signal!="exit" else 0
            target = round(price*1.12,1) if signal!="exit" else 0
            rr     = round((target-entry)/(entry-stop),1) if (entry-stop)>0 else 0

            results.append({
                "code":sid,"name":name,"tag":TAGS.get(sid,""),
                "price":price,"ma5":ma5,"ma20":ma20,"vs5":vs5,"vs20":vs20,
                "signal":signal,"kd":cross,"K":K,"D":D,
                "buyDays":buy_days,"chipTrend":chip_trend,
                "chipNow":chip_trend[-1],"chipDelta":chip_delta,
                "entry":entry,"stop":stop,"target":target,"rr":rr,"score":score
            })
            print(f"    ✓ {price} {signal} KD={K}/{D} 外資持股={chip_trend[-1]}% 連買={buy_days}日")

        except Exception as e:
            print(f"    ✗ {e}"); continue

    results.sort(key=lambda x:(0 if x["signal"]=="buy" else 1 if x["signal"]=="watch" else 2,-x["score"]))

    summary = {
        "buy":     len([s for s in results if s["signal"]=="buy"]),
        "watch":   len([s for s in results if s["signal"]=="watch"]),
        "exit":    len([s for s in results if s["signal"]=="exit"]),
        "kd":      len([s for s in results if s["kd"]]),
        "scanned": len(WATCH_LIST)
    }
    output = {
        "updated": datetime.datetime.now().strftime("%Y/%m/%d %H:%M"),
        "date":    TODAY,
        "summary": summary,
        "stocks":  results
    }
    with open(OUTPUT_PATH,"w",encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 完成！掃描{len(WATCH_LIST)}檔，輸出{len(results)}檔")
    print(f"   買進:{summary['buy']} 觀察:{summary['watch']} 出場:{summary['exit']} KD↑:{summary['kd']}")

if __name__ == "__main__":
    main()
