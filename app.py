# -*- coding: utf-8 -*-
"""مستثمرين مصريين — Backend (Flask).  تشغيل:  python app.py  ثم افتح http://localhost:5000"""
import re, time, datetime as dt
from html import escape
from flask import Flask, request, jsonify, Response
import yfinance as yf, csv, os
from indicators import compute

app = Flask(__name__, static_folder=".", static_url_path="")
SITE = "مستثمرين مصريين"

# ---------- جدول المطابقة: الرمز -> (الاسم، مرادفات) — عدّله وأضف عليه بحرية ----------
SYMBOLS = {
 "COMI": ("البنك التجاري الدولي", ["التجاري الدولي", "cib"]),
 "ETEL": ("المصرية للاتصالات", ["المصريه للاتصالات", "تيليكوم مصر", "وي"]),
 "TMGH": ("مجموعة طلعت مصطفى القابضة", ["طلعت مصطفى", "تي ام جي اتش"]),
 "EFID": ("إيديتا للصناعات الغذائية", ["ايديتا"]),
 "JUFO": ("جهينة للصناعات الغذائية", ["جهينة"]),
 "SWDY": ("السويدي إليكتريك", ["السويدي", "السويدى"]),
 "HRHO": ("إي إف جي القابضة", ["هيرميس", "اي اف جي", "efg"]),
 "EAST": ("الشرقية - إيسترن كومباني", ["الشرقية للدخان", "ايسترن كومباني"]),
 "ORWE": ("النساجون الشرقيون للسجاد", ["النساجون الشرقيون", "اوريينتال ويفرز"]),
 "PHDC": ("بالم هيلز للتعمير", ["بالم هيلز"]),
 "MNHD": ("مدينة نصر للإسكان والتعمير", ["مدينة نصر"]),
 "OCDI": ("سوديك", ["سوديك", "sodic"]),
 "HELI": ("مصر الجديدة للإسكان والتعمير", ["مصر الجديدة"]),
 "ABUK": ("أبو قير للأسمدة", ["ابوقير", "ابو قير"]),
 "MFPC": ("مصر لإنتاج الأسمدة - موبكو", ["موبكو"]),
 "SKPC": ("سيدي كرير للبتروكيماويات", ["سيدي كرير"]),
 "ESRS": ("حديد عز", ["عز", "عز للصلب"]),
 "EKHO": ("القابضة المصرية الكويتية", ["المصرية الكويتية"]),
 "ORAS": ("أوراسكوم كونستراكشون", ["اوراسكوم للانشاء"]),
 "ORHD": ("أوراسكوم للتنمية مصر", ["اوراسكوم للتنمية"]),
 "CIEB": ("بنك كريدي أجريكول مصر", ["كريدي اجريكول"]),
 "ADIB": ("مصرف أبوظبي الإسلامي - مصر", ["ابوظبي الاسلامي"]),
 "HDBK": ("بنك التعمير والإسكان", ["التعمير والاسكان"]),
 "CANA": ("بنك قناة السويس", ["قناة السويس"]),
 "FAIT": ("بنك فيصل الإسلامي", ["فيصل الاسلامي"]),
 "QNBE": ("بنك قطر الوطني الأهلي", ["qnb", "قطر الوطني"]),
 "FWRY": ("فوري لتكنولوجيا البنوك", ["فوري"]),
 "CLHO": ("مستشفى كليوباترا", ["كليوباترا"]),
 "AMOC": ("الإسكندرية للزيوت المعدنية - أموك", ["اموك"]),
 "EGAL": ("مصر للألومنيوم", ["مصر للالومنيوم"]),
 "CCAP": ("القلعة للاستشارات المالية", ["القلعة"]),
 "ISPH": ("ابن سينا فارما", ["ابن سينا"]),
 "PHAR": ("المصرية الدولية للصناعات الدوائية - إيبيكو", ["ايبيكو"]),
 "ACGC": ("العربية لحليج الأقطان", ["حليج الاقطان"]),
 "SUGR": ("الدلتا للسكر", ["دلتا للسكر"]),
 "GBCO": ("جي بي أوتو", ["جي بي اوتو", "gb auto"]),
 "EFIH": ("إي فاينانس", ["اي فاينانس"]),
 "ARCC": ("العربية للأسمنت", ["العربيه للاسمنت"]),
 "MCQE": ("مصر للأسمنت - قنا", ["اسمنت قنا"]),
 "SCEM": ("أسمنت سيناء", ["اسمنت سيناء"]),
}

# قائمة ياهو الكاملة (تُولَّد بـ update_symbols.py): تضيف الأسهم غير الموجودة بأسمائها الإنجليزية
_ycsv = os.path.join(os.path.dirname(os.path.abspath(__file__)), "symbols_yahoo.csv")
if os.path.exists(_ycsv):
    for row in csv.DictReader(open(_ycsv, encoding="utf-8-sig")):
        _c = (row.get("code") or "").strip().upper()
        if _c: SYMBOLS.setdefault(_c, (row["name"].strip(), [row["name"].strip()]))

# تحميل symbols.csv (code,name,aliases مفصولة بـ |) وتتغلّب على الجدول أعلاه
_csv = os.path.join(os.path.dirname(os.path.abspath(__file__)), "symbols.csv")
if os.path.exists(_csv):
    for row in csv.DictReader(open(_csv, encoding="utf-8-sig")):
        code = (row.get("code") or "").strip().upper()
        if code and not code.startswith("#"):
            SYMBOLS[code] = (row["name"].strip(), [a for a in (row.get("aliases") or "").split("|") if a.strip()])

def norm(s):
    s = re.sub(r"[\u064B-\u0652\u0640]", "", s.strip().lower())
    s = re.sub(r"[أإآ]", "ا", s).replace("ة", "ه").replace("ى", "ي")
    s = re.sub(r"^(حلل|تحليل)\s+", "", s)
    s = re.sub(r"^(سهم|اسهم)\s+", "", s)
    return re.sub(r"[.\u2026]+$", "", s).strip()

INDEX = {c: [norm(n)] + [norm(a) for a in al] + [c.lower()] for c, (n, al) in SYMBOLS.items()}

def suggest(q, limit=6):
    q = norm(q)
    if len(q) < 2: return []
    hits = [c for c, keys in INDEX.items() if any(k.startswith(q) for k in keys)]
    hits += [c for c, keys in INDEX.items() if c not in hits and any(q in k for k in keys)]
    return [{"symbol": c, "name": SYMBOLS[c][0]} for c in hits[:limit]]

def resolve(q):
    """رمز مباشر (COMI / COMI.CA) يؤخذ فورًا، والاسم العربي يُطابَق من الجدول."""
    raw = q.strip().upper()
    if re.fullmatch(r"[A-Z0-9\-]{2,10}(\.CA)?", raw):
        return raw.removesuffix(".CA")
    n = norm(q)
    for c, keys in INDEX.items():
        if n in keys: return c
    s = suggest(q, 1)
    return s[0]["symbol"] if s else None

# ---------- جلب الأسعار (yfinance: رمز + .CA) ----------
_cache = {}
def get_df(code):
    now = time.time()
    if code in _cache and now - _cache[code][0] < 300: return _cache[code][1]
    df = yf.Ticker(code + ".CA").history(period="1y", auto_adjust=False)
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    if len(df) < 30: raise ValueError("لا توجد بيانات كافية لهذا الرمز")
    _cache[code] = (now, df)
    return df

# ---------- الأطر الزمنية ----------
PERIODS = [("year", "آخر سنة", 250, 1.0), ("month", "آخر شهر", 22, .6), ("week", "آخر أسبوع", 5, .3), ("session", "آخر جلسة", 1, .15)]
rd = lambda x: round(float(x), 2)

def pstats(df, n):
    w = df.tail(n); pc = float(df.Close.iloc[-n-1]) if len(df) > n else float(w.Open.iloc[0])
    last, hi, lo = float(w.Close.iloc[-1]), float(w.High.max()), float(w.Low.min()); rets = df.Close.pct_change().tail(n)
    av = float(df.Volume.tail(20).mean())
    st = {"open": rd(w.Open.iloc[0]), "close": rd(last), "change": rd((last / pc - 1) * 100), "high": rd(hi), "low": rd(lo),
          "range_pct": rd((hi - lo) / lo * 100), "pos": rd((last - lo) / (hi - lo) * 100 if hi > lo else 50),
          "volume": int(w.Volume.sum()), "vol_ratio": rd(float(w.Volume.mean()) / av) if av else None, "sessions": len(w)}
    if n > 1:
        cum = (1 + rets.fillna(0)).cumprod()
        st.update(volatility=rd(rets.std() * 100), max_dd=rd((cum / cum.cummax() - 1).min() * 100), up_days=int((rets > 0).sum()))
    else:
        o, cl = float(w.Open.iloc[0]), last; rg = hi - lo or 1
        st["gap"] = rd((o / pc - 1) * 100)
        st["candle"] = "دوجي (تردد)" if abs(cl - o) / rg < .1 else "شمعة صاعدة" if cl > o else "شمعة هابطة"
    return st

def ptext(label, st, sm):
    t = (f"{label}: {'ارتفع' if st['change'] >= 0 else 'انخفض'} السهم {abs(st['change']):.2f}% متحركًا بين {st['low']:.2f} و{st['high']:.2f} (مدى {st['range_pct']:.1f}%)، "
         f"ويغلق عند {st['pos']:.0f}% من نطاق الفترة. ")
    if st.get("vol_ratio"): t += f"متوسط الحجم {st['vol_ratio']:.1f} ضعف متوسط 20 جلسة. "
    if "gap" in st: t += f"فجوة الافتتاح {st['gap']:+.2f}% والشمعة: {st['candle']}. "
    else: t += f"التقلب اليومي {st['volatility']:.2f}% وأقصى تراجع {st['max_dd']:.1f}% وأيام الصعود {st['up_days']} من {st['sessions']}. "
    return t + f"المؤشرات (مُعايَرة لهذا الإطار): {sm['buy']} شراء / {sm['sell']} بيع / {sm['neutral']} محايد ← {sm['overall']}."

def get_info(code):
    try:
        i = yf.Ticker(code + ".CA").info
        return {k: i.get(k) for k in ("longName", "sector", "industry", "marketCap", "trailingPE", "priceToBook", "dividendYield")}
    except Exception: return {}

# ---------- التحليل الفني ----------
def analyze(code):
    df = get_df(code); c = df.Close
    last, prev = float(c.iloc[-1]), float(c.iloc[-2])
    sma50 = float(c.tail(50).mean()) if len(c) >= 50 else None
    sma200 = float(c.tail(200).mean()) if len(c) >= 200 else None
    d = c.diff()
    g = d.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    l = (-d.clip(upper=0)).ewm(alpha=1/14, adjust=False).mean()
    rsi = 100.0 if l.iloc[-1] == 0 else float(100 - 100 / (1 + g.iloc[-1] / l.iloc[-1]))
    if rsi > 70: rz = "تشبع شرائي: السهم صعد بقوة وقد يكون عرضة لجني أرباح أو تصحيح"
    elif rsi < 30: rz = "تشبع بيعي: السهم هبط بقوة وقد يكون قريبًا من ارتداد فني"
    elif rsi >= 50: rz = "منطقة محايدة مائلة للإيجابية (زخم صاعد معتدل)"
    else: rz = "منطقة محايدة مائلة للضعف (زخم هابط معتدل)"
    refs = [x for x in (sma50, sma200) if x]
    up = sum(last > x for x in refs)
    trend = "صاعد" if up == len(refs) else "هابط" if up == 0 else "عرضي"

    sup = float(df.Low.tail(20).min())
    cands = sorted({float(df.High.tail(n).max()) for n in (20, 60, 120, 250)})
    above = [x for x in cands if x > last * 1.01]
    r1 = above[0] if above else last * 1.04
    r2 = next((x for x in above if x > r1 * 1.02), r1 * 1.06)
    elo, ehi, basis = sup, sup * 1.012, "الدعم الرئيسي (أدنى سعر خلال آخر 20 جلسة)"
    if sma50 and sup < sma50 <= last and (last - sma50) / sma50 <= .03:
        elo, ehi, basis = sma50 * .99, sma50 * 1.005, "ارتداد إيجابي من المتوسط المتحرك 50 يوم"
    sl = min(elo, sup) * (1 - .0175)
    mid = (elo + ehi) / 2
    rr = (r1 - mid) / (mid - sl) if mid > sl else 0
    dist = (last - ehi) / last * 100
    in_zone = dist <= 1

    score = (1 if trend == "صاعد" else -1 if trend == "هابط" else 0)
    score += -1 if rsi > 70 else .5 if rsi < 30 or 40 <= rsi <= 65 else 0
    score += 1 if dist <= 3 else 0
    view = "إيجابية" if score >= 1.5 else "سلبية" if score <= -1 else "محايدة"

    chg = (last / prev - 1) * 100
    text = (f"أغلق سهم {SYMBOLS.get(code, (code,))[0]} ({code}) عند {last:.2f} جنيه بتغير {chg:+.2f}% عن الجلسة السابقة. "
            f"الاتجاه العام {trend}" + (f" (المتوسط 50 يوم عند {sma50:.2f}" + (f" و200 يوم عند {sma200:.2f})" if sma200 else ")") if sma50 else "") + ". "
            f"مؤشر القوة النسبية RSI(14) عند {rsi:.1f} — {rz}. "
            f"أقرب دعم {sup:.2f} وأقرب مقاومة {r1:.2f}، والمقاومة التالية {r2:.2f}. "
            + ("السعر الحالي داخل منطقة الدخول أو قريب منها. " if in_zone else f"السعر الحالي أعلى منطقة الدخول بنحو {dist:.1f}%، والأنسب انتظار تراجع نحوها بدل الملاحقة. ")
            + f"نسبة العائد إلى المخاطرة حتى الهدف الأول ≈ {rr:.1f}:1. وقف الخسارة تحت الدعم بنحو 1.75% لحماية رأس المال عند كسره. "
            f"النظرة الفنية العامة: {view}.")
    periods = {}
    for key, label, n, k in PERIODS:
        i, sm = compute(df, k); st = pstats(df, n)
        periods[key] = {"label": label, "stats": st, "indicators": i, "summary": sm, "text": ptext(label, st, sm)}
    info = get_info(code)
    r = lambda x: round(float(x), 2)
    return {"symbol": code, "name": SYMBOLS.get(code, (code,))[0], "date": str(df.index[-1].date()),
            "price": r(last), "change": r(chg), "trend": trend, "rsi": r(rsi), "rsi_zone": rz,
            "sma50": sma50 and r(sma50), "sma200": sma200 and r(sma200),
            "volume": int(df.Volume.iloc[-1]), "high": r(df.High.tail(60).max()), "low": r(df.Low.tail(60).min()),
            "entry": [r(elo), r(ehi)], "entry_basis": basis, "in_zone": bool(in_zone), "dist": r(dist),
            "tp1": r(r1), "tp2": r(r2), "sl": r(sl), "rr": r(rr), "view": view, "text": text,
            "hist": [r(x) for x in c.tail(90)], "sup": r(sup), "periods": periods, "info": info}

# ---------- تقرير PDF احترافي (HTML+CSS -> WeasyPrint) ----------
def _svg(a):
    h = a["hist"]; L = h + [a["tp2"], a["sl"]]; mx, mn = max(L), min(L); y = lambda v: 8 + (mx - v) / ((mx - mn) or 1) * 134
    pts = " ".join(f"{i / (len(h) - 1) * 600:.1f},{y(v):.1f}" for i, v in enumerate(h))
    ln = lambda v, c, t: f'<line x1="0" x2="600" y1="{y(v):.1f}" y2="{y(v):.1f}" stroke="{c}" stroke-dasharray="5 4"/><text x="598" y="{y(v) - 3:.1f}" fill="{c}" font-size="10" text-anchor="end">{t} {v}</text>'
    return (f'<svg viewBox="0 0 600 150" width="100%" height="150"><polyline fill="none" stroke="#1a56c4" stroke-width="2" points="{pts}"/>'
            + ln(a["tp2"], "#16845b", "TP2") + ln(a["tp1"], "#16845b", "TP1") + ln(a["entry"][1], "#b69a50", "entry") + ln(a["sl"], "#c83c45", "SL") + "</svg>")

def build_pdf(a):
    from weasyprint import HTML
    e = escape; s = lambda v: "—" if v is None else f"{v:,.2f}"
    now = dt.datetime.now().strftime("%Y-%m-%d  %H:%M")
    cls = {"شراء": "b", "بيع": "s", "محايد": "n"}
    summ = "".join(f"<tr><td>{p['label']}</td><td>{p['stats']['change']:+.2f}%</td><td>{p['summary']['buy']} / {p['summary']['sell']} / {p['summary']['neutral']}</td><td><b>{p['summary']['overall']}</b></td></tr>" for p in a["periods"].values())
    secs = ""
    for p in a["periods"].values():
        st = p["stats"]; names = [("open", "افتتاح الفترة"), ("close", "الإغلاق"), ("change", "التغير %"), ("high", "الأعلى"), ("low", "الأدنى"), ("range_pct", "المدى %"), ("pos", "موقع الإغلاق في النطاق %"), ("vol_ratio", "الحجم ÷ متوسط 20"), ("volatility", "التقلب اليومي %"), ("max_dd", "أقصى تراجع %"), ("gap", "فجوة الافتتاح %"), ("candle", "الشمعة")]
        sr = "".join(f"<tr><td>{t}</td><td>{e(str(st[k]))}</td></tr>" for k, t in names if k in st and st[k] is not None)
        last = ""; ir = ""
        for i in p["indicators"]:
            if i["group"] != last: last = i["group"]; ir += f'<tr><th colspan="3">{e(last)}</th></tr>'
            ir += f'<tr><td>{e(i["name"])}</td><td>{s(i["value"])}</td><td class="{cls[i["signal"]]}">{i["signal"]}</td></tr>'
        m = p["summary"]
        secs += (f'<div class="pg"><h2>{p["label"]} — الخلاصة: {m["overall"]} (شراء {m["buy"]} · بيع {m["sell"]} · محايد {m["neutral"]})</h2><p>{e(p["text"])}</p>'
                 f'<table class="st">{sr}</table><h3>المؤشرات الفنية</h3><table class="it">{ir}</table></div>')
    inf = a.get("info") or {}
    fund = "".join(f"<tr><td>{t}</td><td>{e(str(inf[k]))}</td></tr>" for k, t in (("sector", "القطاع"), ("industry", "النشاط"), ("marketCap", "القيمة السوقية"), ("trailingPE", "مكرر الربحية P/E"), ("priceToBook", "السعر/القيمة الدفترية"), ("dividendYield", "عائد التوزيعات")) if inf.get(k) is not None)
    html = f"""<html dir="rtl" lang="ar"><head><meta charset="utf-8"><style>
    @page{{size:A4;margin:14mm;@bottom-center{{content:"{SITE} — صفحة " counter(page);font-size:9px;color:#777}}}}
    body{{font-family:'Cairo','Noto Naskh Arabic','Amiri','DejaVu Sans',sans-serif;color:#071d3a;font-size:12px;line-height:1.8}}
    .hd{{background:#071d3a;color:#fff;padding:14px 18px;border-radius:10px}} .hd h1{{margin:0;font-size:22px;color:#e6c97a}} .hd p{{margin:2px 0 0;font-size:12px;color:#cfd8e6}}
    h2{{font-size:14.5px;margin:16px 0 6px;border-right:4px solid #b69a50;padding-right:8px}} h3{{font-size:13px;margin:10px 0 4px;color:#b69a50}}
    table{{width:100%;border-collapse:collapse}} td,th{{border:1px solid #ddd8c8;padding:4px 9px;text-align:right}} td:first-child{{background:#f8f6f0}} th{{background:#071d3a;color:#fff}}
    .it td:nth-child(2){{direction:ltr;text-align:left}} .b{{color:#16845b;font-weight:bold}} .s{{color:#c83c45;font-weight:bold}} .n{{color:#777}}
    .tc{{border:2px solid #b69a50;border-radius:10px;padding:8px 14px;background:#fbf9f2}} .tc div{{padding:2px 0;font-size:13px}} .pg{{page-break-before:always}}
    .dis{{margin-top:16px;font-size:10px;color:#4b5563;border-top:1px solid #ddd8c8;padding-top:8px}}</style></head><body>
    <div class="hd"><h1>{SITE}</h1><p>تقرير التحليل الفني الشامل — {e(a['symbol'])} · {e(a['name'])}</p><p>تاريخ ووقت الإصدار: {now} · آخر جلسة: {a['date']}</p></div>
    <h2>الملخص التنفيذي</h2><p>{e(a['text'])}</p>
    <table><tr><td>السعر الحالي</td><td>{s(a['price'])} جنيه ({a['change']:+.2f}%)</td></tr><tr><td>الاتجاه العام</td><td>{a['trend']}</td></tr>
    <tr><td>RSI (14)</td><td>{a['rsi']} — {e(a['rsi_zone'])}</td></tr><tr><td>متوسط 50 / 200 يوم</td><td>{s(a['sma50'])} / {s(a['sma200'])}</td></tr>{fund}</table>
    <h2>صندوق التوصية ونقاط التداول</h2><div class="tc"><div>🟢 منطقة الشراء / الدخول: بين {s(a['entry'][0])} و {s(a['entry'][1])} جنيه <small>({e(a['entry_basis'])})</small></div>
    <div>🎯 الهدف الأول (جني أرباح): {s(a['tp1'])} جنيه</div><div>🎯 الهدف الثاني (جني أرباح): {s(a['tp2'])} جنيه</div><div>🔴 مستوى وقف الخسارة: {s(a['sl'])} جنيه</div>
    <div>⚖️ العائد/المخاطرة حتى الهدف الأول: {a['rr']}:1</div></div>
    <h2>حركة السعر (آخر 90 جلسة)</h2>{_svg(a)}
    <h2>ملخص الأطر الزمنية</h2><table><tr><th>الإطار</th><th>التغير</th><th>شراء / بيع / محايد</th><th>الخلاصة</th></tr>{summ}</table>
    {secs}
    <div class="dis"><b>إخلاء المسؤولية:</b> هذا التقرير مُولَّد آليًا من بيانات Yahoo Finance لأغراض استرشادية وتحليلية فقط، ولا يُعد توصية مباشرة بالشراء أو البيع.
    الاستثمار في الأسهم ينطوي على مخاطر قد تصل إلى خسارة رأس المال، والقرار النهائي مسؤولية المستثمر وحده.</div></body></html>"""
    return HTML(string=html).write_pdf()

# ---------- المسارات ----------
@app.route("/")
def home(): return app.send_static_file("index.html")

@app.route("/api/suggest")
def api_suggest(): return jsonify(suggest(request.args.get("q", "")))

_ac = {}
def _run():
    code = resolve(request.args.get("q", "") or request.args.get("symbol", ""))
    if not code: return None, (jsonify(error="لم أجد سهمًا بهذا الاسم. جرّب الرمز مثل COMI."), 404)
    try:
        h = _ac.get(code)
        if not h or time.time() - h[0] > 300: h = _ac[code] = (time.time(), analyze(code))
        return h[1], None
    except Exception as ex: return None, (jsonify(error=f"تعذر جلب بيانات {code}: {ex}"), 502)

@app.route("/api/analyze")
def api_analyze():
    a, err = _run()
    return err if err else jsonify(a)

@app.route("/api/report.pdf")
def api_pdf():
    a, err = _run()
    if err: return err
    return Response(build_pdf(a), mimetype="application/pdf",
                    headers={"Content-Disposition": f"attachment; filename={a['symbol']}_report.pdf"})

if __name__ == "__main__":
    app.run(debug=True)
