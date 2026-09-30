#pragma once
#include <QString>

// Logging sederhana ke konsol + berkas (padanan src/logger.py).
namespace Logger {

// Pasang handler pesan Qt (qDebug/qInfo/qWarning/qCritical) agar juga ditulis
// ke berkas log dengan timestamp. Aman dipanggil sekali di awal main().
void init(const QString &logDir = QStringLiteral("logs"));

} // namespace Logger
