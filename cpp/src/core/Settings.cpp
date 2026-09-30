#include "core/Settings.h"

Settings &settings()
{
    static Settings instance;
    return instance;
}

QStringList Settings::symbolsList() const
{
    QString raw = symbol;
    raw.replace(QLatin1Char(';'), QLatin1Char(','));
    QStringList out;
    const auto parts = raw.split(QLatin1Char(','), Qt::SkipEmptyParts);
    for (const QString &p : parts) {
        const QString t = p.trimmed();
        if (!t.isEmpty())
            out << t; // JANGAN paksa huruf besar (broker Exness pakai suffix kecil)
    }
    if (out.isEmpty())
        out << QStringLiteral("EURUSDm");
    return out;
}
