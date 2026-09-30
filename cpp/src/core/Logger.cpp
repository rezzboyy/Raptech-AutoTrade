#include "core/Logger.h"

#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QMutex>
#include <QTextStream>
#include <QtGlobal>

namespace {
QString g_logFile;
QMutex g_mutex;

const char *levelName(QtMsgType t)
{
    switch (t) {
    case QtDebugMsg: return "DEBUG";
    case QtInfoMsg: return "INFO";
    case QtWarningMsg: return "WARNING";
    case QtCriticalMsg: return "ERROR";
    case QtFatalMsg: return "FATAL";
    }
    return "INFO";
}

void handler(QtMsgType type, const QMessageLogContext &, const QString &msg)
{
    const QString line = QStringLiteral("%1 | %2 | %3")
        .arg(QDateTime::currentDateTime().toString("HH:mm:ss"),
             QString::fromLatin1(levelName(type)), msg);

    // Konsol.
    fprintf(stderr, "%s\n", line.toLocal8Bit().constData());
    fflush(stderr);

    // Berkas (thread-safe).
    if (!g_logFile.isEmpty()) {
        QMutexLocker lock(&g_mutex);
        QFile f(g_logFile);
        if (f.open(QIODevice::Append | QIODevice::Text)) {
            QTextStream ts(&f);
            ts << line << '\n';
            f.close();
        }
    }
    if (type == QtFatalMsg)
        abort();
}
} // namespace

namespace Logger {

void init(const QString &logDir)
{
    QDir().mkpath(logDir);
    g_logFile = logDir + QStringLiteral("/bot.log");
    qInstallMessageHandler(handler);
}

} // namespace Logger
