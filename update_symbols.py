# -*- coding: utf-8 -*-
"""يسحب كل أسهم بورصة القاهرة (CAI) من ياهو فايننس ويكتب symbols_yahoo.csv.  التشغيل:  python update_symbols.py"""
import csv, yfinance as yf
q = yf.EquityQuery("eq", ["exchange", "CAI"]); rows = {}; off = 0
while True:
    r = yf.screen(q, offset=off, size=100, sortField="ticker", sortAsc=True)
    qs = r.get("quotes", [])
    if not qs: break
    for x in qs:
        code = x["symbol"].removesuffix(".CA")
        rows[code] = x.get("longName") or x.get("shortName") or code
    off += 100
    if off >= r.get("total", 0): break
with open("symbols_yahoo.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.writer(f); w.writerow(["code", "name"]); w.writerows(sorted(rows.items()))
print(f"تم حفظ {len(rows)} سهم في symbols_yahoo.csv")
