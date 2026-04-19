# ResellerHub Fullstack - Sistem Reseller Terintegrasi

Implementasi fullstack berbasis **Python (stdlib) + SQLite + Vanilla JS** untuk kebutuhan PRD website reseller.

## Cakupan fitur

### Reseller
- Login role reseller.
- Melihat dashboard ringkasan produk, order, dan komisi.
- Melihat produk, stok, harga normal vs harga reseller, dan rate komisi.
- Membuat order satuan / borongan.
- Melihat komisi otomatis dari order yang tercatat.
- Mengirim komplain/feedback.
- Melihat update/news produk.

### Admin
- Login role admin.
- Dashboard metrik sistem.
- Melihat dan approve pendaftaran reseller pending.
- Melihat semua order, komisi, komplain.
- Menambah produk baru.
- Memposting news/update.

### Sistem
- Database SQLite persisten (`resellerhub.db`).
- Autentikasi berbasis token sederhana (Bearer token in-memory).
- Pencatatan simulasi notifikasi WhatsApp/Email pada `notifications_log`.
- Menyajikan frontend (`index.html`, `style.css`, `app.js`) langsung dari backend Python.

## Akun demo

- Admin:
  - Email: `admin@resellerhub.id`
  - Password: `admin123`
- Reseller approved:
  - Email: `reseller@resellerhub.id`
  - Password: `reseller123`

## Menjalankan aplikasi

1. Jalankan server:

```bash
python3 server.py
```

2. Buka browser ke:

```text
http://localhost:8080
```

## Catatan implementasi

- Saat admin approve reseller, password default diset ke `reseller123`.
- Integrasi WhatsApp/Email masih berupa **log simulasi** (siap disambungkan ke provider nyata di tahap berikutnya).
