#include "backend/SymbolUtils.h"

#include <QHash>
#include <QRegularExpression>
#include <QTimeZone>

namespace {
// Regex penghapus suffix broker umum (sama dgn versi Python).
QRegularExpression &suffixRe()
{
    static QRegularExpression re(
        QStringLiteral("(\\.pro|_pro|pro|\\.raw|_raw|raw|\\.z|_z|z|\\.c|_c|c|"
                       "\\.m|_m|m|_i|\\.i|_sb|\\.s|\\.a|\\+)$"),
        QRegularExpression::CaseInsensitiveOption);
    return re;
}

double rangeBuffer() { return 3.0; }
} // namespace

namespace SymbolUtils {

QString classifyAccountType(const QString &typeStr, const QString &server)
{
    const QString t = typeStr.trimmed().toLower();
    const QString srv = server.toLower();
    if (srv.contains("demo") || srv.contains("trial"))
        return QStringLiteral("DEMO");
    if (t == "contest" || srv.contains("contest"))
        return QStringLiteral("CONTEST");
    if (t == "demo")
        return QStringLiteral("DEMO");
    if (t == "real")
        return QStringLiteral("REAL");
    return QStringLiteral("?");
}

QString mapTimeframeToPeriod(const QString &timeframeStr)
{
    static const QHash<QString, QString> m{
        {"M1", "M1"}, {"M5", "M5"}, {"M15", "M15"}, {"M30", "M30"},
        {"H1", "H1"}, {"H4", "H4"}, {"D1", "D1"}};
    return m.value(timeframeStr.toUpper(), QStringLiteral("M5"));
}

int timeframeMinutes(const QString &timeframeStr)
{
    static const QHash<QString, int> m{
        {"M1", 1}, {"M5", 5}, {"M15", 15}, {"M30", 30},
        {"H1", 60}, {"H4", 240}, {"D1", 1440}};
    return m.value(timeframeStr.toUpper(), 5);
}

QPair<QString, QString> candleTimeRange(const QString &timeframeStr, int count,
                                        const QDateTime &nowIn)
{
    if (count < 1)
        count = 1;
    QDateTime now = nowIn.isValid() ? nowIn.toUTC() : QDateTime::currentDateTimeUtc();
    now.setTimeZone(QTimeZone::utc());
    const double spanMinutes = timeframeMinutes(timeframeStr) * double(count) * rangeBuffer();
    const QDateTime from = now.addMSecs(-qint64(spanMinutes * 60000.0));
    return {from.toString(Qt::ISODate), now.toString(Qt::ISODate)};
}

QStringList candidateSymbolVariations(const QString &symbolIn)
{
    const QString sym = symbolIn.trimmed();
    if (sym.isEmpty())
        return {};
    QStringList candidates{sym};
    QString root = sym;
    root.remove(suffixRe());
    if (root.isEmpty())
        root = sym;
    const QStringList variants{
        root, root + "m", root + "c", root + ".pro", root + "pro",
        root + "raw", root + ".raw", root + "z", root + "_i"};
    for (const QString &v : variants)
        if (!candidates.contains(v))
            candidates << v;
    return candidates;
}

QString resolveSymbolName(const QString &requested, const QStringList &available)
{
    const QString req = requested.trimmed();
    if (req.isEmpty() || available.isEmpty())
        return {};

    // 1. Exact match.
    if (available.contains(req))
        return req;

    // Peta upper -> asli.
    QHash<QString, QString> availUpper;
    for (const QString &s : available)
        availUpper.insert(s.toUpper(), s);

    // 2. Case-insensitive exact.
    if (availUpper.contains(req.toUpper()))
        return availUpper.value(req.toUpper());

    // 3. Variasi kandidat suffix.
    const QStringList cands = candidateSymbolVariations(req);
    for (const QString &cand : cands) {
        if (available.contains(cand))
            return cand;
        if (availUpper.contains(cand.toUpper()))
            return availUpper.value(cand.toUpper());
    }

    // 4. Prefix match berbasis root.
    QString root = req;
    root.remove(suffixRe());
    if (!root.isEmpty()) {
        const QString rootUpper = root.toUpper();
        for (const QString &s : available) {
            if (s.toUpper().startsWith(rootUpper) && s.size() <= root.size() + 5)
                return s;
        }
    }
    return {};
}

} // namespace SymbolUtils
