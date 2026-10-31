"""Kullanım:
  python scripts/run.py nightly            -> tüm fonları tara, düzenli fonları yeniden seç, siteyi üret
  python scripts/run.py nightly --from DIR -> indirme yerine DIR/<KOD>.json dosyalarını kullan (ilk kurulum)
  python scripts/run.py intraday           -> saati gelen fonları güncelle, siteyi üret
  python scripts/run.py render             -> yalnızca siteyi yeniden üret
"""
import csv, glob, json, os, statistics, sys, time, datetime as dt
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(__file__))
import ekofin, compute, sitegen  # noqa: E402

sys.stdout.reconfigure(encoding='utf-8')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')
PRICES = os.path.join(DATA, 'prices')
TR = dt.timezone(dt.timedelta(hours=3))  # Türkiye saati (yaz saati yok)
LEAD = 45  # öğrenilen saatten bu kadar dakika önce kontrole başla
TYPES = ('Menkul Kıymet Yatırım Fonları', 'Borsa Yatırım Fonları')


def now_tr():
    return dt.datetime.now(TR)


def jload(p, default):
    try:
        with open(p, encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def jsave(p, o):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(o, f, ensure_ascii=False, separators=(',', ':'), sort_keys=True)


def wcsv(p, header, rows):
    with open(p, 'w', encoding='utf-8', newline='') as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def expected(s):
    """Fonun fiyatının genelde çıktığı saat (gece yarısından dakika), en az 2 gözlem gerekir."""
    obs = s.get('obs') or []
    return round(statistics.median(obs)) if len(obs) >= 2 else None


def hhmm(m):
    return '' if m is None else f'{m // 60:02d}:{m % 60:02d}'


def fetch_many(codes, cut, workers=3, pause=0.3):
    out, fail = {}, []

    def one(k):
        try:
            o = ekofin.fund_detail(k, cut)
            time.sleep(pause)
            return k, o
        except Exception as e:
            print('HATA', k, e, flush=True)
            return k, None

    with ThreadPoolExecutor(workers) as ex:
        for i, (k, o) in enumerate(ex.map(one, codes), 1):
            if o and o['prices']:
                out[k] = o
            else:
                fail.append(k)
            if i % 200 == 0:
                print('ilerleme', i, '/', len(codes), flush=True)
    return out, fail


# ---------------------------------------------------------------- gece taraması
def nightly(src=None):
    cut = compute.cut_date()
    if src:
        A = jload(os.path.join(src, '..', 'allfunds.json'), None) or jload(os.path.join(src, 'allfunds.json'), {})
        recs = {}
        for f in glob.glob(os.path.join(src, '*.json')):
            k = os.path.basename(f)[:-5]
            if len(k) == 3:
                recs[k] = jload(f, None)
    else:
        A = ekofin.fund_list()
        codes = sorted(k for k, o in A.items() if o.get('FON_TIPI') in TYPES)
        print('fon listesi', len(A), 'taranacak', len(codes), flush=True)
        if len(codes) < 1000:
            sys.exit('Fon listesi eksik geldi, mevcut veri korunuyor.')
        recs, fail = fetch_many(codes, cut)
        print('indirilen', len(recs), 'hata', len(fail), flush=True)
        if len(recs) < len(codes) * 0.9:
            sys.exit('Çok fazla fon indirilemedi, mevcut veri korunuyor.')
    rows, mon, tarama, END, S12 = compute.compute(recs, A)
    sel = compute.select(rows)
    print('bitiş', END, 'seçilen', len(sel), flush=True)
    for rk in range(1, 8):
        print(' risk', rk, tarama[rk], sum(1 for r in sel if r['risk'] == rk))
    keep = {r['kod'] for r in sel}
    os.makedirs(PRICES, exist_ok=True)
    for f in glob.glob(os.path.join(PRICES, '*.json')):
        if os.path.basename(f)[:-5] not in keep:
            os.remove(f)
    state = jload(os.path.join(DATA, 'state.json'), {})
    for k in keep:
        o = recs[k]
        o = dict(o, prices={d: p for d, p in o['prices'].items() if d >= cut})
        jsave(os.path.join(PRICES, k + '.json'), o)
        s = state.setdefault(k, {})
        newest = max(o['prices'])
        if newest > s.get('last_date', ''):
            s['last_date'] = newest  # gün içinde yakalanmadıysa saat gözlemi yazılmaz
    state = {k: v for k, v in state.items() if k in keep}
    jsave(os.path.join(DATA, 'state.json'), state)
    jsave(os.path.join(DATA, 'meta.json'), {k: A.get(k, {}) for k in keep})
    jsave(os.path.join(DATA, 'selection.json'), {r['kod']: r['durum'] for r in sel})
    wcsv(os.path.join(DATA, 'tarama.csv'), ['risk', 'guncel_fon', 'yeterli_veri', 'eksi_gunu_yok', 'donem_bas', 'donem_bit'],
         [[rk, *tarama[rk], S12, END] for rk in range(1, 8)])
    jsave(os.path.join(DATA, 'run.json'), dict(jload(os.path.join(DATA, 'run.json'), {}),
                                               tam_tarama=now_tr().isoformat(timespec='minutes')))
    render()


# ---------------------------------------------------------------- gün içi
def intraday():
    now = now_tr()
    today = now.date().isoformat()
    nowm = now.hour * 60 + now.minute
    sel = jload(os.path.join(DATA, 'selection.json'), {})
    state = jload(os.path.join(DATA, 'state.json'), {})
    if not sel:
        sys.exit('Seçim yok; önce nightly çalışmalı.')
    any_today = any(s.get('seen_day') == today for s in state.values())
    holiday_like = nowm >= 12 * 60 and not any_today
    due = []
    for k in sel:
        s = state.get(k, {})
        if s.get('seen_day') == today:
            continue
        exp = expected(s)
        if holiday_like and now.minute >= 15:
            continue  # öğlene kadar hiç fiyat gelmediyse (tatil olabilir) saatte bir bak
        if exp is None or nowm >= exp - LEAD:
            due.append(k)
    print(now.strftime('%d.%m %H:%M'), 'kontrol edilecek fon:', len(due), flush=True)
    if not due:
        render()
        return
    cut = compute.cut_date()
    got, fail = fetch_many(due, cut)
    changed = []
    for k, o in got.items():
        s = state.setdefault(k, {})
        newest = max(o['prices'])
        prev = s.get('checked_at')
        watched = False  # fon son 40 dakikada zaten kontrol edilmişse yeni fiyatın çıkış saati güvenilirdir
        if prev:
            try:
                watched = 0 <= (now - dt.datetime.fromisoformat(prev)).total_seconds() <= 40 * 60
            except ValueError:
                pass
        s['checked_at'] = now.isoformat(timespec='minutes')
        if newest > s.get('last_date', ''):
            s['last_date'] = newest
            s['seen_day'] = today
            s['seen_at'] = now.strftime('%H:%M')
            if watched and now.weekday() < 5:
                s['obs'] = (s.get('obs') or [])[-19:] + [nowm]
            jsave(os.path.join(PRICES, k + '.json'), o)
            changed.append(k)
    print('güncellenen:', len(changed), ' '.join(sorted(changed)), '| hata:', len(fail), flush=True)
    jsave(os.path.join(DATA, 'state.json'), state)
    if changed:
        jsave(os.path.join(DATA, 'run.json'), dict(jload(os.path.join(DATA, 'run.json'), {}),
                                                   son_guncelleme=now.isoformat(timespec='minutes')))
    render()


# ---------------------------------------------------------------- site
def render():
    sel = jload(os.path.join(DATA, 'selection.json'), {})
    meta = jload(os.path.join(DATA, 'meta.json'), {})
    state = jload(os.path.join(DATA, 'state.json'), {})
    recs = {k: jload(os.path.join(PRICES, k + '.json'), None) for k in sel}
    recs = {k: v for k, v in recs.items() if v}
    rows, mon, _, END, _ = compute.compute(recs, meta)
    out = []
    for r in rows:
        # gün içinde eksi gün gören fon listeden çıkar
        if r['kod'] not in sel or not r['regular']:
            continue
        r['durum'] = sel[r['kod']]
        del r['regular']
        s = state.get(r['kod'], {})
        r['beklenen'] = hhmm(expected(s))
        r['guncellendi_gun'] = s.get('seen_day', '')
        r['guncellendi_saat'] = s.get('seen_at', '')
        out.append(compute.finish(r))
    with open(os.path.join(DATA, 'fonlar.csv'), 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(out[0]))
        w.writeheader()
        w.writerows(out)
    wcsv(os.path.join(DATA, 'aylik.csv'), ['kod', 'ay', 'getiri', 'son_gun'],
         [[r['kod'], *m] for r in out for m in mon[r['kod']]])
    run = jload(os.path.join(DATA, 'run.json'), {})
    sitegen.build(ROOT, uretildi=now_tr().isoformat(timespec='minutes'),
               son_guncelleme=run.get('son_guncelleme') or run.get('tam_tarama', ''))
    print('site üretildi:', len(out), 'fon, veri', END, flush=True)


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) > 1 else 'intraday'
    if mode == 'nightly':
        src = sys.argv[sys.argv.index('--from') + 1] if '--from' in sys.argv else None
        nightly(src)
    elif mode == 'intraday':
        intraday()
    else:
        render()
