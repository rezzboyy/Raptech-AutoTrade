#include "backend/McpParse.h"

#include <QDateTime>
#include <QJsonValue>
#include <QTimeZone>

namespace McpParse {

double num(const QJsonObject &o, const QStringList &keys, double def)
{
    for (const QString &k : keys) {
        if (o.contains(k)) {
            const QJsonValue v = o.value(k);
            if (v.isDouble())
                return v.toDouble();
            if (v.isString()) {
                bool ok = false;
                const double d = v.toString().toDouble(&ok);
                if (ok)
                    return d;
            }
        }
    }
    return def;
}

long long parseMt5TimeEpoch(const QJsonValue &value)
{
    if (value.isUndefined() || value.isNull())
        return 0;
    if (value.isDouble())
        return static_cast<long long>(value.toDouble());

    const QString s = value.toString().trimmed();
    if (s.isEmpty())
        return 0;

    // Angka dalam bentuk string.
    bool isNum = false;
    const double asNum = s.toDouble(&isNum);
    if (isNum)
        return static_cast<long long>(asNum);

    static const QStringList fmts{
        "yyyy.MM.dd HH:mm:ss", "yyyy.MM.dd HH:mm", "yyyy-MM-dd HH:mm:ss"};
    for (const QString &fmt : fmts) {
        QDateTime dt = QDateTime::fromString(s, fmt);
        if (dt.isValid()) {
            dt.setTimeZone(QTimeZone::utc());
            return dt.toSecsSinceEpoch();
        }
    }
    QDateTime iso = QDateTime::fromString(s, Qt::ISODate);
    if (iso.isValid())
        return iso.toSecsSinceEpoch();
    return 0;
}

QString sideToMcp(const QString &side)
{
    const QString s = side.trimmed().toUpper();
    if (s == "BUY" || s == "0" || s == "ORDER_TYPE_BUY")
        return QStringLiteral("buy");
    if (s == "SELL" || s == "1" || s == "ORDER_TYPE_SELL")
        return QStringLiteral("sell");
    return {};
}

QString clampComment(const QString &comment, int limit)
{
    return comment.left(limit);
}

static bool isIntString(const QString &s)
{
    QString t = s;
    if (t.startsWith('-'))
        t = t.mid(1);
    if (t.isEmpty())
        return false;
    for (const QChar &c : t)
        if (!c.isDigit())
            return false;
    return true;
}

OrderResult parseOrderResult(const QJsonObject &res)
{
    OrderResult r;

    // retcode / return_code.
    QJsonValue retcodeVal;
    if (res.contains("retcode"))
        retcodeVal = res.value("retcode");
    else if (res.contains("return_code"))
        retcodeVal = res.value("return_code");

    bool ok = res.value("success").toBool(res.value("ok").toBool(false));

    QString retcodeStr;
    bool haveRetcode = false;
    long long retcode = 0;
    if (!retcodeVal.isUndefined() && !retcodeVal.isNull()) {
        haveRetcode = true;
        if (retcodeVal.isDouble()) {
            retcode = static_cast<long long>(retcodeVal.toDouble());
            retcodeStr = QString::number(retcode);
        } else {
            retcodeStr = retcodeVal.toString();
            if (isIntString(retcodeStr))
                retcode = retcodeStr.toLongLong();
        }
    }

    if (!ok && haveRetcode)
        ok = isIntString(retcodeStr) && (retcode == 10009 || retcode == 0);

    // ticket dari berbagai kemungkinan kunci.
    const QStringList ticketKeys{
        "ticket", "order", "position_ticket", "position_id", "order_id", "deal"};
    long long ticket = 0;
    bool hasTicket = false;
    for (const QString &k : ticketKeys) {
        if (res.contains(k)) {
            const QJsonValue v = res.value(k);
            if (v.isDouble()) {
                ticket = static_cast<long long>(v.toDouble());
                hasTicket = ticket != 0;
                if (hasTicket)
                    break;
            } else if (v.isString() && isIntString(v.toString())) {
                ticket = v.toString().toLongLong();
                hasTicket = ticket != 0;
                if (hasTicket)
                    break;
            }
        }
    }

    // pesan.
    QString message;
    const QStringList msgKeys{
        "message", "retcode_details", "comment", "description", "error"};
    for (const QString &k : msgKeys) {
        if (res.contains(k) && res.value(k).isString() && !res.value(k).toString().isEmpty()) {
            message = res.value(k).toString();
            break;
        }
    }

    if (!ok && haveRetcode) {
        if (message.isEmpty())
            message = QStringLiteral("retcode %1").arg(retcodeStr);
        else if (!message.contains(retcodeStr))
            message = QStringLiteral("[%1] %2").arg(retcodeStr, message);
    }

    // Bila tak ada indikator eksplisit tapi ada ticket -> anggap sukses.
    if (!ok && hasTicket)
        ok = true;

    r.ok = ok;
    r.ticket = ticket;
    r.hasTicket = hasTicket;
    r.message = message;
    return r;
}

Position normalizePosition(const QJsonObject &p)
{
    Position out;
    QString side = p.value("type").toString(
        p.value("position_type").toString(p.value("action").toString())).toUpper();
    if (side == "0" || side == "BUY" || side == "POSITION_TYPE_BUY")
        side = "BUY";
    else if (side == "1" || side == "SELL" || side == "POSITION_TYPE_SELL")
        side = "SELL";
    out.ticket = static_cast<long long>(
        num(p, {"ticket", "position", "position_ticket", "position_id"}));
    out.symbol = p.value("symbol").toString();
    out.type = side;
    out.volume = num(p, {"volume", "volume_current"});
    out.priceOpen = num(p, {"price_open", "open_price", "price"});
    out.priceCurrent = num(p, {"price_current", "current_price", "price_last"});
    out.sl = num(p, {"sl", "stop_loss"});
    out.tp = num(p, {"tp", "take_profit"});
    out.profit = num(p, {"profit"});
    out.magic = static_cast<long long>(num(p, {"magic", "magic_number"}));
    out.time = parseMt5TimeEpoch(p.value("time"));
    if (out.time == 0)
        out.time = parseMt5TimeEpoch(p.value("time_setup"));
    return out;
}

Order normalizeOrder(const QJsonObject &o)
{
    Order out;
    out.ticket = static_cast<long long>(
        num(o, {"ticket", "order", "order_ticket", "order_id"}));
    out.symbol = o.value("symbol").toString();
    out.type = o.value("type").toString(
        o.value("order_type").toString(o.value("action").toString())).toLower();
    out.volume = num(o, {"volume", "volume_current", "volume_initial"});
    out.price = num(o, {"price_open", "price", "price_order"});
    out.sl = num(o, {"sl", "stop_loss"});
    out.tp = num(o, {"tp", "take_profit"});
    out.magic = static_cast<long long>(num(o, {"magic", "magic_number"}));
    return out;
}

Deal normalizeDeal(const QJsonObject &d)
{
    Deal out;
    const double profit = num(d, {"profit"});
    const double comm = num(d, {"commission"});
    const double swap = num(d, {"swap"});
    const double fee = num(d, {"fee"});
    out.ticket = static_cast<long long>(num(d, {"ticket", "position", "position_id"}));
    out.time = static_cast<long long>(num(d, {"time_close", "time", "close_time"}));
    out.symbol = d.value("symbol").toString();
    out.magic = static_cast<long long>(num(d, {"magic", "magic_number"}));
    out.netProfit = profit + comm + swap + fee;
    out.profit = profit;
    return out;
}

QString friendlyTradeError(const QString &rawMsg)
{
    const QString text = rawMsg.trimmed();
    const QString lower = text.toLower();
    if (lower.contains("trading is not permitted"))
        return QStringLiteral(
            "Trading tidak diizinkan oleh terminal MT5 ('trading is not permitted'). "
            "Pastikan tombol 'Algo Trading' di toolbar MT5 sudah aktif (ikon hijau / "
            "shortcut Ctrl+E) dan akun tidak berstatus investor/read-only.");
    if (lower.contains("invalid stops") || text.contains("10016"))
        return QStringLiteral(
            "Jarak SL/TP terlalu dekat dengan harga pasar / melanggar batas stops-level "
            "broker (Error #10016: %1). Gunakan jarak SL/TP yang lebih lebar.").arg(text);
    if (lower.contains("market closed") || text.contains("10018"))
        return QStringLiteral(
            "Pasar sedang tutup di broker (Error #10018: Market closed). Pasar Forex tutup "
            "di akhir pekan. Gunakan aset Crypto (BTCUSDm) untuk trading 24/7.");
    return text;
}

} // namespace McpParse
