# Düzenli Getirili Fonlar

Son 12 ayda hiç eksi günü olmayan yatırım fonlarını risk seviyesine göre listeleyen, ay ay getirileri ve birikim hesaplayıcısı olan site.

**Yatırım tavsiyesi değildir.** Geçmiş getiri geleceği garanti etmez.

## Nasıl güncellenir

GitHub Actions (`.github/workflows/guncelle.yml` ve `saat.yml`):

- **Her gün 07:00–19:00, saat başı** (`saat.yml` gün içinde açık kalıp her saat başında başlatır; GitHub zamanlayıcısı saat başlarında güvenilir olmadığı için): bugün henüz yeni fiyatı gelmemiş tüm seçili fonlar kontrol edilir; yeni fiyat görülünce veri GitHub'a kaydedilir ve site yayınlanır. Fonun genelde hangi saatte güncellendiği `data/state.json`'a yazılır.
- **Her gün 23:47:** TEFAS'taki ~2.000 menkul kıymet ve borsa yatırım fonu baştan taranır, düzenli fon listesi yeniden seçilir.

Elle çalıştırmak için: Actions → "Fon verilerini güncelle" → Run workflow.

## Dosyalar

- `scripts/ekofin.py` – veri kaynağı (TEFAS verisi, Ekofin üzerinden)
- `scripts/compute.py` – eksi gün, dönem getirileri, seçim
- `scripts/run.py` – gece taraması, gün içi güncelleme, site üretimi
- `scripts/sitegen.py` + `page.html` – site
- `data/` – seçilen fonların fiyatları ve güncelleme saatleri
