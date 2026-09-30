#include <QtTest>
#include <QTcpServer>
#include <QTcpSocket>
#include <QHash>
#include <QHostAddress>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTimeZone>

#include "backend/McpBackend.h"
#include "backend/McpParse.h"
#include "backend/SymbolUtils.h"

using namespace McpParse;
using namespace SymbolUtils;

// ---------------- Mock server MCP untuk backend ----------------
class MockMt5 : public QObject
{
    Q_OBJECT
public:
    bool expertsTradeAllowed = true;
    bool mcpTradeAllowed = true;
    bool serverConnected = true;

    MockMt5()
    {
        server.listen(QHostAddress::LocalHost, 0);
        connect(&server, &QTcpServer::newConnection, this, &MockMt5::onConn);
    }
    quint16 port() const { return server.serverPort(); }
    QString url() const { return QStringLiteral("http://127.0.0.1:%1/mcp").arg(port()); }

private slots:
    void onConn()
    {
        QTcpSocket *sock = server.nextPendingConnection();
        connect(sock, &QTcpSocket::readyRead, this, [this, sock]() { onData(sock); });
        connect(sock, &QTcpSocket::disconnected, sock, &QObject::deleteLater);
    }

    void onData(QTcpSocket *sock)
    {
        m_buf[sock] += sock->readAll();
        QByteArray &buf = m_buf[sock];
        const int idx = buf.indexOf("\r\n\r\n");
        if (idx < 0)
            return;
        int contentLen = 0;
        for (const QByteArray &line : buf.left(idx).split('\n')) {
            const QByteArray l = line.trimmed();
            if (l.toLower().startsWith("content-length:"))
                contentLen = l.mid(15).trimmed().toInt();
        }
        QByteArray body = buf.mid(idx + 4);
        if (body.size() < contentLen)
            return;
        const QJsonObject req = QJsonDocument::fromJson(body).object();
        const QString method = req.value("method").toString();
        m_buf.remove(sock);

        if (method == "initialize") {
            sendRpc(sock, QJsonObject{{"serverInfo", QJsonObject{{"name", "mt5"}}}}, "sess-1");
            return;
        }
        if (method == "notifications/initialized") {
            sendHttp(sock, 200, "{}");
            return;
        }
        if (method == "tools/call") {
            const QJsonObject params = req.value("params").toObject();
            handleTool(sock, params.value("name").toString(), params.value("arguments").toObject());
            return;
        }
        sendRpc(sock, QJsonObject{});
    }

private:
    void handleTool(QTcpSocket *sock, const QString &name, const QJsonObject &args)
    {
        if (name == "get_trading_account_info") {
            QJsonObject account{
                {"login", 416355944}, {"balance", 482.891}, {"equity", 480.0},
                {"margin", 10.0}, {"margin_free", 470.0}, {"profit", -2.5},
                {"currency", "USD"}, {"server", "Exness-MT5Trial14"}, {"type", "real"}};
            QJsonObject terminal{
                {"mcp_trade_allowed", mcpTradeAllowed},
                {"experts_trade_allowed", expertsTradeAllowed},
                {"server_connected", serverConnected}};
            sendToolJson(sock, QJsonObject{{"account", account}, {"terminal", terminal}});
            return;
        }
        if (name == "get_marketwatch_symbols") {
            QJsonArray symbols{
                QJsonObject{{"symbol", "EURUSDm"}, {"digits", 5}, {"point", 0.00001},
                            {"volume_min", 0.01}, {"volume_step", 0.01},
                            {"trade_stops_level", 10}},
                QJsonObject{{"symbol", "XAUUSDm"}, {"digits", 2}, {"point", 0.01}}};
            sendToolJson(sock, QJsonObject{{"symbols", symbols}});
            return;
        }
        if (name == "trade_send_market_order") {
            // Sukses via retcode DONE + order ticket.
            sendToolJson(sock, QJsonObject{{"retcode", 10009}, {"order", 55}});
            return;
        }
        if (name == "get_trading_open_positions") {
            QJsonArray positions{
                QJsonObject{{"ticket", 1001}, {"symbol", "EURUSDm"}, {"type", "0"},
                            {"volume", 0.10}, {"price_open", 1.1000},
                            {"price_current", 1.1010}, {"profit", 1.23}}};
            sendToolJson(sock, QJsonObject{{"positions", positions}, {"orders", QJsonArray{}}});
            return;
        }
        Q_UNUSED(args);
        sendToolJson(sock, QJsonObject{});
    }

    // Kirim result RPC berisi content[0].text = JSON(payload).
    void sendToolJson(QTcpSocket *sock, const QJsonObject &payload)
    {
        const QByteArray inner = QJsonDocument(payload).toJson(QJsonDocument::Compact);
        QJsonObject content{{"type", "text"}, {"text", QString::fromUtf8(inner)}};
        QJsonObject result{{"content", QJsonArray{content}}};
        sendRpc(sock, result);
    }

    void sendRpc(QTcpSocket *sock, const QJsonObject &result, const QByteArray &sessionId = {})
    {
        QJsonObject rpc{{"jsonrpc", "2.0"}, {"id", 1}, {"result", result}};
        sendHttp(sock, 200, QJsonDocument(rpc).toJson(QJsonDocument::Compact), sessionId);
    }

    void sendHttp(QTcpSocket *sock, int status, const QByteArray &body,
                  const QByteArray &sessionId = {})
    {
        QByteArray resp = "HTTP/1.1 " + QByteArray::number(status) + " OK\r\n";
        resp += "Content-Type: application/json\r\n";
        if (!sessionId.isEmpty())
            resp += "Mcp-Session-Id: " + sessionId + "\r\n";
        resp += "Content-Length: " + QByteArray::number(body.size()) + "\r\n";
        resp += "Connection: close\r\n\r\n";
        resp += body;
        sock->write(resp);
        sock->flush();
        sock->disconnectFromHost();
    }

    QTcpServer server;
    QHash<QTcpSocket *, QByteArray> m_buf;
};

// ---------------- Test cases ----------------
class TestBackend : public QObject
{
    Q_OBJECT

private slots:
    // ----- SymbolUtils (pure) -----
    void classifyAccount()
    {
        QCOMPARE(classifyAccountType("real", "Exness-MT5Trial14"), QStringLiteral("DEMO"));
        QCOMPARE(classifyAccountType("real", "Exness-Real"), QStringLiteral("REAL"));
        QCOMPARE(classifyAccountType("demo", "SomeServer"), QStringLiteral("DEMO"));
        QCOMPARE(classifyAccountType("contest", "X"), QStringLiteral("CONTEST"));
        QCOMPARE(classifyAccountType("", ""), QStringLiteral("?"));
    }

    void timeframe()
    {
        QCOMPARE(mapTimeframeToPeriod("m5"), QStringLiteral("M5"));
        QCOMPARE(mapTimeframeToPeriod("H4"), QStringLiteral("H4"));
        QCOMPARE(mapTimeframeToPeriod("XX"), QStringLiteral("M5"));
        QCOMPARE(timeframeMinutes("H1"), 60);
    }

    void candleRange_orderedAndSpan()
    {
        QDateTime now(QDate(2024, 1, 1), QTime(0, 0), QTimeZone::utc());
        auto r = candleTimeRange("M5", 10, now);
        QDateTime from = QDateTime::fromString(r.first, Qt::ISODate);
        QDateTime to = QDateTime::fromString(r.second, Qt::ISODate);
        QVERIFY(from < to);
        // span = 5 * 10 * 3 = 150 menit.
        QCOMPARE(from.secsTo(to), qint64(150 * 60));
    }

    void symbolVariations()
    {
        const QStringList v = candidateSymbolVariations("EURUSDm");
        QVERIFY(v.contains("EURUSDm"));
        QVERIFY(v.contains("EURUSD"));
    }

    void resolveSymbol_variants()
    {
        const QStringList avail{"EURUSDm", "XAUUSDm", "BTCUSDm"};
        QCOMPARE(resolveSymbolName("EURUSDm", avail), QStringLiteral("EURUSDm")); // exact
        QCOMPARE(resolveSymbolName("eurusdm", avail), QStringLiteral("EURUSDm")); // case
        QCOMPARE(resolveSymbolName("EURUSD", avail), QStringLiteral("EURUSDm"));  // suffix
        QVERIFY(resolveSymbolName("GBPUSD", avail).isEmpty());                    // tak ada
    }

    // ----- McpParse (pure) -----
    void side_and_comment()
    {
        QCOMPARE(sideToMcp("BUY"), QStringLiteral("buy"));
        QCOMPARE(sideToMcp("sell"), QStringLiteral("sell"));
        QVERIFY(sideToMcp("x").isEmpty());
        QCOMPARE(clampComment(QString(40, 'a')).size(), 31);
    }

    void orderResult_variants()
    {
        // retcode DONE.
        OrderResult a = parseOrderResult(QJsonObject{{"retcode", 10009}, {"order", 55}});
        QVERIFY(a.ok);
        QCOMPARE(a.ticket, 55LL);
        // success flag eksplisit.
        OrderResult b = parseOrderResult(QJsonObject{{"success", true}, {"ticket", 7}});
        QVERIFY(b.ok);
        QCOMPARE(b.ticket, 7LL);
        // gagal dengan retcode != done -> pesan memuat retcode.
        OrderResult c = parseOrderResult(QJsonObject{{"retcode", 10018}, {"message", "closed"}});
        QVERIFY(!c.ok);
        QVERIFY(c.message.contains("10018"));
        // hanya ticket -> dianggap sukses.
        OrderResult d = parseOrderResult(QJsonObject{{"deal", 99}});
        QVERIFY(d.ok);
        QCOMPARE(d.ticket, 99LL);
    }

    void normalizePosition_side()
    {
        Position p = normalizePosition(QJsonObject{
            {"ticket", 1001}, {"symbol", "EURUSDm"}, {"type", "1"}, {"volume", 0.1}});
        QCOMPARE(p.type, QStringLiteral("SELL"));
        QCOMPARE(p.ticket, 1001LL);
    }

    void normalizeDeal_netProfit()
    {
        Deal d = normalizeDeal(QJsonObject{
            {"ticket", 5}, {"profit", 10.0}, {"commission", -1.0},
            {"swap", -0.5}, {"fee", 0.0}});
        QCOMPARE(d.profit, 10.0);
        QCOMPARE(d.netProfit, 8.5);
    }

    void friendlyError_mapping()
    {
        QVERIFY(friendlyTradeError("trading is not permitted").contains("Ctrl+E"));
        QVERIFY(friendlyTradeError("Error 10018 market closed").contains("akhir pekan"));
        QVERIFY(friendlyTradeError("invalid stops").contains("stops-level"));
    }

    void parseTime_formats()
    {
        QDateTime exp = QDateTime::fromString("2024.01.02 03:04:05", "yyyy.MM.dd HH:mm:ss");
        exp.setTimeZone(QTimeZone::utc());
        QCOMPARE(parseMt5TimeEpoch(QJsonValue("2024.01.02 03:04:05")), exp.toSecsSinceEpoch());
        QCOMPARE(parseMt5TimeEpoch(QJsonValue(1700000000.0)), 1700000000LL);
    }

    // ----- McpBackend end-to-end (mock server) -----
    void accountInfo_normalized()
    {
        MockMt5 mock;
        McpBackend b(mock.url(), "key");
        QVERIFY(b.connect());
        Account a = b.accountInfo();
        QVERIFY(a.valid);
        QCOMPARE(a.login, 416355944LL);
        QCOMPARE(a.balance, 482.89);       // dibulatkan 2 desimal
        QCOMPARE(a.accountType, QStringLiteral("DEMO")); // server 'Trial' -> DEMO
        QVERIFY(a.tradeAllowed);
    }

    void tradingGate_expertsOff_blocksOrder()
    {
        MockMt5 mock;
        mock.expertsTradeAllowed = false; // simulasi Algo Trading OFF (RDP)
        McpBackend b(mock.url(), "key");
        QVERIFY(b.connect());
        QVERIFY(b.tradingBlockedReason().contains("Ctrl+E"));
        OrderResult r = b.sendMarketOrder("EURUSDm", "BUY", 0.01);
        QVERIFY(!r.ok);
        QVERIFY(r.message.contains("Algo Trading"));
    }

    void sendMarketOrder_success()
    {
        MockMt5 mock;
        McpBackend b(mock.url(), "key");
        QVERIFY(b.connect());
        OrderResult r = b.sendMarketOrder("EURUSDm", "BUY", 0.01, 0, 0, 100200, "test");
        QVERIFY(r.ok);
        QCOMPARE(r.ticket, 55LL);
    }

    void positions_parsed()
    {
        MockMt5 mock;
        McpBackend b(mock.url(), "key");
        QVERIFY(b.connect());
        QVector<Position> pos = b.positions();
        QCOMPARE(pos.size(), 1);
        QCOMPARE(pos.first().type, QStringLiteral("BUY"));
        QCOMPARE(pos.first().ticket, 1001LL);
    }

    void listSymbols_fromCache()
    {
        MockMt5 mock;
        McpBackend b(mock.url(), "key");
        QVERIFY(b.connect());
        const QStringList syms = b.listSymbols();
        QVERIFY(syms.contains("EURUSDm"));
        QVERIFY(syms.contains("XAUUSDm"));
    }
};

QTEST_GUILESS_MAIN(TestBackend)
#include "test_backend.moc"
