#include <QtTest>
#include <QTemporaryDir>
#include <QJsonObject>

#include "core/Settings.h"
#include "core/ConfigStore.h"
#include "core/SecureStore.h"

// Test unit pustaka inti (Settings, ConfigStore, SecureStore).
class TestCore : public QObject
{
    Q_OBJECT

private slots:
    // ---------- Settings ----------
    void symbolsList_default()
    {
        Settings s;
        s.symbol = QString();
        QCOMPARE(s.symbolsList(), QStringList{QStringLiteral("EURUSDm")});
    }

    void symbolsList_noUppercase()
    {
        Settings s;
        s.symbol = "eurusdm";
        // TIDAK boleh dipaksa uppercase (Exness pakai suffix huruf kecil).
        QCOMPARE(s.symbolsList(), QStringList{QStringLiteral("eurusdm")});
    }

    void symbolsList_multiSplit()
    {
        Settings s;
        s.symbol = "EURUSDm, XAUUSDm ; BTCUSDm";
        QStringList expected{"EURUSDm", "XAUUSDm", "BTCUSDm"};
        QCOMPARE(s.symbolsList(), expected);
    }

    // ---------- ConfigStore ----------
    void configToJson_hasFields_noSecrets()
    {
        Settings s;
        s.mcpApiKey = "RAHASIA";
        s.login = 12345;
        const QJsonObject o = ConfigStore::toJson(s);
        QVERIFY(o.contains("symbol"));
        QVERIFY(o.contains("backend"));
        QVERIFY(o.contains("mcp_endpoint"));
        // Kredensial & api key tidak boleh dipersist.
        QVERIFY(!o.contains("mcp_api_key"));
        QVERIFY(!o.contains("login"));
        QVERIFY(!o.contains("password"));
    }

    void configValidate_ok()
    {
        Settings s;
        QVERIFY(ConfigStore::validate(ConfigStore::toJson(s), s).isEmpty());
    }

    void configValidate_badTimeframe()
    {
        Settings s;
        QJsonObject o;
        o["timeframe_str"] = "X9";
        QVERIFY(!ConfigStore::validate(o, s).isEmpty());
    }

    void configValidate_badRisk()
    {
        Settings s;
        QJsonObject o;
        o["risk_per_trade"] = 2.0; // > 1 tidak valid
        QVERIFY(!ConfigStore::validate(o, s).isEmpty());
    }

    void configApply_partial()
    {
        Settings s;
        const QString origSymbol = s.symbol;
        QJsonObject o;
        o["timeframe_str"] = "h1"; // harus jadi uppercase H1
        o["max_open_positions"] = 3;
        const QStringList errs = ConfigStore::apply(o, s);
        QVERIFY(errs.isEmpty());
        QCOMPARE(s.timeframeStr, QStringLiteral("H1"));
        QCOMPARE(s.maxOpenPositions, 3);
        // Field yang tak ada di obj tak berubah.
        QCOMPARE(s.symbol, origSymbol);
    }

    void configApply_invalid_noChange()
    {
        Settings s;
        const int orig = s.maxOpenPositions;
        QJsonObject o;
        o["max_open_positions"] = 5;
        o["risk_per_trade"] = 99.0; // invalid -> seluruh apply dibatalkan
        const QStringList errs = ConfigStore::apply(o, s);
        QVERIFY(!errs.isEmpty());
        QCOMPARE(s.maxOpenPositions, orig); // tidak berubah
    }

    void configSaveLoad_roundtrip()
    {
        QTemporaryDir dir;
        QVERIFY(dir.isValid());
        const QString path = dir.filePath("config.json");

        Settings a;
        a.symbol = "XAUUSDm";
        a.timeframeStr = "H4";
        a.maxOpenPositions = 2;
        a.riskPerTrade = 0.02;
        a.backend = "mcp";
        QVERIFY(ConfigStore::save(a, path));

        Settings b;
        QVERIFY(ConfigStore::load(b, path));
        QCOMPARE(b.symbol, QStringLiteral("XAUUSDm"));
        QCOMPARE(b.timeframeStr, QStringLiteral("H4"));
        QCOMPARE(b.maxOpenPositions, 2);
        QCOMPARE(b.riskPerTrade, 0.02);
        QCOMPARE(b.backend, QStringLiteral("mcp"));
    }

    // C1: mcp_secret.json simpan/muat + tidak menimpa key yang sudah ada.
    void mcpSecret_saveLoad()
    {
        QTemporaryDir dir;
        QVERIFY(dir.isValid());
        const QString path = dir.filePath("mcp_secret.json");

        Settings a;
        a.mcpApiKey = "RAHASIA123";
        a.mcpEndpoint = "http://127.0.0.1:9999/mcp";
        QVERIFY(ConfigStore::saveMcpSecret(a, path));

        Settings b; // key kosong -> harus terisi dari file
        QVERIFY(ConfigStore::loadMcpSecret(b, path));
        QCOMPARE(b.mcpApiKey, QStringLiteral("RAHASIA123"));
        QCOMPARE(b.mcpEndpoint, QStringLiteral("http://127.0.0.1:9999/mcp"));

        Settings c; // key sudah diset -> TIDAK ditimpa
        c.mcpApiKey = "SUDAH_ADA";
        QVERIFY(ConfigStore::loadMcpSecret(c, path));
        QCOMPARE(c.mcpApiKey, QStringLiteral("SUDAH_ADA"));
    }

    void mcpSecret_saveEmptyKeyRejected()
    {
        QTemporaryDir dir;
        Settings a; // apiKey kosong
        QVERIFY(!ConfigStore::saveMcpSecret(a, dir.filePath("x.json")));
    }

    // ---------- SecureStore ----------
    void secure_roundtrip()
    {
        QTemporaryDir dir;
        QVERIFY(dir.isValid());
        SecureStore::setKeyFilePath(dir.filePath(".secret_key"));

        const QString plain = "api-key-12345-XYZ";
        const QString token = SecureStore::encrypt(plain);
        QVERIFY(token.startsWith("v1:"));
        QVERIFY(token != plain);
        QCOMPARE(SecureStore::decrypt(token), plain);
    }

    void secure_emptyString()
    {
        QCOMPARE(SecureStore::encrypt(QString()), QString());
        QCOMPARE(SecureStore::decrypt(QString()), QString());
    }

    void secure_backwardCompatBase64()
    {
        QTemporaryDir dir;
        QVERIFY(dir.isValid());
        SecureStore::setKeyFilePath(dir.filePath(".secret_key"));

        // Format lama: base64 polos tanpa prefix v1:
        const QString legacy = QString::fromLatin1(QByteArray("hello").toBase64());
        QCOMPARE(SecureStore::decrypt(legacy), QStringLiteral("hello"));
    }
};

QTEST_APPLESS_MAIN(TestCore)
#include "test_core.moc"
