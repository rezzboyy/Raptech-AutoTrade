#include <QtTest>

#include "backend/TradingBackend.h"
#include "core/Settings.h"
#include "engine/BotEngine.h"
#include "engine/TradeRules.h"
#include "strategy/Strategy.h"

// ---------------- Backend palsu in-memory ----------------
class FakeBackend : public TradingBackend
{
public:
    Account account;
    SymbolSpec spec;
    Tick tick;
    double spread = 0.0;
    QVector<Candle> candles;
    QVector<Position> pos;
    QVector<Deal> deals;
    long long nextTicket = 1000;
    int marketOrders = 0;

    FakeBackend()
    {
        account.balance = 1000;
        account.equity = 1000;
        account.tradeAllowed = true;
        account.serverConnected = true;
        account.valid = true;
        spec.symbol = "EURUSDm";
        spec.digits = 5;
        spec.point = 0.00001;
        spec.tickSize = 0.00001;
        spec.tickValue = 1.0;
        spec.volumeMin = 0.01;
        spec.volumeStep = 0.01;
        spec.volumeMax = 100.0;
        spec.valid = true;
        tick.bid = 1.10000;
        tick.ask = 1.10002;
        tick.valid = true;
    }

    bool connect() override { return true; }
    void disconnect() override {}
    Account accountInfo() override { return account; }
    QStringList listSymbols(int) override { return {"EURUSDm"}; }
    SymbolSpec symbolSpec(const QString &) override { return spec; }
    QString resolveSymbol(const QString &s) override { return s; }
    bool ensureSymbol(const QString &) override { return true; }
    QVector<Candle> getRates(const QString &, const QString &, int) override { return candles; }
    Tick getTick(const QString &) override { return tick; }
    double spreadPoints(const QString &, bool *ok) override
    {
        if (ok) *ok = true;
        return spread;
    }
    QVector<Position> positions(const QString &symbol = QString()) override
    {
        if (symbol.isEmpty())
            return pos;
        QVector<Position> out;
        for (const Position &p : pos)
            if (p.symbol == symbol)
                out << p;
        return out;
    }
    QVector<Deal> historyDeals(const QDateTime &, const QDateTime &) override { return deals; }
    OrderResult sendMarketOrder(const QString &symbol, const QString &side, double volume,
                                double sl, double tp, long long magic, const QString &) override
    {
        ++marketOrders;
        Position p;
        p.ticket = nextTicket++;
        p.symbol = symbol;
        p.type = side.toLower() == "buy" ? "BUY" : "SELL";
        p.volume = volume;
        p.priceOpen = p.type == "BUY" ? tick.ask : tick.bid;
        p.sl = sl;
        p.tp = tp;
        p.magic = magic;
        pos << p;
        OrderResult r;
        r.ok = true;
        r.ticket = p.ticket;
        r.hasTicket = true;
        return r;
    }
    OrderResult closePosition(long long ticket, const QString &) override
    {
        OrderResult r;
        for (int i = 0; i < pos.size(); ++i)
            if (pos[i].ticket == ticket) {
                pos.remove(i);
                r.ok = true;
                r.ticket = ticket;
                r.hasTicket = true;
                return r;
            }
        r.message = "not found";
        return r;
    }
    bool modifySlTp(long long ticket, const QString &, bool hasSl, double sl,
                    bool hasTp, double tp) override
    {
        for (Position &p : pos)
            if (p.ticket == ticket) {
                if (hasSl) p.sl = sl;
                if (hasTp) p.tp = tp;
                return true;
            }
        return false;
    }
    OrderResult sendPendingOrder(const QString &, const QString &, double, double, double,
                                 double, long long, const QString &) override { return {}; }
    OrderResult deletePendingOrder(long long) override { return {}; }
    QVector<Order> pendingOrders(const QString &) override { return {}; }
};

// Strategi palsu: selalu BUY + scriptSettings yang bisa dikonfigurasi (tanpa QJSEngine).
class SettingsStrategy : public Strategy
{
public:
    QVariantMap sets;
    QString sigOut = sig::BUY;   // sinyal yang dikembalikan tiap bar
    QString name() const override { return QStringLiteral("fake_settings"); }
    QVariantMap scriptSettings() const override { return sets; }
    QString generateSignal(const QVector<Candle> &) override { return sigOut; }
};

static QVector<Candle> candlesFromCloses(const QVector<double> &closes)
{
    QVector<Candle> out;
    long long t = 1700000000;
    for (double x : closes) {
        Candle c;
        c.t = t;
        t += 300;
        c.o = x;
        c.h = x + 0.3;
        c.l = x - 0.3;
        c.c = x;
        c.tickVolume = 100;
        out << c;
    }
    return out;
}

class TestEngine : public QObject
{
    Q_OBJECT

private slots:
    // ----- Strategi -----
    void factory()
    {
        QVERIFY(createStrategy("ma_cross") != nullptr);
        QVERIFY(createStrategy("rsi") != nullptr);
        QVERIFY(createStrategy("bollinger") != nullptr);
        QVERIFY(createStrategy("macd") != nullptr);
        QVERIFY(createStrategy("multi_indicator") != nullptr);
        QVERIFY(createStrategy("tidak_ada") == nullptr);
    }

    void maCross_buySell()
    {
        auto s = createStrategy("ma_cross", {{"fast_period", 2}, {"slow_period", 4}});
        // Flat lalu lonjakan naik -> fast cross ke atas slow.
        QVector<double> up{10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 20};
        QCOMPARE(s->generateSignal(candlesFromCloses(up)), sig::BUY);
        // Flat lalu jatuh -> cross ke bawah.
        QVector<double> down{10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 0};
        QCOMPARE(s->generateSignal(candlesFromCloses(down)), sig::SELL);
    }

    // ----- TradeRules -----
    void calcLot()
    {
        FakeBackend b;
        // risk 1% dari 1000 = 10; jarak SL 300 pts (0.003); tickValue 1/tick 0.00001.
        const double lot = TradeRules::calcLotFromSpec(b.spec, 1000.0, 0.01, 1.09700, 1.10000);
        QCOMPARE(lot, 0.03);
    }

    void riskGate_maxPositions()
    {
        FakeBackend b;
        Settings s;
        s.maxOpenPositions = 1;
        s.magicNumber = 0;
        Position p;
        p.ticket = 1;
        p.symbol = "EURUSDm";
        p.type = "BUY";
        b.pos << p;
        QString reason;
        QVERIFY(!TradeRules::passesRiskGates(b, s, "EURUSDm", reason));
        QVERIFY(reason.contains("Batas posisi"));
    }

    void openOrder_allowed()
    {
        FakeBackend b;
        Settings s;
        s.maxOpenPositions = 2;
        OrderResult r = TradeRules::openOrderIfAllowed(b, s, "EURUSDm", "buy", 0.01,
                                                       1.097, 1.106, "test");
        QVERIFY(r.ok);
        QCOMPARE(b.pos.size(), 1);
    }

    void openOrder_blockedByExposure()
    {
        FakeBackend b;
        Settings s;
        s.magicNumber = 0;
        s.maxOpenPositions = 5;
        s.maxExposureLots = 0.05;
        // Sudah ada eksposur 0.04, tambah 0.03 -> lewat batas 0.05.
        Position p;
        p.ticket = 1; p.symbol = "EURUSDm"; p.type = "BUY"; p.volume = 0.04;
        b.pos << p;
        OrderResult r = TradeRules::openOrderIfAllowed(b, s, "EURUSDm", "buy", 0.03,
                                                       0, 0, "x");
        QVERIFY(!r.ok);
        QVERIFY(r.message.contains("eksposur"));
    }

    // ----- BotEngine -----
    void processStep_opensOnSignal()
    {
        FakeBackend b;
        Settings s;
        s.symbol = "EURUSDm";
        s.maxOpenPositions = 1;
        s.slPoints = 300;
        s.tpPoints = 600;
        b.candles = candlesFromCloses({10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 20});
        BotEngine engine(&b, &s);
        engine.setStrategy(createStrategy("ma_cross", {{"fast_period", 2}, {"slow_period", 4}}));
        QVERIFY(engine.processTradingStep());
        QCOMPARE(b.marketOrders, 1);
        QCOMPARE(b.pos.size(), 1);
        QCOMPARE(b.pos.first().type, QStringLiteral("BUY"));
    }

    void processStep_respectsMaxPositions()
    {
        FakeBackend b;
        Settings s;
        s.magicNumber = 0;
        s.symbol = "EURUSDm";
        s.maxOpenPositions = 1;
        // Sudah ada 1 posisi -> tidak boleh buka lagi.
        Position p;
        p.ticket = 1; p.symbol = "EURUSDm"; p.type = "BUY"; p.magic = 0;
        b.pos << p;
        b.candles = candlesFromCloses({10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 20});
        BotEngine engine(&b, &s);
        engine.setStrategy(createStrategy("ma_cross", {{"fast_period", 2}, {"slow_period", 4}}));
        engine.processTradingStep();
        QCOMPARE(b.marketOrders, 0); // tidak ada order baru
    }

    void equityStop_closesAndStops()
    {
        FakeBackend b;
        b.account.balance = 1000;
        b.account.equity = 900; // drawdown 10%
        Settings s;
        s.magicNumber = 0;
        s.equityStopLoss = 0.05; // batas 5%
        Position p;
        p.ticket = 1; p.symbol = "EURUSDm"; p.type = "BUY";
        b.pos << p;
        BotEngine engine(&b, &s);
        QVERIFY(!engine.processTradingStep()); // false = stop
        QCOMPARE(b.pos.size(), 0);             // semua ditutup
    }

    // ----- A1: filter waktu/sesi (SETTINGS skrip) -----
    void sessionFilter_activeDaysBlocks()
    {
        FakeBackend b;
        Settings s; s.symbol = "EURUSDm"; s.magicNumber = 0; s.maxOpenPositions = 5;
        b.candles = candlesFromCloses({10, 10, 10, 10, 10});
        auto strat = std::make_unique<SettingsStrategy>();
        // Rabu 2024-01-03 (pyWeekday=2). active_days hanya Senin(0) -> harus diblok.
        strat->sets.insert("active_days", QVariantList{0});
        BotEngine engine(&b, &s);
        engine.setStrategy(std::move(strat));
        engine.setNowOverrideForTest(QDateTime(QDate(2024, 1, 3), QTime(12, 0), Qt::UTC));
        QVERIFY(engine.processTradingStep());   // true = lanjut (tak stop)
        QCOMPARE(b.marketOrders, 0);            // tapi tak buka order (hari tak aktif)
    }

    void sessionFilter_activeDaysAllows()
    {
        FakeBackend b;
        Settings s; s.symbol = "EURUSDm"; s.magicNumber = 0; s.maxOpenPositions = 5;
        s.slPoints = 300; s.tpPoints = 600;
        b.candles = candlesFromCloses({10, 10, 10, 10, 10});
        auto strat = std::make_unique<SettingsStrategy>();
        strat->sets.insert("active_days", QVariantList{0, 1, 2, 3, 4});
        BotEngine engine(&b, &s);
        engine.setStrategy(std::move(strat));
        engine.setNowOverrideForTest(QDateTime(QDate(2024, 1, 3), QTime(12, 0), Qt::UTC)); // Rabu
        engine.processTradingStep();
        QCOMPARE(b.marketOrders, 1);            // hari aktif -> order dibuka
    }

    void sessionFilter_tradeHoursBlocks()
    {
        FakeBackend b;
        Settings s; s.symbol = "EURUSDm"; s.magicNumber = 0; s.maxOpenPositions = 5;
        b.candles = candlesFromCloses({10, 10, 10, 10, 10});
        auto strat = std::make_unique<SettingsStrategy>();
        strat->sets.insert("trade_start_time", "08:00");
        strat->sets.insert("trade_end_time", "17:00");
        BotEngine engine(&b, &s);
        engine.setStrategy(std::move(strat));
        // Jam 06:00 (< start) -> diblok.
        engine.setNowOverrideForTest(QDateTime(QDate(2024, 1, 3), QTime(6, 0), Qt::UTC));
        engine.processTradingStep();
        QCOMPARE(b.marketOrders, 0);
    }

    void sessionFilter_closeFridayClosesAll()
    {
        FakeBackend b;
        Settings s; s.symbol = "EURUSDm"; s.magicNumber = 0;
        Position p; p.ticket = 1; p.symbol = "EURUSDm"; p.type = "BUY"; p.magic = 0;
        b.pos << p;
        b.candles = candlesFromCloses({10, 10, 10, 10, 10});
        auto strat = std::make_unique<SettingsStrategy>();
        strat->sets.insert("close_friday_hour", 20);
        BotEngine engine(&b, &s);
        engine.setStrategy(std::move(strat));
        // Jumat 2024-01-05, jam 21:00 (>= 20) -> tutup semua.
        engine.setNowOverrideForTest(QDateTime(QDate(2024, 1, 5), QTime(21, 0), Qt::UTC));
        QVERIFY(engine.processTradingStep());
        QCOMPARE(b.pos.size(), 0);
    }

    // ----- A2: cooldown, min margin level, max holding bars -----
    void maxHoldingBars_closesOldPosition()
    {
        FakeBackend b;
        Settings s; s.symbol = "EURUSDm"; s.magicNumber = 0; s.timeframeStr = "M5";
        // Posisi lama: dibuka 700 detik lalu (> 2 bar M5 = 600 detik).
        const qint64 nowSec = QDateTime(QDate(2024, 1, 3), QTime(12, 0), Qt::UTC).toSecsSinceEpoch();
        Position p; p.ticket = 1; p.symbol = "EURUSDm"; p.type = "BUY"; p.magic = 0;
        p.time = nowSec - 700;
        b.pos << p;
        b.candles = candlesFromCloses({10, 10, 10, 10, 10});
        auto strat = std::make_unique<SettingsStrategy>();
        strat->sigOut = QString();                    // tanpa sinyal (isolasi)
        strat->sets.insert("max_holding_bars", 2);
        BotEngine engine(&b, &s);
        engine.setStrategy(std::move(strat));
        engine.setNowOverrideForTest(QDateTime(QDate(2024, 1, 3), QTime(12, 0), Qt::UTC));
        engine.processTradingStep();
        QCOMPARE(b.pos.size(), 0);                    // posisi lama ditutup
    }

    void maxHoldingBars_keepsFreshPosition()
    {
        FakeBackend b;
        Settings s; s.symbol = "EURUSDm"; s.magicNumber = 0; s.timeframeStr = "M5";
        const qint64 nowSec = QDateTime(QDate(2024, 1, 3), QTime(12, 0), Qt::UTC).toSecsSinceEpoch();
        Position p; p.ticket = 1; p.symbol = "EURUSDm"; p.type = "BUY"; p.magic = 0;
        p.time = nowSec - 100;                        // baru 100 detik (< 600)
        b.pos << p;
        b.candles = candlesFromCloses({10, 10, 10, 10, 10});
        auto strat = std::make_unique<SettingsStrategy>();
        strat->sigOut = QString();
        strat->sets.insert("max_holding_bars", 2);
        BotEngine engine(&b, &s);
        engine.setStrategy(std::move(strat));
        engine.setNowOverrideForTest(QDateTime(QDate(2024, 1, 3), QTime(12, 0), Qt::UTC));
        engine.processTradingStep();
        QCOMPARE(b.pos.size(), 1);                    // posisi tetap
    }

    void minMarginLevel_blocksEntry()
    {
        FakeBackend b;
        b.account.margin = 100.0;   // margin level = equity/margin*100 = 1000%
        b.account.equity = 1000.0;
        Settings s; s.symbol = "EURUSDm"; s.magicNumber = 0; s.maxOpenPositions = 5;
        b.candles = candlesFromCloses({10, 10, 10, 10, 10});
        auto strat = std::make_unique<SettingsStrategy>();
        strat->sets.insert("min_margin_level", 2000.0);   // butuh >= 2000% -> diblok
        BotEngine engine(&b, &s);
        engine.setStrategy(std::move(strat));
        engine.processTradingStep();
        QCOMPARE(b.marketOrders, 0);
    }

    void cooldownBars_blocksSecondEntry()
    {
        FakeBackend b;
        Settings s; s.symbol = "EURUSDm"; s.magicNumber = 0; s.maxOpenPositions = 5;
        s.slPoints = 300; s.tpPoints = 600;
        b.candles = candlesFromCloses({10, 10, 10, 10, 10});
        auto strat = std::make_unique<SettingsStrategy>();
        strat->sets.insert("one_trade_per_bar", false);   // agar cooldown yang diuji
        strat->sets.insert("cooldown_bars", 5);
        BotEngine engine(&b, &s);
        engine.setStrategy(std::move(strat));
        engine.processTradingStep();      // step 1: buka
        QCOMPARE(b.marketOrders, 1);
        engine.processTradingStep();      // step 2: masih cooldown -> diblok
        QCOMPARE(b.marketOrders, 1);
    }

    // ----- A3: risk_reward_ratio, ATR SL/TP, strategi stochastic -----
    void riskRewardRatio_setsTpFromSl()
    {
        FakeBackend b;
        Settings s; s.symbol = "EURUSDm"; s.slPoints = 300; s.tpPoints = 1000;
        auto strat = std::make_unique<SettingsStrategy>();
        strat->sets.insert("risk_reward_ratio", 2.0);   // TP = SL(300) * 2 = 600 pts
        BotEngine engine(&b, &s);
        engine.setStrategy(std::move(strat));
        double sl = 0, tp = 0;
        Command ov;
        engine.computeSlTp("EURUSDm", sig::BUY, 1.10000, ov, sl, tp);
        // SL 300 pts -> 1.09700 ; TP 600 pts (bukan 1000) -> 1.10600.
        QVERIFY(qAbs(sl - 1.09700) < 1e-6);
        QVERIFY(qAbs(tp - 1.10600) < 1e-6);
    }

    void scriptSlPoints_usedWhenNoOverride()
    {
        FakeBackend b;
        Settings s; s.symbol = "EURUSDm"; s.slPoints = 300; s.tpPoints = 600;
        auto strat = std::make_unique<SettingsStrategy>();
        strat->sets.insert("sl_points", 500);
        strat->sets.insert("tp_points", 800);
        BotEngine engine(&b, &s);
        engine.setStrategy(std::move(strat));
        double sl = 0, tp = 0;
        Command ov;
        engine.computeSlTp("EURUSDm", sig::BUY, 1.10000, ov, sl, tp);
        QVERIFY(qAbs(sl - 1.09500) < 1e-6);   // 500 pts
        QVERIFY(qAbs(tp - 1.10800) < 1e-6);   // 800 pts
    }

    void stochasticStrategy_factory()
    {
        auto s = createStrategy("stochastic",
                                {{"k_period", 5}, {"d_period", 3}, {"oversold", 20}, {"overbought", 80}});
        QVERIFY(s != nullptr);
        // Data datar -> tak ada sinyal (tak crash).
        QCOMPARE(s->generateSignal(candlesFromCloses({10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10})),
                 QString());
    }

    void virtualExit_hitTp()
    {
        FakeBackend b;
        Settings s;
        s.symbol = "EURUSDm";
        s.maxOpenPositions = 1;
        s.virtualSltpEnabled = true;
        s.slPoints = 300;
        s.tpPoints = 600;
        BotEngine engine(&b, &s);
        engine.setStrategy(createStrategy("ma_cross"));
        Command cmd;
        cmd.action = sig::BUY;
        QVERIFY(engine.handleSignal("EURUSDm", sig::BUY, cmd));
        QCOMPARE(engine.virtualCount(), 1);
        QCOMPARE(b.pos.size(), 1);
        // Order dikirim TANPA SL/TP (virtual).
        QCOMPARE(b.pos.first().tp, 0.0);
        // Naikkan harga menembus TP virtual -> checkVirtualExits menutup.
        b.tick.bid = 2.0;
        b.tick.ask = 2.00002;
        engine.checkVirtualExits();
        QCOMPARE(b.pos.size(), 0);
        QCOMPARE(engine.virtualCount(), 0);
    }
};

QTEST_APPLESS_MAIN(TestEngine)
#include "test_engine.moc"
