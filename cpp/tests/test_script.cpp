#include <QtTest>

#include "script/ScriptStrategy.h"
#include "strategy/Command.h"

static QVector<Candle> candlesRising(int n)
{
    QVector<Candle> out;
    long long t = 1700000000;
    for (int i = 0; i < n; ++i) {
        Candle c;
        c.t = t;
        t += 300;
        c.c = 10.0 + i * 0.5;
        c.o = c.c;
        c.h = c.c + 0.3;
        c.l = c.c - 0.3;
        c.tickVolume = 100 + i;
        out << c;
    }
    return out;
}

static RuntimeContext makeRuntime()
{
    RuntimeContext rt;
    rt.symbol = "EURUSDm";
    rt.account.balance = 1000;
    rt.account.equity = 1000;
    rt.account.valid = true;
    rt.tick.bid = 1.10000;
    rt.tick.ask = 1.10002;
    rt.tick.valid = true;
    rt.spec.symbol = "EURUSDm";
    rt.spec.point = 0.00001;
    rt.spec.digits = 5;
    rt.spec.valid = true;
    return rt;
}

class TestScript : public QObject
{
    Q_OBJECT

    QVector<Candle> candles;
    RuntimeContext rt;

private slots:
    void initTestCase()
    {
        candles = candlesRising(60);
        rt = makeRuntime();
    }

    // ----- Validasi -----
    void validate_ok()
    {
        ScriptValidation v = ScriptStrategy::validate("function on_bar(ctx){ return null; }");
        QVERIFY(v.ok);
    }

    void validate_missingOnBar()
    {
        ScriptValidation v = ScriptStrategy::validate("function foo(){ return 1; }");
        QVERIFY(!v.ok);
        QVERIFY(v.message.contains("on_bar"));
    }

    void validate_syntaxError()
    {
        ScriptValidation v = ScriptStrategy::validate("function on_bar(ctx){ return @@@ }");
        QVERIFY(!v.ok);
    }

    // ----- Sinyal sederhana -----
    void simpleBuySignal()
    {
        ScriptStrategy s("function on_bar(ctx){ return 'BUY'; }");
        QVERIFY(s.compiled());
        const QVector<Command> cmds = s.onBar(candles, rt);
        QCOMPARE(cmds.size(), 1);
        QCOMPARE(cmds.first().action, QStringLiteral("BUY"));
    }

    void nullNoSignal()
    {
        ScriptStrategy s("function on_bar(ctx){ return null; }");
        QVERIFY(s.onBar(candles, rt).isEmpty());
    }

    // ----- Order intent (cBot style) -----
    void buyIntent_explicit()
    {
        ScriptStrategy s("function on_bar(ctx){ return ctx.buy({volume:0.1, sl_points:300, tp_points:600}); }");
        QVERIFY(s.compiled());
        const QVector<Command> cmds = s.onBar(candles, rt);
        QCOMPARE(cmds.size(), 1);
        const Command &c = cmds.first();
        QCOMPARE(c.action, QStringLiteral("BUY"));
        QVERIFY(c.hasVolume);
        QCOMPARE(c.volume, 0.1);
        QVERIFY(c.hasSlPoints);
        QCOMPARE(c.slPoints, 300);
        QVERIFY(c.hasTpPoints);
        QCOMPARE(c.tpPoints, 600);
    }

    void buyIntent_fromSettings()
    {
        // ctx.buy() tanpa argumen -> ambil dari SETTINGS.
        const char *src =
            "var SETTINGS = { volume: 0.05, sl_points: 250, tp_points: 500 };"
            "function on_bar(ctx){ return ctx.buy(); }";
        ScriptStrategy s(src);
        QVERIFY2(s.compiled(), qUtf8Printable(s.error()));
        const QVector<Command> cmds = s.onBar(candles, rt);
        QCOMPARE(cmds.size(), 1);
        QCOMPARE(cmds.first().volume, 0.05);
        QCOMPARE(cmds.first().slPoints, 250);
        QCOMPARE(cmds.first().tpPoints, 500);
    }

    void closeAll_and_array()
    {
        const char *src =
            "function on_bar(ctx){ return [ ctx.close_all(), ctx.buy({volume:0.02}) ]; }";
        ScriptStrategy s(src);
        const QVector<Command> cmds = s.onBar(candles, rt);
        QCOMPARE(cmds.size(), 2);
        QCOMPARE(cmds[0].action, QStringLiteral("CLOSE_ALL"));
        QCOMPARE(cmds[1].action, QStringLiteral("BUY"));
        QCOMPARE(cmds[1].volume, 0.02);
    }

    void modify_activePosition()
    {
        RuntimeContext r = rt;
        Position p;
        p.ticket = 777;
        p.symbol = "EURUSDm";
        p.type = "BUY";
        r.positions << p;
        ScriptStrategy s("function on_bar(ctx){ return ctx.modify({sl:1.09, tp:1.11}); }");
        const QVector<Command> cmds = s.onBar(candles, r);
        QCOMPARE(cmds.size(), 1);
        QCOMPARE(cmds.first().action, QStringLiteral("MODIFY"));
        QCOMPARE(cmds.first().ticket, 777LL);
        QVERIFY(cmds.first().hasSl);
        QVERIFY(cmds.first().hasTp);
    }

    // ----- Indikator dari dalam skrip -----
    void indicatorAccess()
    {
        // Tren naik: SMA terakhir > harga pertama -> BUY.
        const char *src =
            "function on_bar(ctx){ var m = ctx.sma(ctx.close, 5);"
            " if (m[m.length-1] > ctx.close[0]) return 'BUY'; return null; }";
        ScriptStrategy s(src);
        QVERIFY(s.compiled());
        QCOMPARE(s.onBar(candles, rt).size(), 1);
    }

    void ctxDataExposed()
    {
        const char *src =
            "function on_bar(ctx){ if (ctx.symbol === 'EURUSDm' && ctx.close.length === 60)"
            " return ctx.buy({volume:0.01}); return null; }";
        ScriptStrategy s(src);
        const QVector<Command> cmds = s.onBar(candles, rt);
        QCOMPARE(cmds.size(), 1);
        QCOMPARE(cmds.first().volume, 0.01);
    }

    // ----- B1: ctx.settings / ctx.time / ctx.now -----
    void ctxSettingsAndTimeExposed()
    {
        const char *src =
            "var SETTINGS = { foo: 42 };"
            "function on_bar(ctx){"
            "  if (ctx.settings.foo === 42 && ctx.time > 0 && ctx.now > 0) return 'BUY';"
            "  return null; }";
        ScriptStrategy s(src);
        QVERIFY2(s.compiled(), qUtf8Printable(s.error()));
        const QVector<Command> cmds = s.onBar(candles, rt);
        QCOMPARE(cmds.size(), 1);
        QCOMPARE(cmds.first().action, QStringLiteral("BUY"));
    }

    void ctxTimeMatchesLastBar()
    {
        // ctx.time harus sama dengan epoch candle terakhir.
        const long long lastT = candles.last().t;
        const QString js =
            QStringLiteral("function on_bar(ctx){ if (ctx.time === %1) return 'BUY'; return null; }")
                .arg(lastT);
        ScriptStrategy s(js);
        QVERIFY2(s.compiled(), qUtf8Printable(s.error()));
        QCOMPARE(s.onBar(candles, rt).size(), 1);
    }

    // ----- Fail-safe -----
    void runtimeError_noCrash()
    {
        ScriptStrategy s("function on_bar(ctx){ return nonExistent.foo; }");
        QVERIFY(s.compiled());
        QVERIFY(s.onBar(candles, rt).isEmpty()); // error ditangkap -> tanpa sinyal
    }

    void infiniteLoop_interrupted()
    {
        ScriptStrategy s("function on_bar(ctx){ while(true){} }", {}, 200);
        QVERIFY(s.compiled());
        const QVector<Command> cmds = s.onBar(candles, rt); // watchdog interupsi ~200ms
        QVERIFY(cmds.isEmpty());
    }
};

QTEST_GUILESS_MAIN(TestScript)
#include "test_script.moc"
