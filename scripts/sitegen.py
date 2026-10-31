"""Siteyi üretir: public/index.html (sayfa) ve public/data.json (veri)."""
import csv, json, os

AY = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran', 'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık']

HEAD = r'''<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Düzenli Getirili Fonlar</title>
<meta name="description" content="Son 12 ayda hiç eksi günü olmayan yatırım fonları: risk seviyesine göre, ay ay getiri, valör ve birikim hesaplayıcı.">
<meta property="og:title" content="Düzenli Getirili Fonlar">
<meta property="og:description" content="Son 12 ayda hiç eksi günü olmayan yatırım fonları ve birikim hesaplayıcı.">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='7' fill='%231f7a6d'/%3E%3Cpath d='M7 22l6-6 4 4 8-9' stroke='white' stroke-width='3' fill='none' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Source+Serif+4:opsz,wght@8..60,400;8..60,600&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.9.0/d3.min.js"></script>
<style>
:root{
  --font-anthropic-sans:Inter,system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;
  --font-anthropic-serif:"Source Serif 4",Georgia,serif;
  --cds-gap-xs:.25rem;--cds-gap-sm:.5rem;--cds-gap-md:.75rem;--cds-gap-lg:1.5rem;
  --cds-pad-xs:.25rem;--cds-pad-sm:.5rem;--cds-pad-md:.75rem;--cds-pad-lg:1.25rem;
  --cds-radius:8px;--cds-dur-slow:.6s;
  --cds-font-size-caption:.8125rem;--cds-font-size-body:.9375rem;--cds-font-size-heading:1.0625rem;--cds-font-size-title:clamp(1.6rem,4vw,2.25rem);
  --cds-font-weight-medium:500;
  --color-bg:#f7f6f2;--color-panel:#ffffff;--color-fg:#1d1d1b;--color-fg-muted:#5f5e58;--color-border-line:#e2e0d8;
  --color-ok:#1f7a4d;--color-warn:#b7791f;--color-bad:#c0392b;
  --cds-border:#d8d6cd;--cds-surface-popover:#ffffff;--cds-shadow-popover:0 6px 24px rgba(0,0,0,.12);--cds-text-secondary:#6b6a63;
  --cds-chart-grid:#ebe9e2;--cds-chart-muted:#dcdad2;--cds-chart-status-critical:#d64545;
  --accent:#1f7a6d;
  color-scheme:light;
}
@media (prefers-color-scheme: dark){
  :root:not([data-theme="light"]){
    --color-bg:#161615;--color-panel:#1f1f1d;--color-fg:#ecebe6;--color-fg-muted:#a3a29b;--color-border-line:#33322f;
    --color-ok:#5cc28d;--color-warn:#e0a84a;--color-bad:#ef6b5e;
    --cds-border:#3a3936;--cds-surface-popover:#262624;--cds-shadow-popover:0 6px 24px rgba(0,0,0,.5);--cds-text-secondary:#a3a29b;
    --cds-chart-grid:#2c2b28;--cds-chart-muted:#3a3936;--cds-chart-status-critical:#ef6b5e;
    --accent:#4fb8a6;color-scheme:dark;
  }
}
:root[data-theme="dark"]{
  --color-bg:#161615;--color-panel:#1f1f1d;--color-fg:#ecebe6;--color-fg-muted:#a3a29b;--color-border-line:#33322f;
  --color-ok:#5cc28d;--color-warn:#e0a84a;--color-bad:#ef6b5e;
  --cds-border:#3a3936;--cds-surface-popover:#262624;--cds-shadow-popover:0 6px 24px rgba(0,0,0,.5);--cds-text-secondary:#a3a29b;
  --cds-chart-grid:#2c2b28;--cds-chart-muted:#3a3936;--cds-chart-status-critical:#ef6b5e;
  --accent:#4fb8a6;color-scheme:dark;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--color-bg);color:var(--color-fg);font-family:var(--font-anthropic-sans);line-height:1.45}
.site{max-width:84rem;margin:0 auto;padding:2rem 16px 3rem}
@media (min-width:700px){.site{padding:2.5rem 2rem 4rem}}
.dash-skeleton{color:transparent!important;background:linear-gradient(90deg,var(--cds-chart-muted) 25%,var(--cds-chart-grid) 50%,var(--cds-chart-muted) 75%);background-size:200% 100%;animation:sk 1.4s infinite;border-radius:4px}
@keyframes sk{to{background-position:-200% 0}}
svg text{fill:var(--color-fg-muted);font-size:11px;font-family:var(--font-anthropic-sans)}
.site-foot{margin-top:2.5rem;padding-top:1.25rem;border-top:1px solid var(--color-border-line);color:var(--color-fg-muted);font-size:var(--cds-font-size-caption);display:flex;flex-direction:column;gap:.35rem}
</style>
<script>
(function(){
  let store={}, uretildi=null;
  const calcs=[]; let listener=null;
  const dark=()=>matchMedia('(prefers-color-scheme: dark)').matches;
  window.FZ_META={};
  function load(d){
    store={}; for(const k of ['fonlar','aylik','tarama']) store[k]={status:'ok',data:d[k]||[]};
    uretildi=d.uretildi; window.FZ_META={uretildi:d.uretildi,son_guncelleme:d.son_guncelleme,tam_tarama:d.tam_tarama};
    for(const [id,o] of calcs){
      try{store[id]={status:'ok',data:o.fn(...o.inputs.map(i=>store[i].data))};}
      catch(e){console.error(e);store[id]={status:'error',data:[]};}
    }
    if(listener) listener();
  }
  window.dash={
    get colors(){return [getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()||(dark()?'#4fb8a6':'#1f7a6d')];},
    data(id){return store[id]||{status:'loading',data:[]};},
    calc(id,o){calcs.push([id,o]);},
    onData(fn){listener=fn;},
    _run(){
      fetch('data.json?t='+Date.now(),{cache:'no-store'}).then(r=>r.json()).then(load).catch(e=>{
        console.error(e); for(const k of ['fonlar','aylik','tarama','ozet']) store[k]={status:'error',data:[]}; if(listener) listener();
      });
      // açık sayfa yeni veriyi kendisi alır
      setInterval(()=>{
        if(document.hidden) return;
        fetch('data.json?t='+Date.now(),{cache:'no-store'}).then(r=>r.json()).then(d=>{ if(d.uretildi!==uretildi&&d.son_guncelleme!==window.FZ_META.son_guncelleme) load(d); else window.FZ_META.uretildi=d.uretildi; }).catch(()=>{});
      },120000);
    }
  };
  matchMedia('(prefers-color-scheme: dark)').addEventListener('change',()=>listener&&listener());
})();
</script>
</head>
<body>
<main class="site">
'''

FOOT = '''
<footer class="site-foot">
  <span>Veriler TEFAS fiyatlarıdır (Ekofin üzerinden). Veriler tek merkezden güncellenir, herkes aynı veriyi görür: her gün 07:00–19:00 arasında saat başı yeni fiyatlar alınır, her gece 23:35'te tüm fonlar yeniden taranır. TEFAS hafta sonu ve resmi tatillerde fiyat yayınlamaz; bu günlerde fiyatlar son iş gününde kalır. Getiriler vergi öncesidir.</span>
  <span>Geçmiş getiri geleceği garanti etmez. <b>Bu site yatırım tavsiyesi değildir</b>; karar vermeden önce bankanıza ya da aracı kurumunuza danışın.</span>
  <span><a href="gizlilik.html" style="color:inherit">Gizlilik politikası</a></span>
</footer>
</main>
<script>dash._run();</script>
</body>
</html>
'''


def build(root, uretildi, son_guncelleme, tam_tarama=''):
    pub = os.path.join(root, 'public')
    os.makedirs(pub, exist_ok=True)
    page = open(os.path.join(root, 'page.html'), encoding='utf-8').read()
    page = page.replace("d.textContent='Failed to load'", "d.textContent='Yüklenemedi'")
    with open(os.path.join(pub, 'index.html'), 'w', encoding='utf-8') as f:
        f.write(HEAD + page + FOOT)
    data = {}
    for k in ('fonlar', 'aylik', 'tarama'):
        with open(os.path.join(root, 'data', k + '.csv'), encoding='utf-8') as f:
            data[k] = list(csv.DictReader(f))
    data['uretildi'] = uretildi
    data['son_guncelleme'] = son_guncelleme
    data['tam_tarama'] = tam_tarama
    with open(os.path.join(pub, 'data.json'), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))
    import shutil
    for extra in ('gizlilik.html',):
        src = os.path.join(root, extra)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(pub, extra))
    with open(os.path.join(pub, '.nojekyll'), 'w') as f:
        f.write('')
