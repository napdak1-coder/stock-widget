"""
📈 주식 실시간 알리미 v2.0 — Bloomberg Edition
================================================
메인: Bloomberg 터미널 스타일 (주황 헤더 + 테이블)
몰컴: 원라인 틱커바 (🫣 버튼으로 즉시 전환)
기능: 종목 검색 / 급등급락 알림 / 30초 자동 갱신 / 드래그 이동

데이터: Yahoo Finance (무료, API 키 불필요)
빌드:  pyinstaller --onefile --noconsole --name StockWidget stock_widget.py
"""

import tkinter as tk
import threading
import json
import urllib.request
import urllib.error
from datetime import datetime
try:
    import winsound
except ImportError:
    winsound = None  # Mac/Linux 에서는 소리 비활성

# ============================================================
# ⚙️ 설정
# ============================================================
REFRESH_SEC = 30
ALERT_THRESHOLD = 3.0

# Bloomberg 색상
C = {
    "bg":       "#000000",   # 완전 검정
    "header":   "#ff6600",   # 블룸버그 주황
    "header_t": "#000000",   # 헤더 텍스트 (검정)
    "row_bg":   "#0a0a0a",   # 행 배경
    "row_alt":  "#0f0f0f",   # 행 배경 (짝수)
    "border":   "#333333",   # 테두리
    "text":     "#cccccc",   # 기본 텍스트
    "bright":   "#ffffff",   # 강조 텍스트
    "sym":      "#ff8800",   # 심볼 색상 (주황)
    "sub":      "#666666",   # 보조 텍스트
    "dim":      "#444444",   # 흌미한 텍스트
    "accent":   "#ff6600",   # 강조
    "up":       "#00cc66",   # 상승
    "down":     "#ff4444",   # 하락
    "flat":     "#666666",   # 보합
    "input_bg": "#111111",
    # 몰컴 모드
    "s_bg":     "#000000",
}

FONT_MONO = ("Consolas", 10)
FONT_MONO_B = ("Consolas", 10, "bold")
FONT_MONO_S = ("Consolas", 9)
FONT_MONO_XS = ("Consolas", 8)
FONT_HEADER = ("Consolas", 10, "bold")
FONT_TH = ("Consolas", 8, "bold")
FONT_KR = ("맑은 고딕", 9)
FONT_KR_S = ("맑은 고딕", 8)

MARKET_LABEL = {
    "PRE": "PRE", "REGULAR": "OPEN", "POST": "AFTER",
    "POSTPOST": "CLOSED", "CLOSED": "CLOSED", "PREPRE": "CLOSED",
}

DEFAULT_TICKERS = [
    {"symbol": "TSLA",  "name": "Tesla Inc",     "prefix": "", "dec": 2},
    {"symbol": "NQ=F",  "name": "Nasdaq 100 Fut", "prefix": "", "dec": 2},
    {"symbol": "KRW=X", "name": "USD/KRW",        "prefix": "", "dec": 2},
]

# ============================================================
# 📡 Yahoo Finance API
# ============================================================
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
}

def yahoo_quote(symbol):
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
           f"?interval=1d&range=1d&includePrePost=true")
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10) as r:
        meta = json.loads(r.read())["chart"]["result"][0]["meta"]
    rp = meta["regularMarketPrice"]
    pc = meta.get("chartPreviousClose", meta.get("previousClose", rp))
    ms = meta.get("marketState", "CLOSED")
    dp, ext = rp, False
    if ms == "PRE" and "preMarketPrice" in meta:
        dp, ext = meta["preMarketPrice"], True
    elif ms in ("POST", "POSTPOST") and "postMarketPrice" in meta:
        dp, ext = meta["postMarketPrice"], True
    chg = dp - pc
    pct = (chg / pc * 100) if pc else 0
    return {"price": dp, "prev": pc, "chg": chg, "pct": pct,
            "state": ms, "ext": ext}

def yahoo_search(query):
    url = (f"https://query2.finance.yahoo.com/v1/finance/search"
           f"?q={urllib.request.quote(query)}&quotesCount=6&newsCount=0")
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.loads(r.read())
    results = []
    for q in data.get("quotes", []):
        if q.get("quoteType") in ("EQUITY","INDEX","FUTURE","CURRENCY","ETF","MUTUALFUND"):
            results.append({
                "symbol": q["symbol"],
                "name": q.get("shortname", q.get("longname", q["symbol"])),
                "type": q.get("quoteType", ""),
                "exchange": q.get("exchange", ""),
            })
    return results

# ============================================================
# 🖥️ Bloomberg Widget
# ============================================================
class StockWidget:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("StockWidget")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.95)
        self.root.configure(bg=C["bg"])

        sw = self.root.winfo_screenwidth()
        self.root.geometry(f"+{sw - 400}+20")

        self.mode = "main"
        self.tickers = list(DEFAULT_TICKERS)
        self.data = {}
        self.labels = {}
        self.is_fetching = False
        self.drag_x = self.drag_y = 0
        self.alert_pct = ALERT_THRESHOLD
        self.alert_active = {}
        self.search_results = []

        self._build_main()
        self._schedule()
        self.root.mainloop()

    # ─────────────────────────────────
    # 🎨 메인 모드 (Bloomberg)
    # ─────────────────────────────────
    def _build_main(self):
        self.mode = "main"
        for w in self.root.winfo_children():
            w.destroy()
        self.root.configure(bg=C["bg"])

        # ── 주황 헤더바 ──
        header = tk.Frame(self.root, bg=C["header"], height=26)
        header.pack(fill="x")
        header.pack_propagate(False)

        tk.Label(header, text=" WATCHLIST", fg=C["header_t"], bg=C["header"],
                 font=FONT_HEADER).pack(side="left", padx=4)

        # 버튼들 (검정 글씨 on 주황)
        close_btn = tk.Label(header, text=" ✕ ", fg="#000", bg=C["header"],
                             font=("Consolas", 10), cursor="hand2")
        close_btn.pack(side="right", padx=1)
        close_btn.bind("<Button-1>", lambda e: self.root.quit())

        stealth_btn = tk.Label(header, text=" 🫣 ", fg="#000", bg=C["header"],
                               font=("Consolas", 10), cursor="hand2")
        stealth_btn.pack(side="right", padx=1)
        stealth_btn.bind("<Button-1>", lambda e: self._build_stealth())

        min_btn = tk.Label(header, text=" ─ ", fg="#000", bg=C["header"],
                           font=("Consolas", 10), cursor="hand2")
        min_btn.pack(side="right", padx=1)
        min_btn.bind("<Button-1>", lambda e: self.root.iconify())

        # 드래그
        for w in (header, header.winfo_children()[0]):
            w.bind("<Button-1>", self._drag_start)
            w.bind("<B1-Motion>", self._drag_move)

        # ── 테이블 휤더 ──
        th_frame = tk.Frame(self.root, bg=C["bg"])
        th_frame.pack(fill="x", padx=1)

        cols = [("SYMBOL", 80, "w"), ("PRICE", 90, "e"),
                ("CHG", 70, "e"), ("%CHG", 60, "e"), ("MKT", 50, "e")]
        for text, width, anchor in cols:
            tk.Label(th_frame, text=text, fg=C["header"], bg=C["bg"],
                     font=FONT_TH, width=0, anchor=anchor,
                     ).pack(side="left", fill="x", expand=True, padx=2, pady=(4, 2))

        sep = tk.Frame(self.root, bg=C["border"], height=1)
        sep.pack(fill="x", padx=4)

        # ── 종목 행 ──
        self.row_frame = tk.Frame(self.root, bg=C["bg"])
        self.row_frame.pack(fill="x")
        self._rebuild_rows()

        # ── 구분선 ──
        tk.Frame(self.root, bg=C["border"], height=1).pack(fill="x", padx=4, pady=(2, 0))

        # ── 검색바 ──
        sf = tk.Frame(self.root, bg=C["bg"])
        sf.pack(fill="x", padx=6, pady=(4, 2))

        self.search_var = tk.StringVar()
        se = tk.Entry(sf, textvariable=self.search_var,
                      bg=C["input_bg"], fg=C["text"], insertbackground=C["accent"],
                      font=FONT_MONO_S, relief="flat",
                      highlightthickness=1, highlightbackground=C["border"],
                      highlightcolor=C["accent"])
        se.pack(side="left", fill="x", expand=True, ipady=2)
        se.insert(0, " Search ticker...")
        se.bind("<FocusIn>", lambda e: (
            se.delete(0, "end") if "Search" in se.get() else None))
        se.bind("<Return>", self._on_search)

        sb = tk.Label(sf, text=" GO ", fg="#000", bg=C["accent"],
                      font=("Consolas", 9, "bold"), cursor="hand2")
        sb.pack(side="right", padx=(3, 0), ipady=1)
        sb.bind("<Button-1>", self._on_search)

        # 검색 결과
        self.result_frame = tk.Frame(self.root, bg=C["bg"])

        # ── 알림 + 상태 ──
        bottom = tk.Frame(self.root, bg=C["bg"])
        bottom.pack(fill="x", padx=6, pady=(2, 4))

        tk.Label(bottom, text="⚡", fg=C["accent"], bg=C["bg"],
                 font=FONT_MONO_XS).pack(side="left")

        self.alert_var = tk.StringVar(value=str(self.alert_pct))
        ae = tk.Entry(bottom, textvariable=self.alert_var, width=4,
                      bg=C["input_bg"], fg=C["accent"], insertbackground=C["accent"],
                      font=("Consolas", 9, "bold"), relief="flat", justify="center",
                      highlightthickness=1, highlightbackground=C["border"])
        ae.pack(side="left", padx=2)
        ae.bind("<Return>", self._update_alert_threshold)

        tk.Label(bottom, text="% alert", fg=C["dim"], bg=C["bg"],
                 font=FONT_MONO_XS).pack(side="left")

        self.status_lbl = tk.Label(bottom, text="", fg=C["dim"], bg=C["bg"],
                                   font=FONT_MONO_XS)
        self.status_lbl.pack(side="right")

    def _rebuild_rows(self):
        for w in self.row_frame.winfo_children():
            w.destroy()
        self.labels = {}

        for i, t in enumerate(self.tickers):
            sym = t["symbol"]
            bg = C["row_alt"] if i % 2 == 0 else C["row_bg"]

            row = tk.Frame(self.row_frame, bg=bg,
                           highlightbackground=C["bg"], highlightthickness=1)
            row.pack(fill="x", padx=1, pady=0)

            # SYMBOL (주황)
            sym_frm = tk.Frame(row, bg=bg)
            sym_frm.pack(side="left", fill="x", expand=True, padx=4, pady=3)

            sym_lbl = tk.Label(sym_frm, text=sym.replace("=F","").replace("=X",""),
                               fg=C["sym"], bg=bg, font=FONT_MONO_B, anchor="w")
            sym_lbl.pack(anchor="w")

            name_lbl = tk.Label(sym_frm, text=t["name"][:16], fg=C["dim"], bg=bg,
                                font=FONT_MONO_XS, anchor="w")
            name_lbl.pack(anchor="w")

            # PRICE
            price_lbl = tk.Label(row, text="···", fg=C["bright"], bg=bg,
                                 font=FONT_MONO_B, width=10, anchor="e")
            price_lbl.pack(side="left", padx=2)

            # CHG
            chg_lbl = tk.Label(row, text="", fg=C["flat"], bg=bg,
                               font=FONT_MONO_S, width=8, anchor="e")
            chg_lbl.pack(side="left", padx=2)

            # %CHG
            pct_lbl = tk.Label(row, text="", fg=C["flat"], bg=bg,
                               font=FONT_MONO_B, width=7, anchor="e")
            pct_lbl.pack(side="left", padx=2)

            # MKT state
            mkt_lbl = tk.Label(row, text="", fg=C["dim"], bg=bg,
                               font=FONT_MONO_XS, width=6, anchor="e")
            mkt_lbl.pack(side="left", padx=(2, 4))

            # 삭제 버튼 (기본 3종목 외)
            if sym not in ("TSLA", "NQ=F", "KRW=X"):
                del_b = tk.Label(row, text="✕", fg="#555", bg=bg,
                                 font=FONT_MONO_XS, cursor="hand2")
                del_b.pack(side="right", padx=2)
                del_b.bind("<Button-1>", lambda e, s=sym: self._remove_ticker(s))

            self.labels[sym] = {
                "price": price_lbl, "chg": chg_lbl, "pct": pct_lbl,
                "mkt": mkt_lbl, "row": row, "bg": bg,
            }

    # ─────────────────────────────────
    # 🫣 몰컴 모드
    # ─────────────────────────────────
    def _build_stealth(self):
        self.mode = "stealth"
        for w in self.root.winfo_children():
            w.destroy()
        self.root.configure(bg=C["s_bg"])

        bar = tk.Frame(self.root, bg=C["s_bg"])
        bar.pack(fill="x", padx=2, pady=2)
        bar.bind("<Button-1>", self._drag_start)
        bar.bind("<B1-Motion>", self._drag_move)

        self.stealth_labels = {}
        for i, t in enumerate(self.tickers):
            sym = t["symbol"]
            if i > 0:
                tk.Label(bar, text="│", fg="#222", bg=C["s_bg"],
                         font=FONT_MONO_S).pack(side="left", padx=1)
            frm = tk.Frame(bar, bg=C["s_bg"])
            frm.pack(side="left", padx=3)

            tk.Label(frm, text=sym.replace("=F","").replace("=X",""),
                     fg="#555", bg=C["s_bg"], font=FONT_MONO_XS).pack(side="left")
            vl = tk.Label(frm, text="···", fg=C["text"], bg=C["s_bg"],
                          font=FONT_MONO_B)
            vl.pack(side="left", padx=(3, 2))
            cl = tk.Label(frm, text="", fg=C["flat"], bg=C["s_bg"],
                          font=FONT_MONO_S)
            cl.pack(side="left")
            self.stealth_labels[sym] = {"val": vl, "chg": cl}

        tk.Label(bar, text=" ◀ ", fg="#444", bg=C["s_bg"],
                 font=FONT_KR_S, cursor="hand2").pack(side="right", padx=2)
        bar.winfo_children()[-1].bind("<Button-1>", lambda e: self._build_main())

        self._update_stealth_ui()

    def _update_stealth_ui(self):
        if self.mode != "stealth":
            return
        for t in self.tickers:
            sym = t["symbol"]
            if sym not in self.stealth_labels or sym not in self.data:
                continue
            d = self.data[sym]
            lbl = self.stealth_labels[sym]
            if d is None:
                lbl["val"].config(text="ERR", fg=C["down"])
                continue
            p, pct, dec, pfx = d["price"], d["pct"], t["dec"], t["prefix"]
            lbl["val"].config(text=f"{pfx}{p:,.{dec}f}")
            color = C["up"] if pct > 0 else C["down"] if pct < 0 else C["flat"]
            lbl["chg"].config(text=f"{pct:+.1f}%", fg=color)

    # ─────────────────────────────────
    # 🔍 종목 검색
    # ────────────────────────────────────────────
    def _on_search(self, event=None):
        query = self.search_var.get().strip()
        if not query or "Search" in query:
            return
        self.result_frame.pack(fill="x", padx=6, pady=(0, 2))
        for w in self.result_frame.winfo_children():
            w.destroy()
        tk.Label(self.result_frame, text="Searching...", fg=C["dim"],
                 bg=C["bg"], font=FONT_MONO_XS).pack()

        def do():
            try:
                res = yahoo_search(query)
                self.root.after(0, lambda: self._show_results(res))
            except Exception as e:
                self.root.after(0, lambda: self._show_search_err(str(e)))
        threading.Thread(target=do, daemon=True).start()

    def _show_results(self, results):
        for w in self.result_frame.winfo_children():
            w.destroy()
        if not results:
            tk.Label(self.result_frame, text="No results", fg=C["dim"],
                     bg=C["bg"], font=FONT_MONO_XS).pack()
            return
        for r in results[:4]:
            row = tk.Frame(self.result_frame, bg=C["row_alt"])
            row.pack(fill="x", pady=1)
            tk.Label(row, text=f" {r['symbol']}", fg=C["sym"], bg=C["row_alt"],
                     font=FONT_MONO_S).pack(side="left", padx=2, pady=2)
            tk.Label(row, text=r["name"][:22], fg=C["sub"], bg=C["row_alt"],
                     font=FONT_MONO_XS).pack(side="left", padx=4)
            ab = tk.Label(row, text=" + ADD ", fg="#000", bg=C["up"],
                          font=("Consolas", 8, "bold"), cursor="hand2")
            ab.pack(side="right", padx=3, pady=1)
            ab.bind("<Button-1>", lambda e, s=r["symbol"], n=r["name"]:
                    self._add_ticker(s, n))

    def _show_search_err(self, msg):
        for w in self.result_frame.winfo_children():
            w.destroy()
        tk.Label(self.result_frame, text=f"ERR: {msg[:40]}", fg=C["down"],
                 bg=C["bg"], font=FONT_MONO_XS).pack()

    def _add_ticker(self, symbol, name):
        if any(t["symbol"] == symbol for t in self.tickers):
            return
        self.tickers.append({"symbol": symbol, "name": name[:16], "prefix": "", "dec": 2})
        self.result_frame.pack_forget()
        self._rebuild_rows()
        self._fetch_all()

    def _remove_ticker(self, symbol):
        self.tickers = [t for t in self.tickers if t["symbol"] != symbol]
        self.data.pop(symbol, None)
        self._rebuild_rows()

    # ─────────────────────────────────
    # ⚡ 알림
    # ─────────────────────────────────
    def _update_alert_threshold(self, event=None):
        try:
            v = float(self.alert_var.get())
            if 0.1 <= v <= 50:
                self.alert_pct = v
        except ValueError:
            pass

    def _check_alerts(self):
        for t in self.tickers:
            sym = t["symbol"]
            d = self.data.get(sym)
            if d is None:
                continue
            if abs(d["pct"]) >= self.alert_pct:
                if not self.alert_active.get(sym):
                    self.alert_active[sym] = True
                    self._flash_alert(sym, d)
            else:
                self.alert_active[sym] = False

    def _flash_alert(self, symbol, data):
        if winsound:
            try:
                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
            except Exception:
                pass
        if self.mode == "main" and symbol in self.labels:
            row = self.labels[symbol]["row"]
            color = C["up"] if data["pct"] > 0 else C["down"]
            self._blink(row, color, 8)
        print(f"🔔 ALERT: {symbol} {data['pct']:+.2f}%")

    def _blink(self, widget, color, count):
        if count <= 0:
            widget.config(highlightbackground=C["bg"])
            return
        cur = widget.cget("highlightbackground")
        nxt = color if cur == C["bg"] else C["bg"]
        widget.config(highlightbackground=nxt)
        self.root.after(150, lambda: self._blink(widget, color, count - 1))

    # ─────────────────────────────────
    # 📡 데이터
    # ─────────────────────────────────
    def _schedule(self):
        self._fetch_all()
        self.root.after(REFRESH_SEC * 1000, self._schedule)

    def _fetch_all(self):
        if self.is_fetching:
            return
        self.is_fetching = True
        threading.Thread(target=self._fetch_worker, daemon=True).start()

    def _fetch_worker(self):
        errs = 0
        for t in self.tickers:
            try:
                self.data[t["symbol"]] = yahoo_quote(t["symbol"])
            except Exception as e:
                errs += 1
                print(f"[ERR] {t['symbol']}: {e}")
        self.root.after(0, lambda: self._on_data(errs))
        self.is_fetching = False

    def _on_data(self, errs):
        now = datetime.now().strftime("%H:%M:%S")
        if self.mode == "main":
            self._update_main(errs, now)
        else:
            self._update_stealth_ui()
        self._check_alerts()

    def _update_main(self, errs, now):
        krw = None
        if self.data.get("KRW=X"):
            krw = self.data["KRW=X"]["price"]

        for t in self.tickers:
            sym = t["symbol"]
            d = self.data.get(sym)
            lbl = self.labels.get(sym)
            if not lbl:
                continue

            if d is None:
                lbl["price"].config(text="ERROR", fg=C["down"])
                lbl["chg"].config(text="")
                lbl["pct"].config(text="")
                lbl["mkt"].config(text="")
                continue

            p, chg, pct = d["price"], d["chg"], d["pct"]
            dec = t["dec"]

            # PRICE
            lbl["price"].config(text=f"{p:,.{dec}f}", fg=C["bright"])

            # CHG
            color = C["up"] if chg > 0 else C["down"] if chg < 0 else C["flat"]
            lbl["chg"].config(text=f"{chg:+,.{dec}f}", fg=color)

            # %CHG
            pct_text = f"{pct:+.2f}%"
            lbl["pct"].config(text=pct_text, fg=color)

            # MKT
            state = MARKET_LABEL.get(d["state"], "")
            if d["ext"]:
                state += "*"
            lbl["mkt"].config(text=state, fg=C["dim"])

        # 상태
        if errs:
            self.status_lbl.config(text=f"⚠{errs}ERR {now}", fg=C["down"])
        else:
            self.status_lbl.config(text=f"LIVE · {REFRESH_SEC}s · {now}", fg=C["dim"])

    # ─────────────────────────────────
    # 🔧 유틸
    # ─────────────────────────────────
    def _drag_start(self, e):
        self.drag_x, self.drag_y = e.x, e.y

    def _drag_move(self, e):
        x = self.root.winfo_x() + e.x - self.drag_x
        y = self.root.winfo_y() + e.y - self.drag_y
        self.root.geometry(f"+{x}+{y}")


# ============================================================
if __name__ == "__main__":
    print("📈 StockWidget v2.0 — Bloomberg Edition")
    print(f"   Refresh: {REFRESH_SEC}s | Alert: ±{ALERT_THRESHOLD}%")
    print("   🫣 Stealth: click 🫣 on header")
    StockWidget()
