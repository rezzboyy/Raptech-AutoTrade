#include "core/SecureStore.h"

#include <QByteArray>
#include <QCryptographicHash>
#include <QFile>
#include <QRandomGenerator>

namespace {
QString g_keyPath = QStringLiteral(".secret_key");
const QByteArray kPrefix = QByteArrayLiteral("v1:");

// Muat kunci 32-byte dari berkas; buat baru (acak) bila belum ada.
QByteArray loadOrCreateKey()
{
    QFile f(g_keyPath);
    if (f.exists() && f.open(QIODevice::ReadOnly)) {
        const QByteArray b64 = f.readAll().trimmed();
        f.close();
        const QByteArray key = QByteArray::fromBase64(b64);
        if (key.size() >= 16)
            return key;
    }
    // Generate 32 byte acak.
    QByteArray key(32, '\0');
    auto *rng = QRandomGenerator::system();
    for (int i = 0; i < key.size(); ++i)
        key[i] = static_cast<char>(rng->bounded(256));
    if (f.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        f.write(key.toBase64());
        f.close();
    }
    return key;
}

// Keystream CTR: blok ke-i = SHA256(key || i(4 byte LE)).
QByteArray keystream(const QByteArray &key, int length)
{
    QByteArray out;
    out.reserve(length + 32);
    quint32 counter = 0;
    while (out.size() < length) {
        QByteArray block = key;
        block.append(char(counter & 0xFF));
        block.append(char((counter >> 8) & 0xFF));
        block.append(char((counter >> 16) & 0xFF));
        block.append(char((counter >> 24) & 0xFF));
        out.append(QCryptographicHash::hash(block, QCryptographicHash::Sha256));
        ++counter;
    }
    out.truncate(length);
    return out;
}

QByteArray xorBytes(const QByteArray &data, const QByteArray &ks)
{
    QByteArray out(data.size(), '\0');
    for (int i = 0; i < data.size(); ++i)
        out[i] = data[i] ^ ks[i];
    return out;
}
} // namespace

namespace SecureStore {

void setKeyFilePath(const QString &path) { g_keyPath = path; }
QString keyFilePath() { return g_keyPath; }

QString encrypt(const QString &plain)
{
    if (plain.isEmpty())
        return QString();
    const QByteArray data = plain.toUtf8();
    const QByteArray key = loadOrCreateKey();
    const QByteArray ks = keystream(key, data.size());
    const QByteArray enc = xorBytes(data, ks);
    return QString::fromLatin1(kPrefix + enc.toBase64());
}

QString decrypt(const QString &token)
{
    if (token.isEmpty())
        return QString();
    const QByteArray raw = token.toLatin1();
    if (raw.startsWith(kPrefix)) {
        const QByteArray enc = QByteArray::fromBase64(raw.mid(kPrefix.size()));
        const QByteArray key = loadOrCreateKey();
        const QByteArray ks = keystream(key, enc.size());
        return QString::fromUtf8(xorBytes(enc, ks));
    }
    // Kompatibilitas mundur: coba base64 polos; jika bukan, kembalikan apa adanya.
    const QByteArray dec = QByteArray::fromBase64(raw);
    if (!dec.isEmpty())
        return QString::fromUtf8(dec);
    return token;
}

} // namespace SecureStore
