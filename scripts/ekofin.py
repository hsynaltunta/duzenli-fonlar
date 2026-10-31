"""Ekofin'den TEFAS fon verisi: fon listesi ve tek fonun fiyat geçmişi."""
import json, re, time, urllib.request

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36'


def _get(url, rsc=False, timeout=40):
    h = {'User-Agent': UA}
    if rsc:
        h['RSC'] = '1'
    err = None
    for i in range(3):
        try:
            req = urllib.request.Request(url, headers=h)
            return urllib.request.urlopen(req, timeout=timeout).read().decode('utf-8', 'replace')
        except Exception as e:  # ağ hatasında birkaç kez dene
            err = e
            time.sleep(4 * (i + 1))
    raise err


def fund_list():
    """Tüm fonların künyesi: {KOD: {...}}"""
    t = _get('https://www.ekofin.net/fonlar').replace('\\"', '"')
    objs = {}
    for m in re.finditer(r'\{"SON_FIYAT":[^{}]*?"FON_KODU":"([A-Z0-9]{3})"[^{}]*\}', t):
        try:
            o = json.loads(m.group(0))
        except Exception:
            continue
        objs[o['FON_KODU']] = o
    return objs


def fund_detail(k, cut):
    """Tek fonun risk, valör, stopaj bilgisi ve cut tarihinden bu yana günlük fiyatları."""
    t = _get(f'https://www.ekofin.net/fonlar/detay/{k}', rsc=True).replace('\\"', '"')
    pat = r'"son_Fiyat":([\d.eE+-]+),"gunluk_Getiri":[-\d.eE+]+,"fon_Kodu":"' + k + r'","İslem_Tarihi":"(\d{4}-\d\d-\d\d)'
    pr = {d: float(p) for p, d in re.findall(pat, t) if d >= cut}

    def g(n):
        m = re.search('"' + n + r'":"?([^",}]*)', t)
        return m.group(1) if m else None

    return dict(risk=g('RISK_DEGERI'), alis=g('FON_ALIS_VALORU_TEXT'), satis=g('FON_SATIS_VALORU_TEXT'),
                durum=g('DURUM'), stopaj=g('STOPAJ_ORANI'), tur=g('FON_TURU'), prices=pr)
