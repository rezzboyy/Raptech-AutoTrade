"""Paket strategi.

Import eksplisit di sini memastikan strategi bawaan terdaftar meski aplikasi
dibundel jadi EXE (di mana penemuan berbasis file tidak selalu tersedia).
Strategi tambahan (file .py baru di folder ini) tetap ditemukan otomatis saat
mode pengembangan lewat strategy_loader.
"""

from strategies import ma_cross  # noqa: F401
from strategies import rsi  # noqa: F401
from strategies import bollinger  # noqa: F401
from strategies import macd  # noqa: F401
from strategies import stochastic  # noqa: F401
from strategies import multi_indicator  # noqa: F401
