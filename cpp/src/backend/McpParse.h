#pragma once
#include <QJsonObject>
#include <QString>
#include <QStringList>

#include "backend/Models.h"

// Fungsi normalisasi/parse respons MCP (pure, tanpa jaringan) — dari mcp_backend.py.
namespace McpParse {

// Ambil nilai numerik pertama yang ada dari beberapa kemungkinan kunci.
double num(const QJsonObject &o, const QStringList &keys, double def = 0.0);

// Parse waktu MT5 ("YYYY.MM.DD HH:MM:SS" / ISO / epoch) -> epoch detik UTC. 0 bila gagal.
long long parseMt5TimeEpoch(const QJsonValue &value);

// Petakan arah sinyal -> "buy"/"sell". QString() bila tak valid.
QString sideToMcp(const QString &side);

// Batasi komentar order (skema MCP: 31 char).
QString clampComment(const QString &comment, int limit = 31);

// Normalkan hasil tool trading -> OrderResult {ok, ticket, message}.
OrderResult parseOrderResult(const QJsonObject &res);

Position normalizePosition(const QJsonObject &p);
Order normalizeOrder(const QJsonObject &o);
Deal normalizeDeal(const QJsonObject &d);

// Ubah pesan error MT5 teknis -> pesan jelas & dapat ditindaklanjuti.
QString friendlyTradeError(const QString &rawMsg);

} // namespace McpParse
