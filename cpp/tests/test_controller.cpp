#include <QtTest>
#include <QSignalSpy>
#include <QMutex>
#include <QFile>
#include <atomic>

#include "app/BotController.h"
#include "backend/TradingBackend.h"
#include "core/Settings.h"

// Backend palsu thread-safe untuk uji integrasi controller<->worker.
class FakeBackend : public TradingBackend
{
public:
    Account account;
    SymbolSpec spec;
    Tick tick;
    QVector<Candle> candles;
    std::atomic<int> marketOrders{0};
    std::atomic<int> connects{0};
    mutable QMutex mtx;
    QVector<Position> pos;

    FakeBackend()
    {
        account.balance = 500;
        account.equity = 500;
        account.currency = "USD";
        account.accountType = "DEMO";
        account.tradeAllowed = true;
        account.serverConnected = true;
        account.valid = true;
        spec.symbol = "EURUSDm"; spec.digits = 5; spec.point = 0.00001;
        spec.tickSize = 0.00001; spec.tickValue = 1.0; spec.volumeMin = 0.01;
        spec.volumeStep = 0.01; spec.volumeMax = 100; spec.valid = true;
        tick.bid = 1.1; tick.ask = 1.10002; tick.valid = true;
        long long t = 1700000000;
        for (int i = 0; i < 30; ++i) {
            Candle c; c.t = t; t += 300; c.o = c.h = c.l = c.c = 1.1; c.tickVolume = 100;
            candles << c;
        }
    }

    bool connect() override { ++connects; return true; }
    void disconnect() override {}
    Account accountInfo() override { return account; }
    QStringList listSymbols(int) override { return {"EURUSDm"}; }
    SymbolSpec symbolSpec(const QString &) override { return spec; }
    QString resolveSymbol(const QString &s) override { return s; }
    bool ensureSymbol(const QString &) override { return true; }
    QVector<Candle> getRates(const QString &, const QString &, int) override { return candles; }
    Tick getTick(const QString &) override { return tick; }
    double spreadPoints(const QString &, bool *ok) override { if (ok) *ok = true; return 0; }
    QVector<Position> positions(const QString & = QString()) override
    {
        QMutexLocker l(&mtx);
        return pos;
    }
    QVector<Deal> historyDeals(const QDateTime &, const QDateTime &) override { return {}; }
    OrderResult sendMarketOrder(const QString &symbol, const QString &side, double volume,
                                double sl, double tp, long long magic, const QString &) override
    {
        ++marketOrders;
        QMutexLocker l(&mtx);
        Position p;
        p.ticket = 5000 + marketOrders.load();
        p.symbol = symbol; p.type = side.toLower() == "buy" ? "BUY" : "SELL";
        p.volume = volume; p.sl = sl; p.tp = tp; p.magic = magic;
        pos << p;
        OrderResult r; r.ok = true; r.ticket = p.ticket; r.hasTicket = true;
        return r;
    }
    OrderResult closePosition(long long ticket, const QString &) override
    {
        QMutexLocker l(&mtx);
        for (int i = 0; i < pos.size(); ++i)
            if (pos[i].ticket == ticket) { pos.remove(i); break; }
        OrderResult r; r.ok = true; r.ticket = ticket; r.hasTicket = true; return r;
    }
    bool modifySlTp(long long, const QString &, bool, double, bool, double) override { return true; }
    OrderResult sendPendingOrder(const QString &, const QString &, double, double, double,
                                 double, long long, const QString &) override { return {}; }
    OrderResult deletePendingOrder(long long) override { return {}; }
    QVector<Order> pendingOrders(const QString &) override { return {}; }
};

class TestController : public QObject
{
    Q_OBJECT

private slots:
    void connect_updatesAccount_manualOrder_disconnect()
    {
        settings().symbol = "EURUSDm";
        settings().backend = "mcp";

        BotController ctrl;
        FakeBackend *fake = new FakeBackend();
        ctrl.setInjectedBackend(fake);

        QSignalSpy connSpy(&ctrl, &BotController::connectedChanged);
        QSignalSpy accSpy(&ctrl, &BotController::accountChanged);

        ctrl.connectBot();
        QVERIFY(connSpy.wait(5000));
        QVERIFY(ctrl.connected());

        // Akun terisi dari worker.
        QVERIFY(accSpy.wait(3000));
        QTRY_VERIFY_WITH_TIMEOUT(ctrl.balance() > 0.0, 3000);
        QCOMPARE(ctrl.currency(), QStringLiteral("USD"));
        QVERIFY(ctrl.tradeAllowed());

        // Aktifkan trading lalu kirim order manual (dieksekusi di worker thread).
        ctrl.setTrading(true);
        QVERIFY(ctrl.trading());
        ctrl.openManualOrder("EURUSDm", "buy", 0.01, 0, 0);
        QTRY_VERIFY_WITH_TIMEOUT(fake->marketOrders.load() > 0, 5000);

        // Disconnect bersih.
        QSignalSpy discSpy(&ctrl, &BotController::connectedChanged);
        ctrl.disconnectBot();
        QTRY_VERIFY_WITH_TIMEOUT(!ctrl.connected(), 5000);
    }

    void manualOrder_blockedWhenDisconnected()
    {
        BotController ctrl;
        QSignalSpy errSpy(&ctrl, &BotController::configError);
        ctrl.openManualOrder("EURUSDm", "buy", 0.01);
        QCOMPARE(errSpy.count(), 1);
    }

    void config_roundtrip()
    {
        BotController ctrl;
        QVariantMap cfg = ctrl.getConfig();
        QVERIFY(cfg.contains("symbol"));
        cfg["max_open_positions"] = 3;
        QVERIFY(ctrl.applyConfig(cfg));
        QCOMPARE(settings().maxOpenPositions, 3);
    }

    void validateScript_slot()
    {
        BotController ctrl;
        QVariantMap ok = ctrl.validateScript("function on_bar(ctx){ return null; }");
        QVERIFY(ok.value("ok").toBool());
        QVariantMap bad = ctrl.validateScript("function foo(){}");
        QVERIFY(!bad.value("ok").toBool());
    }

    // B2: simpan -> muat -> daftar skrip (roundtrip file).
    void scriptFile_saveLoadList()
    {
        BotController ctrl;
        const QString nm = "unit_test_tmp_script";
        const QString body = "function on_bar(ctx){ return null; }";
        QVERIFY(ctrl.saveScript(nm, body));
        QCOMPARE(ctrl.loadScript(nm).trimmed(), body);
        QVERIFY(ctrl.listScripts().contains(QVariant(nm)));
        QVERIFY(!ctrl.saveScript("  ", body));   // nama kosong ditolak
        QFile::remove("scripts/" + nm + ".js");
    }

    // B3: referensi & template SETTINGS.
    void settingsReference_available()
    {
        BotController ctrl;
        const QVariantList groups = ctrl.settingsReference();
        QVERIFY(!groups.isEmpty());
        // Grup punya "group" & "items".
        const QVariantMap g0 = groups.first().toMap();
        QVERIFY(g0.contains("group"));
        QVERIFY(!g0.value("items").toList().isEmpty());
        // Template memuat kata kunci SETTINGS & salah satu fitur A.
        const QString tpl = ctrl.settingsTemplate();
        QVERIFY(tpl.contains("SETTINGS"));
        QVERIFY(tpl.contains("trade_start_time"));
    }
};

QTEST_GUILESS_MAIN(TestController)
#include "test_controller.moc"
