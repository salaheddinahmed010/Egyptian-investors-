# -*- coding: utf-8 -*-
"""كل المؤشرات الفنية: تعيد قائمة {name,value,signal,group} + ملخص."""
import pandas as pd, numpy as np
B, S, N = "شراء", "بيع", "محايد"
ema = lambda s, n: s.ewm(span=n, adjust=False).mean()
wil = lambda s, n: s.ewm(alpha=1/n, adjust=False).mean()

def psar(h, l, af0=.02, afm=.2):
    h, l = h.values, l.values; up = True; sar = l[0]; ep = h[0]; af = af0
    for i in range(1, len(h)):
        sar += af * (ep - sar)
        if up:
            sar = min(sar, l[i-1], l[i-2] if i > 1 else l[i-1])
            if l[i] < sar: up, sar, ep, af = False, ep, l[i], af0
            elif h[i] > ep: ep, af = h[i], min(af + af0, afm)
        else:
            sar = max(sar, h[i-1], h[i-2] if i > 1 else h[i-1])
            if h[i] > sar: up, sar, ep, af = True, ep, h[i], af0
            elif l[i] < ep: ep, af = l[i], min(af + af0, afm)
    return sar, up

def compute(df, kk=1.0):
    W = lambda n: max(3, int(round(n * kk)))
    c, h, l, v = df.Close, df.High, df.Low, df.Volume; p = float(c.iloc[-1]); out = []
    def add(g, n, val, sig):
        ok = val is not None and not pd.isna(val)
        out.append({"group": g, "name": n, "value": round(float(val), 2) if ok else None, "signal": sig if ok else N})
    ge = lambda x, lo, hi: B if x < lo else S if x > hi else N
    for n in sorted({W(x) for x in (10, 20, 50, 100, 200)}):
        if len(c) >= n:
            m = c.tail(n).mean(); add("المتوسطات المتحركة", f"SMA {n}", m, B if p > m else S)
    for n in sorted({W(x) for x in (10, 20, 50, 100, 200)}):
        if len(c) >= n:
            m = ema(c, n).iloc[-1]; add("المتوسطات المتحركة", f"EMA {n}", m, B if p > m else S)
    # زخم
    d = c.diff(); rs = wil(d.clip(lower=0), W(14)) / wil(-d.clip(upper=0), W(14)).replace(0, np.nan)
    rsi = 100 - 100 / (1 + rs); add("الزخم", f"RSI ({W(14)})", rsi.iloc[-1], ge(rsi.iloc[-1], 30, 70))
    ll, hh = l.rolling(W(14)).min(), h.rolling(W(14)).max()
    k = 100 * (c - ll) / (hh - ll); add("الزخم", f"Stochastic %K ({W(14)})", k.iloc[-1], ge(k.iloc[-1], 20, 80))
    add("الزخم", "Stochastic %D (3)", k.rolling(3).mean().iloc[-1], ge(k.rolling(3).mean().iloc[-1], 20, 80))
    r14 = rsi.rolling(W(14)); sr = 100 * (rsi - r14.min()) / (r14.max() - r14.min()); add("الزخم", "Stochastic RSI", sr.iloc[-1], ge(sr.iloc[-1], 20, 80))
    wr = -100 * (hh - c) / (hh - ll); add("الزخم", f"Williams %R ({W(14)})", wr.iloc[-1], B if wr.iloc[-1] < -80 else S if wr.iloc[-1] > -20 else N)
    tp = (h + l + c) / 3; sm = tp.rolling(W(20)).mean(); cci = (tp - sm) / (.015 * tp.rolling(W(20)).apply(lambda x: np.abs(x - x.mean()).mean()))
    add("الزخم", f"CCI ({W(20)})", cci.iloc[-1], ge(cci.iloc[-1], -100, 100))
    roc = c.pct_change(W(12)) * 100; add("الزخم", f"ROC ({W(12)})", roc.iloc[-1], B if roc.iloc[-1] > 0 else S)
    mom = c - c.shift(W(10)); add("الزخم", f"Momentum ({W(10)})", mom.iloc[-1], B if mom.iloc[-1] > 0 else S)
    md = (h + l) / 2; ao = md.rolling(W(5)).mean() - md.rolling(W(34)).mean(); add("الزخم", "Awesome Oscillator", ao.iloc[-1], B if ao.iloc[-1] > 0 else S)
    macd = ema(c, W(12)) - ema(c, W(26)); sg = ema(macd, W(9)); hs = macd - sg
    add("الاتجاه", f"MACD ({W(12)},{W(26)})", macd.iloc[-1], B if macd.iloc[-1] > sg.iloc[-1] else S)
    add("الاتجاه", f"MACD Signal ({W(9)})", sg.iloc[-1], B if hs.iloc[-1] > 0 else S)
    add("الاتجاه", "MACD Histogram", hs.iloc[-1], B if hs.iloc[-1] > 0 else S)
    # ADX
    up, dn = h.diff(), -l.diff(); pdm = up.where((up > dn) & (up > 0), 0); mdm = dn.where((dn > up) & (dn > 0), 0)
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1); atr = wil(tr, W(14))
    pdi, mdi = 100 * wil(pdm, W(14)) / atr, 100 * wil(mdm, W(14)) / atr; adx = wil(100 * (pdi - mdi).abs() / (pdi + mdi), W(14))
    add("الاتجاه", f"ADX ({W(14)})", adx.iloc[-1], B if adx.iloc[-1] > 25 and pdi.iloc[-1] > mdi.iloc[-1] else S if adx.iloc[-1] > 25 else N)
    add("الاتجاه", f"+DI ({W(14)})", pdi.iloc[-1], N); add("الاتجاه", f"-DI ({W(14)})", mdi.iloc[-1], N)
    s_, u_ = psar(h, l); add("الاتجاه", "Parabolic SAR", s_, B if u_ else S)
    # إيشيموكو
    tk = (h.rolling(W(9)).max() + l.rolling(W(9)).min()) / 2; kj = (h.rolling(W(26)).max() + l.rolling(W(26)).min()) / 2
    sa = ((tk + kj) / 2).shift(W(26)); sb = ((h.rolling(W(52)).max() + l.rolling(W(52)).min()) / 2).shift(W(26))
    add("إيشيموكو", "Tenkan-sen (9)", tk.iloc[-1], B if p > tk.iloc[-1] else S); add("إيشيموكو", "Kijun-sen (26)", kj.iloc[-1], B if p > kj.iloc[-1] else S)
    if not pd.isna(sa.iloc[-1]) and not pd.isna(sb.iloc[-1]):
        add("إيشيموكو", "Senkou Span A", sa.iloc[-1], B if p > sa.iloc[-1] else S); add("إيشيموكو", "Senkou Span B", sb.iloc[-1], B if p > sb.iloc[-1] else S)
    # تقلب
    m20, sd = c.rolling(W(20)).mean(), c.rolling(W(20)).std(); up_b, lo_b = m20 + 2 * sd, m20 - 2 * sd
    add("التقلب", "Bollinger العلوي", up_b.iloc[-1], S if p > up_b.iloc[-1] else N); add("التقلب", "Bollinger الأوسط", m20.iloc[-1], B if p > m20.iloc[-1] else S)
    add("التقلب", "Bollinger السفلي", lo_b.iloc[-1], B if p < lo_b.iloc[-1] else N)
    add("التقلب", "Bollinger %B", (p - lo_b.iloc[-1]) / (up_b.iloc[-1] - lo_b.iloc[-1]), ge((p - lo_b.iloc[-1]) / (up_b.iloc[-1] - lo_b.iloc[-1]), 0, 1))
    add("التقلب", f"ATR ({W(14)})", atr.iloc[-1], N); add("التقلب", "ATR %", atr.iloc[-1] / p * 100, N)
    ke = ema(c, W(20)); add("التقلب", "Keltner العلوي", ke.iloc[-1] + 2 * atr.iloc[-1], S if p > ke.iloc[-1] + 2 * atr.iloc[-1] else N)
    add("التقلب", "Keltner السفلي", ke.iloc[-1] - 2 * atr.iloc[-1], B if p < ke.iloc[-1] - 2 * atr.iloc[-1] else N)
    dh, dl = h.rolling(W(20)).max(), l.rolling(W(20)).min(); add("التقلب", f"Donchian العلوي ({W(20)})", dh.iloc[-1], B if p >= dh.iloc[-1] else N); add("التقلب", f"Donchian السفلي ({W(20)})", dl.iloc[-1], S if p <= dl.iloc[-1] else N)
    # حجم
    obv = (np.sign(d).fillna(0) * v).cumsum(); add("الحجم", "OBV", obv.iloc[-1], B if obv.iloc[-1] > obv.rolling(W(20)).mean().iloc[-1] else S)
    rmf = tp * v; pos = rmf.where(tp.diff() > 0, 0).rolling(W(14)).sum(); neg = rmf.where(tp.diff() < 0, 0).rolling(W(14)).sum()
    mfi = 100 - 100 / (1 + pos / neg.replace(0, np.nan)); add("الحجم", f"MFI ({W(14)})", mfi.iloc[-1], ge(mfi.iloc[-1], 20, 80))
    mf = ((2 * c - h - l) / (h - l).replace(0, np.nan) * v); cmf = mf.rolling(W(20)).sum() / v.rolling(W(20)).sum(); add("الحجم", f"CMF ({W(20)})", cmf.iloc[-1], B if cmf.iloc[-1] > .05 else S if cmf.iloc[-1] < -.05 else N)
    vw = (tp * v).rolling(W(20)).sum() / v.rolling(W(20)).sum(); add("الحجم", f"VWAP ({W(20)})", vw.iloc[-1], B if p > vw.iloc[-1] else S)
    add("الحجم", f"متوسط حجم {W(20)} جلسة", v.tail(W(20)).mean(), N)
    # نقاط الارتكاز (من آخر جلسة)
    H_, L_, C_ = float(h.iloc[-1]), float(l.iloc[-1]), float(c.iloc[-1]); P = (H_ + L_ + C_) / 3
    for n, x in (("Pivot", P), ("R1", 2 * P - L_), ("R2", P + H_ - L_), ("S1", 2 * P - H_), ("S2", P - H_ + L_)): add("نقاط الارتكاز", n, x, N)
    nb, ns = sum(i["signal"] == B for i in out), sum(i["signal"] == S for i in out); nn = len(out) - nb - ns
    r = nb / (nb + ns) if nb + ns else .5
    ov = "شراء قوي" if r >= .75 else "شراء" if r >= .6 else "بيع قوي" if r <= .25 else "بيع" if r <= .4 else "محايد"
    return out, {"buy": nb, "sell": ns, "neutral": nn, "total": len(out), "overall": ov}
