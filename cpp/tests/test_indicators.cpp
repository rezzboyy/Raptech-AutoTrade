#include <QtTest>
#include <QVector>

#include "indicators/Indicators.h"

// Dataset uji (sama persis dengan _ref_ind.py yang menghasilkan nilai referensi
// dari implementasi Python). Nilai referensi = keluaran indikator versi Python.
using ind::nan;
using ind::isNan;

static QVector<double> closeSeries()
{
    return {10.0, 10.5, 10.2, 10.8, 11.0, 10.6, 10.9, 11.5, 11.2, 11.8,
            12.0, 11.7, 12.3, 12.1, 11.9, 12.5, 12.2, 12.8, 13.0, 12.6,
            12.9, 13.5, 13.2, 13.8, 14.0, 13.6, 13.9, 14.5, 14.2, 14.8};
}

class TestIndicators : public QObject
{
    Q_OBJECT

    QVector<double> c, h, l, v;

    static double lastVal(const QVector<double> &x) { return x.isEmpty() ? nan() : x.last(); }

    void chk(const QVector<double> &x, double ref, const char *label)
    {
        const double got = lastVal(x);
        QVERIFY2(!isNan(got), label);
        QVERIFY2(qAbs(got - ref) < 1e-6, label);
    }

private slots:
    void initTestCase()
    {
        c = closeSeries();
        for (double x : c) {
            h << x + 0.3;
            l << x - 0.3;
        }
        for (int i = 0; i < c.size(); ++i)
            v << 100.0 + 5.0 * i;
    }

    void movingAverages()
    {
        chk(ind::sma(c, 5), 14.2000000000, "sma5");
        chk(ind::ema(c, 5), 14.2868742532, "ema5");
        chk(ind::wma(c, 5), 14.3800000000, "wma5");
        chk(ind::stdev(c, 5), 0.4242640687, "stdev5");
    }

    void oscillators()
    {
        chk(ind::rsi(c, 14), 75.5433700957, "rsi14");
        chk(ind::atr(h, l, c, 14), 0.7118639109, "atr14");
        chk(ind::highest(h, 5), 15.1000000000, "highest5");
        chk(ind::lowest(l, 5), 13.3000000000, "lowest5");
    }

    void bollinger()
    {
        ind::Band b = ind::bbands(c, 20, 2.0);
        chk(b.upper, 14.8759719598, "bb_u");
        chk(b.mid, 13.0750000000, "bb_m");
        chk(b.lower, 11.2740280402, "bb_l");
    }

    void macdTest()
    {
        ind::MacdResult m = ind::macd(c);
        chk(m.macd, 0.8881396434, "macd");
        chk(m.signal, 0.7898761743, "macd_sig");
        chk(m.hist, 0.0982634691, "macd_hist");
    }

    void stochTest()
    {
        ind::StochResult s = ind::stochastic(h, l, c, 14, 3, 3);
        chk(s.k, 86.8534482759, "stoch_k");
        chk(s.d, 85.0627926777, "stoch_d");
    }

    void adxTest()
    {
        ind::AdxResult a = ind::adx(h, l, c, 14);
        chk(a.adx, 63.2997700932, "adx");
        chk(a.plusDI, 44.5375998676, "plus_di");
        chk(a.minusDI, 14.4187318544, "minus_di");
    }

    void others()
    {
        chk(ind::cci(h, l, c, 20), 146.9648562300, "cci20");
        chk(ind::vwap(h, l, c, v, 14), 13.5650420168, "vwap14");
        chk(ind::williamsR(h, l, c, 14), -9.3750000000, "willr14");
        chk(ind::obv(c, v), 1245.0000000000, "obv");
        chk(ind::mfi(h, l, c, v, 14), 65.5738923580, "mfi14");
    }

    void channels()
    {
        ind::Band d = ind::donchian(h, l, 20);
        chk(d.upper, 15.1000000000, "don_u");
        chk(d.mid, 13.2500000000, "don_m");
        chk(d.lower, 11.4000000000, "don_l");
    }

    void trendFollowers()
    {
        chk(ind::parabolicSar(h, l), 13.8400000000, "psar");
        ind::SuperTrendResult st = ind::supertrend(h, l, c, 10, 3.0);
        chk(st.line, 12.6282147800, "st");
        QCOMPARE(st.direction.last(), 1);
    }

    void ichimokuTest()
    {
        ind::IchimokuResult i = ind::ichimoku(h, l, c, 9, 26, 52);
        chk(i.tenkan, 14.0000000000, "ichi_tenkan");
        chk(i.kijun, 12.7000000000, "ichi_kijun");
    }

    void pivots()
    {
        ind::Pivots p = ind::pivotPoints(h, l, c);
        QVERIFY(p.valid);
        QVERIFY(qAbs(p.pivot - 14.8) < 1e-6);
        QVERIFY(qAbs(p.r1 - 15.1) < 1e-6);
        QVERIFY(qAbs(p.s1 - 14.5) < 1e-6);
    }

    void crossings()
    {
        QVector<double> a{1, 2, 3};
        QVector<double> b{3, 2, 1};
        QVERIFY(ind::crossover(a, b));
        QVERIFY(!ind::crossunder(a, b));
        QVERIFY(ind::crossunder(b, a));
        QVERIFY(!ind::crossover(b, a));
        // NaN -> false.
        QVector<double> x{nan(), 2.0};
        QVERIFY(!ind::crossover(x, b));
    }
};

QTEST_APPLESS_MAIN(TestIndicators)
#include "test_indicators.moc"
