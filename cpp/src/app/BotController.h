#pragma once
#include <QObject>
#include <QString>
#include <QStringList>
#include <QVariantList>
#include <QVariantMap>

class QThread;
class Worker;
class BotEngine;
class TradingBackend;

// Jembatan bot <-> QML (padanan BotController di src/controller.py).
// Semua operasi MT5 terjadi di satu worker thread; UI diperbarui via sinyal.
class BotController : public QObject
{
    Q_OBJECT
    Q_PROPERTY(bool connected READ connected NOTIFY connectedChanged)
    Q_PROPERTY(bool trading READ trading NOTIFY tradingChanged)
    Q_PROPERTY(QString status READ status NOTIFY statusChanged)
    Q_PROPERTY(QString backend READ backend NOTIFY backendChanged)
    Q_PROPERTY(double balance READ balance NOTIFY accountChanged)
    Q_PROPERTY(double equity READ equity NOTIFY accountChanged)
    Q_PROPERTY(double margin READ margin NOTIFY accountChanged)
    Q_PROPERTY(double freeMargin READ freeMargin NOTIFY accountChanged)
    Q_PROPERTY(double profit READ profit NOTIFY accountChanged)
    Q_PROPERTY(QString currency READ currency NOTIFY accountChanged)
    Q_PROPERTY(QString accountType READ accountType NOTIFY accountChanged)
    Q_PROPERTY(QString accountServer READ accountServer NOTIFY accountChanged)
    Q_PROPERTY(bool serverConnected READ serverConnected NOTIFY accountChanged)
    Q_PROPERTY(bool tradeAllowed READ tradeAllowed NOTIFY accountChanged)
    Q_PROPERTY(QString chartSymbol READ chartSymbol NOTIFY chartSymbolChanged)
    Q_PROPERTY(QVariantMap stats READ stats NOTIFY statsChanged)
    Q_PROPERTY(QVariantList equityCurve READ equityCurve NOTIFY equityChanged)
    Q_PROPERTY(QVariantList journal READ journal NOTIFY journalChanged)

public:
    explicit BotController(QObject *parent = nullptr);
    ~BotController() override;

    // Untuk test: suntikkan backend palsu (controller mengambil kepemilikan).
    void setInjectedBackend(TradingBackend *backend);

    bool connected() const { return m_connected; }
    bool trading() const { return m_trading; }
    QString status() const { return m_status; }
    QString backend() const;
    double balance() const { return m_balance; }
    double equity() const { return m_equity; }
    double margin() const { return m_margin; }
    double freeMargin() const { return m_freeMargin; }
    double profit() const { return m_profit; }
    QString currency() const { return m_currency; }
    QString accountType() const { return m_accountType; }
    QString accountServer() const { return m_accountServer; }
    bool serverConnected() const { return m_serverConnected; }
    bool tradeAllowed() const { return m_tradeAllowed; }
    QString chartSymbol() const { return m_chartSymbol; }
    QVariantMap stats() const { return m_stats; }
    QVariantList equityCurve() const { return m_equityCurve; }
    QVariantList journal() const { return m_journal; }

public slots:
    void connectBot();
    void disconnectBot();
    void logoutAccount();
    void setTrading(bool enabled);
    void closePosition(qlonglong ticket);
    void openManualOrder(const QString &symbol, const QString &side, double volume,
                         double sl = 0.0, double tp = 0.0);
    void placePendingOrder(const QString &symbol, const QString &orderType, double volume,
                           double price, double sl = 0.0, double tp = 0.0);
    void closeAllPositions();
    void deletePendingOrder(qlonglong ticket);
    void setChartSymbol(const QString &symbol);
    void setBackend(const QString &name);
    void setMcpConfig(const QString &endpoint, const QString &apiKey);
    void refreshStats();
    QVariantMap getConfig();
    QVariantMap getMcpConfig();
    bool applyConfig(const QVariantMap &cfg);
    bool saveConfig(const QVariantMap &cfg);
    QVariantList getStrategies();
    // Login/koneksi MCP + profil.
    bool connectMcp(const QVariantMap &cfg, const QString &saveName = QString());
    QVariantList listMcpProfiles();
    QVariantMap loadMcpProfileFile(const QString &url);
    bool deleteMcpProfile(const QString &file);
    // Stub native (versi C++ MCP-only) agar UI Login tetap kompatibel.
    QVariantList listProfiles();
    QVariantMap loadProfileFile(const QString &url);
    bool deleteProfile(const QString &file);
    bool loginAndConnect(const QVariantMap &creds, const QString &saveName = QString());
    QString scriptTemplate();
    QVariantMap validateScript(const QString &source);
    void setScript(const QString &source);
    QString currentScript();
    QVariantList apiReference();
    QVariantList settingsReference();
    QString settingsTemplate();
    // Manajemen file skrip (folder "scripts", ekstensi .js).
    QVariantList listScripts();
    QString loadScript(const QString &name);
    QString loadScriptFile(const QString &url);
    bool saveScript(const QString &name, const QString &source);
    bool exportJournalCsv(const QString &path);
    bool exportLogs(const QString &path);
    void clearJournal();
    void clearLogs();

signals:
    void logMessage(const QString &msg);
    void statusChanged(const QString &status);
    void connectedChanged(bool connected);
    void tradingChanged(bool trading);
    void accountChanged();
    void positionsChanged(const QVariantList &positions);
    void ordersChanged(const QVariantList &orders);
    void configError(const QString &msg);
    void backendChanged(const QString &name);
    void chartUpdated(const QString &symbol, const QVariant &payload);
    void symbolsAvailable(const QStringList &symbols);
    void chartSymbolChanged(const QString &symbol);
    void statsChanged();
    void equityChanged();
    void journalChanged();
    void journalEntry(const QVariantMap &entry);
    void profilesChanged(const QVariantList &profiles);
    void mcpProfilesChanged(const QVariantList &profiles);

private slots:
    void onJournal(const QVariantMap &entry);
    void onAccount(const QVariantMap &account);
    void onPositions(const QVariantList &positions);
    void onOrders(const QVariantList &orders);
    void onCandles(const QString &symbol, const QVariant &payload);
    void onSymbols(const QStringList &symbols);
    void onStats(const QVariantMap &stats);
    void onEquity(const QVariantList &curve);
    void onAutoDisabled(const QString &reason);
    void onWorkerConnected(bool connected);
    void onWorkerChartSymbol(const QString &symbol);
    void onWorkerStopped();

private:
    void setStatus(const QString &s);
    void setConnectedState(bool v);
    void setTradingState(bool v);
    void buildStrategy();

    bool m_connected = false;
    bool m_trading = false;
    QString m_status = QStringLiteral("Terputus");

    double m_balance = 0, m_equity = 0, m_margin = 0, m_freeMargin = 0, m_profit = 0;
    QString m_currency, m_accountType = QStringLiteral("?"), m_accountServer;
    bool m_serverConnected = false, m_tradeAllowed = false;
    QString m_chartSymbol;
    QVariantMap m_stats;
    QVariantList m_equityCurve;
    QVariantList m_journal;

    QThread *m_thread = nullptr;
    Worker *m_worker = nullptr;
    BotEngine *m_engine = nullptr;
    TradingBackend *m_backend = nullptr;
    bool m_ownBackend = false;
    TradingBackend *m_injectedBackend = nullptr;
};
