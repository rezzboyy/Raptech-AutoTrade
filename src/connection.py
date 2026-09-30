"""Manajemen koneksi ke terminal MetaTrader 5."""

import time

import MetaTrader5 as mt5

from config.settings import settings
from src.logger import get_logger

logger = get_logger(__name__)

# Kode error IPC MT5 yang biasanya disebabkan beda level hak akses / terminal
# belum siap. Ditangani dengan retry + pesan yang jelas.
_IPC_ERRORS = (-10001, -10004, -10005)  # IPC send failed / IPC init / IPC timeout


class MT5Connection:
    """Membungkus inisialisasi, login, dan shutdown terminal MT5."""

    def __init__(self):
        self.connected = False

    def _initialize(self) -> bool:
        """Inisialisasi terminal dengan beberapa kali percobaan.

        IPC MT5 kadang gagal di percobaan pertama (terminal masih sibuk/loading),
        jadi kita coba ulang beberapa kali sebelum menyerah.
        """
        # timeout eksplisit agar gagal cepat (bukan menggantung sampai 60 dtk default).
        init_kwargs = {"timeout": 15000}
        if settings.path:
            init_kwargs["path"] = settings.path

        last_err = None
        for attempt in range(1, 4):
            if mt5.initialize(**init_kwargs):
                return True
            last_err = mt5.last_error()
            logger.warning(
                "initialize() percobaan %d/3 gagal (error=%s). Mencoba lagi...",
                attempt, last_err,
            )
            try:
                mt5.shutdown()
            except Exception:  # noqa: BLE001
                pass
            time.sleep(1.5)

        code = last_err[0] if isinstance(last_err, (tuple, list)) else None
        if code in _IPC_ERRORS:
            try:
                import MetaTrader5 as _mt5pkg
                pkg_ver = getattr(_mt5pkg, "__version__", "?")
            except Exception:  # noqa: BLE001
                pkg_ver = "?"
            logger.error(
                "Gagal terhubung ke terminal MT5: IPC error %s. Terminal terdeteksi tapi "
                "handshake gagal. Penyebab yang mungkin, urut prioritas: "
                "(1) VERSI TIDAK COCOK — build terminal MT5 lebih baru dari paket Python "
                "MetaTrader5 (terpasang v%s). Cek build di terminal (Help > About) lalu "
                "'pip install --upgrade MetaTrader5'; jika belum ada yang cocok, "
                "nonaktifkan auto-update terminal atau turunkan build terminal. "
                "(2) BEDA level hak akses — jalankan bot & MT5 SAMA-SAMA normal, atau "
                "SAMA-SAMA 'Run as administrator'. "
                "(3) Terminal belum selesai loading / belum login manual. "
                "(4) Isi kolom Path ke terminal64.exe.", last_err, pkg_ver,
            )
        else:
            logger.error(
                "initialize() gagal (error=%s). Pastikan terminal MT5 terbuka & "
                "sudah login. Bila perlu isi kolom Path ke terminal64.exe.", last_err,
            )
        return False

    def connect(self) -> bool:
        """Inisialisasi terminal dan pastikan login ke akun yang benar.

        Strategi:
            1. initialize() (attach ke terminal yang sedang berjalan) dengan retry.
            2. Bila terminal SUDAH login ke akun yang diminta, pakai sesi itu
               langsung (hindari login ulang yang rawan gagal IPC).
            3. Selain itu, lakukan login() eksplisit.

        Returns:
            True jika koneksi + login berhasil, selain itu False.
        """
        if not self._initialize():
            return False

        # Terminal siap. Cek apakah sudah login ke akun yang diminta.
        account = mt5.account_info()
        if account is not None and int(account.login) == int(settings.login):
            logger.info(
                "Terminal sudah login ke akun %s (%s). Memakai sesi yang ada | "
                "Balance=%.2f %s",
                account.login, account.server, account.balance, account.currency,
            )
            self.connected = True
            return True

        # Perlu login eksplisit ke akun yang diminta.
        logger.info("Terminal MT5 terinisialisasi. Mencoba login akun %s...", settings.login)

        authorized = mt5.login(
            login=settings.login,
            password=settings.password,
            server=settings.server,
            timeout=15000,
        )
        if not authorized:
            logger.error(
                "login() gagal untuk akun %s di server '%s' (error=%s). "
                "Periksa Login/Password/Server (perhatikan huruf besar/kecil server).",
                settings.login, settings.server, mt5.last_error(),
            )
            mt5.shutdown()
            return False

        account = mt5.account_info()
        if account is not None:
            logger.info(
                "Terhubung. Akun=%s | Broker=%s | Balance=%.2f %s",
                account.login,
                account.server,
                account.balance,
                account.currency,
            )
        self.connected = True
        return True

    def ensure_symbol(self, symbol: str) -> bool:
        """Pastikan simbol tersedia dan aktif di Market Watch.

        Args:
            symbol: nama simbol, mis. "EURUSD".

        Returns:
            True jika simbol siap dipakai.
        """
        info = mt5.symbol_info(symbol)
        if info is None:
            logger.error("Simbol %s tidak ditemukan di broker.", symbol)
            return False
        if not info.visible:
            if not mt5.symbol_select(symbol, True):
                logger.error("Gagal mengaktifkan simbol %s.", symbol)
                return False
        return True

    def ensure_symbols(self, symbols: list) -> list:
        """Pastikan semua simbol dalam daftar aktif di Market Watch. Kembalikan simbol yang valid."""
        valid = []
        for s in symbols:
            s = str(s).strip()
            if not s:
                continue
            if self.ensure_symbol(s):
                valid.append(s)
        return valid

    def disconnect(self) -> None:
        """Tutup koneksi ke terminal."""
        if self.connected:
            mt5.shutdown()
            self.connected = False
            logger.info("Koneksi MT5 ditutup.")
