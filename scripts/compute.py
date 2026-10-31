"""Fiyat geçmişinden fon ölçüleri: eksi gün, dönem getirileri, aylık getiriler ve seçim."""
import math, collections, datetime as dt


def D(s):
    return dt.date.fromisoformat(s)


def periods(END):
    e = D(END)
    S12 = e.replace(year=e.year - 1).isoformat() if not (e.month == 2 and e.day == 29) else dt.date(e.year - 1, 2, 28).isoformat()
    S18 = dt.date(e.year - 1 if e.month > 6 else e.year - 2, (e.month - 18 - 1) % 12 + 1, min(e.day, 28)).isoformat()
    S6 = dt.date(e.year if e.month > 6 else e.year - 1, (e.month - 6 - 1) % 12 + 1, min(e.day, 28)).isoformat()
    return S6, S12, S18


def cut_date(today=None):
    """Fiyatları bu tarihten itibaren tut (18 ay + pay)."""
    e = today or dt.date.today()
    return (e - dt.timedelta(days=590)).isoformat()


def clean(pr):
    """Sıfır fiyatları at, pay bölünmelerini düzelt."""
    pr = {d: p for d, p in pr.items() if p and p > 0}
    ds = sorted(pr)
    for a, b in zip(ds, ds[1:]):
        r = pr[a] / pr[b]
        if r > 50 or r < 0.02:
            fac = 10 ** round(math.log10(r))
            for d in ds:
                if d <= a:
                    pr[d] /= fac
    return pr, ds


def compute(recs, A, END=None):
    """recs: {kod: detay}, A: {kod: künye}. Dönüş: (satırlar, aylık, tarama, END, S12)"""
    prepared = []
    for k, o in recs.items():
        pr, ds = clean(dict(o['prices']))
        if len(ds) < 30:
            continue
        prepared.append((k, o, pr, ds))
    if not prepared:
        return [], {}, {}, END, None
    END = END or max(r[3][-1] for r in prepared)
    e = D(END)
    S6, S12, S18 = periods(END)
    rows = []
    mon = {}
    tarama = collections.defaultdict(lambda: [0, 0, 0])
    for k, o, pr, ds in prepared:
        a = A.get(k, {})
        try:
            risk = int(o.get('risk'))
        except Exception:
            continue
        if not 1 <= risk <= 7:
            continue
        if ds[-1] < (e - dt.timedelta(days=10)).isoformat():
            continue
        tarama[risk][0] += 1
        base = [d for d in ds if d <= S12]
        if not base:
            continue
        w = [d for d in ds if d >= base[-1]]
        if len(w) < 200:
            continue
        wj = [d for d in ds if d >= S18]
        if any(pr[y] / pr[x] > 1.4 or pr[y] / pr[x] < 0.7 for x, y in zip(wj, wj[1:])):
            continue  # tek günde %40'tan fazla oynama: veri hatası ya da fon dönüşümü
        tarama[risk][1] += 1
        neg = sum(1 for x, y in zip(w, w[1:]) if pr[y] < pr[x])
        zero = sum(1 for x, y in zip(w, w[1:]) if pr[y] == pr[x])
        tot = pr[w[-1]] / pr[w[0]] - 1
        months = (D(w[-1]) - D(w[0])).days / 30.4375
        g12 = (1 + tot) ** (1 / months) - 1 if tot > -1 else -1
        pk = 0
        mdd = 0
        for d in w:
            pk = max(pk, pr[d])
            mdd = min(mdd, pr[d] / pk - 1)
        b18 = [d for d in ds if d <= S18]
        d0 = b18[-1] if b18 else ds[0]
        m18 = (D(ds[-1]) - D(d0)).days / 30.4375
        g18 = (pr[ds[-1]] / pr[d0]) ** (1 / m18) - 1
        w18 = [d for d in ds if d >= d0]
        tot18 = pr[ds[-1]] / pr[d0] - 1
        b6 = [d for d in ds if d <= S6]
        d6 = b6[-1]
        tot6 = pr[ds[-1]] / pr[d6] - 1
        g6 = (1 + tot6) ** (1 / ((D(ds[-1]) - D(d6)).days / 30.4375)) - 1
        me = {}
        for d in w18:
            me[d[:7]] = d
        ms = sorted(me)
        mret = [(b, round((pr[me[b]] / pr[me[a2]] - 1) * 100, 2), me[b]) for a2, b in zip(ms, ms[1:])]
        full = [x[1] for x in mret if x[0] < END[:7] and x[0] > S12[:7]]
        regular = neg == 0 and tot > 0 and zero <= 25
        if regular:
            tarama[risk][2] += 1
        name = a.get('FON_ADI', k)
        rows.append(dict(
            kod=k, ad=name, kurucu=a.get('KURUCU', ''),
            kategori=(a.get('KATEGORI') or '').replace(' Şemsiye Fonu', ''), tur=o.get('tur') or '',
            alabilir='Nitelikli yatırımcı' if 'SERBEST' in name.upper() else 'Herkes', risk=risk,
            alis_valor=o.get('alis') or '', satis_valor=o.get('satis') or '',
            tefas='Evet' if a.get('TEFAS_ISLEM_DURUMU') else 'Hayır',
            portfoy_mn_tl=round((a.get('FON_TOPLAM_DEGER') or 0) / 1e6, 2), yatirimci=a.get('YATIRIMCI_SAYISI') or 0,
            stopaj=o.get('stopaj') or '',
            getiri_1a=a.get('SON_BIR_AY_GETIRISI'), getiri_3a=a.get('SON_UC_AY_GETIRISI'),
            getiri_6a=round(tot6 * 100, 2), ort_6ay=round(g6 * 100, 2),
            getiri_1y=round(tot * 100, 2), ort_12ay=round(g12 * 100, 2),
            getiri_18ay=round(tot18 * 100, 2), ort_18ay=round(g18 * 100, 2), gecmis_18=round(min(m18, 18)),
            en_dusuk_ay=min(full) if full else '', eksi_gun=neg, sabit_gun=zero, en_buyuk_dusus=round(mdd * 100, 2),
            son_fiyat_tarihi=ds[-1], veri_tarihi=END, regular=regular))
        mon[k] = mret
    return rows, mon, tarama, END, S12


VAL = {'Aynı gün': 'T+0 (aynı gün)', '1 iş günü': 'T+1', '2 iş günü': 'T+2', '3 iş günü': 'T+3', '4 iş günü': 'T+4'}


def finish(r):
    for f in ('alis_valor', 'satis_valor', 'stopaj', 'tur'):
        if str(r[f]) in ('null', 'None'):
            r[f] = ''
    for f in ('alis_valor', 'satis_valor'):
        r[f] = VAL.get(r[f], r[f])
    return r


def select(rows):
    """Eksi günü olmayan tüm fonlar; 3'ten az olan seviyelerde en az eksi günü olan 5 fon."""
    out = [r for r in rows if r['regular']]
    for rk in range(1, 8):
        if sum(1 for r in out if r['risk'] == rk) < 3:
            cand = sorted([r for r in rows if r['risk'] == rk and not r['regular'] and r['getiri_1y'] > 0],
                          key=lambda r: (r['eksi_gun'], -r['en_buyuk_dusus'], -r['ort_12ay']))[:5]
            out += cand
    for r in out:
        r['durum'] = 'Eksi gün yok' if r['regular'] else 'Seviyesinin en düzenlisi'
    return out
