# 台股波段選股儀表板

手機瀏覽器可看、每天 17:45 全自動更新的台股波段儀表板。
**零主機費用，零程式設定。**

---

## 📦 檔案說明

```
twstock-dashboard/
├── fetcher.py                        # 每日資料抓取腳本（GitHub Actions 自動跑）
├── docs/
│   ├── index.html                    # 手機優化儀表板網頁
│   └── data.json                     # 每日自動更新的資料（不需手動編輯）
└── .github/workflows/daily_update.yml  # 自動排程設定
```

---

## 🚀 五步驟完成部署（約 15 分鐘）

### Step 1：申請 GitHub 帳號
前往 https://github.com 免費註冊（已有帳號跳過）

### Step 2：建立新 Repository
1. 登入後按右上角 **+** → **New repository**
2. Repository name 填：`twstock-dashboard`
3. 選 **Public**（GitHub Pages 免費版需要 Public）
4. 勾選 **Add a README file**
5. 按 **Create repository**

### Step 3：上傳所有檔案
1. 在新建的 repo 頁面，按 **Add file** → **Upload files**
2. 把以下資料夾結構全部上傳（拖曳即可）：
   - `fetcher.py`
   - `docs/index.html`
   - `docs/data.json`
   - `.github/workflows/daily_update.yml`
3. 按 **Commit changes**

### Step 4：開啟 GitHub Pages（免費網站空間）
1. 進入 repo → 上方 **Settings**
2. 左側選單找 **Pages**
3. Source 選 **Deploy from a branch**
4. Branch 選 **main**，資料夾選 **/docs**
5. 按 **Save**
6. 等約 2 分鐘，頁面上方會出現你的網址：
   `https://你的帳號.github.io/twstock-dashboard/`

**這個網址就是你的手機儀表板！** 加到手機主畫面書籤即可。

### Step 5：設定 FinMind Token（讓法人 + 籌碼資料真實更新）
1. 前往 https://finmindtrade.com 免費註冊
2. 登入後到 **個人資訊** → 複製你的 **API Token**
3. 回到 GitHub repo → **Settings** → **Secrets and variables** → **Actions**
4. 按 **New repository secret**
5. Name 填：`FINMIND_TOKEN`，Value 貼上你的 token
6. 按 **Add secret**

✅ 完成！之後每個交易日 17:45，GitHub Actions 會自動：
- 抓最新收盤價、法人買賣超、籌碼集中度
- 計算 KD、均線、訊號
- 更新 data.json
- 你手機開網頁就是最新資料

---

## 📱 手機加到主畫面

### iPhone（Safari）
1. Safari 開啟你的網址
2. 下方工具列按「分享」圖示
3. 選「加入主畫面」

### Android（Chrome）
1. Chrome 開啟你的網址
2. 右上角三點選單
3. 選「新增至主畫面」

---

## ⚙️ 自訂追蹤股票

編輯 `fetcher.py` 第 20 行的 `WATCH_LIST`，加入你想追蹤的股票代號，
同時更新 `NAMES` 和 `TAGS` 字典加入對應名稱與類別。

---

## 📊 資料來源

| 資料 | 來源 | 費用 |
|------|------|------|
| 收盤價、均線 | TWSE OpenAPI | 完全免費 |
| 法人買賣超 | FinMind API | 免費版每日 600 次 |
| 大戶籌碼比例 | FinMind API | 同上 |
| 融資增減 | FinMind API | 同上 |
| KD 指標 | 本地計算 | 不需 API |

FinMind 免費版追蹤 18 檔約使用 108 次/日（18 檔 × 3 個 endpoint），
遠低於 600 次上限，免費版完全夠用。

---

## ⚠️ 免責聲明

本系統所有資訊僅供技術面參考，不構成投資建議。
股市投資有風險，所有操作決策請自行判斷負責。
