#pragma once
#include <QObject>
#include <QVariant>
#include <QVariantList>
#include <QVariantMap>
#include <QVector>

#include "backend/Models.h"
#include "strategy/Command.h"

// Objek `ctx` yang diekspos ke skrip JavaScript (QJSEngine) — padanan
// ScriptContext di strategies/script_runtime.py. Menyediakan data harga,
// indikator, konteks akun/posisi, dan perintah order gaya cBot.
class ScriptContext : public QObject
{
    Q_OBJECT
    // Deret harga (lama -> baru).
    Q_PROPERTY(QVariantList open READ open CONSTANT)
    Q_PROPERTY(QVariantList high READ high CONSTANT)
    Q_PROPERTY(QVariantList low READ low CONSTANT)
    Q_PROPERTY(QVariantList close READ close CONSTANT)
    Q_PROPERTY(QVariantList volume READ volume CONSTANT)
    // Parameter strategi & pengaturan skrip.
    Q_PROPERTY(QVariantMap params MEMBER m_params CONSTANT)
    // Konteks live.
    Q_PROPERTY(QString symbol MEMBER m_symbol CONSTANT)
    Q_PROPERTY(double bid MEMBER m_bid CONSTANT)
    Q_PROPERTY(double ask MEMBER m_ask CONSTANT)
    Q_PROPERTY(double spread MEMBER m_spread CONSTANT)
    Q_PROPERTY(double point MEMBER m_point CONSTANT)
    Q_PROPERTY(int digits MEMBER m_digits CONSTANT)
    Q_PROPERTY(double balance MEMBER m_balance CONSTANT)
    Q_PROPERTY(double equity MEMBER m_equity CONSTANT)
    Q_PROPERTY(double margin MEMBER m_margin CONSTANT)
    Q_PROPERTY(double freeMargin MEMBER m_freeMargin CONSTANT)
    Q_PROPERTY(double marginLevel MEMBER m_marginLevel CONSTANT)
    Q_PROPERTY(double floatingProfit MEMBER m_floatingProfit CONSTANT)
    Q_PROPERTY(double unrealizedProfit MEMBER m_floatingProfit CONSTANT)
    Q_PROPERTY(int hour MEMBER m_hour CONSTANT)
    Q_PROPERTY(int minute MEMBER m_minute CONSTANT)
    Q_PROPERTY(int weekday MEMBER m_weekday CONSTANT)
    Q_PROPERTY(qlonglong time MEMBER m_time CONSTANT)   // waktu bar terakhir (epoch dtk UTC)
    Q_PROPERTY(qlonglong now MEMBER m_now CONSTANT)     // waktu sekarang (epoch dtk UTC)
    Q_PROPERTY(QVariantMap settings MEMBER m_settings CONSTANT)
    Q_PROPERTY(QVariant position MEMBER m_position CONSTANT)
    Q_PROPERTY(QVariantList positions MEMBER m_positions CONSTANT)

public:
    explicit ScriptContext(QObject *parent = nullptr);

    // Isi data per bar (dipanggil engine sebelum on_bar).
    void setCandles(const QVector<Candle> &candles);
    void setRuntime(const RuntimeContext &rt);
    void setParams(const QVariantMap &p) { m_params = p; }
    void setSettings(const QVariantMap &s) { m_settings = s; }

    QVariantList open() const { return toList(m_open); }
    QVariantList high() const { return toList(m_high); }
    QVariantList low() const { return toList(m_low); }
    QVariantList close() const { return toList(m_close); }
    QVariantList volume() const { return toList(m_volume); }

    // ----- Indikator -----
    Q_INVOKABLE QVariantList sma(const QVariantList &src, int n);
    Q_INVOKABLE QVariantList ema(const QVariantList &src, int n);
    Q_INVOKABLE QVariantList wma(const QVariantList &src, int n);
    Q_INVOKABLE QVariantList rsi(const QVariantList &src, int n);
    Q_INVOKABLE QVariantList stdev(const QVariantList &src, int n);
    Q_INVOKABLE QVariantList highest(const QVariantList &src, int n);
    Q_INVOKABLE QVariantList lowest(const QVariantList &src, int n);
    Q_INVOKABLE QVariantList atr(int n);
    Q_INVOKABLE QVariantList bbands(const QVariantList &src, int n, double mult);
    Q_INVOKABLE QVariantList macd(const QVariantList &src, int fast = 12, int slow = 26, int signal = 9);
    Q_INVOKABLE QVariantList stochastic(int k = 14, int d = 3, int smooth = 3);
    Q_INVOKABLE QVariantList adx(int n = 14);
    Q_INVOKABLE QVariantList cci(int n = 20);
    Q_INVOKABLE QVariantList vwap(int n = 14);
    Q_INVOKABLE QVariantList williams_r(int n = 14);
    Q_INVOKABLE QVariantList obv();
    Q_INVOKABLE QVariantList mfi(int n = 14);
    Q_INVOKABLE QVariantList donchian(int n = 20);
    Q_INVOKABLE QVariantList parabolic_sar(double step = 0.02, double maxStep = 0.2);
    Q_INVOKABLE QVariantList supertrend(int n = 10, double mult = 3.0);
    Q_INVOKABLE QVariantList ichimoku(int tenkan = 9, int kijun = 26, int senkou = 52);
    Q_INVOKABLE QVariantMap pivot_points();
    Q_INVOKABLE bool crossover(const QVariantList &a, const QVariantList &b);
    Q_INVOKABLE bool crossunder(const QVariantList &a, const QVariantList &b);

    // ----- Util -----
    Q_INVOKABLE void log(const QString &msg);

    // ----- Perintah order (gaya cBot) -----
    Q_INVOKABLE QVariantMap buy(const QVariantMap &opts = {});
    Q_INVOKABLE QVariantMap sell(const QVariantMap &opts = {});
    Q_INVOKABLE QVariant close_position(const QVariantMap &opts = {});
    Q_INVOKABLE QVariantMap close_all();
    Q_INVOKABLE QVariant modify(const QVariantMap &opts = {});

    // Ambil pesan log yang dikumpulkan (untuk jurnal/UI).
    QStringList takeLogs();

private:
    static QVector<double> toVec(const QVariantList &l);
    static QVariantList toList(const QVector<double> &v);
    QVariantMap buildOrder(const QString &action, const QVariantMap &opts);
    long long ticketOf(const QVariantMap &opts) const;

    QVector<double> m_open, m_high, m_low, m_close, m_volume;
    QVariantMap m_params;
    QVariantMap m_settings;
    QString m_symbol;
    double m_bid = 0, m_ask = 0, m_spread = 0, m_point = 0;
    int m_digits = 5;
    double m_balance = 0, m_equity = 0, m_margin = 0, m_freeMargin = 0;
    double m_marginLevel = 99999.0, m_floatingProfit = 0;
    int m_hour = 0, m_minute = 0, m_weekday = 0;
    qlonglong m_time = 0, m_now = 0;
    QVariant m_position;      // QVariantMap posisi aktif atau invalid
    QVariantList m_positions; // daftar posisi (QVariantMap)
    QStringList m_logs;
};
