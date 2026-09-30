#pragma once
#include <QHash>

#include "backend/TradingBackend.h"
#include "net/McpClient.h"

// Implementasi TradingBackend memakai McpClient (padanan mcp_backend.py).
class McpBackend : public TradingBackend
{
public:
    McpBackend(const QString &endpoint, const QString &apiKey, int timeoutMs = 15000);
    ~McpBackend() override;

    bool connect() override;
    void disconnect() override;
    Account accountInfo() override;
    QStringList listSymbols(int limit = 60) override;
    SymbolSpec symbolSpec(const QString &symbol) override;
    QString resolveSymbol(const QString &symbol) override;
    bool ensureSymbol(const QString &symbol) override;
    QVector<Candle> getRates(const QString &symbol, const QString &timeframeStr,
                             int count = 200) override;
    Tick getTick(const QString &symbol) override;
    double spreadPoints(const QString &symbol, bool *ok = nullptr) override;
    QVector<Position> positions(const QString &symbol = QString()) override;
    QVector<Deal> historyDeals(const QDateTime &from, const QDateTime &to) override;
    OrderResult sendMarketOrder(const QString &symbol, const QString &side, double volume,
                                double sl = 0.0, double tp = 0.0, long long magic = 0,
                                const QString &comment = "mt5bot") override;
    OrderResult closePosition(long long ticket, const QString &symbol) override;
    bool modifySlTp(long long ticket, const QString &symbol,
                    bool hasSl, double sl, bool hasTp, double tp) override;
    OrderResult sendPendingOrder(const QString &symbol, const QString &orderType,
                                 double volume, double price, double sl = 0.0,
                                 double tp = 0.0, long long magic = 0,
                                 const QString &comment = "mt5bot") override;
    OrderResult deletePendingOrder(long long ticket) override;
    QVector<Order> pendingOrders(const QString &symbol = QString()) override;

    bool isConnected() const { return m_connected; }
    // Alasan trading diblokir (fail-safe) atau QString() bila boleh. Dipakai juga di test.
    QString tradingBlockedReason() const;

    // Akses klien (untuk dependency injection / test lanjutan).
    McpClient &client() { return m_client; }

private:
    void refreshSymbolCache(bool force = false);

    McpClient m_client;
    bool m_connected = false;
    bool m_tradeAllowed = false;
    bool m_expertsTradeAllowed = true;
    bool m_serverConnected = false;
    QHash<QString, SymbolSpec> m_symbolCache;
};
