# Strict Engineering Rules & Standards — Raptech Autotrade CLI

> 📌 **Navigasi Dokumentasi**:  
> [📋 Task & Roadmap](task.md) • [📐 System Design](design.md) • [🛡️ Engineering Rules](rules.md) • [🚀 Production Guide](production.md) • [🤖 Agents Playbook](agents.md)

Dokumen ini mendefinisikan aturan rekayasa perangkat lunak, standar keamanan modal, batasan konkurensi, dan penjaga integritas data (*guardrails*) yang **WAJIB** dipatuhi oleh seluruh pengembang dan agen AI saat berkontribusi pada proyek **Raptech Autotrade CLI**. Seluruh implementasi harus mengacu pada arsitektur [design.md](design.md) dan dijadwalkan pada [task.md](task.md).

---

## 1. Aturan Keamanan Modal & Finansial (Capital Protection Invariants)

Trading otomatis melibatkan risiko kerugian dana riil pengguna. Oleh karena itu, aturan keamanan berikut bersifat **INVARIANT MUTLAK** (tidak boleh dilanggar dalam kondisi apa pun):

1. **Validasi Lot Sebelum Eksekusi**:
   - Seluruh order **WAJIB** divalidasi terhadap spesifikasi broker (`volume_min`, `volume_max`, `volume_step`).
   - Jangan pernah mengirimkan volume di bawah lot minimum atau pecahan lot yang tidak kelipatan `volume_step`.
2. **Kewajiban Proteksi Stop Loss (Hard / Virtual)**:
   - Setiap posisi yang dibuka oleh bot **HARUS** memiliki Stop Loss (baik berupa hard SL di server MT5 maupun SL virtual di `RiskManager`).
   - Dilarang membuka posisi "telanjang" (*naked position*) tanpa batas risiko kerugian terdefinisi.
3. **Maksimum Posisi Terbuka (Max Exposure Limit)**:
   - Bot **DILARANG** membuka posisi baru jika jumlah order aktif telah mencapai `max_open_positions` pada konfigurasi profil yang bersangkutan.
4. **Circuit Breaker (Emergency Lockout)**:
   - Jika kerugian harian mencapai `max_daily_loss` atau drawdown akun mencapai batas `max_drawdown_percent`, bot **HARUS** seketika menghentikan auto-trading dan menolak sinyal entry baru sampai reset manual oleh pengguna.
5. **Fail-Safe Hotkey Emergency Close**:
   - Fungsi penutupan darurat (`[C]` pada TUI atau `python main.py close --all` pada CLI) harus memiliki prioritas eksekusi tertinggi, memotong antrean order biasa (*queue preemption*).

---

## 2. Aturan Thread-Safety & Konektivitas MetaTrader 5

1. **Pantangan Pemanggilan Paralel MT5**:
   - Library `MetaTrader5` resmi Python **TIDAK THREAD-SAFE**.
   - **DILARANG KERAS** memanggil fungsi `mt5.initialize()`, `mt5.order_send()`, `mt5.positions_get()`, atau `mt5.copy_rates_from_pos()` dari thread yang berbeda-beda secara serentak.
2. **Dedicated Backend Worker Pattern**:
   - Semua pemanggilan fungsi ke `MetaTrader5` **WAJIB** dieksekusi di dalam satu *dedicated worker thread* khusus.
   - Lapisan antarmuka (asyncio / Textual / Typer) berkomunikasi dengan worker melalui antrean pesan thread-safe (`queue.Queue` atau `asyncio.to_thread`).
3. **Penanganan Reconnect Otomatis (Resilience)**:
   - Jika koneksi ke broker terputus (*heartbeat lost*), bot harus melakukan *exponential backoff retry* (1s, 2s, 4s, 8s, maks 30s) tanpa membuat program crash atau membekukan antarmuka pengguna.

---

## 3. Aturan Asynchronous & Antarmuka Terminal (Textual / Rich)

1. **Never Block the Event Loop**:
   - Textual TUI dan Ultra-Light Live UI berjalan di atas event loop `asyncio`.
   - **DILARANG KERAS** memanggil operasi sinkron pemblokir di dalam coroutine utama, seperti:
     - `time.sleep()` (gunakan `await asyncio.sleep()`)
     - I/O file sinkron lambat
     - Pemanggilan jaringan HTTP sinkron (gunakan `aiohttp` / `httpx`)
     - Pemanggilan MT5 IPC langsung (gunakan `await asyncio.to_thread(worker_call)`)
2. **Nol Dependensi Desktop GUI (Zero Qt / PySide)**:
   - Repositori ini adalah proyek **CLI & Terminal UI murni**.
   - **DILARANG MENGIMPOR** `PySide6`, `PyQt5`, `shiboken6`, `tkinter`, atau pustaka GUI desktop lainnya.
   - Seluruh interaksi visual hanya menggunakan `Rich` dan `Textual`.
3. **Pembersihan Terminal Saat Shutdown (Graceful Exit)**:
   - Saat bot dihentikan melalui hotkey `[Q]`, sinyal `SIGINT` (`Ctrl+C`), atau perintah CLI, aplikasi harus:
     - Menghentikan loop auto-trading.
     - Menyelesaikan pencatatan jurnal transaksi ke disk.
     - Menutup koneksi MT5 / MCP secara rapi (`backend.disconnect()`).
     - Mengembalikan mode terminal ke state normal (kursor terlihat, buffer alternate ditutup).

---

## 4. Aturan Integritas Data & Penyimpanan Rahasia

1. **Zero Data Loss di Folder `data/`**:
   - Direktori `data/` menyimpan profil akun (`data/profiles/`), riwayat trade (`data/history/`), log audit, dan pengaturan keamanan.
   - **DILARANG KERAS** menghapus, memformat, atau menimpa folder `data/` dalam skrip build atau clean.
2. **Atomic Configuration Write**:
   - Seluruh operasi penulisan konfigurasi (`config.json`, profil akun) **WAJIB** menggunakan *atomic file write* (tulis ke file `.tmp` terlebih dahulu, lalu lakukan `os.replace` ke nama target) guna mencegah korupsi file saat listrik padam.
3. **Perlindungan Kredensial & Kunci API**:
   - Password akun MT5 dan API Key MCP **TIDAK BOLEH** disimpan dalam bentuk plain-text di repositori atau log console.
   - Enkripsi kredensial menggunakan modul `SecureStore` (kombinasi SHA-256 + keystream CTR dengan master key mesin lokal `.secret_key`).
   - Setiap output log terminal harus menyamarkan token/password (`mask_token`).

---

## 5. Standar Kode Python & Lingkungan Windows

1. **Header Kompatibilitas Tipe**:
   - Setiap file Python baru atau modifikasi **WAJIB** menyertakan deklarasi masa depan di baris pertama:
     ```python
     from __future__ import annotations
     ```
2. **Console Code Page UTF-8 di Windows**:
   - Windows Console secara default menggunakan CP437 atau CP1252 yang dapat merusak simbol Unicode UI (seperti `●`, `⚡`, `📈`, `🛡️`).
   - Di `main.py`, standar stream dan Windows Code Page **WAJIB** diset ke UTF-8 (CP 65001) sebelum library UI dimuat:
     ```python
     if sys.platform == "win32":
         import ctypes
         ctypes.windll.kernel32.SetConsoleOutputCP(65001)
         ctypes.windll.kernel32.SetConsoleCP(65001)
     ```
3. **Pengujian Sebelum Menyatakan Selesai (Rigorous Testing)**:
   - Setiap modifikasi pada engine trading atau logika order **WAJIB** diverifikasi menggunakan unit test `pytest tests/`.
   - Kode dilarang memiliki syntax error, import error, atau regresi logika.
