#pragma once
#include <QHash>
#include <QString>
#include <QVariantMap>
#include <QVector>
#include <memory>

#include "backend/Models.h"
#include "strategy/Command.h"

// Sinyal yang dikenali loop trading.
namespace sig {
inline const QString BUY = QStringLiteral("BUY");
inline const QString SELL = QStringLiteral("SELL");
} // namespace sig

// Antarmuka dasar strategi (padanan strategies/base.py).
// - Strategi bawaan meng-override generateSignal (BUY/SELL/"").
// - Strategi skrip meng-override onBar (bisa mengembalikan banyak perintah).
class Strategy
{
public:
    virtual ~Strategy() = default;
    virtual QString name() const = 0;

    // Strategi bawaan: kembalikan sig::BUY / sig::SELL / QString().
    virtual QString generateSignal(const QVector<Candle> &candles)
    {
        Q_UNUSED(candles);
        return {};
    }

    // Hasilkan daftar perintah. Default: bungkus generateSignal().
    virtual QVector<Command> onBar(const QVector<Candle> &candles, const RuntimeContext &rt)
    {
        Q_UNUSED(rt);
        QVector<Command> out;
        const QString s = generateSignal(candles);
        if (s == sig::BUY || s == sig::SELL) {
            Command c;
            c.action = s;
            out << c;
        }
        return out;
    }

    // SETTINGS skrip (Mode Programmer). Strategi bawaan: kosong.
    // Dipakai engine untuk fitur lanjutan (filter waktu/sesi, cooldown, ATR SL/TP, dll).
    virtual QVariantMap scriptSettings() const { return {}; }

    void setParams(const QHash<QString, double> &p) { m_params = p; }
    double param(const QString &key, double def) const { return m_params.value(key, def); }
    bool hasParam(const QString &key) const { return m_params.contains(key); }

protected:
    QHash<QString, double> m_params;
};

// Factory: buat strategi berdasarkan nama + parameter. Nullptr bila nama tak dikenal.
std::unique_ptr<Strategy> createStrategy(const QString &name,
                                         const QHash<QString, double> &params = {});
