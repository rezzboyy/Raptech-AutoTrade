#pragma once
#include <QMutex>
#include <QObject>
#include <QQueue>
#include <QString>
#include <QVariant>
#include <QVariantList>
#include <QVariantMap>
#include <atomic>

class BotEngine;
struct Settings;

// Perintah order manual dari UI (diantrikan, dieksekusi di worker thread).
struct ManualCommand {
    QString action; // market | pending | close_all | delete_order | close_ticket
    QString symbol;
    QString side;
    QString orderType;
    double volume = 0;
    double price = 0;
    double sl = 0;
    double tp = 0;
    long long ticket = 0;
};

// Loop tunggal monitoring + trading di satu thread (padanan _Worker di controller.py).
class Worker : public QObject
{
    Q_OBJECT
public:
    Worker(BotEngine *engine, Settings *settings, const QString &chartSymbol = QString());

    // Aman dipanggil dari thread lain.
    void setTrading(bool enabled) { m_trading.store(enabled); }
    void setChartSymbol(const QString &symbol);
    void requestStop() { m_running.store(false); }
    void enqueue(const ManualCommand &cmd);
    void enqueueClose(long long ticket);

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
    void connectedChanged(bool connected);
    void chartSymbolChanged(const QString &symbol);
    void stopped();

public slots:
    void run();

private:
    void drainCommands();

    BotEngine *m_engine;
    Settings *m_settings;
    std::atomic<bool> m_running{false};
    std::atomic<bool> m_trading{false};
    QString m_chartSymbol;
    std::atomic<bool> m_chartDirty{true};
    QMutex m_mutex; // lindungi m_chartSymbol & antrian
    QQueue<ManualCommand> m_queue;
    static constexpr int kChartInterval = 5;
};
