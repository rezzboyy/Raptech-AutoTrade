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

        // Strategi resmi tunggal: Mode Programmer (custom_script)
        QVariantList strats = ctrl.getStrategies();
        QCOMPARE(strats.size(), 1);
        QCOMPARE(strats[0].toMap().value(QStringLiteral("name")).toString(), QStringLiteral("custom_script"));
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

        // Uji Bantuan API & SETTINGS Mode Programmer
        QVERIFY(!ctrl.apiReference().isEmpty());
        QVERIFY(!ctrl.settingsReference().isEmpty());
        QVERIFY(!ctrl.settingsTemplate().isEmpty());

        // Uji simpan -> daftar -> muat -> hapus skrip di Mode Programmer
        const QString tmpName = QStringLiteral("smoke_prog_test");
        QVERIFY(ctrl.saveScript(tmpName, pyScript));
        QVERIFY(ctrl.listScripts().contains(tmpName));
        QCOMPARE(ctrl.loadScript(tmpName), pyScript);
        QVERIFY(ctrl.deleteScript(tmpName));
        QVERIFY(!ctrl.listScripts().contains(tmpName));
        QDir().rmdir(QStringLiteral("scripts"));
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

    void resetStats_clearsStatsAndEquity()
    {
        BotController ctrl;
        QSignalSpy spyStats(&ctrl, &BotController::statsChanged);
        QSignalSpy spyEquity(&ctrl, &BotController::equityChanged);

        ctrl.resetStats();

        QCOMPARE(spyStats.count(), 1);
        QCOMPARE(spyEquity.count(), 1);
        QVariantMap s = ctrl.stats();
        QCOMPARE(s.value(QStringLiteral("win_rate")).toDouble(), 0.0);
        QCOMPARE(s.value(QStringLiteral("net_profit")).toDouble(), 0.0);
        QCOMPARE(s.value(QStringLiteral("total_trades")).toInt(), 0);
        QCOMPARE(ctrl.equityCurve().size(), 0);
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

    void theme_and_simBackend()
    {
        BotController ctrl;
        const QString origTheme = ctrl.theme();
        const QString origBackend = ctrl.backend();

        QSignalSpy spyTheme(&ctrl, &BotController::themeChanged);
        ctrl.setTheme(QStringLiteral("light"));
        QCOMPARE(ctrl.theme(), QStringLiteral("light"));
        QCOMPARE(spyTheme.count(), origTheme == QStringLiteral("light") ? 0 : 1);

        QSignalSpy spyBackend(&ctrl, &BotController::backendChanged);
        ctrl.setBackend(QStringLiteral("sim"));
        QCOMPARE(ctrl.backend(), QStringLiteral("sim"));
        QCOMPARE(spyBackend.count(), origBackend == QStringLiteral("sim") ? 0 : 1);

        // Pulihkan default
        ctrl.setTheme(origTheme);
        ctrl.setBackend(origBackend);
    }

    void inspectScriptVariables_checksValidAndWarnings()
    {
        BotController ctrl;
        const QString good = QStringLiteral(
            "SETTINGS = {'volume': 0.05, 'max_spread_points': 40}\n"
            "PARAMS = [{'key': 'fast', 'default': 12}]\n"
            "def on_bar(ctx):\n"
            "    v = ctx.ema(ctx.close, ctx.params.fast)\n"
            "    if ctx.crossover(v, ctx.close):\n"
            "        return ctx.buy()\n"
            "    return None\n"
        );
        QVariantMap okRes = ctrl.inspectScriptVariables(good);
        QCOMPARE(okRes["ok"].toBool(), true);
        QCOMPARE(okRes["hasWarnings"].toBool(), false);
        QCOMPARE(okRes["status"].toString(), QStringLiteral("VALID"));

        const QString badVars = QStringLiteral(
            "SETTINGS = {'typo_key': 1}\n"
            "def on_bar(ctx):\n"
            "    return ctx.non_existent_api()\n"
        );
        QVariantMap warnRes = ctrl.inspectScriptVariables(badVars);
        QCOMPARE(warnRes["ok"].toBool(), true);
        QCOMPARE(warnRes["hasWarnings"].toBool(), true);
        QCOMPARE(warnRes["status"].toString(), QStringLiteral("PERINGATAN"));
        QVERIFY(warnRes["unknownSettings"].toStringList().contains(QStringLiteral("typo_key")));
        QVERIFY(warnRes["unknownCtxMembers"].toStringList().contains(QStringLiteral("non_existent_api")));
    }

    void simConnectAndLogout_noCrashAndAuthLoading()
    {
        BotController ctrl;
        const QString origBackend = ctrl.backend();

        QVariantMap cfg;
        cfg[QStringLiteral("symbol")] = QStringLiteral("XAUUSDm");
        cfg[QStringLiteral("balance")] = 10000.0;
        cfg[QStringLiteral("scenario")] = QStringLiteral("volatile");
        cfg[QStringLiteral("spread_points")] = 25;

        QSignalSpy spyAuth(&ctrl, &BotController::authStateChanged);
        QVERIFY(ctrl.connectSim(cfg));
        QCOMPARE(ctrl.authBusy(), true);
        QCOMPARE(ctrl.authAction(), QStringLiteral("login"));
        QVERIFY(!ctrl.authMessage().isEmpty());
        QVERIFY(spyAuth.count() >= 1);

        // Tunggu sesi simulasi terhubung (maks 8 detik)
        QTRY_COMPARE_WITH_TIMEOUT(ctrl.connected(), true, 8000);
        QCOMPARE(ctrl.authBusy(), false);
        QVERIFY(!ctrl.authMessage().isEmpty());

        // Uji logout -> HARUS kembali terputus dengan bersih tanpa crash/force close
        ctrl.logoutAccount();
        QCOMPARE(ctrl.authBusy(), true);
        QCOMPARE(ctrl.authAction(), QStringLiteral("logout"));

        QTRY_COMPARE_WITH_TIMEOUT(ctrl.connected(), false, 5000);
        QTRY_COMPARE_WITH_TIMEOUT(ctrl.authBusy(), false, 5000);
        QCOMPARE(ctrl.status(), QStringLiteral("Terputus"));
        QVERIFY(ctrl.authMessage().contains(QStringLiteral("Logout"), Qt::CaseInsensitive));

        // Pastikan bisa login lagi setelah logout
        QVERIFY(ctrl.connectSim(cfg));
        QTRY_COMPARE_WITH_TIMEOUT(ctrl.connected(), true, 8000);
        ctrl.logoutAccount();
        QTRY_COMPARE_WITH_TIMEOUT(ctrl.connected(), false, 5000);

        ctrl.setBackend(origBackend);
    }
};

QTEST_MAIN(TestController)
#include "test_controller.moc"
