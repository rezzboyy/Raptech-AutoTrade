#include <QtTest>
#include <QSignalSpy>
#include <QFile>

#include "app/BotController.h"
#include "app/UpdateManager.h"
#include "core/Settings.h"
#include "indicators/Indicators.h"

class TestController : public QObject
{
    Q_OBJECT

private slots:
    void defaultState_and_properties()
    {
        BotController ctrl;
        QCOMPARE(ctrl.connected(), false);
        QCOMPARE(ctrl.trading(), false);
        QCOMPARE(ctrl.status(), QStringLiteral("Terputus"));
        QCOMPARE(ctrl.balance(), 0.0);
        QCOMPARE(ctrl.equity(), 0.0);
        QVERIFY(ctrl.currency().isEmpty());
        QCOMPARE(ctrl.accountLogin(), 0LL);
        QVERIFY(ctrl.accountServer().isEmpty());

        // Konfigurasi default simbol harus ada
        QVariantMap cfg = ctrl.getConfig();
        QVERIFY(cfg.contains(QStringLiteral("symbol")));
        QVERIFY(!cfg[QStringLiteral("symbol")].toString().isEmpty());
    }

    void scriptValidation_valid()
    {
        BotController ctrl;
        QString validScript = QStringLiteral(
            "function on_bar(ctx) {\n"
            "    let rsiVal = ctx.rsi(14);\n"
            "    if (rsiVal < 30) return 'BUY';\n"
            "    return null;\n"
            "}\n"
        );
        QVariantMap res = ctrl.validateScript(validScript);
        QCOMPARE(res["ok"].toBool(), true);
        QCOMPARE(res["line"].toInt(), 0);
    }

    void scriptValidation_empty()
    {
        BotController ctrl;
        QVariantMap res = ctrl.validateScript(QStringLiteral("   \n\t  "));
        QCOMPARE(res["ok"].toBool(), false);
        QVERIFY(!res["message"].toString().isEmpty());
    }

    void scriptValidation_unclosedBracket()
    {
        BotController ctrl;
        QString invalidScript = QStringLiteral(
            "function on_bar(ctx) {\n"
            "    let arr = [1, 2, 3;\n"
            "}\n"
        );
        QVariantMap res = ctrl.validateScript(invalidScript);
        QCOMPARE(res["ok"].toBool(), false);
        QVERIFY(res["message"].toString().contains(QStringLiteral("siku")));
    }

    void scriptValidation_withComments()
    {
        BotController ctrl;
        QString scriptWithComments = QStringLiteral(
            "# (catatan penting parameter)\n"
            "// (komentar lagi dengan kurung)\n"
            "/* block (kurung di dalam) */\n"
            "def on_bar(ctx):\n"
            "    val = \"string (dengan kurung)\"\n"
            "    if ctx.close[-1] > 1.0:\n"
            "        return 'BUY'\n"
            "    return None\n"
        );
        QVariantMap res = ctrl.validateScript(scriptWithComments);
        QCOMPARE(res["ok"].toBool(), true);
        QCOMPARE(res["line"].toInt(), 0);
    }

    void scriptManagement_and_template()
    {
        BotController ctrl;
        QString tpl = ctrl.scriptTemplate();
        QVERIFY(!tpl.isEmpty());

        ctrl.setScript(tpl);
        QCOMPARE(ctrl.currentScript(), tpl);

        // Pastikan skrip Python tidak di-wipe out
        QString pyScript = QStringLiteral("def on_bar(ctx):\n    return ctx.buy()\n");
        ctrl.setScript(pyScript);
        QCOMPARE(ctrl.currentScript(), pyScript);

        QVariantList scripts = ctrl.listScripts();
        // Memastikan tidak crash saat memindai folder skrip
        QVERIFY(scripts.size() >= 0);
    }

    void computeOverlays_works()
    {
        BotController ctrl;
        QVariantList available = ctrl.availableIndicators();
        QVERIFY(!available.isEmpty());

        // Buat mock data candle
        QVariantList mockCandles;
        double basePrice = 1.1000;
        for (int i = 0; i < 30; ++i) {
            QVariantMap c;
            c["t"] = 1700000000 + i * 300;
            c["o"] = basePrice;
            c["h"] = basePrice + 0.0010;
            c["l"] = basePrice - 0.0005;
            c["c"] = basePrice + 0.0002;
            c["tickVolume"] = 100;
            mockCandles.append(c);
            basePrice += 0.0001;
        }

        QStringList activeIds = {QStringLiteral("sma_50")};
        QVariantList overlays = ctrl.computeOverlays(mockCandles, activeIds);
        QVERIFY(!overlays.isEmpty());
        QVariantMap first = overlays.first().toMap();
        QCOMPARE(first[QStringLiteral("type")].toString(), QStringLiteral("overlay"));
        QCOMPARE(first[QStringLiteral("id")].toString(), QStringLiteral("sma_50"));
        QVariantList points = first[QStringLiteral("points")].toList();
        QCOMPARE(points.size(), 30);
    }

    void manualOrderQueueing_safeWhenDisconnected()
    {
        BotController ctrl;
        // Panggilan order manual saat offline tidak boleh meng-crash aplikasi
        ctrl.openManualOrder(QStringLiteral("EURUSDm"), QStringLiteral("buy"), 0.01, 100, 200);
        ctrl.openHedgeOrder(QStringLiteral("EURUSDm"), 0.02);
        ctrl.placePendingOrder(QStringLiteral("EURUSDm"), QStringLiteral("buy_limit"), 0.01, 1.05, 1.04, 1.06);
        ctrl.closePosition(12345);
        ctrl.closeAllPositions();
        ctrl.emergencyCloseAllReset();
        ctrl.deletePendingOrder(99999);

        // State tetap aman
        QCOMPARE(ctrl.connected(), false);
    }

    void journal_onJournal_and_clearJournal()
    {
        BotController ctrl;
        QCOMPARE(ctrl.journal().size(), 0);

        QVariantMap entry;
        entry["action"] = QStringLiteral("START");
        entry["symbol"] = QStringLiteral("EURUSDm");
        entry["detail"] = QStringLiteral("Mode Programmer aktif — Skrip strategi berjalan (TF: M5)");
        entry["ok"] = true;

        QSignalSpy journalSpy(&ctrl, &BotController::journalChanged);
        ctrl.onJournal(entry);

        QCOMPARE(ctrl.journal().size(), 1);
        QCOMPARE(journalSpy.count(), 1);

        QVariantMap saved = ctrl.journal().first().toMap();
        QCOMPARE(saved["action"].toString(), QStringLiteral("START"));
        QCOMPARE(saved["symbol"].toString(), QStringLiteral("EURUSDm"));
        QCOMPARE(saved["ok"].toBool(), true);
        QVERIFY(!saved["time"].toString().isEmpty());

        ctrl.clearJournal();
        QCOMPARE(ctrl.journal().size(), 0);
    }

    void updateManager_semverComparison()
    {
        QCOMPARE(UpdateManager::isNewerVersion(QStringLiteral("v1.0.1"), QStringLiteral("1.0.0")), true);
        QCOMPARE(UpdateManager::isNewerVersion(QStringLiteral("1.1.0"), QStringLiteral("1.0.9")), true);
        QCOMPARE(UpdateManager::isNewerVersion(QStringLiteral("2.0.0"), QStringLiteral("1.9.9")), true);
        QCOMPARE(UpdateManager::isNewerVersion(QStringLiteral("1.0.0"), QStringLiteral("1.0.0")), false);
        QCOMPARE(UpdateManager::isNewerVersion(QStringLiteral("0.9.9"), QStringLiteral("1.0.0")), false);
        QCOMPARE(UpdateManager::isNewerVersion(QStringLiteral("v1.0.0"), QStringLiteral("v1.0.1")), false);

        QList<int> parts = UpdateManager::parseSemver(QStringLiteral("v3.12.5"));
        QCOMPARE(parts.size(), 3);
        QCOMPARE(parts[0], 3);
        QCOMPARE(parts[1], 12);
        QCOMPARE(parts[2], 5);

        UpdateManager um;
        // isInstalledMode returns a valid boolean without crashing
        bool mode = um.isInstalledMode();
        Q_UNUSED(mode);
    }
};

QTEST_MAIN(TestController)
#include "test_controller.moc"
