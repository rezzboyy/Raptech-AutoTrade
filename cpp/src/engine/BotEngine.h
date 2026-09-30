#pragma once
#include <QDateTime>
#include <QHash>
#include <QString>
#include <QVariantMap>
#include <QVector>
#include <functional>
#include <memory>

#include "backend/Models.h"
#include "strategy/Command.h"
#include "strategy/Strategy.h"

class TradingBackend;
struct Settings;

// Engine tingkat tinggi (padanan src/bot_engine.py) — TIDAK menjalankan loop
// sendiri; dipanggil oleh worker. Semua operasi lewat TradingBackend.
class BotEngine
{
public:
    BotEngine(TradingBackend *backend, Settings *settings);

    void setStrategy(std::unique_ptr<Strategy> strategy) { m_strategy = std::move(strategy); }
    Strategy *strategy() const { return m_strategy.get(); }

    // Jurnal aksi (opsional): action, symbol, detail, ok.
    std::function<void(const QString &, const QString &, const QString &, bool)> onJournal;

    void manageOpenPositions();
    void computeSlTp(const QString &symbol, const QString &signal, double entry,
                     const Command &ov, double &outSl, double &outTp);
    bool handleSignal(const QString &symbol, const QString &signal, const Command &ov);
    void checkVirtualExits();
    bool processTradingStep(); // false => hentikan auto-trading (proteksi terpicu)
    void executeCommand(const QString &symbol, const Command &cmd);
    int closeAll(const QString &symbol = QString());

    // ----- Siklus koneksi & monitoring (dipakai Worker) -----
    bool connect();
    void disconnect();
    Account pollAccount();
    QVector<Position> pollPositions();
    QVector<Order> pollOrders();
    QVector<Candle> pollCandles(const QString &symbol, int count = 150);
    QStringList listSymbols(int limit = 60);
    QVariantMap pollStats();
    QVariantList pollEquityCurve(double balance, double equity);

    // ----- Operasi order manual (dari UI) -----
    OrderResult manualMarketOrder(const QString &symbol, const QString &side, double volume,
                                  double sl = 0.0, double tp = 0.0);
    OrderResult placePendingOrder(const QString &symbol, const QString &orderType, double volume,
                                  double price, double sl = 0.0, double tp = 0.0);
    bool closeTicket(long long ticket);
    bool deletePending(long long ticket);

    // Jumlah SL/TP virtual aktif (untuk inspeksi/test).
    int virtualCount() const { return m_virtual.size(); }

    // Override waktu UTC (khusus test filter waktu/sesi). Invalid = pakai jam nyata.
    void setNowOverrideForTest(const QDateTime &dt) { m_nowOverride = dt; }

private:
    struct VirtualSltp { QString symbol; QString type; double sl = 0; double tp = 0; };

    QDateTime nowUtc() const;

    void updateVirtualSl(const Position &pos, VirtualSltp &v, const SymbolSpec &spec,
                         const Tick &tick);
    void journal(const QString &action, const QString &symbol, const QString &detail, bool ok);

    TradingBackend *m_backend;
    Settings *m_settings;
    std::unique_ptr<Strategy> m_strategy;
    QHash<long long, VirtualSltp> m_virtual;
    QHash<QString, QString> m_lastTradeBar;
    QHash<QString, int> m_lastTradeStep;
    int m_tradeSteps = 0;
    QDateTime m_nowOverride;
};
