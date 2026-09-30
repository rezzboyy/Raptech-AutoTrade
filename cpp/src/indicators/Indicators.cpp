#include "indicators/Indicators.h"

#include <algorithm>

namespace ind {
namespace {

int len(const QVector<double> &v) { return v.size(); }

// diff: out[0]=NaN; out[i]=x[i]-x[i-1].
QVector<double> diff(const QVector<double> &x)
{
    QVector<double> out(x.size(), nan());
    for (int i = 1; i < x.size(); ++i)
        out[i] = x[i] - x[i - 1];
    return out;
}

// Rolling mean (min_periods=n; window ber-NaN -> NaN).
QVector<double> rollMean(const QVector<double> &x, int n)
{
    QVector<double> out(x.size(), nan());
    if (n < 1)
        return out;
    for (int i = n - 1; i < x.size(); ++i) {
        double s = 0;
        bool ok = true;
        for (int j = i - n + 1; j <= i; ++j) {
            if (isNan(x[j])) { ok = false; break; }
            s += x[j];
        }
        if (ok)
            out[i] = s / n;
    }
    return out;
}

// Rolling std populasi (ddof=0).
QVector<double> rollStd(const QVector<double> &x, int n)
{
    QVector<double> out(x.size(), nan());
    if (n < 1)
        return out;
    for (int i = n - 1; i < x.size(); ++i) {
        double s = 0;
        bool ok = true;
        for (int j = i - n + 1; j <= i; ++j) {
            if (isNan(x[j])) { ok = false; break; }
            s += x[j];
        }
        if (!ok)
            continue;
        const double m = s / n;
        double var = 0;
        for (int j = i - n + 1; j <= i; ++j)
            var += (x[j] - m) * (x[j] - m);
        out[i] = std::sqrt(var / n);
    }
    return out;
}

QVector<double> rollMax(const QVector<double> &x, int n)
{
    QVector<double> out(x.size(), nan());
    for (int i = n - 1; i < x.size(); ++i) {
        double m = -std::numeric_limits<double>::infinity();
        bool ok = true;
        for (int j = i - n + 1; j <= i; ++j) {
            if (isNan(x[j])) { ok = false; break; }
            m = std::max(m, x[j]);
        }
        if (ok)
            out[i] = m;
    }
    return out;
}

QVector<double> rollMin(const QVector<double> &x, int n)
{
    QVector<double> out(x.size(), nan());
    for (int i = n - 1; i < x.size(); ++i) {
        double m = std::numeric_limits<double>::infinity();
        bool ok = true;
        for (int j = i - n + 1; j <= i; ++j) {
            if (isNan(x[j])) { ok = false; break; }
            m = std::min(m, x[j]);
        }
        if (ok)
            out[i] = m;
    }
    return out;
}

QVector<double> rollSum(const QVector<double> &x, int n)
{
    QVector<double> out(x.size(), nan());
    for (int i = n - 1; i < x.size(); ++i) {
        double s = 0;
        bool ok = true;
        for (int j = i - n + 1; j <= i; ++j) {
            if (isNan(x[j])) { ok = false; break; }
            s += x[j];
        }
        if (ok)
            out[i] = s;
    }
    return out;
}

// ewm adjust=False, seed x[0] (asumsi x[0] tak NaN).
QVector<double> ewmSeed(const QVector<double> &x, double alpha)
{
    QVector<double> out(x.size(), nan());
    if (x.isEmpty())
        return out;
    out[0] = x[0];
    for (int i = 1; i < x.size(); ++i)
        out[i] = out[i - 1] + alpha * (x[i] - out[i - 1]);
    return out;
}

// ewm adjust=False melewati NaN di depan; seed pada nilai valid pertama.
QVector<double> ewmSkipLeadingNan(const QVector<double> &x, double alpha)
{
    QVector<double> out(x.size(), nan());
    int j = 0;
    while (j < x.size() && isNan(x[j]))
        ++j;
    if (j >= x.size())
        return out;
    out[j] = x[j];
    for (int i = j + 1; i < x.size(); ++i) {
        if (isNan(x[i]))
            out[i] = out[i - 1];
        else
            out[i] = out[i - 1] + alpha * (x[i] - out[i - 1]);
    }
    return out;
}

} // namespace

QVector<double> sma(const QVector<double> &src, int n) { return rollMean(src, n); }

QVector<double> ema(const QVector<double> &src, int n)
{
    return ewmSeed(src, 2.0 / (n + 1.0));
}

QVector<double> stdev(const QVector<double> &src, int n) { return rollStd(src, n); }

QVector<double> wma(const QVector<double> &src, int n)
{
    QVector<double> out(src.size(), nan());
    if (n < 1)
        return out;
    const double wsum = n * (n + 1) / 2.0;
    for (int i = n - 1; i < src.size(); ++i) {
        double total = 0;
        bool ok = true;
        for (int k = 0; k < n; ++k) {
            const double val = src[i - n + 1 + k];
            if (isNan(val)) { ok = false; break; }
            total += val * (k + 1);
        }
        if (ok)
            out[i] = total / wsum;
    }
    return out;
}

QVector<double> rsi(const QVector<double> &src, int n)
{
    const int sz = src.size();
    QVector<double> out(sz, nan());
    if (sz == 0)
        return out;
    const QVector<double> d = diff(src);
    QVector<double> gain(sz, nan()), loss(sz, nan());
    for (int i = 0; i < sz; ++i) {
        if (isNan(d[i]))
            continue;
        gain[i] = d[i] > 0 ? d[i] : 0.0;
        loss[i] = d[i] < 0 ? -d[i] : 0.0;
    }
    const double alpha = 1.0 / n;
    const QVector<double> g = ewmSkipLeadingNan(gain, alpha);
    const QVector<double> l = ewmSkipLeadingNan(loss, alpha);
    for (int i = 0; i < sz; ++i) {
        double v;
        if (isNan(g[i]) || isNan(l[i])) {
            v = nan();
        } else if (l[i] == 0.0 && g[i] == 0.0) {
            v = 50.0;
        } else if (l[i] == 0.0) {
            v = 100.0;
        } else {
            const double rs = g[i] / l[i];
            v = 100.0 - 100.0 / (1.0 + rs);
        }
        out[i] = isNan(v) ? 50.0 : v; // fillna(50)
    }
    return out;
}

QVector<double> atr(const QVector<double> &h, const QVector<double> &l,
                    const QVector<double> &c, int n)
{
    const int sz = h.size();
    QVector<double> tr(sz, nan());
    for (int i = 0; i < sz; ++i) {
        double best = h[i] - l[i];
        if (i >= 1) {
            best = std::max(best, std::abs(h[i] - c[i - 1]));
            best = std::max(best, std::abs(l[i] - c[i - 1]));
        }
        tr[i] = best;
    }
    return ewmSeed(tr, 1.0 / n);
}

QVector<double> highest(const QVector<double> &src, int n) { return rollMax(src, n); }
QVector<double> lowest(const QVector<double> &src, int n) { return rollMin(src, n); }

Band bbands(const QVector<double> &src, int n, double mult)
{
    Band b;
    const QVector<double> mid = rollMean(src, n);
    const QVector<double> sd = rollStd(src, n);
    b.mid = mid;
    b.upper.resize(src.size());
    b.lower.resize(src.size());
    for (int i = 0; i < src.size(); ++i) {
        if (isNan(mid[i]) || isNan(sd[i])) {
            b.upper[i] = nan();
            b.lower[i] = nan();
        } else {
            b.upper[i] = mid[i] + mult * sd[i];
            b.lower[i] = mid[i] - mult * sd[i];
        }
    }
    return b;
}

MacdResult macd(const QVector<double> &src, int fast, int slow, int signal)
{
    MacdResult r;
    const QVector<double> ef = ema(src, fast);
    const QVector<double> es = ema(src, slow);
    r.macd.resize(src.size());
    for (int i = 0; i < src.size(); ++i)
        r.macd[i] = ef[i] - es[i];
    r.signal = ema(r.macd, signal);
    r.hist.resize(src.size());
    for (int i = 0; i < src.size(); ++i)
        r.hist[i] = r.macd[i] - r.signal[i];
    return r;
}

StochResult stochastic(const QVector<double> &h, const QVector<double> &l,
                       const QVector<double> &c, int k, int d, int smooth)
{
    StochResult r;
    const QVector<double> ll = rollMin(l, k);
    const QVector<double> hh = rollMax(h, k);
    QVector<double> rawK(c.size(), nan());
    for (int i = 0; i < c.size(); ++i) {
        if (isNan(ll[i]) || isNan(hh[i]))
            continue;
        const double rng = hh[i] - ll[i];
        rawK[i] = rng != 0.0 ? 100.0 * (c[i] - ll[i]) / rng : 50.0;
    }
    r.k = rollMean(rawK, smooth);
    r.d = rollMean(r.k, d);
    return r;
}

AdxResult adx(const QVector<double> &h, const QVector<double> &l,
              const QVector<double> &c, int n)
{
    AdxResult r;
    const int sz = h.size();
    const QVector<double> up = diff(h);
    QVector<double> downv(sz, nan());
    const QVector<double> dl = diff(l);
    for (int i = 0; i < sz; ++i)
        if (!isNan(dl[i]))
            downv[i] = -dl[i];

    QVector<double> plusDm(sz, nan()), minusDm(sz, nan());
    for (int i = 0; i < sz; ++i) {
        if (isNan(up[i]) || isNan(downv[i]))
            continue; // tetap NaN (padanan 0.0*NaN)
        plusDm[i] = (up[i] > downv[i] && up[i] > 0) ? up[i] : 0.0;
        minusDm[i] = (downv[i] > up[i] && downv[i] > 0) ? downv[i] : 0.0;
    }
    // TR (tr[0] valid).
    QVector<double> tr(sz, nan());
    for (int i = 0; i < sz; ++i) {
        double best = h[i] - l[i];
        if (i >= 1) {
            best = std::max(best, std::abs(h[i] - c[i - 1]));
            best = std::max(best, std::abs(l[i] - c[i - 1]));
        }
        tr[i] = best;
    }
    const double alpha = 1.0 / n;
    const QVector<double> atr_ = ewmSeed(tr, alpha);
    const QVector<double> pdm = ewmSkipLeadingNan(plusDm, alpha);
    const QVector<double> mdm = ewmSkipLeadingNan(minusDm, alpha);

    r.plusDI.resize(sz);
    r.minusDI.resize(sz);
    QVector<double> dx(sz, nan());
    for (int i = 0; i < sz; ++i) {
        if (isNan(pdm[i]) || isNan(atr_[i]) || atr_[i] == 0.0)
            r.plusDI[i] = nan();
        else
            r.plusDI[i] = 100.0 * pdm[i] / atr_[i];
        if (isNan(mdm[i]) || isNan(atr_[i]) || atr_[i] == 0.0)
            r.minusDI[i] = nan();
        else
            r.minusDI[i] = 100.0 * mdm[i] / atr_[i];

        if (!isNan(r.plusDI[i]) && !isNan(r.minusDI[i])) {
            const double diSum = r.plusDI[i] + r.minusDI[i];
            dx[i] = diSum != 0.0
                        ? 100.0 * std::abs(r.plusDI[i] - r.minusDI[i]) / diSum
                        : 0.0;
        }
    }
    r.adx = ewmSkipLeadingNan(dx, alpha);
    return r;
}

QVector<double> cci(const QVector<double> &h, const QVector<double> &l,
                    const QVector<double> &c, int n)
{
    const int sz = h.size();
    QVector<double> tp(sz);
    for (int i = 0; i < sz; ++i)
        tp[i] = (h[i] + l[i] + c[i]) / 3.0;
    const QVector<double> ma = rollMean(tp, n);
    QVector<double> out(sz, nan());
    for (int i = n - 1; i < sz; ++i) {
        if (isNan(ma[i]))
            continue;
        double mad = 0;
        for (int j = i - n + 1; j <= i; ++j)
            mad += std::abs(tp[j] - ma[i]);
        mad /= n;
        out[i] = mad != 0.0 ? (tp[i] - ma[i]) / (0.015 * mad) : 0.0;
    }
    return out;
}

QVector<double> vwap(const QVector<double> &h, const QVector<double> &l,
                     const QVector<double> &c, const QVector<double> &v, int n)
{
    const int sz = h.size();
    QVector<double> pvv(sz);
    for (int i = 0; i < sz; ++i)
        pvv[i] = ((h[i] + l[i] + c[i]) / 3.0) * v[i];
    const QVector<double> pv = rollSum(pvv, n);
    const QVector<double> vv = rollSum(v, n);
    QVector<double> out(sz, nan());
    for (int i = 0; i < sz; ++i)
        if (!isNan(pv[i]) && !isNan(vv[i]) && vv[i] != 0.0)
            out[i] = pv[i] / vv[i];
    return out;
}

QVector<double> williamsR(const QVector<double> &h, const QVector<double> &l,
                          const QVector<double> &c, int n)
{
    const int sz = h.size();
    const QVector<double> hh = rollMax(h, n);
    const QVector<double> ll = rollMin(l, n);
    QVector<double> out(sz, nan());
    for (int i = 0; i < sz; ++i) {
        if (isNan(hh[i]) || isNan(ll[i]))
            continue;
        const double rng = hh[i] - ll[i];
        out[i] = rng != 0.0 ? -100.0 * (hh[i] - c[i]) / rng : -50.0;
    }
    return out;
}

QVector<double> obv(const QVector<double> &c, const QVector<double> &v)
{
    const int sz = c.size();
    QVector<double> out(sz, nan());
    const QVector<double> d = diff(c);
    double cum = 0;
    for (int i = 0; i < sz; ++i) {
        double dir = 0.0;
        if (!isNan(d[i]))
            dir = d[i] > 0 ? 1.0 : (d[i] < 0 ? -1.0 : 0.0);
        cum += dir * v[i];
        out[i] = cum;
    }
    return out;
}

QVector<double> mfi(const QVector<double> &h, const QVector<double> &l,
                    const QVector<double> &c, const QVector<double> &v, int n)
{
    const int sz = h.size();
    QVector<double> tp(sz), rmf(sz);
    for (int i = 0; i < sz; ++i) {
        tp[i] = (h[i] + l[i] + c[i]) / 3.0;
        rmf[i] = tp[i] * v[i];
    }
    const QVector<double> d = diff(tp);
    QVector<double> posF(sz, 0.0), negF(sz, 0.0);
    for (int i = 0; i < sz; ++i) {
        if (!isNan(d[i]) && d[i] > 0)
            posF[i] = rmf[i];
        if (!isNan(d[i]) && d[i] < 0)
            negF[i] = rmf[i];
    }
    const QVector<double> pos = rollSum(posF, n);
    const QVector<double> neg = rollSum(negF, n);
    QVector<double> out(sz, nan());
    for (int i = 0; i < sz; ++i) {
        if (isNan(pos[i]) || isNan(neg[i]))
            continue;
        if (neg[i] == 0.0 && pos[i] == 0.0)
            out[i] = 50.0;
        else if (neg[i] == 0.0)
            out[i] = 100.0;
        else {
            const double ratio = pos[i] / neg[i];
            out[i] = 100.0 - 100.0 / (1.0 + ratio);
        }
    }
    return out;
}

Band donchian(const QVector<double> &h, const QVector<double> &l, int n)
{
    Band b;
    b.upper = rollMax(h, n);
    b.lower = rollMin(l, n);
    b.mid.resize(h.size());
    for (int i = 0; i < h.size(); ++i) {
        if (isNan(b.upper[i]) || isNan(b.lower[i]))
            b.mid[i] = nan();
        else
            b.mid[i] = (b.upper[i] + b.lower[i]) / 2.0;
    }
    return b;
}

QVector<double> parabolicSar(const QVector<double> &high, const QVector<double> &low,
                             double step, double maxStep)
{
    const int n = high.size();
    QVector<double> sar(n, nan());
    if (n < 2)
        return sar;
    bool uptrend = high[1] >= high[0];
    double af = step;
    double ep = uptrend ? high[1] : low[1];
    sar[1] = uptrend ? low[0] : high[0];
    for (int i = 2; i < n; ++i) {
        const double prev = sar[i - 1];
        double cur = prev + af * (ep - prev);
        if (uptrend) {
            cur = std::min({cur, low[i - 1], low[i - 2]});
            if (low[i] < cur) {
                uptrend = false;
                cur = ep;
                ep = low[i];
                af = step;
            } else if (high[i] > ep) {
                ep = high[i];
                af = std::min(af + step, maxStep);
            }
        } else {
            cur = std::max({cur, high[i - 1], high[i - 2]});
            if (high[i] > cur) {
                uptrend = true;
                cur = ep;
                ep = high[i];
                af = step;
            } else if (low[i] < ep) {
                ep = low[i];
                af = std::min(af + step, maxStep);
            }
        }
        sar[i] = cur;
    }
    return sar;
}

SuperTrendResult supertrend(const QVector<double> &h, const QVector<double> &l,
                            const QVector<double> &c, int n, double mult)
{
    SuperTrendResult r;
    const int sz = c.size();
    r.line.fill(nan(), sz);
    r.direction.fill(0, sz);
    if (sz == 0)
        return r;

    QVector<double> tr(sz, nan());
    for (int i = 0; i < sz; ++i) {
        double best = h[i] - l[i];
        if (i >= 1) {
            best = std::max(best, std::abs(h[i] - c[i - 1]));
            best = std::max(best, std::abs(l[i] - c[i - 1]));
        }
        tr[i] = best;
    }
    const QVector<double> atr_ = ewmSeed(tr, 1.0 / n);
    QVector<double> upper(sz), lower(sz), finalUpper(sz, nan()), finalLower(sz, nan());
    for (int i = 0; i < sz; ++i) {
        const double hl2 = (h[i] + l[i]) / 2.0;
        upper[i] = hl2 + mult * atr_[i];
        lower[i] = hl2 - mult * atr_[i];
    }
    for (int i = 0; i < sz; ++i) {
        if (i == 0 || isNan(atr_[i])) {
            finalUpper[i] = upper[i];
            finalLower[i] = lower[i];
            r.direction[i] = 1;
            r.line[i] = lower[i];
            continue;
        }
        const double fu = (upper[i] < finalUpper[i - 1] || c[i - 1] > finalUpper[i - 1])
                              ? upper[i] : finalUpper[i - 1];
        const double fl = (lower[i] > finalLower[i - 1] || c[i - 1] < finalLower[i - 1])
                              ? lower[i] : finalLower[i - 1];
        finalUpper[i] = fu;
        finalLower[i] = fl;
        if (c[i] > fu)
            r.direction[i] = 1;
        else if (c[i] < fl)
            r.direction[i] = -1;
        else
            r.direction[i] = r.direction[i - 1];
        r.line[i] = r.direction[i] == 1 ? fl : fu;
    }
    return r;
}

IchimokuResult ichimoku(const QVector<double> &h, const QVector<double> &l,
                        const QVector<double> &c, int tenkan, int kijun, int senkou)
{
    IchimokuResult r;
    const int sz = h.size();
    auto mid = [&](int period) {
        const QVector<double> hh = rollMax(h, period);
        const QVector<double> ll = rollMin(l, period);
        QVector<double> out(sz, nan());
        for (int i = 0; i < sz; ++i)
            if (!isNan(hh[i]) && !isNan(ll[i]))
                out[i] = (hh[i] + ll[i]) / 2.0;
        return out;
    };
    r.tenkan = mid(tenkan);
    r.kijun = mid(kijun);
    QVector<double> sa(sz, nan());
    for (int i = 0; i < sz; ++i)
        if (!isNan(r.tenkan[i]) && !isNan(r.kijun[i]))
            sa[i] = (r.tenkan[i] + r.kijun[i]) / 2.0;
    const QVector<double> sb = mid(senkou);
    // shift maju kijun (index i mengambil nilai i-kijun).
    r.senkouA.fill(nan(), sz);
    r.senkouB.fill(nan(), sz);
    for (int i = 0; i < sz; ++i) {
        if (i - kijun >= 0) {
            r.senkouA[i] = sa[i - kijun];
            r.senkouB[i] = sb[i - kijun];
        }
    }
    // chikou: shift mundur kijun (index i mengambil c[i+kijun]).
    r.chikou.fill(nan(), sz);
    for (int i = 0; i < sz; ++i)
        if (i + kijun < sz)
            r.chikou[i] = c[i + kijun];
    return r;
}

Pivots pivotPoints(const QVector<double> &h, const QVector<double> &l,
                   const QVector<double> &c)
{
    Pivots p;
    if (h.isEmpty())
        return p;
    const double hi = h.last(), lo = l.last(), cl = c.last();
    p.pivot = (hi + lo + cl) / 3.0;
    p.r1 = 2 * p.pivot - lo;
    p.s1 = 2 * p.pivot - hi;
    p.r2 = p.pivot + (hi - lo);
    p.s2 = p.pivot - (hi - lo);
    p.r3 = hi + 2 * (p.pivot - lo);
    p.s3 = lo - 2 * (hi - p.pivot);
    p.valid = true;
    return p;
}

bool crossover(const QVector<double> &a, const QVector<double> &b)
{
    if (a.size() < 2 || b.size() < 2)
        return false;
    const double a0 = a[a.size() - 2], a1 = a.last();
    const double b0 = b[b.size() - 2], b1 = b.last();
    if (isNan(a0) || isNan(a1) || isNan(b0) || isNan(b1))
        return false;
    return a0 <= b0 && a1 > b1;
}

bool crossunder(const QVector<double> &a, const QVector<double> &b)
{
    if (a.size() < 2 || b.size() < 2)
        return false;
    const double a0 = a[a.size() - 2], a1 = a.last();
    const double b0 = b[b.size() - 2], b1 = b.last();
    if (isNan(a0) || isNan(a1) || isNan(b0) || isNan(b1))
        return false;
    return a0 >= b0 && a1 < b1;
}

} // namespace ind
