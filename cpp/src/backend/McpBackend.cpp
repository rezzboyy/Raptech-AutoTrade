#include "backend/McpBackend.h"

#include "backend/McpParse.h"
#include "backend/SymbolUtils.h"

#include <QJsonArray>
#include <QLoggingCategory>
#include <QtGlobal>
#include <cmath>

using namespace McpParse;

McpBackend::McpBackend(const QString &endpoint, const QString &apiKey, int timeoutMs)
    : m_client(endpoint, apiKey, timeoutMs)
{
}

McpBackend::~McpBackend() = default;

// ----- Siklus koneksi -----

bool McpBackend::connect()
{
    McpReply init = m_client.initialize();
    if (!init.ok) {
        qCritical("Gagal inisialisasi MCP: %s", qUtf8Printable(init.errorMessage));
        return false;
    }

    Account acc = accountInfo();
    if (!acc.valid) {
        qCritical("MCP terhubung tapi info akun tidak terbaca.");
        return false;
    }

    m_tradeAllowed = acc.tradeAllowed;
    m_serverConnected = acc.serverConnected;
    m_expertsTradeAllowed = acc.expertsTradeAllowed;

    qInfo("Terhubung via MCP. Akun=%lld | Balance=%.2f %s | trade_allowed=%s "
          "(algo_trading=%s) | server_connected=%s",
          acc.login, acc.balance, qUtf8Printable(acc.currency),
          m_tradeAllowed ? "true" : "false",
          m_expertsTradeAllowed ? "true" : "false",
          m_serverConnected ? "true" : "false");

    if (!m_expertsTradeAllowed) {
        qWarning("[PERINGATAN] Algo Trading NONAKTIF di terminal MT5 "
                 "(experts_trade_allowed=false). Order tidak dapat dieksekusi. "
                 "Perbaiki: 1) tombol 'Algo Trading' HIJAU (Ctrl+E); 2) di RDP/VPS: "
                 "disconnect bot -> Algo Trading OFF lalu ON -> connect ulang; "
                 "3) Tools -> Options -> Expert Advisors -> 'Allow algorithmic trading'.");
    } else if (!m_tradeAllowed) {
        qWarning("MCP melaporkan trade TIDAK diizinkan (mcp_trade_allowed=false).");
    }
    if (!m_serverConnected) {
        qWarning("Terminal MT5 belum tersambung ke broker (server_connected=false). "
                 "Harga & monitoring mungkin kosong.");
    }

    m_connected = true;
    return true;
}

void McpBackend::disconnect()
{
    m_client.close();
    m_connected = false;
}

// ----- Info akun -----

Account McpBackend::accountInfo()
{
    Account out;
    McpReply r = m_client.callTool("get_trading_account_info");
    if (!r.ok) {
        qCritical("get_trading_account_info gagal: %s", qUtf8Printable(r.errorMessage));
        return out;
    }
    const QJsonObject acc = r.data.value("account").toObject();
    const QJsonObject term = r.data.value("terminal").toObject();
    if (acc.isEmpty())
        return out;

    const bool mcpTrade = term.value("mcp_trade_allowed").toBool(false);
    const bool experts = term.contains("experts_trade_allowed")
                             ? term.value("experts_trade_allowed").toBool(true)
                             : true;
    const bool serverConnected = term.value("server_connected").toBool(false);

    m_tradeAllowed = mcpTrade && experts;
    m_expertsTradeAllowed = experts;
    m_serverConnected = serverConnected;

    const QString server = acc.value("server").toString();
    out.login = static_cast<long long>(num(acc, {"login"}));
    out.balance = std::round(num(acc, {"balance"}) * 100.0) / 100.0;
    out.equity = std::round(num(acc, {"equity"}) * 100.0) / 100.0;
    out.margin = std::round(num(acc, {"margin"}) * 100.0) / 100.0;
    out.freeMargin = std::round(num(acc, {"margin_free"}) * 100.0) / 100.0;
    out.profit = std::round(num(acc, {"profit"}) * 100.0) / 100.0;
    out.currency = acc.value("currency").toString();
    out.server = server;
    out.accountType = SymbolUtils::classifyAccountType(acc.value("type").toString(), server);
    out.tradeAllowed = m_tradeAllowed;
    out.expertsTradeAllowed = experts;
    out.serverConnected = serverConnected;
    out.valid = true;
    return out;
}

// ----- Data pasar & simbol -----

void McpBackend::refreshSymbolCache(bool force)
{
    if (!m_symbolCache.isEmpty() && !force)
        return;
    McpReply r = m_client.callTool("get_marketwatch_symbols");
    if (!r.ok) {
        qCritical("get_marketwatch_symbols gagal: %s", qUtf8Printable(r.errorMessage));
        return;
    }
    QHash<QString, SymbolSpec> cache;
    const QJsonArray arr = r.data.value("symbols").toArray();
    for (const QJsonValue &v : arr) {
        const QJsonObject s = v.toObject();
        const QString name = s.value("symbol").toString();
        if (name.isEmpty())
            continue;
        SymbolSpec spec;
        spec.symbol = name;
        spec.digits = static_cast<int>(num(s, {"digits"}, 5));
        spec.point = num(s, {"point"});
        spec.volumeMin = num(s, {"volume_min"}, 0.01);
        spec.volumeMax = num(s, {"volume_max"});
        spec.volumeStep = num(s, {"volume_step"}, 0.01);
        spec.tickValue = num(s, {"tick_value"});
        spec.tickSize = num(s, {"tick_size"});
        spec.stopLevel = static_cast<int>(num(s, {"trade_stops_level"}));
        spec.valid = true;
        cache.insert(name, spec);
    }
    if (!cache.isEmpty())
        m_symbolCache = cache;
}

QStringList McpBackend::listSymbols(int limit)
{
    refreshSymbolCache();
    QStringList names = m_symbolCache.keys();
    if (limit > 0 && names.size() > limit)
        names = names.mid(0, limit);
    return names;
}

SymbolSpec McpBackend::symbolSpec(const QString &symbolIn)
{
    const QString symbol = symbolIn.trimmed();
    if (symbol.isEmpty())
        return {};
    if (!m_symbolCache.contains(symbol))
        refreshSymbolCache();
    if (m_symbolCache.contains(symbol))
        return m_symbolCache.value(symbol);
    const QString resolved = resolveSymbol(symbol);
    if (!resolved.isEmpty() && m_symbolCache.contains(resolved))
        return m_symbolCache.value(resolved);
    return {};
}

QString McpBackend::resolveSymbol(const QString &symbolIn)
{
    const QString symbol = symbolIn.trimmed();
    if (symbol.isEmpty())
        return {};
    refreshSymbolCache();
    QString resolved = SymbolUtils::resolveSymbolName(symbol, m_symbolCache.keys());
    if (!resolved.isEmpty())
        return resolved;
    const QStringList cands = SymbolUtils::candidateSymbolVariations(symbol);
    for (const QString &cand : cands) {
        McpReply r = m_client.callTool("add_marketwatch_symbol", {{"symbol", cand}});
        if (!r.ok)
            continue;
        refreshSymbolCache(true);
        if (m_symbolCache.contains(cand)) {
            qInfo("Simbol '%s' ditemukan & diaktifkan di Market Watch.", qUtf8Printable(cand));
            return cand;
        }
    }
    return {};
}

bool McpBackend::ensureSymbol(const QString &symbolIn)
{
    const QString symbol = symbolIn.trimmed();
    if (symbol.isEmpty())
        return false;
    if (m_symbolCache.contains(symbol))
        return true;
    McpReply r = m_client.callTool("add_marketwatch_symbol", {{"symbol", symbol}});
    if (r.ok) {
        refreshSymbolCache(true);
        if (m_symbolCache.contains(symbol))
            return true;
    }
    const QString resolved = resolveSymbol(symbol);
    if (!resolved.isEmpty() && m_symbolCache.contains(resolved))
        return true;
    qCritical("Simbol %s tidak ditemukan di broker/Market Watch.", qUtf8Printable(symbol));
    return false;
}

QVector<Candle> McpBackend::getRates(const QString &symbol, const QString &timeframeStr, int count)
{
    QVector<Candle> out;
    const QString period = SymbolUtils::mapTimeframeToPeriod(timeframeStr);
    const auto range = SymbolUtils::candleTimeRange(timeframeStr, count);
    QJsonObject args{
        {"symbol", symbol}, {"period", period},
        {"datetime_from", range.first}, {"datetime_to", range.second},
        {"limit", count}};
    McpReply r = m_client.callTool("get_chart_history", args);
    if (!r.ok) {
        qWarning("get_chart_history gagal untuk %s: %s",
                 qUtf8Printable(symbol), qUtf8Printable(r.errorMessage));
        return out;
    }
    const QJsonArray hist = r.data.value("history").toArray();
    int start = 0;
    if (count > 0 && hist.size() > count)
        start = hist.size() - count;
    for (int i = start; i < hist.size(); ++i) {
        const QJsonObject h = hist.at(i).toObject();
        Candle c;
        c.t = parseMt5TimeEpoch(h.value("time"));
        c.o = num(h, {"open"});
        c.h = num(h, {"high"});
        c.l = num(h, {"low"});
        c.c = num(h, {"close"});
        c.tickVolume = num(h, {"tick_volume"});
        c.spread = num(h, {"spread"});
        out << c;
    }
    return out;
}

Tick McpBackend::getTick(const QString &symbol)
{
    Tick out;
    const QVector<Candle> df = getRates(symbol, "M1", 1);
    if (df.isEmpty())
        return out;
    const Candle last = df.last();
    const double close = last.c;
    const double spPts = last.spread;
    const SymbolSpec spec = symbolSpec(symbol);
    const double point = spec.point;
    const int digits = spec.digits > 0 ? spec.digits : 5;

    auto roundTo = [](double v, int d) {
        const double f = std::pow(10.0, d);
        return std::round(v * f) / f;
    };

    if (spPts > 0 && point > 0) {
        out.bid = roundTo(close, digits);
        out.ask = roundTo(close + spPts * point, digits);
    } else {
        out.bid = close;
        out.ask = close;
    }
    out.time = last.t;
    out.valid = true;
    return out;
}

double McpBackend::spreadPoints(const QString &symbol, bool *ok)
{
    const auto range = SymbolUtils::candleTimeRange("M1", 2);
    QJsonObject args{
        {"symbol", symbol}, {"period", "M1"},
        {"datetime_from", range.first}, {"datetime_to", range.second}, {"limit", 2}};
    McpReply r = m_client.callTool("get_chart_history", args);
    if (!r.ok) {
        if (ok) *ok = false;
        return 0.0;
    }
    const QJsonArray hist = r.data.value("history").toArray();
    if (hist.isEmpty()) {
        if (ok) *ok = false;
        return 0.0;
    }
    if (ok) *ok = true;
    return num(hist.last().toObject(), {"spread"});
}

QVector<Position> McpBackend::positions(const QString &symbol)
{
    QVector<Position> out;
    McpReply r = m_client.callTool("get_trading_open_positions");
    if (!r.ok) {
        qCritical("get_trading_open_positions gagal: %s", qUtf8Printable(r.errorMessage));
        return out;
    }
    const QJsonArray arr = r.data.value("positions").toArray();
    for (const QJsonValue &v : arr) {
        Position p = normalizePosition(v.toObject());
        if (symbol.isEmpty() || p.symbol == symbol)
            out << p;
    }
    return out;
}

QVector<Deal> McpBackend::historyDeals(const QDateTime &from, const QDateTime &to)
{
    QVector<Deal> out;
    QJsonObject args{
        {"datetime_from", from.toString(Qt::ISODate)},
        {"datetime_to", to.toString(Qt::ISODate)}};
    McpReply r = m_client.callTool("get_trading_history_positions", args);
    if (!r.ok) {
        qCritical("get_trading_history_positions gagal: %s", qUtf8Printable(r.errorMessage));
        return out;
    }
    const QJsonArray arr = r.data.value("positions").toArray();
    for (const QJsonValue &v : arr)
        out << normalizeDeal(v.toObject());
    return out;
}

// ----- Trading (fail-safe) -----

QString McpBackend::tradingBlockedReason() const
{
    if (!m_expertsTradeAllowed)
        return QStringLiteral(
            "Algo Trading nonaktif di MT5 (experts_trade_allowed=false). Solusi cepat: "
            "tekan Ctrl+E di MT5. Solusi RDP/VPS: klik Algo Trading OFF -> ON, lalu "
            "Disconnect & Connect ulang di bot. Atau Tools -> Options -> Expert Advisors "
            "-> centang 'Allow algorithmic trading'.");
    if (!m_tradeAllowed)
        return QStringLiteral("MCP tidak mengizinkan trading (mcp_trade_allowed=false).");
    if (!m_serverConnected)
        return QStringLiteral("Terminal MT5 belum tersambung ke broker (server_connected=false).");
    return {};
}

OrderResult McpBackend::sendMarketOrder(const QString &symbol, const QString &side,
                                        double volume, double sl, double tp,
                                        long long magic, const QString &comment)
{
    Q_UNUSED(magic);
    OrderResult r;
    const QString blocked = tradingBlockedReason();
    if (!blocked.isEmpty()) {
        qWarning("Order %s %s dibatalkan: %s", qUtf8Printable(side),
                 qUtf8Printable(symbol), qUtf8Printable(blocked));
        r.message = blocked;
        return r;
    }
    const QString sideNorm = sideToMcp(side);
    if (sideNorm.isEmpty()) {
        r.message = QStringLiteral("Arah order tidak valid: %1").arg(side);
        qCritical("%s", qUtf8Printable(r.message));
        return r;
    }
    QJsonObject args{
        {"symbol", symbol}, {"type", sideNorm}, {"volume", volume},
        {"comment", clampComment(comment)}};
    if (sl > 0)
        args["sl"] = sl;
    if (tp > 0)
        args["tp"] = tp;

    McpReply reply = m_client.callTool("trade_send_market_order", args);
    if (!reply.ok) {
        r.message = friendlyTradeError(reply.errorMessage);
        qCritical("trade_send_market_order gagal: %s", qUtf8Printable(r.message));
        return r;
    }
    r = parseOrderResult(reply.data);
    if (r.ok) {
        qInfo("Order %s %.2f %s terkirim (ticket=%lld).",
              qUtf8Printable(sideNorm), volume, qUtf8Printable(symbol), r.ticket);
    } else {
        r.message = friendlyTradeError(r.message);
        qCritical("Order %s %s gagal: %s", qUtf8Printable(sideNorm),
                  qUtf8Printable(symbol), qUtf8Printable(r.message));
    }
    return r;
}

OrderResult McpBackend::closePosition(long long ticket, const QString &symbol)
{
    OrderResult r;
    if (ticket <= 0) {
        r.ticket = ticket;
        r.message = QStringLiteral("Nomor tiket posisi tidak valid (%1).").arg(ticket);
        qWarning("%s", qUtf8Printable(r.message));
        return r;
    }
    const QString blocked = tradingBlockedReason();
    if (!blocked.isEmpty()) {
        r.ticket = ticket;
        r.message = blocked;
        qWarning("Tutup posisi %lld dibatalkan: %s", ticket, qUtf8Printable(blocked));
        return r;
    }
    QJsonObject args{{"symbol", symbol}, {"position_ticket", double(ticket)}};
    McpReply reply = m_client.callTool("trade_close_single_position", args);
    if (!reply.ok) {
        r.ticket = ticket;
        r.message = friendlyTradeError(reply.errorMessage);
        qCritical("trade_close_single_position gagal: %s", qUtf8Printable(r.message));
        return r;
    }
    r = parseOrderResult(reply.data);
    r.ticket = ticket;
    if (r.ok) {
        qInfo("Posisi %lld (%s) ditutup.", ticket, qUtf8Printable(symbol));
    } else {
        r.message = friendlyTradeError(r.message);
        qCritical("Gagal menutup posisi %lld: %s", ticket, qUtf8Printable(r.message));
    }
    return r;
}

bool McpBackend::modifySlTp(long long ticket, const QString &symbol,
                            bool hasSl, double sl, bool hasTp, double tp)
{
    if (!tradingBlockedReason().isEmpty())
        return false;
    QJsonObject args{{"symbol", symbol}, {"position_ticket", double(ticket)}};
    if (hasSl)
        args["sl"] = sl;
    if (hasTp)
        args["tp"] = tp;
    McpReply reply = m_client.callTool("trade_modify_sl_tp", args);
    if (!reply.ok) {
        qCritical("trade_modify_sl_tp gagal untuk posisi %lld: %s",
                  ticket, qUtf8Printable(friendlyTradeError(reply.errorMessage)));
        return false;
    }
    OrderResult r = parseOrderResult(reply.data);
    if (r.ok)
        qInfo("SL/TP posisi %lld dimodifikasi.", ticket);
    else
        qCritical("Gagal memodifikasi SL/TP posisi %lld: %s",
                  ticket, qUtf8Printable(friendlyTradeError(r.message)));
    return r.ok;
}

OrderResult McpBackend::sendPendingOrder(const QString &symbol, const QString &orderType,
                                         double volume, double price, double sl, double tp,
                                         long long magic, const QString &comment)
{
    Q_UNUSED(magic);
    OrderResult r;
    const QString blocked = tradingBlockedReason();
    if (!blocked.isEmpty()) {
        r.message = blocked;
        qWarning("Pending order %s %s dibatalkan: %s", qUtf8Printable(orderType),
                 qUtf8Printable(symbol), qUtf8Printable(blocked));
        return r;
    }
    const QString ot = orderType.trimmed().toLower();
    if (!SymbolUtils::pendingOrderTypes().contains(ot)) {
        r.message = QStringLiteral("Tipe pending tidak valid: %1").arg(orderType);
        return r;
    }
    if (price <= 0) {
        r.message = QStringLiteral("Harga pending order harus > 0.");
        return r;
    }
    QJsonObject args{
        {"symbol", symbol}, {"type", ot}, {"volume", volume},
        {"price", price}, {"comment", clampComment(comment)}};
    if (sl > 0)
        args["sl"] = sl;
    if (tp > 0)
        args["tp"] = tp;
    McpReply reply = m_client.callTool("trade_send_pending_order", args);
    if (!reply.ok) {
        r.message = friendlyTradeError(reply.errorMessage);
        qCritical("trade_send_pending_order gagal: %s", qUtf8Printable(r.message));
        return r;
    }
    r = parseOrderResult(reply.data);
    if (r.ok)
        qInfo("Pending %s %.2f %s @ %.5f terpasang (ticket=%lld).",
              qUtf8Printable(ot), volume, qUtf8Printable(symbol), price, r.ticket);
    else {
        r.message = friendlyTradeError(r.message);
        qCritical("Pending order %s %s gagal: %s", qUtf8Printable(ot),
                  qUtf8Printable(symbol), qUtf8Printable(r.message));
    }
    return r;
}

OrderResult McpBackend::deletePendingOrder(long long ticket)
{
    OrderResult r;
    const QString blocked = tradingBlockedReason();
    if (!blocked.isEmpty()) {
        r.ticket = ticket;
        r.message = blocked;
        return r;
    }
    McpReply reply = m_client.callTool("trade_delete_order", {{"order_ticket", double(ticket)}});
    if (!reply.ok) {
        r.ticket = ticket;
        r.message = friendlyTradeError(reply.errorMessage);
        qCritical("trade_delete_order gagal: %s", qUtf8Printable(r.message));
        return r;
    }
    r = parseOrderResult(reply.data);
    r.ticket = ticket;
    if (r.ok)
        qInfo("Pending order %lld dihapus.", ticket);
    else {
        r.message = friendlyTradeError(r.message);
        qCritical("Gagal menghapus pending order %lld: %s", ticket, qUtf8Printable(r.message));
    }
    return r;
}

QVector<Order> McpBackend::pendingOrders(const QString &symbol)
{
    QVector<Order> out;
    McpReply r = m_client.callTool("get_trading_open_positions");
    if (!r.ok) {
        qCritical("get_trading_open_positions (orders) gagal: %s",
                  qUtf8Printable(r.errorMessage));
        return out;
    }
    const QJsonArray arr = r.data.value("orders").toArray();
    for (const QJsonValue &v : arr) {
        Order o = normalizeOrder(v.toObject());
        if (symbol.isEmpty() || o.symbol == symbol)
            out << o;
    }
    return out;
}
