#pragma once
#include <QByteArray>
#include <QJsonObject>
#include <QString>

class QNetworkAccessManager;

// Klien MCP (Model Context Protocol) untuk terminal MetaTrader 5.
// Padanan src/mcp_client.py: JSON-RPC 2.0 via HTTP "Streamable" (respons bisa
// JSON biasa atau SSE 'data: {..}'), autentikasi Bearer API key, sesi Mcp-Session-Id.
//
// Bersifat SINKRON: setiap panggilan memblok memakai QEventLoop lokal, jadi HARUS
// dipakai di worker thread (bukan main/UI thread). QNetworkAccessManager dibuat
// lazily di thread pemanggil pertama.

enum class McpErrorType {
    None,        // sukses
    Connection,  // endpoint tak terjangkau (server MCP mati/belum aktif)
    Auth,        // HTTP 401 — API key salah/kedaluwarsa
    Timeout,     // melebihi batas waktu
    Tool,        // server mengembalikan error di hasil tool
    Protocol,    // respons/HTTP tak terduga
};

// Hasil pemanggilan. `ok=true` -> `data` berisi payload hasil.
struct McpReply {
    bool ok = false;
    McpErrorType errorType = McpErrorType::None;
    QString errorMessage;
    QJsonObject data;
};

class McpClient
{
public:
    explicit McpClient(const QString &endpoint = QString(),
                       const QString &apiKey = QString(),
                       int timeoutMs = 15000);
    ~McpClient();

    void setEndpoint(const QString &endpoint) { m_endpoint = endpoint; }
    void setApiKey(const QString &apiKey) { m_apiKey = apiKey; }
    void setTimeoutMs(int ms) { m_timeoutMs = ms; }
    QString endpoint() const { return m_endpoint; }
    QString sessionId() const { return m_sessionId; }

    // Handshake: initialize + notifications/initialized. Menyimpan session id.
    McpReply initialize();

    // Panggil satu tool MCP. Mengurai result.content[].text (JSON) jadi objek.
    // Bila sesi tampak kedaluwarsa, coba initialize ulang sekali lalu ulangi.
    McpReply callTool(const QString &name, const QJsonObject &arguments = {});

    bool isReady() const { return m_initialized && !m_sessionId.isEmpty(); }
    void close();

    // Samarkan token untuk log (tak pernah tampil utuh).
    static QString maskToken(const QString &token);

private:
    struct PostResult {
        McpErrorType netError = McpErrorType::None;
        QString errorMessage;
        int status = 0;
        QString body;
    };

    PostResult post(const QJsonObject &payload);
    // Kirim satu JSON-RPC. Untuk notifikasi (tanpa id) `data` kosong bila sukses.
    McpReply rpc(const QString &method, const QJsonObject &params = {},
                 bool hasParams = false, bool isNotification = false);
    McpReply callToolOnce(const QString &name, const QJsonObject &arguments);

    static QJsonObject extractJsonPayload(const QString &body);
    static bool firstText(const QJsonObject &result, QString &out);
    static bool looksLikeSessionError(const QString &msg);

    QString m_endpoint;
    QString m_apiKey;
    int m_timeoutMs;
    QString m_sessionId;
    bool m_initialized = false;
    QNetworkAccessManager *m_nam = nullptr;
};
