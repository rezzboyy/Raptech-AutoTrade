#pragma once
#include <QJsonObject>
#include <QString>
#include <QStringList>

struct Settings;

// Persistensi konfigurasi trading ke config.json (padanan src/config_store.py).
// Kredensial (login/password/server) & mcpApiKey TIDAK disimpan.
namespace ConfigStore {

// Konfigurasi -> QJsonObject (hanya field yang dipersist).
QJsonObject toJson(const Settings &s);

// Validasi nilai. Field yang tak ada di `obj` dianggap memakai nilai `current`.
// Kembalikan daftar pesan error (kosong = valid).
QStringList validate(const QJsonObject &obj, const Settings &current);

// Validasi lalu terapkan (partial: hanya field yang ada di `obj`).
// Kembalikan daftar error; bila tidak kosong, TIDAK ada yang diterapkan.
QStringList apply(const QJsonObject &obj, Settings &s);

// Simpan/muat berkas config.json.
bool save(const Settings &s, const QString &path = QStringLiteral("config.json"));
bool load(Settings &s, const QString &path = QStringLiteral("config.json"));

// Rahasia MCP (mcp_secret.json, gitignored): {"mcp_endpoint":.., "mcp_api_key":<teks biasa>}.
// loadMcpSecret: isi endpoint/apiKey bila belum diset (auto-load saat startup).
// saveMcpSecret: tulis endpoint+apiKey (auto-save saat connect MCP sukses).
bool loadMcpSecret(Settings &s, const QString &path = QStringLiteral("mcp_secret.json"));
bool saveMcpSecret(const Settings &s, const QString &path = QStringLiteral("mcp_secret.json"));

} // namespace ConfigStore
