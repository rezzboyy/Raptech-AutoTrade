#pragma once
#include <QDateTime>
#include <QString>
#include <QVector>

#include "backend/Models.h"

// Kontrak operasi MT5 yang dipakai bot (padanan Protocol TradingBackend di base.py).
// Implementasi: McpBackend (via server MCP). Native ditinggalkan di versi C++.
class TradingBackend
{
public:
    virtual ~TradingBackend() = default;

    virtual bool connect() = 0;
    virtual void disconnect() = 0;
    virtual Account accountInfo() = 0;
    virtual QStringList listSymbols(int limit = 60) = 0;
    virtual SymbolSpec symbolSpec(const QString &symbol) = 0;
    virtual QString resolveSymbol(const QString &symbol) = 0;
    virtual bool ensureSymbol(const QString &symbol) = 0;
    virtual QVector<Candle> getRates(const QString &symbol, const QString &timeframeStr,
                                     int count = 200) = 0;
    virtual Tick getTick(const QString &symbol) = 0;
    virtual double spreadPoints(const QString &symbol, bool *ok = nullptr) = 0;
    virtual QVector<Position> positions(const QString &symbol = QString()) = 0;
    virtual QVector<Deal> historyDeals(const QDateTime &from, const QDateTime &to) = 0;
    virtual OrderResult sendMarketOrder(const QString &symbol, const QString &side,
                                        double volume, double sl = 0.0, double tp = 0.0,
                                        long long magic = 0,
                                        const QString &comment = "mt5bot") = 0;
    virtual OrderResult closePosition(long long ticket, const QString &symbol) = 0;
    virtual bool modifySlTp(long long ticket, const QString &symbol,
                            bool hasSl, double sl, bool hasTp, double tp) = 0;
    virtual OrderResult sendPendingOrder(const QString &symbol, const QString &orderType,
                                         double volume, double price, double sl = 0.0,
                                         double tp = 0.0, long long magic = 0,
                                         const QString &comment = "mt5bot") = 0;
    virtual OrderResult deletePendingOrder(long long ticket) = 0;
    virtual QVector<Order> pendingOrders(const QString &symbol = QString()) = 0;
};
