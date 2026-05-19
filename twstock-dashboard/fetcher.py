"""
台股波段選股儀表板 — 每日資料抓取腳本
執行時機：每天 17:45（收盤後），由 GitHub Actions 自動觸發
輸出：docs/data.json（供 index.html 讀取）
"""

import json
import time
import requests
import datetime
import os
from pathlib import Path

# ── 設定 ──────────────────────────────────────────
FINMIND_TOKEN = os.environ.get("FINMIND_TOKEN", "")   # 填入 FinMind token（免費版即可）
OUTPUT_PATH   = Path("docs/data.json")

# 追蹤股票清單（可自行增減）
WATCH_LIST = [
    "2382","6138","3443","3231","3017","5274",  # 主要關注
    "3711","6257","6669","2330","2345","2308",
    "2603","2002","2609","2615","1718","2409",
]

TODAY = datetime.date.today().strftime("%Y-%m-%d")
# 往前抓 40 個交易日（計算均線與 KD 用）
START  = (datetime.date.today() - datetime.timedelta(days=60)).strftime("%Y-%m-%d")

HEADERS = {"Authorization": f"Bearer {FINMIND_TOKEN}"} if FINMIND_TOKEN else {}
FINMIND_URL = "https://api.finmindtrade.com/api/v4/data"

# ── 公用函式 ─────────────────────────────────────

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

def twse_price(stock_id):
    """TWSE OpenAPI：抓個股近 60 日收盤價（免費、不需 token）"""
    url = f"https://api.twse.com.tw/v1/exchangeReport/STOCK_DAY"
    # TWSE 一次只能抓一個月，抓兩個月再合併
    rows = []
    for delta in [60, 30, 0]:
        d = (datetime.date.today() - datetime.timedelta(days=delta))
        ym = d.strftime("%Y%m01")
        try:
            r = requests.get(url, params={"response":"json","date":ym,"stockNo":stock_id}, timeout=15)
            data = r.json()
            if data.get("stat") == "OK":
                rows.extend(data.get("data", []))
        except:
            pass
        time.sleep(0.4)
    # 去重、排序
    seen = set()
    clean = []
    for row in rows:
        if row[0] not in seen:
            seen.add(row[0])
            clean.append(row)
    clean.sort(key=lambda x: x[0])
    return clean  # [日期, 成交量, 成交金額, 開, 高, 低, 收, 漲跌, 筆數]

def to_float(s):
    try:
        return float(str(s).replace(",","").replace("--","0").replace("X","0"))
    except:
        return 0.0

def calc_ma(closes, n):
    if len(closes) < n:
        return None
    return round(sum(closes[-n:]) / n, 2)

def calc_kd(closes, highs, lows, n=9, m=3):
    """標準 KD 指標計算"""
    if len(closes) < n:
        return 50, 50
    K, D = 50.0, 50.0
    for i in range(n-1, len(closes)):
        period_high = max(highs[i-n+1:i+1])
        period_low  = min(lows[i-n+1:i+1])
        denom = period_high - period_low
        rsv = ((closes[i] - period_low) / denom * 100) if denom > 0 else 50
        K = K * (m-1)/m + rsv / m
        D = D * (m-1)/m + K   / m
    return round(K, 1), round(D, 1)

def kd_cross(closes, highs, lows):
    """是否剛發生黃金交叉（前日 K<D，今日 K>D，且 K<70）"""
    if len(closes) < 12:
        return False
    K_prev, D_prev = calc_kd(closes[:-1], highs[:-1], lows[:-1])
    K_now,  D_now  = calc_kd(closes,       highs,       lows)
    return K_prev < D_prev and K_now > D_now and K_now < 70

# ── FinMind 法人買賣超 ────────────────────────────

def get_institution(stock_id):
    """回傳外資連買/賣天數（正=連買，負=連賣）"""
    params = {
        "dataset":   "TaiwanStockInstitutionalInvestorsBuySell",
        "data_id":   stock_id,
        "start_date": (datetime.date.today() - datetime.timedelta(days=20)).strftime("%Y-%m-%d"),
        "end_date":   TODAY,
    }
    data = safe_get(FINMIND_URL, params)
    rows = data.get("data", [])
    if not rows:
        return 0
    # 只看外資
    foreign = [r for r in rows if r.get("name") == "外資"]
    foreign.sort(key=lambda x: x["date"])
    if not foreign:
        return 0
    # 計算連買/賣天數
    count = 0
    last_sign = None
    for r in reversed(foreign):
        net = to_float(r.get("buy","0")) - to_float(r.get("sell","0"))
        sign = 1 if net > 0 else -1
        if last_sign is None:
            last_sign = sign
        if sign == last_sign:
            count += sign
        else:
            break
    return count

# ── FinMind 持股分級（大戶比例）─────────────────

def get_chip(stock_id):
    """回傳大戶(400張以上)持股比例，近5日走勢"""
    params = {
        "dataset":   "TaiwanStockHoldingSharesPer",
        "data_id":   stock_id,
        "start_date": (datetime.date.today() - datetime.timedelta(days=14)).strftime("%Y-%m-%d"),
        "end_date":   TODAY,
    }
    data = safe_get(FINMIND_URL, params)
    rows = data.get("data", [])
    if not rows:
        return [50,50,50,50,50], 0
    rows.sort(key=lambda x: x["date"])
    # 加總 400張以上各級
    by_date = {}
    for r in rows:
        d = r["date"]
        level = r.get("HoldingSharesLevel","")
        pct   = to_float(r.get("percent","0"))
        if "400" in level or "1,000" in level or "4,000" in level or "10,000" in level or "15,000" in level or "20,000" in level:
            by_date[d] = by_date.get(d, 0) + pct
    if not by_date:
        return [50,50,50,50,50], 0
    dates = sorted(by_date.keys())[-5:]
    trend = [round(by_date[d], 1) for d in dates]
    while len(trend) < 5:
        trend.insert(0, trend[0] if trend else 50)
    delta = round(trend[-1] - trend[0], 1)
    return trend, delta

# ── 融資增減 ─────────────────────────────────────

def get_margin(stock_id):
    params = {
        "dataset":   "TaiwanStockMarginPurchaseShortSale",
        "data_id":   stock_id,
        "start_date": (datetime.date.today() - datetime.timedelta(days=7)).strftime("%Y-%m-%d"),
        "end_date":   TODAY,
    }
    data = safe_get(FINMIND_URL, params)
    rows = data.get("data", [])
    rows.sort(key=lambda x: x["date"])
    if len(rows) < 2:
        return 0
    today_m = to_float(rows[-1].get("MarginPurchaseTodayBalance","0"))
    prev_m  = to_float(rows[-2].get("MarginPurchaseTodayBalance","0"))
    return int(today_m - prev_m)

# ── 股票名稱對照 ──────────────────────────────────

NAMES = {
    "2382":"廣達","6138":"茂達","3443":"創意","3231":"緯創","3017":"奇鋐","5274":"信驊",
    "3711":"日月光","6257":"矽格","6669":"緯穎","2330":"台積電","2345":"智邦","2308":"台達電",
    "2603":"長榮","2002":"中鋼","2609":"陽明","2615":"萬海","1718":"中纖","2409":"友達",
}
TAGS = {
    "2382":"AI","6138":"電源","3443":"ASIC","3231":"AI","3017":"散熱","5274":"BMC",
    "3711":"封裝","6257":"封裝","6669":"AI","2330":"晶圓","2345":"網通","2308":"電源",
    "2603":"航運","2002":"鋼鐵","2609":"航運","2615":"航運","1718":"傳產","2409":"面板",
}

# ── 訊號判斷 ──────────────────────────────────────

def classify_signal(price, ma5, ma20, buy_days, chip_trend, chip_delta, kd_cross_flag, K, D, margin):
    score = 0
    if price > ma5 > 0:           score += 1
    if price > ma20 > 0:          score += 1
    if buy_days >= 3:              score += 2
    elif buy_days >= 1:            score += 1
    if chip_trend[-1] > 60:       score += 1
    if chip_delta > 3:             score += 1
    if kd_cross_flag:              score += 2
    if margin < 0:                 score += 1  # 融資減少是好事

    if buy_days <= -3 and chip_delta < -5:
        signal = "exit"
    elif score >= 5:
        signal = "buy"
    elif score >= 3:
        signal = "watch"
    else:
        signal = "exit"
    return signal, min(score, 5)

def calc_entry_stop_target(price, ma5, ma20, signal):
    if signal == "exit":
        return 0, 0, 0
    entry  = round(price * 1.005, 1)
    stop   = round(ma5 * 0.98, 1) if ma5 > 0 else round(price * 0.93, 1)
    target = round(price * 1.12, 1)
    return entry, stop, target

# ── 主程式 ────────────────────────────────────────

def main():
    OUTPUT_PATH.parent.mkdir(exist_ok=True)
    results = []
    print(f"開始抓取資料，共 {len(WATCH_LIST)} 檔，時間：{TODAY}")

    for sid in WATCH_LIST:
        print(f"  處理 {sid} {NAMES.get(sid,'')} ...")
        try:
            # 1. 抓價格
            rows = twse_price(sid)
            if not rows:
                print(f"    ⚠ 無價格資料，跳過")
                continue
            closes = [to_float(r[6]) for r in rows if to_float(r[6]) > 0]
            highs  = [to_float(r[4]) for r in rows if to_float(r[6]) > 0]
            lows   = [to_float(r[5]) for r in rows if to_float(r[6]) > 0]
            if not closes:
                continue
            price  = closes[-1]
            ma5    = calc_ma(closes, 5)  or price
            ma20   = calc_ma(closes, 20) or price
            K, D   = calc_kd(closes, highs, lows)
            cross  = kd_cross(closes, highs, lows)

            # 2. 法人（有 token 才抓，否則用 0）
            buy_days = get_institution(sid) if FINMIND_TOKEN else 0
            time.sleep(0.3)

            # 3. 籌碼
            chip_trend, chip_delta = get_chip(sid) if FINMIND_TOKEN else ([55,57,59,61,63], 4)
            time.sleep(0.3)

            # 4. 融資
            margin = get_margin(sid) if FINMIND_TOKEN else 0
            time.sleep(0.3)

            # 5. 計算訊號
            vs5  = round((price - ma5)  / ma5  * 100, 1) if ma5  else 0
            vs20 = round((price - ma20) / ma20 * 100, 1) if ma20 else 0
            signal, score = classify_signal(price, ma5, ma20, buy_days, chip_trend, chip_delta, cross, K, D, margin)
            entry, stop, target = calc_entry_stop_target(price, ma5, ma20, signal)
            rr = round((target - entry) / (entry - stop), 1) if (entry - stop) > 0 else 0

            results.append({
                "code":       sid,
                "name":       NAMES.get(sid, sid),
                "tag":        TAGS.get(sid, ""),
                "price":      price,
                "ma5":        ma5,
                "ma20":       ma20,
                "vs5":        vs5,
                "vs20":       vs20,
                "signal":     signal,
                "kd":         cross,
                "K":          K,
                "D":          D,
                "buyDays":    buy_days,
                "chipTrend":  chip_trend,
                "chipNow":    chip_trend[-1],
                "chipDelta":  chip_delta,
                "margin":     margin,
                "entry":      entry,
                "stop":       stop,
                "target":     target,
                "rr":         rr,
                "score":      score,
            })
            print(f"    ✓ {price} | signal={signal} | KD={K}/{D} | 連買={buy_days}日")

        except Exception as e:
            print(f"    ✗ 錯誤：{e}")
            continue

    # 計算彙總
    summary = {
        "buy":   len([s for s in results if s["signal"]=="buy"]),
        "watch": len([s for s in results if s["signal"]=="watch"]),
        "exit":  len([s for s in results if s["signal"]=="exit"]),
        "kd":    len([s for s in results if s["kd"]]),
    }

    output = {
        "updated": datetime.datetime.now().strftime("%Y/%m/%d %H:%M"),
        "date":    TODAY,
        "summary": summary,
        "stocks":  results,
    }

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 完成！輸出至 {OUTPUT_PATH}，共 {len(results)} 檔")
    print(f"   買進:{summary['buy']}  觀察:{summary['watch']}  出場:{summary['exit']}  KD交叉:{summary['kd']}")

if __name__ == "__main__":
    main()
