#pragma once
#include <QVector>
#include <cmath>

// Pustaka indikator teknikal (port dari strategies/script_runtime.py).
// Konvensi: keluaran QVector<double> sejajar input; nilai tak tersedia = NaN
// (padanan None/NaN di versi Python). Deret input diasumsikan lama->baru.
namespace ind {

inline double nan() { return std::numeric_limits<double>::quiet_NaN(); }
inline bool isNan(double v) { return std::isnan(v); }

// Keluaran multi-garis.
struct Band { QVector<double> upper, mid, lower; };
struct MacdResult { QVector<double> macd, signal, hist; };
struct StochResult { QVector<double> k, d; };
struct AdxResult { QVector<double> adx, plusDI, minusDI; };
struct SuperTrendResult { QVector<double> line; QVector<int> direction; };
struct IchimokuResult { QVector<double> tenkan, kijun, senkouA, senkouB, chikou; };
struct Pivots {
    bool valid = false;
    double pivot = 0, r1 = 0, s1 = 0, r2 = 0, s2 = 0, r3 = 0, s3 = 0;
};

// Rata-rata & deviasi.
QVector<double> sma(const QVector<double> &src, int n);
QVector<double> ema(const QVector<double> &src, int n);
QVector<double> wma(const QVector<double> &src, int n);
QVector<double> stdev(const QVector<double> &src, int n);

// Osilator & rentang.
QVector<double> rsi(const QVector<double> &src, int n);
QVector<double> atr(const QVector<double> &high, const QVector<double> &low,
                    const QVector<double> &close, int n);
QVector<double> highest(const QVector<double> &src, int n);
QVector<double> lowest(const QVector<double> &src, int n);
Band bbands(const QVector<double> &src, int n, double mult);
MacdResult macd(const QVector<double> &src, int fast = 12, int slow = 26, int signal = 9);
StochResult stochastic(const QVector<double> &high, const QVector<double> &low,
                       const QVector<double> &close, int k = 14, int d = 3, int smooth = 3);
AdxResult adx(const QVector<double> &high, const QVector<double> &low,
              const QVector<double> &close, int n = 14);
QVector<double> cci(const QVector<double> &high, const QVector<double> &low,
                    const QVector<double> &close, int n = 20);
QVector<double> vwap(const QVector<double> &high, const QVector<double> &low,
                     const QVector<double> &close, const QVector<double> &volume, int n = 14);
QVector<double> williamsR(const QVector<double> &high, const QVector<double> &low,
                          const QVector<double> &close, int n = 14);
QVector<double> obv(const QVector<double> &close, const QVector<double> &volume);
QVector<double> mfi(const QVector<double> &high, const QVector<double> &low,
                    const QVector<double> &close, const QVector<double> &volume, int n = 14);
Band donchian(const QVector<double> &high, const QVector<double> &low, int n = 20);
QVector<double> parabolicSar(const QVector<double> &high, const QVector<double> &low,
                             double step = 0.02, double maxStep = 0.2);
SuperTrendResult supertrend(const QVector<double> &high, const QVector<double> &low,
                            const QVector<double> &close, int n = 10, double mult = 3.0);
IchimokuResult ichimoku(const QVector<double> &high, const QVector<double> &low,
                        const QVector<double> &close, int tenkan = 9, int kijun = 26,
                        int senkou = 52);
Pivots pivotPoints(const QVector<double> &high, const QVector<double> &low,
                   const QVector<double> &close);
bool crossover(const QVector<double> &a, const QVector<double> &b);
bool crossunder(const QVector<double> &a, const QVector<double> &b);

} // namespace ind
