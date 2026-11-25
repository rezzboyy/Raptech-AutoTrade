#pragma once
#include <QString>
#include <QStringList>
#include <QVariantMap>

// Konfigurasi terpusat bot (padanan config/settings.py versi Python).
// Kredensial (login/password/server/mcpApiKey) TIDAK disimpan ke config.json.
struct Settings {
    // ----- Koneksi -----
    QString backend = "mcp";                                   // "native" | "mcp" | "sim"
    QString mcpEndpoint = "http://127.0.0.1:22346/mcp";
    QString mcpApiKey;                                          // dari mcp_secret.json / env
    QString theme = "dark";                                    // "dark" | "light"
    double simBalance = 10000.0;                               // saldo awal mode simulasi
    QString simScenario = "volatile";                          // skenario market simulasi
    int simSpreadPoints = 25;                                  // spread simulasi (points)

    // ----- Kredensial (tidak dipersist ke config.json) -----
    long long login = 0;
    QString password;
    QString server;
    QString path;

    // ----- Parameter trading (default akun Exness Standard: suffix 'm') -----
    QString symbol = "EURUSDm";
    QString timeframeStr = "M5";
    int magicNumber = 100200;
    double riskPerTrade = 0.01;
    int maxOpenPositions = 1;

    // ----- SL/TP -----
    QString slTpMode = "points";                               // "points" | "percent"
    int slPoints = 300;
    int tpPoints = 600;
    double slPercent = 0.5;
    double tpPercent = 1.0;
    bool virtualSltpEnabled = false;

    // ----- Trailing / Break-even -----
    bool trailingStopEnabled = false;
    int trailingStopPoints = 200;
    int trailingStepPoints = 50;
    bool breakEvenEnabled = false;
    int breakEvenTriggerPoints = 150;
    int breakEvenOffsetPoints = 10;

    // ----- Proteksi -----
    double dailyDrawdownLimit = 0.05;                          // 0 = nonaktif
    int maxDailyTrades = 10;                                   // 0 = tanpa batas
    int maxSpreadPoints = 0;
    double maxExposureLots = 0.0;
    double equityStopLoss = 0.0;
    int maxConsecutiveLosses = 0;

    // ----- Strategi / Mode Programmer (Single Official Engine) -----
    QString strategyName = "custom_script";
    QVariantMap strategyParams;                                // parameter strategi bawaan
    QString scriptName;
    QString scriptSource;

    int loopInterval = 15;

    // Daftar simbol (multi, pisah ',' atau ';'). TIDAK di-uppercase (Exness pakai suffix
    // huruf kecil, mis. 'EURUSDm'). Kosong -> ["EURUSDm"].
    QStringList symbolsList() const;
};

// Instance global tunggal (padanan `settings` di Python).
Settings &settings();
