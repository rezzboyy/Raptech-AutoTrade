#pragma once
#include <QDateTime>
#include <QString>
#include <QStringList>

// Util backend-agnostik (padanan fungsi modul di backends/base.py).
namespace SymbolUtils {

// Tipe pending order yang didukung.
inline const QStringList &pendingOrderTypes()
{
    static const QStringList v{"buy_limit", "sell_limit", "buy_stop", "sell_stop"};
    return v;
}

// Klasifikasi tipe akun: "DEMO" | "REAL" | "CONTEST" | "?".
// Server memuat 'demo'/'trial' -> DEMO (Exness taruh demo di server 'real').
QString classifyAccountType(const QString &typeStr, const QString &server);

// Petakan timeframe internal (mis. "M5") -> string period MCP. Default "M5".
QString mapTimeframeToPeriod(const QString &timeframeStr);

// Menit per timeframe (default 5 bila tak dikenal).
int timeframeMinutes(const QString &timeframeStr);

// Hitung (datetime_from, datetime_to) ISO 8601 untuk mengambil `count` candle.
// to = now (UTC); from mundur menit_per_tf * count * buffer. Menjamin from < to.
QPair<QString, QString> candleTimeRange(const QString &timeframeStr, int count,
                                        const QDateTime &now = QDateTime());

// Variasi nama simbol broker (Exness Standard 'm', Cent 'c', Pro/Raw, dst).
QStringList candidateSymbolVariations(const QString &symbol);

// Cocokkan simbol yang diminta dengan daftar tersedia (suffix/case-insensitive).
// Kembalikan nama tepat di broker, atau QString() bila tak ada.
QString resolveSymbolName(const QString &requested, const QStringList &available);

} // namespace SymbolUtils
