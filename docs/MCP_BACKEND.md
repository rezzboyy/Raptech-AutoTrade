# Backend MCP (MetaTrader 5)

Bot ini dapat terhubung ke MetaTrader 5 lewat **dua backend**:

- **native** — memakai library Python `MetaTrader5` (default). Terikat versi:
  build terminal harus cocok dengan versi paket di PyPI.
- **mcp** — memakai **server MCP bawaan terminal** (`http://127.0.0.1:22346/mcp`).
  Tidak bergantung pada versi library, sehingga tetap jalan walau build terminal
  lebih baru dari paket `MetaTrader5`.

## Mengaktifkan backend MCP

1. Di MetaTrader 5: **Tools → Options → tab MCP** → centang **Enable internal
   server**. Salin **API Key** yang tertera.
2. Buat berkas `mcp_secret.json` di folder project (sudah masuk `.gitignore`):

   ```json
   {
     "mcp_endpoint": "http://127.0.0.1:22346/mcp",
     "mcp_api_key": "TEMPEL_API_KEY_DI_SINI"
   }
   ```

   Alternatif tanpa berkas: set environment variable `MCP_API_KEY` (dan opsional
   `MCP_ENDPOINT`).
3. Pilih backend MCP dengan salah satu cara:
   - Environment variable: `set BACKEND=mcp` sebelum menjalankan bot, atau
   - Simpan lewat konfigurasi (field `backend` = `mcp`).

## Verifikasi cepat (read-only)

```
python tools\verify_mcp.py
```

Skrip ini menguji koneksi + baca akun/simbol/posisi/statistik/chart TANPA
mengirim order. Gunakan sebelum menyalakan auto-trading.

## Beralih kembali ke backend native (fallback)

Bila MCP bermasalah, kembali ke library dengan salah satu:
- Set `BACKEND=native` (atau kosongkan), atau
- Set field `backend` = `native` di konfigurasi.

Tidak ada perubahan kode yang diperlukan untuk beralih backend.

## Catatan penting

- **Trading butuh terminal tersambung broker.** Jika `server_connected=false`
  atau `mcp_trade_allowed=false`, bot menolak mengirim order (fail-safe) dan
  hanya melakukan monitoring.
- **Keamanan:** `mcp_api_key` tidak pernah disimpan ke `config.json` dan tidak
  pernah ditulis utuh ke log (selalu ter-mask). Jangan bagikan `mcp_secret.json`.
- Data candle "sekarang" bisa kosong bila terminal belum tersambung broker
  (data historis mengikuti ketersediaan terminal).
