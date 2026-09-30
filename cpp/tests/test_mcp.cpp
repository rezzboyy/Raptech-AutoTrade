#include <QtTest>
#include <QTcpServer>
#include <QTcpSocket>
#include <QHash>
#include <QHostAddress>
#include <QJsonDocument>
#include <QJsonObject>

#include "net/McpClient.h"

// ------- Mock server HTTP minimal untuk mensimulasikan server MCP MT5 -------
class MockMcp : public QObject
{
    Q_OBJECT
public:
    enum Mode { NormalJson, Sse, ToolError, Always401, Hang, SessionExpiredOnce };
    Mode mode = NormalJson;
    QString lastAuth;      // header Authorization terakhir yang diterima
    QString lastMethod;    // method JSON-RPC terakhir
    QString lastSession;   // header Mcp-Session-Id yang dikirim klien
    int toolCallCount = 0;

    MockMcp()
    {
        server.listen(QHostAddress::LocalHost, 0);
        connect(&server, &QTcpServer::newConnection, this, &MockMcp::onConn);
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
        const QByteArray head = buf.left(idx);
        int contentLen = 0;
        for (const QByteArray &line : head.split('\n')) {
            const QByteArray l = line.trimmed();
            const QByteArray lo = l.toLower();
            if (lo.startsWith("content-length:"))
                contentLen = l.mid(15).trimmed().toInt();
            else if (lo.startsWith("authorization:"))
                lastAuth = QString::fromUtf8(l.mid(14).trimmed());
            else if (lo.startsWith("mcp-session-id:"))
                lastSession = QString::fromUtf8(l.mid(15).trimmed());
        }
        QByteArray body = buf.mid(idx + 4);
        if (body.size() < contentLen)
            return; // tunggu body penuh

        const QJsonObject req = QJsonDocument::fromJson(body).object();
        const QString method = req.value("method").toString();
        lastMethod = method;
        m_buf.remove(sock);

        if (mode == Hang)
            return; // sengaja tidak membalas (uji timeout)

        if (mode == Always401) {
            sendHttp(sock, 401, "{\"error\":\"unauthorized\"}");
            return;
        }

        if (method == "initialize") {
            sendHttp(sock, 200,
                     "{\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{\"serverInfo\":{\"name\":\"mt5\"}}}",
                     "sess-123");
            return;
        }
        if (method == "notifications/initialized") {
            sendHttp(sock, 200, "{}");
            return;
        }
        if (method == "tools/call") {
            ++toolCallCount;
            handleToolCall(sock);
            return;
        }
        sendHttp(sock, 200, "{\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{}}");
    }

private:
    void handleToolCall(QTcpSocket *sock)
    {
        if (mode == ToolError) {
            sendHttp(sock, 200,
                     "{\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{\"isError\":true,"
                     "\"content\":[{\"type\":\"text\",\"text\":\"symbol not found\"}]}}");
            return;
        }
        if (mode == SessionExpiredOnce && toolCallCount == 1) {
            // Balasan error "session" agar klien re-initialize lalu ulangi.
            sendHttp(sock, 200,
                     "{\"jsonrpc\":\"2.0\",\"id\":1,\"error\":{\"message\":\"session expired\"}}");
            return;
        }
        // Isi hasil: content[0].text berisi JSON {"balance":482.89}
        const char *inner = "{\\\"balance\\\":482.89,\\\"login\\\":416355944}";
        const QByteArray okBody =
            QByteArray("{\"jsonrpc\":\"2.0\",\"id\":1,\"result\":{\"content\":"
                       "[{\"type\":\"text\",\"text\":\"") + inner + "\"}]}}";
        if (mode == Sse) {
            const QByteArray sse = QByteArray("event: message\r\ndata: ") + okBody + "\r\n\r\n";
            sendHttp(sock, 200, sse, {}, "text/event-stream");
            return;
        }
        sendHttp(sock, 200, okBody);
    }

    void sendHttp(QTcpSocket *sock, int status, const QByteArray &body,
                  const QByteArray &sessionId = {},
                  const char *contentType = "application/json")
    {
        QByteArray resp = "HTTP/1.1 " + QByteArray::number(status) + " OK\r\n";
        resp += "Content-Type: ";
        resp += contentType;
        resp += "\r\n";
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

// --------------------------- Test cases ---------------------------
class TestMcp : public QObject
{
    Q_OBJECT

private slots:
    void maskToken()
    {
        QCOMPARE(McpClient::maskToken(QString()), QStringLiteral("<kosong>"));
        QCOMPARE(McpClient::maskToken("short"), QStringLiteral("****"));
        QCOMPARE(McpClient::maskToken("ABCDEFGHIJKL"), QStringLiteral("ABCD...IJKL"));
    }

    void initialize_ok_capturesSessionAndAuth()
    {
        MockMcp mock;
        McpClient c(mock.url(), "secret-key-123");
        McpReply r = c.initialize();
        QVERIFY(r.ok);
        QVERIFY(c.isReady());
        QCOMPARE(c.sessionId(), QStringLiteral("sess-123"));
        QCOMPARE(mock.lastAuth, QStringLiteral("Bearer secret-key-123"));
    }

    void callTool_parsesJsonContent()
    {
        MockMcp mock;
        McpClient c(mock.url(), "k");
        McpReply r = c.callTool("get_trading_account_info");
        QVERIFY(r.ok);
        QCOMPARE(r.data.value("balance").toDouble(), 482.89);
        QCOMPARE(r.data.value("login").toDouble(), 416355944.0);
        QCOMPARE(mock.lastMethod, QStringLiteral("tools/call"));
    }

    void callTool_parsesSse()
    {
        MockMcp mock;
        mock.mode = MockMcp::Sse;
        McpClient c(mock.url(), "k");
        McpReply r = c.callTool("get_trading_account_info");
        QVERIFY(r.ok);
        QCOMPARE(r.data.value("balance").toDouble(), 482.89);
    }

    void callTool_toolError()
    {
        MockMcp mock;
        mock.mode = MockMcp::ToolError;
        McpClient c(mock.url(), "k");
        McpReply r = c.callTool("add_marketwatch_symbol");
        QVERIFY(!r.ok);
        QCOMPARE(r.errorType, McpErrorType::Tool);
        QVERIFY(r.errorMessage.contains("symbol not found"));
    }

    void auth401()
    {
        MockMcp mock;
        mock.mode = MockMcp::Always401;
        McpClient c(mock.url(), "wrong-key");
        McpReply r = c.initialize();
        QVERIFY(!r.ok);
        QCOMPARE(r.errorType, McpErrorType::Auth);
    }

    void connectionRefused()
    {
        // Port yang tidak ada yang mendengarkan -> Connection error.
        McpClient c("http://127.0.0.1:1/mcp", "k");
        c.setTimeoutMs(3000);
        McpReply r = c.initialize();
        QVERIFY(!r.ok);
        QVERIFY(r.errorType == McpErrorType::Connection || r.errorType == McpErrorType::Timeout);
    }

    void timeout()
    {
        MockMcp mock;
        mock.mode = MockMcp::Hang;
        McpClient c(mock.url(), "k");
        c.setTimeoutMs(400);
        McpReply r = c.initialize();
        QVERIFY(!r.ok);
        QCOMPARE(r.errorType, McpErrorType::Timeout);
    }

    void sessionExpired_reinitAndRetry()
    {
        MockMcp mock;
        mock.mode = MockMcp::SessionExpiredOnce;
        McpClient c(mock.url(), "k");
        McpReply r = c.callTool("get_trading_account_info");
        QVERIFY(r.ok); // panggilan kedua berhasil setelah re-init
        QCOMPARE(r.data.value("balance").toDouble(), 482.89);
        QVERIFY(mock.toolCallCount >= 2);
    }
};

QTEST_GUILESS_MAIN(TestMcp)
#include "test_mcp.moc"
