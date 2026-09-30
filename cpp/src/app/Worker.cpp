#include "app/Worker.h"

#include "core/Settings.h"
#include "engine/BotEngine.h"

#include <QThread>

namespace {

QVariantMap accountToMap(const Account &a)
{
    return {
        {"balance", a.balance}, {"equity", a.equity}, {"margin", a.margin},
        {"free_margin", a.freeMargin}, {"profit", a.profit}, {"currency", a.currency},
        {"account_type", a.accountType}, {"server", a.server},
        {"server_connected", a.serverConnected}, {"trade_allowed", a.tradeAllowed}};
}

QVariantMap positionToMap(const Position &p)
{
    return {
        {"ticket", static_cast<qlonglong>(p.ticket)}, {"symbol", p.symbol},
        {"type", p.type}, {"volume", p.volume}, {"price_open", p.priceOpen},
        {"price_current", p.priceCurrent}, {"sl", p.sl}, {"tp", p.tp},
        {"profit", p.profit}, {"magic", static_cast<qlonglong>(p.magic)}};
}

QVariantMap orderToMap(const Order &o)
{
    return {
        {"ticket", static_cast<qlonglong>(o.ticket)}, {"symbol", o.symbol},
        {"type", o.type}, {"volume", o.volume}, {"price", o.price},
        {"sl", o.sl}, {"tp", o.tp}, {"magic", static_cast<qlonglong>(o.magic)}};
}

QVariantMap candleToMap(const Candle &c)
{
    return {{"t", static_cast<qlonglong>(c.t)}, {"o", c.o}, {"h", c.h}, {"l", c.l}, {"c", c.c}};
}

} // namespace

Worker::Worker(BotEngine *engine, Settings *settings, const QString &chartSymbol)
    : m_engine(engine), m_settings(settings), m_chartSymbol(chartSymbol)
{
}

void Worker::setChartSymbol(const QString &symbol)
{
    QMutexLocker lock(&m_mutex);
    m_chartSymbol = symbol;
    m_chartDirty.store(true);
}

void Worker::enqueue(const ManualCommand &cmd)
{
    QMutexLocker lock(&m_mutex);
    m_queue.enqueue(cmd);
}

void Worker::enqueueClose(long long ticket)
{
    ManualCommand c;
    c.action = "close_ticket";
    c.ticket = ticket;
    enqueue(c);
}

void Worker::run()
{
    bool connected = false;
    connected = m_engine->connect();
    if (!connected) {
        emit connectedChanged(false);
        emit stopped();
        return;
    }

    m_running.store(true);
    emit connectedChanged(true);

    // Jurnal aksi skrip -> sinyal Qt.
    m_engine->onJournal = [this](const QString &action, const QString &symbol,
                                 const QString &detail, bool ok) {
        emit journalUpdated(QVariantMap{
            {"action", action}, {"symbol", symbol}, {"detail", detail}, {"ok", ok}});
    };

    emit symbolsListed(m_engine->listSymbols());
    {
        QMutexLocker lock(&m_mutex);
        if (m_chartSymbol.isEmpty() || m_chartSymbol != m_settings->symbol) {
            m_chartSymbol = m_settings->symbol;
            emit chartSymbolChanged(m_chartSymbol);
        }
    }

    int tick = 0;
    while (m_running.load()) {
        const Account acc = m_engine->pollAccount();
        if (acc.valid)
            emit accountUpdated(accountToMap(acc));

        const QVector<Position> positions = m_engine->pollPositions();
        QVariantList posList;
        for (const Position &p : positions)
            posList << positionToMap(p);
        emit positionsUpdated(posList);

        m_engine->checkVirtualExits();

        if (m_chartDirty.load() || tick % kChartInterval == 0) {
            QString sym;
            { QMutexLocker lock(&m_mutex); sym = m_chartSymbol; }
            const QVector<Candle> candles = m_engine->pollCandles(sym);
            QVariantList candleList;
            for (const Candle &c : candles)
                candleList << candleToMap(c);
            // Garis posisi (entry/SL/TP) untuk simbol chart.
            QVariantList posLines;
            for (const Position &p : m_engine->pollPositions())
                if (p.symbol == sym)
                    posLines << QVariantMap{{"type", p.type}, {"open", p.priceOpen},
                                            {"sl", p.sl}, {"tp", p.tp}};
            QVariantMap payload{{"candles", candleList}, {"overlays", QVariantList{}},
                                {"positions", posLines}, {"trades", QVariantList{}}};
            emit candlesUpdated(sym, payload);

            emit statsUpdated(m_engine->pollStats());
            emit equityUpdated(m_engine->pollEquityCurve(acc.balance, acc.equity));

            QVariantList orderList;
            for (const Order &o : m_engine->pollOrders())
                orderList << orderToMap(o);
            emit ordersUpdated(orderList);

            m_chartDirty.store(false);
        }

        drainCommands();

        if (m_trading.load() && tick % std::max(1, m_settings->loopInterval) == 0) {
            const bool ok = m_engine->processTradingStep();
            if (!ok) {
                m_trading.store(false);
                emit autoTradingDisabled(
                    QStringLiteral("Proteksi risiko terpicu (drawdown harian / equity "
                                   "cut-loss). Auto trading dinonaktifkan demi proteksi modal."));
            }
        }

        ++tick;
        // Tidur ~1 detik bertahap agar stop cepat direspons.
        for (int i = 0; i < 10 && m_running.load(); ++i)
            QThread::msleep(100);
    }

    m_engine->disconnect();
    emit connectedChanged(false);
    emit stopped();
}

void Worker::drainCommands()
{
    while (true) {
        ManualCommand cmd;
        {
            QMutexLocker lock(&m_mutex);
            if (m_queue.isEmpty())
                break;
            cmd = m_queue.dequeue();
        }
        if (cmd.action == "market")
            m_engine->manualMarketOrder(cmd.symbol, cmd.side, cmd.volume, cmd.sl, cmd.tp);
        else if (cmd.action == "pending")
            m_engine->placePendingOrder(cmd.symbol, cmd.orderType, cmd.volume, cmd.price, cmd.sl, cmd.tp);
        else if (cmd.action == "close_all")
            m_engine->closeAll(cmd.symbol);
        else if (cmd.action == "delete_order")
            m_engine->deletePending(cmd.ticket);
        else if (cmd.action == "close_ticket")
            m_engine->closeTicket(cmd.ticket);
    }
}
