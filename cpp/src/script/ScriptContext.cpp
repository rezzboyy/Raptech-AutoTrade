#include "script/ScriptContext.h"

#include "indicators/Indicators.h"

#include <QDateTime>
#include <QTimeZone>
#include <cmath>

ScriptContext::ScriptContext(QObject *parent) : QObject(parent) {}

QVector<double> ScriptContext::toVec(const QVariantList &l)
{
    QVector<double> out;
    out.reserve(l.size());
    for (const QVariant &v : l)
        out << v.toDouble();
    return out;
}

QVariantList ScriptContext::toList(const QVector<double> &v)
{
    QVariantList out;
    out.reserve(v.size());
    for (double x : v)
        out << x; // NaN dikonversi ke JS NaN
    return out;
}

void ScriptContext::setCandles(const QVector<Candle> &candles)
{
    m_open.clear(); m_high.clear(); m_low.clear(); m_close.clear(); m_volume.clear();
    for (const Candle &c : candles) {
        m_open << c.o;
        m_high << c.h;
        m_low << c.l;
        m_close << c.c;
        m_volume << c.tickVolume;
    }
    // Waktu bar terakhir -> hour/minute/weekday (UTC) + epoch bar & sekarang.
    if (!candles.isEmpty()) {
        QDateTime dt = QDateTime::fromSecsSinceEpoch(candles.last().t, QTimeZone::utc());
        m_hour = dt.time().hour();
        m_minute = dt.time().minute();
        m_weekday = dt.date().dayOfWeek() - 1; // Qt: 1=Senin -> 0=Senin
        m_time = static_cast<qlonglong>(candles.last().t);
    }
    m_now = QDateTime::currentSecsSinceEpoch();
}

void ScriptContext::setRuntime(const RuntimeContext &rt)
{
    m_symbol = rt.symbol;
    const Account &a = rt.account;
    m_balance = a.balance;
    m_equity = a.equity;
    m_margin = a.margin;
    m_freeMargin = a.freeMargin;
    m_floatingProfit = a.profit;
    m_marginLevel = m_margin > 0 ? std::round((m_equity / m_margin) * 10000.0) / 100.0 : 99999.0;

    m_bid = rt.tick.bid;
    m_ask = rt.tick.ask;
    m_point = rt.spec.point;
    m_digits = rt.spec.digits > 0 ? rt.spec.digits : 5;
    m_spread = m_point > 0 ? std::round((m_ask - m_bid) / m_point) : 0;

    auto posToMap = [](const Position &p) {
        QVariantMap m;
        m["ticket"] = static_cast<qlonglong>(p.ticket);
        m["symbol"] = p.symbol;
        m["type"] = p.type;
        m["volume"] = p.volume;
        m["price_open"] = p.priceOpen;
        m["price_current"] = p.priceCurrent;
        m["sl"] = p.sl;
        m["tp"] = p.tp;
        m["profit"] = p.profit;
        m["magic"] = static_cast<qlonglong>(p.magic);
        return m;
    };
    m_positions.clear();
    for (const Position &p : rt.positions)
        m_positions << posToMap(p);
    m_position = rt.positions.isEmpty() ? QVariant() : QVariant(posToMap(rt.positions.first()));
}

// ---- Indikator ----
QVariantList ScriptContext::sma(const QVariantList &src, int n) { return toList(ind::sma(toVec(src), n)); }
QVariantList ScriptContext::ema(const QVariantList &src, int n) { return toList(ind::ema(toVec(src), n)); }
QVariantList ScriptContext::wma(const QVariantList &src, int n) { return toList(ind::wma(toVec(src), n)); }
QVariantList ScriptContext::rsi(const QVariantList &src, int n) { return toList(ind::rsi(toVec(src), n)); }
QVariantList ScriptContext::stdev(const QVariantList &src, int n) { return toList(ind::stdev(toVec(src), n)); }
QVariantList ScriptContext::highest(const QVariantList &src, int n) { return toList(ind::highest(toVec(src), n)); }
QVariantList ScriptContext::lowest(const QVariantList &src, int n) { return toList(ind::lowest(toVec(src), n)); }
QVariantList ScriptContext::atr(int n) { return toList(ind::atr(m_high, m_low, m_close, n)); }

QVariantList ScriptContext::bbands(const QVariantList &src, int n, double mult)
{
    const ind::Band b = ind::bbands(toVec(src), n, mult);
    return {toList(b.upper), toList(b.mid), toList(b.lower)};
}

QVariantList ScriptContext::macd(const QVariantList &src, int fast, int slow, int signal)
{
    const ind::MacdResult m = ind::macd(toVec(src), fast, slow, signal);
    return {toList(m.macd), toList(m.signal), toList(m.hist)};
}

QVariantList ScriptContext::stochastic(int k, int d, int smooth)
{
    const ind::StochResult s = ind::stochastic(m_high, m_low, m_close, k, d, smooth);
    return {toList(s.k), toList(s.d)};
}

QVariantList ScriptContext::adx(int n)
{
    const ind::AdxResult a = ind::adx(m_high, m_low, m_close, n);
    return {toList(a.adx), toList(a.plusDI), toList(a.minusDI)};
}

QVariantList ScriptContext::cci(int n) { return toList(ind::cci(m_high, m_low, m_close, n)); }
QVariantList ScriptContext::vwap(int n) { return toList(ind::vwap(m_high, m_low, m_close, m_volume, n)); }
QVariantList ScriptContext::williams_r(int n) { return toList(ind::williamsR(m_high, m_low, m_close, n)); }
QVariantList ScriptContext::obv() { return toList(ind::obv(m_close, m_volume)); }
QVariantList ScriptContext::mfi(int n) { return toList(ind::mfi(m_high, m_low, m_close, m_volume, n)); }

QVariantList ScriptContext::donchian(int n)
{
    const ind::Band b = ind::donchian(m_high, m_low, n);
    return {toList(b.upper), toList(b.mid), toList(b.lower)};
}

QVariantList ScriptContext::parabolic_sar(double step, double maxStep)
{
    return toList(ind::parabolicSar(m_high, m_low, step, maxStep));
}

QVariantList ScriptContext::supertrend(int n, double mult)
{
    const ind::SuperTrendResult st = ind::supertrend(m_high, m_low, m_close, n, mult);
    QVariantList dir;
    for (int d : st.direction)
        dir << d;
    return {toList(st.line), dir};
}

QVariantList ScriptContext::ichimoku(int tenkan, int kijun, int senkou)
{
    const ind::IchimokuResult i = ind::ichimoku(m_high, m_low, m_close, tenkan, kijun, senkou);
    return {toList(i.tenkan), toList(i.kijun), toList(i.senkouA), toList(i.senkouB), toList(i.chikou)};
}

QVariantMap ScriptContext::pivot_points()
{
    const ind::Pivots p = ind::pivotPoints(m_high, m_low, m_close);
    QVariantMap m;
    if (!p.valid)
        return m;
    m["pivot"] = p.pivot; m["r1"] = p.r1; m["s1"] = p.s1;
    m["r2"] = p.r2; m["s2"] = p.s2; m["r3"] = p.r3; m["s3"] = p.s3;
    return m;
}

bool ScriptContext::crossover(const QVariantList &a, const QVariantList &b)
{
    return ind::crossover(toVec(a), toVec(b));
}
bool ScriptContext::crossunder(const QVariantList &a, const QVariantList &b)
{
    return ind::crossunder(toVec(a), toVec(b));
}

void ScriptContext::log(const QString &msg) { m_logs << msg; }

QStringList ScriptContext::takeLogs()
{
    QStringList out = m_logs;
    m_logs.clear();
    return out;
}

// ---- Order (gaya cBot) ----
QVariantMap ScriptContext::buildOrder(const QString &action, const QVariantMap &opts)
{
    QVariantMap intent;
    intent["action"] = action;

    auto pick = [&](const QString &k1, const QString &k2) -> QVariant {
        if (opts.contains(k1))
            return opts.value(k1);
        if (m_settings.contains(k1))
            return m_settings.value(k1);
        if (!k2.isEmpty()) {
            if (opts.contains(k2))
                return opts.value(k2);
            if (m_settings.contains(k2))
                return m_settings.value(k2);
        }
        return QVariant();
    };

    const QVariant volume = pick("volume", "lot");
    QVariant slPts, tpPts, slAbs, tpAbs;
    if (opts.contains("sl"))
        slAbs = opts.value("sl");
    else if (opts.contains("sl_points"))
        slPts = opts.value("sl_points");
    else
        slPts = pick("sl_points", "sl");
    if (opts.contains("tp"))
        tpAbs = opts.value("tp");
    else if (opts.contains("tp_points"))
        tpPts = opts.value("tp_points");
    else
        tpPts = pick("tp_points", "tp");
    const QVariant risk = pick("risk_per_trade", "risk");
    const QVariant comment = pick("comment", "");

    if (volume.isValid())
        intent["volume"] = volume.toDouble();
    if (slPts.isValid())
        intent["sl_points"] = slPts.toInt();
    if (tpPts.isValid())
        intent["tp_points"] = tpPts.toInt();
    if (slAbs.isValid())
        intent["sl"] = slAbs.toDouble();
    if (tpAbs.isValid())
        intent["tp"] = tpAbs.toDouble();
    if (risk.isValid())
        intent["risk"] = risk.toDouble();
    if (comment.isValid() && !comment.toString().isEmpty())
        intent["comment"] = comment.toString();
    return intent;
}

QVariantMap ScriptContext::buy(const QVariantMap &opts) { return buildOrder(QStringLiteral("BUY"), opts); }
QVariantMap ScriptContext::sell(const QVariantMap &opts) { return buildOrder(QStringLiteral("SELL"), opts); }

long long ScriptContext::ticketOf(const QVariantMap &opts) const
{
    if (opts.contains("ticket"))
        return opts.value("ticket").toLongLong();
    if (opts.contains("position")) {
        const QVariantMap p = opts.value("position").toMap();
        if (p.contains("ticket"))
            return p.value("ticket").toLongLong();
    }
    // Default: posisi aktif.
    if (m_position.isValid())
        return m_position.toMap().value("ticket").toLongLong();
    return 0;
}

QVariant ScriptContext::close_position(const QVariantMap &opts)
{
    const long long t = ticketOf(opts);
    if (t == 0)
        return QVariant();
    QVariantMap m;
    m["action"] = "CLOSE";
    m["ticket"] = static_cast<qlonglong>(t);
    return m;
}

QVariantMap ScriptContext::close_all()
{
    QVariantMap m;
    m["action"] = "CLOSE_ALL";
    return m;
}

QVariant ScriptContext::modify(const QVariantMap &opts)
{
    const long long t = ticketOf(opts);
    if (t == 0)
        return QVariant();
    QVariantMap m;
    m["action"] = "MODIFY";
    m["ticket"] = static_cast<qlonglong>(t);
    if (opts.contains("sl"))
        m["sl"] = opts.value("sl").toDouble();
    if (opts.contains("tp"))
        m["tp"] = opts.value("tp").toDouble();
    return m;
}
