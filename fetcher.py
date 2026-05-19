import json, time, requests, datetime, os
from pathlib import Path

FINMIND_TOKEN = os.environ.get("FINMIND_TOKEN", "")
OUTPUT_PATH = Path("docs/data.json")
WATCH_LIST = ["2382","6138","3443","3231","3017","5274","3711","6257","6669","2330","2345","2308","2603","2002","2609","2615","1718","2409"]
TODAY = datetime.date.today().strftime("%Y-%m-%d")
HEADERS = {"Authorization": f"Bearer {FINMIND_TOKEN}"} if FINMIND_TOKEN else {}
FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"
NAMES = {"2382":"廣達","6138":"茂達","3443":"創意","3231":"緯創","3017":"奇鋐","5274":"信驊","3711":"日月光","6257":"矽格","6669":"緯穎","2330":"台積電","2345":"智邦","2308":"台達電","2603":"長榮","2002":"中鋼","2609":"陽明","2615":"萬海","1718":"中纖","2409":"友達"}
TAGS = {"2382":"AI","6138":"電源","3443":"ASIC","3231":"AI","3017":"散熱","5274":"BMC","3711":"封裝","6257":"封裝","6669":"AI","2330":"晶圓","2345":"網通","2308":"電源","2603":"航運","2002":"鋼鐵","2609":"航運","2615":"航運","1718":"傳產","2409":"面板"}

def safe_get(url, params, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=20)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            print(f"  retry {i+1}: {e}")
            time.sleep(3)
    return {}

def to_float(s):
    try:
        return float(str(s).replace(",","").replace("--","0").replace("X","0"))
    except:
        return 0.0

def twse_price(stock_id):
    rows = []
    for delta in [60, 30, 0]:
        d = datetime.date.today() - datetime.timedelta(days=delta)
        ym = d.strftime("%Y%m01")
        try:
            r = requests.get("https://api.twse.com.tw/v1/exchangeReport/STOCK_DAY", params={"response":"json","date":ym,"stockNo":stock_id}, timeout=15)
            data = r.json()
            if data.get("stat") == "OK":
                rows.extend(data.get("data", []))
        except:
            pass
        time.sleep(0.4)
    seen, clean = set(), []
    for row in rows:
        if row[0] not in seen:
            seen.add(row[0])
            clean.append(row)
    clean.sort(key=lambda x: x[0])
    return clean

def calc_ma(closes, n):
    if len(closes) < n: return None
    return round(sum(closes[-n:]) / n, 2)

def calc_kd(closes, highs, lows, n=9, m=3):
    if len(closes) < n: return 50, 50
    K, D = 50.0, 50.0
    for i in range(n-1, len(closes)):
        ph = max(highs[i-n+1:i+1])
        pl = min(lows[i-n+1:i+1])
        rsv = ((closes[i]-pl)/(ph-pl)*100) if (ph-pl) > 0 else 50
        K = K*(m-1)/m + rsv/m
        D = D*(m-1)/m + K/m
    return round(K,1), round(D,1)

def kd_cross(closes, highs, lows):
    if len(closes) < 12: return False
    Kp, Dp = calc_kd(closes[:-1], highs[:-1], lows[:-1])
    Kn, Dn = calc_kd(closes, highs, lows)
    return Kp < Dp and Kn > Dn and Kn < 70

def get_institution(stock_id):
    if not FINMIND_TOKEN: return 0
    params = {"dataset":"TaiwanStockInstitutionalInvestorsBuySell","data_id":stock_id,"start_date":(datetime.date.today()-datetime.timedelta(days=20)).strftime("%Y-%m-%d"),"end_date":TODAY}
    data = safe_get(FINMIND_URL, params)
    rows = [r for r in data.get("data",[]) if r.get("name")=="外資"]
    rows.sort(key=lambda x: x["date"])
    if not rows: return 0
    count, last_sign = 0, None
    for r in reversed(rows):
        net = to_float(r.get("buy","0")) - to_float(r.get("sell","0"))
        sign = 1 if net > 0 else -1
        if last_sign is None: last_sign = sign
        if sign == last_sign: count += sign
        else: break
    return count

def get_chip(stock_id):
    if not FINMIND_TOKEN: return [55,57,59,61,63], 4
    params = {"dataset":"TaiwanStockHoldingSharesPer","data_id":stock_id,"start_date":(datetime.date.today()-datetime.timedelta(days=14)).strftime("%Y-%m-%d"),"end_date":TODAY}
    data = safe_get(FINMIND_URL, params)
    rows = data.get("data", [])
    by_date = {}
    for r in rows:
        d = r["date"]
        level = r.get("HoldingSharesLevel","")
        pct = to_float(r.get("percent","0"))
        if any(x in level for x in ["400","1,000","4,000","10,000","15,000","20,000"]):
            by_date[d] = by_date.get(d,0) + pct
    if not by_date: return [50,50,50,50,50], 0
    dates = sorted(by_date.keys())[-5:]
    trend = [round(by_date[d],1) for d in dates]
    while len(trend) < 5: trend.insert(0, trend[0] if trend else 50)
    return trend, round(trend[-1]-trend[0],1)

def get_margin(stock_id):
    if not FINMIND_TOKEN: return 0
    params = {"dataset":"TaiwanStockMarginPurchaseShortSale","data_id":stock_id,"start_date":(datetime.date.today()-datetime.timedelta(days=7)).strftime("%Y-%m-%d"),"end_date":TODAY}
    data = safe_get(FINMIND_URL, params)
    rows = sorted(data.get("data",[]), key=lambda x: x["date"])
    if len(rows) < 2: return 0
    return int(to_float(rows[-1].get("MarginPurchaseTodayBalance","0")) - to_float(rows[-2].get("MarginPurchaseTodayBalance","0")))

def classify(price, ma5, ma20, buy_days, chip_trend, chip_delta, cross, K, D, margin):
    s = 0
    if price > ma5 > 0: s += 1
    if price > ma20 > 0: s += 1
    if buy_days >= 3: s += 2
    elif buy_days >= 1: s += 1
    if chip_trend[-1] > 60: s += 1
    if chip_delta > 3: s += 1
    if cross: s += 2
    if margin < 0: s += 1
    if buy_days <= -3 and chip_delta < -5: return "exit", min(s,5)
    if s >= 5: return "buy", min(s,5)
    if s >= 3: return "watch", min(s,5)
    return "exit", min(s,5)

def main():
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    results = []
    print(f"開始抓取，共{len(WATCH_LIST)}檔，{TODAY}")
    for sid in WATCH_LIST:
        print(f"  {sid} {NAMES.get(sid,'')}...")
        try:
            rows = twse_price(sid)
            if not rows: continue
            closes = [to_float(r[6]) for r in rows if to_float(r[6]) > 0]
            highs  = [to_float(r[4]) for r in rows if to_float(r[6]) > 0]
            lows   = [to_float(r[5]) for r in rows if to_float(r[6]) > 0]
            if not closes: continue
            price = closes[-1]
            ma5   = calc_ma(closes, 5) or price
            ma20  = calc_ma(closes, 20) or price
            K, D  = calc_kd(closes, highs, lows)
            cross = kd_cross(closes, highs, lows)
            buy_days = get_institution(sid); time.sleep(0.3)
            chip_trend, chip_delta = get_chip(sid); time.sleep(0.3)
            margin = get_margin(sid); time.sleep(0.3)
            vs5  = round((price-ma5)/ma5*100,1)
            vs20 = round((price-ma20)/ma20*100,1)
            signal, score = classify(price, ma5, ma20, buy_days, chip_trend, chip_delta, cross, K, D, margin)
            entry  = round(price*1.005,1) if signal != "exit" else 0
            stop   = round(ma5*0.98,1)   if signal != "exit" else 0
            target = round(price*1.12,1) if signal != "exit" else 0
            rr = round((target-entry)/(entry-stop),1) if (entry-stop) > 0 else 0
            results.append({"code":sid,"name":NAMES.get(sid,sid),"tag":TAGS.get(sid,""),"price":price,"ma5":ma5,"ma20":ma20,"vs5":vs5,"vs20":vs20,"signal":signal,"kd":cross,"K":K,"D":D,"buyDays":buy_days,"chipTrend":chip_trend,"chipNow":chip_trend[-1],"chipDelta":chip_delta,"margin":margin,"entry":entry,"stop":stop,"target":target,"rr":rr,"score":score})
            print(f"    ✓ {price} signal={signal} KD={K}/{D}")
        except Exception as e:
            print(f"    ✗ {e}")
    summary = {"buy":len([s for s in results if s["signal"]=="buy"]),"watch":len([s for s in results if s["signal"]=="watch"]),"exit":len([s for s in results if s["signal"]=="exit"]),"kd":len([s for s in results if s["kd"]])}
    output = {"updated":datetime.datetime.now().strftime("%Y/%m/%d %H:%M"),"date":TODAY,"summary":summary,"stocks":results}
    with open(OUTPUT_PATH,"w",encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"✅ 完成！共{len(results)}檔")

if __name__ == "__main__":
    main()
