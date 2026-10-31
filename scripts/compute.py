"""Fiyat geçmişinden fon ölçüleri: eksi gün, dönem getirileri, aylık getiriler ve seçim."""
import math, calendar, collections, datetime as dt


def D(s):
    return dt.date.fromisoformat(s)


PERS = (3, 6, 9, 12, 18)


def back(e, n):
    """e tarihinden n ay önce (ay kısaysa ayın son günü)."""
    m = e.month - n
    y = e.year + (m - 1) // 12
    m = (m - 1) % 12 + 1
    return dt.date(y, m, min(e.day, calendar.monthrange(y, m)[1]))


def periods(END):
    e = D(END)
    return {P: back(e, P).isoformat() for P in PERS}


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


def window(pr, ds, start, P):
    """start tarihindeki son fiyattan bugüne pencere ölçüleri; veri yetmezse None."""
    base = [d for d in ds if d <= start]
    if not base:
        return None
    w = [d for d in ds if d >= base[-1]]
    if len(w) < round(P * 16.5):  # ayda ~21 iş günü; boşluklu fiyatları ele
        return None
    neg = sum(1 for x, y in zip(w, w[1:]) if pr[y] < pr[x])
    zero = sum(1 for x, y in zip(w, w[1:]) if pr[y] == pr[x])
    tot = pr[w[-1]] / pr[w[0]] - 1
    months = (D(w[-1]) - D(w[0])).days / 30.4375
    g = (1 + tot) ** (1 / months) - 1 if tot > -1 else -1
    pk = mdd = 0
    for d in w:
        pk = max(pk, pr[d])
        mdd = min(mdd, pr[d] / pk - 1)
    ok = neg == 0 and tot > 0 and zero <= math.ceil(25 * P / 12)
    return dict(neg=neg, zero=zero, tot=tot, g=g, mdd=mdd, ok=ok)


def compute(recs, A, END=None):
    """recs: {kod: detay}, A: {kod: künye}. Dönüş: (satırlar, aylık, tarama, END, dönem başları)"""
    prepared = []
    for k, o in recs.items():
        pr, ds = clean(dict(o['prices']))
        if len(ds) < 30:
            continue
        prepared.append((k, o, pr, ds))
    if not prepared:
        return [], {}, {}, END, {}
    END = END or max(r[3][-1] for r in prepared)
    e = D(END)
    S = periods(END)
    rows = []
    mon = {}
    # risk -> {'guncel': n, P: [yeterli, eksisiz]}
    tarama = collections.defaultdict(lambda: {'guncel': 0, **{P: [0, 0] for P in PERS}})
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
        tarama[risk]['guncel'] += 1
        wj = [d for d in ds if d >= S[18]]
        if any(pr[y] / pr[x] > 1.4 or pr[y] / pr[x] < 0.7 for x, y in zip(wj, wj[1:])):
            continue  # tek günde %40'tan fazla oynama: veri hatası ya da fon dönüşümü
        W = {P: window(pr, ds, S[P], P) for P in PERS}
        if not any(W.values()):
            continue
        for P in PERS:
            if W[P]:
                tarama[risk][P][0] += 1
                tarama[risk][P][1] += W[P]['ok']
        b18 = [d for d in ds if d <= S[18]]
        d0 = b18[-1] if b18 else ds[0]
        me = {}
        for d in ds:
            if d >= d0:
                me[d[:7]] = d
        ms = sorted(me)
        mret = [(b, round((pr[me[b]] / pr[me[a2]] - 1) * 100, 2), me[b]) for a2, b in zip(ms, ms[1:])]
        name = a.get('FON_ADI', k)
        row = dict(
            kod=k, ad=name, kurucu=a.get('KURUCU', ''),
            kategori=(a.get('KATEGORI') or '').replace(' Şemsiye Fonu', ''), tur=o.get('tur') or '',
            alabilir='Nitelikli yatırımcı' if 'SERBEST' in name.upper() else 'Herkes', risk=risk,
            alis_valor=o.get('alis') or '', satis_valor=o.get('satis') or '',
            tefas='Evet' if a.get('TEFAS_ISLEM_DURUMU') else 'Hayır',
            portfoy_mn_tl=round((a.get('FON_TOPLAM_DEGER') or 0) / 1e6, 2), yatirimci=a.get('YATIRIMCI_SAYISI') or 0,
            stopaj=o.get('stopaj') or '', getiri_1a=a.get('SON_BIR_AY_GETIRISI'))
        for P in PERS:
            w = W[P]
            row['g%d' % P] = round(w['tot'] * 100, 2) if w else ''
            row['o%d' % P] = round(w['g'] * 100, 2) if w else ''
            row['e%d' % P] = w['neg'] if w else ''
            row['dd%d' % P] = round(w['mdd'] * 100, 2) if w else ''
            row['d%d' % P] = 1 if w and w['ok'] else 0
        row.update(son_fiyat_tarihi=ds[-1], veri_tarihi=END, regular=any(w and w['ok'] for w in W.values()))
        rows.append(row)
        mon[k] = mret
    return rows, mon, tarama, END, S


VAL = {'Aynı gün': 'T+0 (aynı gün)', '1 iş günü': 'T+1', '2 iş günü': 'T+2', '3 iş günü': 'T+3', '4 iş günü': 'T+4'}


def finish(r):
    for f in ('alis_valor', 'satis_valor', 'stopaj', 'tur'):
        if str(r[f]) in ('null', 'None'):
            r[f] = ''
    for f in ('alis_valor', 'satis_valor'):
        r[f] = VAL.get(r[f], r[f])
    return r


def select(rows):
    """Seçilebilen dönemlerden en az birinde hiç eksi günü olmayan fonlar."""
    out = [r for r in rows if r['regular']]
    for r in out:
        r['durum'] = 'Eksi gün yok'
    return out
