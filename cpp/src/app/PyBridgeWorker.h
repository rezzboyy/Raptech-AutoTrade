#pragma once
#include <QByteArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QObject>
#include <QProcess>
#include <QString>
#include <QStringList>
#include <QVariant>
#include <QVariantList>
#include <QVariantMap>

// Perintah order manual dari UI (diantrikan, dieksekusi di backend Python).
struct ManualCommand {
    QString action; // market | pending | close_all | delete_order
    QString symbol;
    QString side;
    QString orderType;
    double volume = 0;
    double price = 0;
    double sl = 0;
    double tp = 0;
    long long ticket = 0;
};

// Jembatan asinkron C++ <-> Python Backend (stdio NDJSON IPC).
// Memancarkan sinyal yang sama persis seperti Worker C++ agar BotController & QML
// dapat menggunakannya tanpa perubahan kontrak UI.
class PyBridgeWorker : public QObject
{
    Q_OBJECT
public:
    explicit PyBridgeWorker(QObject *parent = nullptr);
    ~PyBridgeWorker() override;

    bool isRunning() const;
    bool startBridge();
    void stopBridge();

    // Kontrak antarmuka yang dipanggil BotController (padanan Worker)
    void connectBackend(const QVariantMap &params);
    void disconnectBackend();
    void setTrading(bool enabled);
    void reloadStrategy();
    void setChartSymbol(const QString &symbol);
    void setTimeframe(const QString &tf);
    void runScriptSimulation(const QVariantMap &params);
    void requestStop();
    void enqueue(const ManualCommand &cmd);
    void enqueueClose(long long ticket);
    void wakeWorker();

    // Akses sinkron / utilitas
    void sendCommand(const QString &method, const QVariantMap &params = QVariantMap());
    QString findStandaloneBridge() const;
    QString findPythonExecutable() const;
    QString findBridgeScript() const;

signals:
    void accountUpdated(const QVariantMap &account);
    void positionsUpdated(const QVariantList &positions);
    void ordersUpdated(const QVariantList &orders);
    void journalUpdated(const QVariantMap &entry);
    void candlesUpdated(const QString &symbol, const QVariant &payload);
    void symbolsListed(const QStringList &symbols);
    void statsUpdated(const QVariantMap &stats);
    void equityUpdated(const QVariantList &curve);
    void autoTradingDisabled(const QString &reason);
    void orderFeedback(bool ok, const QString &message);
    void connectedChanged(bool connected);
    void chartSymbolChanged(const QString &symbol);
    void timeframeChanged(const QString &timeframe);
    void simulationResult(const QVariantMap &result);
    void logMessage(const QString &msg);
    void stopped();

private slots:
    void onReadyReadStdout();
    void onReadyReadStderr();
    void onProcessFinished(int exitCode, QProcess::ExitStatus exitStatus);
    void onProcessError(QProcess::ProcessError error);

private:
    void handleEvent(const QString &event, const QVariant &data);
    void handleResponse(long long id, const QVariant &result, const QString &error);

    QProcess *m_process = nullptr;
    QByteArray m_readBuffer;
    long long m_nextId = 1;
    bool m_connected = false;
    bool m_trading = false;
    QString m_chartSymbol;
};
