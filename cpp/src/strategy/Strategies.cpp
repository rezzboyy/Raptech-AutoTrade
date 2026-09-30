#include "strategy/Strategy.h"

#include "indicators/Indicators.h"

#include <cmath>

namespace {

// Ekstrak deret close dari candle.
QVector<double> closesOf(const QVector<Candle> &c)
{
    QVector<double> out;
    out.reserve(c.size());
    for (const Candle &x : c)
        out << x.c;
    return out;
}

// Rolling std sampel (ddof=1) — dipakai strategi Bollinger (pandas .std() default).
QVector<double> rollStdSample(const QVector<double> &x, int n)
{
    QVector<double> out(x.size(), ind::nan());
    if (n < 2)
        return out;
    for (int i = n - 1; i < x.size(); ++i) {
        double s = 0;
        for (int j = i - n + 1; j <= i; ++j)
            s += x[j];
        const double m = s / n;
        double var = 0;
        for (int j = i - n + 1; j <= i; ++j)
            var += (x[j] - m) * (x[j] - m);
        out[i] = std::sqrt(var / (n - 1));
    }
    return out;
}

// RSI berbasis SMA (rolling mean gain/loss) — dipakai strategi RSI & Multi
// (BERBEDA dari Wilder RSI di pustaka indikator).
QVector<double> smaRsi(const QVector<double> &close, int period)
{
    const int sz = close.size();
    QVector<double> out(sz, ind::nan());
    if (sz < 2)
        return out;
    QVector<double> gain(sz, ind::nan()), loss(sz, ind::nan());
    for (int i = 1; i < sz; ++i) {
        const double d = close[i] - close[i - 1];
        gain[i] = d > 0 ? d : 0.0;
        loss[i] = d < 0 ? -d : 0.0;
    }
    const QVector<double> ag = ind::sma(gain, period);
    const QVector<double> al = ind::sma(loss, period);
    for (int i = 0; i < sz; ++i) {
        if (ind::isNan(ag[i]) || ind::isNan(al[i]))
            continue;
        const double denom = al[i] == 0.0 ? 1e-9 : al[i];
        const double rs = ag[i] / denom;
        out[i] = 100.0 - 100.0 / (1.0 + rs);
    }
    return out;
}

// ---------- Strategi bawaan ----------

class MaCross : public Strategy
{
public:
    QString name() const override { return "ma_cross"; }
    QString generateSignal(const QVector<Candle> &candles) override
    {
        const int fast = int(param("fast_period", 10));
        const int slow = int(param("slow_period", 30));
        if (candles.size() < slow + 2)
            return {};
        const QVector<double> close = closesOf(candles);
        const QVector<double> mf = ind::sma(close, fast);
        const QVector<double> ms = ind::sma(close, slow);
        const int n = close.size();
        const double fp = mf[n - 2], fn = mf[n - 1], sp = ms[n - 2], sn = ms[n - 1];
        if (ind::isNan(fp) || ind::isNan(fn) || ind::isNan(sp) || ind::isNan(sn))
            return {};
        if (fp <= sp && fn > sn)
            return sig::BUY;
        if (fp >= sp && fn < sn)
            return sig::SELL;
        return {};
    }
};

class RsiStrategy : public Strategy
{
public:
    QString name() const override { return "rsi"; }
    QString generateSignal(const QVector<Candle> &candles) override
    {
        const int period = int(param("period", 14));
        const double oversold = param("oversold", 30.0);
        const double overbought = param("overbought", 70.0);
        if (candles.size() < period + 2)
            return {};
        const QVector<double> r = smaRsi(closesOf(candles), period);
        const int n = r.size();
        const double prev = r[n - 2], now = r[n - 1];
        if (ind::isNan(prev) || ind::isNan(now))
            return {};
        if (prev <= oversold && now > oversold)
            return sig::BUY;
        if (prev >= overbought && now < overbought)
            return sig::SELL;
        return {};
    }
};

class Bollinger : public Strategy
{
public:
    QString name() const override { return "bollinger"; }
    QString generateSignal(const QVector<Candle> &candles) override
    {
        const int period = int(param("period", 20));
        const double sd = param("std_dev", 2.0);
        if (candles.size() < period + 2)
            return {};
        const QVector<double> close = closesOf(candles);
        const QVector<double> ma = ind::sma(close, period);
        const QVector<double> st = rollStdSample(close, period);
        const int n = close.size();
        const double prevC = close[n - 2], nowC = close[n - 1];
        if (ind::isNan(ma[n - 2]) || ind::isNan(st[n - 2]) || ind::isNan(ma[n - 1]) || ind::isNan(st[n - 1]))
            return {};
        const double prevL = ma[n - 2] - sd * st[n - 2], nowL = ma[n - 1] - sd * st[n - 1];
        const double prevU = ma[n - 2] + sd * st[n - 2], nowU = ma[n - 1] + sd * st[n - 1];
        if (prevC <= prevL && nowC > nowL)
            return sig::BUY;
        if (prevC >= prevU && nowC < nowU)
            return sig::SELL;
        return {};
    }
};

class MacdStrategy : public Strategy
{
public:
    QString name() const override { return "macd"; }
    QString generateSignal(const QVector<Candle> &candles) override
    {
        const int fast = int(param("fast_ema", 12));
        const int slow = int(param("slow_ema", 26));
        const int signal = int(param("signal_period", 9));
        if (candles.size() < slow + signal + 2)
            return {};
        const ind::MacdResult m = ind::macd(closesOf(candles), fast, slow, signal);
        const int n = m.macd.size();
        const double pm = m.macd[n - 2], nm = m.macd[n - 1];
        const double ps = m.signal[n - 2], ns = m.signal[n - 1];
        if (ind::isNan(pm) || ind::isNan(nm) || ind::isNan(ps) || ind::isNan(ns))
            return {};
        if (pm <= ps && nm > ns)
            return sig::BUY;
        if (pm >= ps && nm < ns)
            return sig::SELL;
        return {};
    }
};

class MultiIndicator : public Strategy
{
public:
    QString name() const override { return "multi_indicator"; }
    QString generateSignal(const QVector<Candle> &candles) override
    {
        const int maFast = int(param("ma_fast", 20));
        const int maSlow = int(param("ma_slow", 50));
        const int rsiP = int(param("rsi_period", 14));
        const double buyLvl = param("rsi_buy_level", 50.0);
        const double sellLvl = param("rsi_sell_level", 50.0);
        const int minBars = std::max(maSlow, rsiP) + 2;
        if (candles.size() < minBars)
            return {};
        const QVector<double> close = closesOf(candles);
        const QVector<double> mf = ind::sma(close, maFast);
        const QVector<double> ms = ind::sma(close, maSlow);
        const QVector<double> r = smaRsi(close, rsiP);
        const int n = close.size();
        const double fastNow = mf[n - 1], slowNow = ms[n - 1];
        const double prevR = r[n - 2], nowR = r[n - 1];
        if (ind::isNan(fastNow) || ind::isNan(slowNow) || ind::isNan(prevR) || ind::isNan(nowR))
            return {};
        const bool bullish = fastNow > slowNow;
        const bool bearish = fastNow < slowNow;
        if (bullish && prevR <= buyLvl && nowR > buyLvl)
            return sig::BUY;
        if (bearish && prevR >= sellLvl && nowR < sellLvl)
            return sig::SELL;
        return {};
    }
};

// Strategi Stochastic Oscillator (port dari strategies/stochastic.py).
// BUY  : %K cross up %D saat prev_k <= oversold.
// SELL : %K cross down %D saat prev_k >= overbought.
// %K = 100*(close - lowest(low,k))/(highest(high,k)-lowest(low,k)); %D = SMA(%K, d).
class StochasticStrategy : public Strategy
{
public:
    QString name() const override { return "stochastic"; }
    QString generateSignal(const QVector<Candle> &candles) override
    {
        const int kP = int(param("k_period", 14));
        const int dP = int(param("d_period", 3));
        const double oversold = param("oversold", 20.0);
        const double overbought = param("overbought", 80.0);
        const int minBars = kP + dP + 2;
        if (candles.size() < minBars)
            return {};
        QVector<double> high, low, close;
        high.reserve(candles.size());
        low.reserve(candles.size());
        close.reserve(candles.size());
        for (const Candle &c : candles) {
            high << c.h;
            low << c.l;
            close << c.c;
        }
        const QVector<double> lowMin = ind::lowest(low, kP);
        const QVector<double> highMax = ind::highest(high, kP);
        const int sz = close.size();
        QVector<double> k(sz, ind::nan());
        for (int i = 0; i < sz; ++i) {
            if (ind::isNan(lowMin[i]) || ind::isNan(highMax[i]))
                continue;
            double denom = highMax[i] - lowMin[i];
            if (denom == 0.0)
                denom = 1e-9;
            k[i] = 100.0 * ((close[i] - lowMin[i]) / denom);
        }
        const QVector<double> d = ind::sma(k, dP);
        const int n = sz;
        const double prevK = k[n - 2], nowK = k[n - 1];
        const double prevD = d[n - 2], nowD = d[n - 1];
        if (ind::isNan(prevK) || ind::isNan(nowK) || ind::isNan(prevD) || ind::isNan(nowD))
            return {};
        if (prevK <= prevD && nowK > nowD && prevK <= oversold)
            return sig::BUY;
        if (prevK >= prevD && nowK < nowD && prevK >= overbought)
            return sig::SELL;
        return {};
    }
};

} // namespace

std::unique_ptr<Strategy> createStrategy(const QString &name, const QHash<QString, double> &params)
{
    std::unique_ptr<Strategy> s;
    if (name == "ma_cross")
        s = std::make_unique<MaCross>();
    else if (name == "rsi")
        s = std::make_unique<RsiStrategy>();
    else if (name == "bollinger")
        s = std::make_unique<Bollinger>();
    else if (name == "macd")
        s = std::make_unique<MacdStrategy>();
    else if (name == "multi_indicator")
        s = std::make_unique<MultiIndicator>();
    else if (name == "stochastic")
        s = std::make_unique<StochasticStrategy>();
    else
        return nullptr;
    s->setParams(params);
    return s;
}
