#include "net/McpClient.h"

#include <QEventLoop>
#include <QJsonArray>
#include <QJsonDocument>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QRegularExpression>
#include <QTimer>
#include <QUrl>

namespace {
const QByteArray kProtocolVersion = QByteArrayLiteral("2025-06-18");
} // namespace

McpClient::McpClient(const QString &endpoint, const QString &apiKey, int timeoutMs)
    : m_endpoint(endpoint), m_apiKey(apiKey), m_timeoutMs(timeoutMs)
{
}

McpClient::~McpClient()
{
    delete m_nam;
}

QString McpClient::maskToken(const QString &token)
{
    if (token.isEmpty())
        return QStringLiteral("<kosong>");
    if (token.size() <= 8)
        return QStringLiteral("****");
    return token.left(4) + QStringLiteral("...") + token.right(4);
}

// Ambil objek JSON dari body (JSON biasa atau SSE: baris 'data: {..}' terakhir).
QJsonObject McpClient::extractJsonPayload(const QString &bodyIn)
{
    const QString body = bodyIn.trimmed();
    if (body.isEmpty())
        return {};

    QString raw = body;
    static const QRegularExpression re(QStringLiteral("data:\\s*(\\{.*\\})"));
    QRegularExpressionMatchIterator it = re.globalMatch(body);
    QString last;
    while (it.hasNext())
        last = it.next().captured(1);
    if (!last.isEmpty())
        raw = last;

    QJsonParseError err{};
    const QJsonDocument doc = QJsonDocument::fromJson(raw.toUtf8(), &err);
    if (err.error != QJsonParseError::NoError || !doc.isObject())
        return {};
    return doc.object();
}

bool McpClient::firstText(const QJsonObject &result, QString &out)
{
    const QJsonValue content = result.value(QStringLiteral("content"));
    if (!content.isArray())
        return false;
    const QJsonArray arr = content.toArray();
    for (const QJsonValue &v : arr) {
        if (v.isObject()) {
            const QJsonObject o = v.toObject();
            if (o.value(QStringLiteral("type")).toString() == QLatin1String("text")) {
                out = o.value(QStringLiteral("text")).toString();
                return true;
            }
        }
    }
    return false;
}

bool McpClient::looksLikeSessionError(const QString &msg)
{
    const QString s = msg.toLower();
    return s.contains("session") || s.contains("not initialized") || s.contains("http 400");
}

McpClient::PostResult McpClient::post(const QJsonObject &payload)
{
    PostResult r;
    if (!m_nam)
        m_nam = new QNetworkAccessManager();

    QNetworkRequest req{QUrl(m_endpoint)};
    req.setHeader(QNetworkRequest::ContentTypeHeader, QByteArrayLiteral("application/json"));
    req.setRawHeader("Authorization", "Bearer " + m_apiKey.toUtf8());
    req.setRawHeader("Accept", "application/json, text/event-stream");
    req.setRawHeader("MCP-Protocol-Version", kProtocolVersion);
    if (!m_sessionId.isEmpty())
        req.setRawHeader("Mcp-Session-Id", m_sessionId.toUtf8());

    const QByteArray data = QJsonDocument(payload).toJson(QJsonDocument::Compact);

    QNetworkReply *reply = m_nam->post(req, data);
    QEventLoop loop;
    QTimer timer;
    timer.setSingleShot(true);
    bool timedOut = false;
    QObject::connect(&timer, &QTimer::timeout, &loop, [&]() {
        timedOut = true;
        reply->abort();
    });
    QObject::connect(reply, &QNetworkReply::finished, &loop, &QEventLoop::quit);
    timer.start(m_timeoutMs);
    loop.exec();
    timer.stop();

    const int status = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
    const QByteArray bodyBytes = reply->readAll();
    const QNetworkReply::NetworkError netErr = reply->error();

    // Tangkap session id dari header respons.
    const QByteArray sid = reply->rawHeader("Mcp-Session-Id");
    if (!sid.isEmpty())
        m_sessionId = QString::fromUtf8(sid);

    reply->deleteLater();

    r.status = status;
    r.body = QString::fromUtf8(bodyBytes);

    if (timedOut) {
        r.netError = McpErrorType::Timeout;
        r.errorMessage = QStringLiteral("Permintaan MCP timeout setelah %1 ms.").arg(m_timeoutMs);
        return r;
    }
    if (status == 401) {
        r.netError = McpErrorType::Auth;
        r.errorMessage = QStringLiteral(
            "Autentikasi MCP gagal (401). Periksa/salin ulang API Key dari "
            "MT5 -> Tools -> Options -> tab MCP.");
        return r;
    }
    // Error jaringan tanpa status HTTP -> tak terjangkau.
    if (netErr != QNetworkReply::NoError && status == 0) {
        r.netError = McpErrorType::Connection;
        r.errorMessage = QStringLiteral(
            "Tidak dapat menjangkau server MCP di %1. Aktifkan 'Enable internal "
            "server' di MT5 -> Options -> MCP.").arg(m_endpoint);
        return r;
    }
    return r; // status bisa >=400; ditangani di rpc()
}

McpReply McpClient::rpc(const QString &method, const QJsonObject &params,
                        bool hasParams, bool isNotification)
{
    QJsonObject payload;
    payload["jsonrpc"] = "2.0";
    payload["method"] = method;
    if (!isNotification)
        payload["id"] = 1;
    if (hasParams)
        payload["params"] = params;

    const PostResult pr = post(payload);
    McpReply out;
    if (pr.netError != McpErrorType::None) {
        out.ok = false;
        out.errorType = pr.netError;
        out.errorMessage = pr.errorMessage;
        return out;
    }
    if (pr.status >= 400) {
        out.ok = false;
        out.errorType = McpErrorType::Protocol;
        out.errorMessage = QStringLiteral("MCP '%1' gagal (HTTP %2): %3")
                               .arg(method).arg(pr.status).arg(pr.body.left(200));
        return out;
    }
    if (isNotification) {
        out.ok = true;
        return out;
    }

    const QJsonObject obj = extractJsonPayload(pr.body);
    const QJsonValue errVal = obj.value(QStringLiteral("error"));
    if (!errVal.isUndefined() && !errVal.isNull()
        && !(errVal.isObject() && errVal.toObject().isEmpty())) {
        out.ok = false;
        out.errorType = McpErrorType::Tool;
        out.errorMessage = QStringLiteral("MCP '%1' error: %2")
                               .arg(method, QString::fromUtf8(
                                   QJsonDocument(errVal.isObject() ? errVal.toObject() : QJsonObject{{"detail", errVal}})
                                       .toJson(QJsonDocument::Compact)));
        return out;
    }

    out.ok = true;
    const QJsonValue result = obj.value(QStringLiteral("result"));
    out.data = result.isObject() ? result.toObject() : obj;
    return out;
}

McpReply McpClient::initialize()
{
    QJsonObject params;
    params["protocolVersion"] = QString::fromUtf8(kProtocolVersion);
    params["capabilities"] = QJsonObject{};
    params["clientInfo"] = QJsonObject{
        {"name", "xaviq-trading-engine"}, {"version", "1.0"}};

    McpReply r = rpc("initialize", params, /*hasParams=*/true);
    if (!r.ok)
        return r;

    // Wajib kirim notifikasi initialized sebelum memanggil tool.
    McpReply n = rpc("notifications/initialized", {}, false, /*isNotification=*/true);
    if (!n.ok)
        return n;

    m_initialized = true;
    return r;
}

McpReply McpClient::callTool(const QString &name, const QJsonObject &arguments)
{
    if (!m_initialized) {
        McpReply init = initialize();
        if (!init.ok)
            return init;
    }

    McpReply r = callToolOnce(name, arguments);
    if (!r.ok && (r.errorType == McpErrorType::Tool || r.errorType == McpErrorType::Protocol)
        && looksLikeSessionError(r.errorMessage)) {
        // Sesi mungkin kedaluwarsa: reset lalu inisialisasi ulang sekali & ulangi.
        m_sessionId.clear();
        m_initialized = false;
        McpReply init = initialize();
        if (!init.ok)
            return init;
        return callToolOnce(name, arguments);
    }
    return r;
}

McpReply McpClient::callToolOnce(const QString &name, const QJsonObject &arguments)
{
    QJsonObject params;
    params["name"] = name;
    params["arguments"] = arguments;

    McpReply r = rpc("tools/call", params, /*hasParams=*/true);
    if (!r.ok)
        return r;

    const QJsonObject result = r.data;

    // Flag error tool.
    if (result.value(QStringLiteral("isError")).toBool(false)) {
        QString text;
        firstText(result, text);
        r.ok = false;
        r.errorType = McpErrorType::Tool;
        r.errorMessage = QStringLiteral("Tool '%1' gagal: %2").arg(name, text);
        return r;
    }

    // Ekstrak teks JSON dari content bila ada.
    QString text;
    if (firstText(result, text)) {
        QJsonParseError perr{};
        const QJsonDocument doc = QJsonDocument::fromJson(text.toUtf8(), &perr);
        if (perr.error == QJsonParseError::NoError) {
            if (doc.isObject()) {
                r.data = doc.object();
            } else {
                r.data = QJsonObject{{"value", doc.isArray() ? QJsonValue(doc.array())
                                                             : QJsonValue()}};
            }
            return r;
        }
        // Teks biasa (bukan JSON): tool MT5 kadang kirim pesan error sbg teks.
        if (text.toLower().contains("invalid")) {
            r.ok = false;
            r.errorType = McpErrorType::Tool;
            r.errorMessage = QStringLiteral("Tool '%1': %2").arg(name, text);
            return r;
        }
        r.data = QJsonObject{{"value", text}};
        return r;
    }

    // Tidak ada content text → kembalikan result apa adanya.
    r.data = result;
    return r;
}

void McpClient::close()
{
    m_sessionId.clear();
    m_initialized = false;
}
