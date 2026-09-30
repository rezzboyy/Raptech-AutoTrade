#include "engine/TradeRules.h"

#include "backend/TradingBackend.h"
#include "core/Settings.h"

#include <QDateTime>
#include <QLoggingCategory>
#include <QTimeZone>
#include <QtGlobal>
#include <algorithm>
#include <cmath>

namespace {

double roundTo(double v, int digits)
{
    const double f = std::pow(10.0, digits);
    return std::round(v * f) / f;
}

QDateTime todayStartUtc()
{
    QDateTime now = QDateTime::currentDateTimeUtc();
    return QDateTime(now.date(), QTime(0, 0), QTimeZone::utc());
}

} // namespace

namespace TradeRules {

QString mapSignalToSide(const QString &signal)
{
    if (signal == "BUY")
        return QStringLiteral("buy");
    if (signal == "SELL")
        return QStringLiteral("sell");
    return {};
}

double calcLotFromSpec(const SymbolSpec &spec, double balance, double riskPercent,
                       double slPrice, double entryPrice)
{
    if (!spec.valid || balance <= 0)
        return 0.0;
    const double slDistance = std::abs(entryPrice - slPrice);
    if (slDistance <= 0)
        return 0.0;
    const double tickSize = spec.tickSize > 0 ? spec.tickSize : spec.point;
    const double tickValue = spec.tickValue;
    if (tickSize <= 0 || tickValue <= 0)
        return 0.0;
    const double lossPerLot = (slDistance / tickSize) * tickValue;
    if (lossPerLot <= 0)
        return 0.0;
    const double rawLot = (balance * riskPercent) / lossPerLot;
    const double step = spec.volumeStep > 0 ? spec.volumeStep : 0.01;
    const double vmin = spec.volumeMin > 0 ? spec.volumeMin : 0.01;
    const double vmax = spec.volumeMax > 0 ? spec.volumeMax : rawLot;
    double lot = std::round(rawLot / step) * step;
    lot = std::max(vmin, std::min(lot, vmax));
    return roundTo(lot, 2);
}

int countOpenPositions(TradingBackend &backend, const QString &symbol, long long magic)
{
    const QVector<Position> positions = backend.positions(symbol);
    if (magic) {
        int c = 0;
        for (const Position &p : positions)
            if (p.magic == magic)
                ++c;
        return c;
    }
    return positions.size();
}

bool canOpenNewPosition(TradingBackend &backend, const QString &symbol, long long magic,
                        int maxPositions)
{
    return countOpenPositions(backend, symbol, magic) < maxPositions;
}

bool applyBreakEven(TradingBackend &backend, const Position &pos, const SymbolSpec &spec,
                    int triggerPoints, int offsetPoints)
{
    if (triggerPoints <= 0 || !spec.valid)
        return false;
    const double point = spec.point;
    const int digits = spec.digits;
    if (point <= 0)
        return false;
    const Tick tick = backend.getTick(pos.symbol);
    if (!tick.valid)
        return false;
    const double entry = pos.priceOpen;
    const double curSl = pos.sl;
    if (pos.type == "BUY") {
        const double profitPts = (tick.bid - entry) / point;
        const double target = roundTo(entry + offsetPoints * point, digits);
        if (profitPts >= triggerPoints && (curSl == 0 || curSl < target))
            return backend.modifySlTp(pos.ticket, pos.symbol, true, target, false, 0);
    } else {
        const double profitPts = (entry - tick.ask) / point;
        const double target = roundTo(entry - offsetPoints * point, digits);
        if (profitPts >= triggerPoints && (curSl == 0 || curSl > target))
            return backend.modifySlTp(pos.ticket, pos.symbol, true, target, false, 0);
    }
    return false;
}

bool applyTrailingStop(TradingBackend &backend, const Position &pos, const SymbolSpec &spec,
                       int trailingPoints, int stepPoints)
{
    if (trailingPoints <= 0 || !spec.valid)
        return false;
    const double point = spec.point;
    const int digits = spec.digits;
    if (point <= 0)
        return false;
    const Tick tick = backend.getTick(pos.symbol);
    if (!tick.valid)
        return false;
    const double entry = pos.priceOpen;
    const double curSl = pos.sl;
    const double minDist = std::max(spec.stopLevel, 10) * point;
    if (pos.type == "BUY") {
        const double price = tick.bid;
        const double ideal = roundTo(price - trailingPoints * point, digits);
        if (ideal > entry && (curSl == 0 || (ideal - curSl) >= stepPoints * point))
            if ((price - ideal) >= minDist)
                return backend.modifySlTp(pos.ticket, pos.symbol, true, ideal, false, 0);
    } else {
        const double price = tick.ask;
        const double ideal = roundTo(price + trailingPoints * point, digits);
        if (ideal < entry && (curSl == 0 || (curSl - ideal) >= stepPoints * point))
            if ((ideal - price) >= minDist)
                return backend.modifySlTp(pos.ticket, pos.symbol, true, ideal, false, 0);
    }
    return false;
}

QString virtualExitHit(const QString &posType, double sl, double tp, double bid, double ask)
{
    if (posType == "BUY") {
        if (sl && bid <= sl)
            return QStringLiteral("SL");
        if (tp && bid >= tp)
            return QStringLiteral("TP");
    } else {
        if (sl && ask >= sl)
            return QStringLiteral("SL");
        if (tp && ask <= tp)
            return QStringLiteral("TP");
    }
    return {};
}

void computePercentSlTp(const QString &side, double entry, double slPercent,
                        double tpPercent, int digits, double &outSl, double &outTp)
{
    const double slp = slPercent / 100.0;
    const double tpp = tpPercent / 100.0;
    const QString s = side.toUpper();
    const bool isBuy = (s == "BUY" || s == "0" || s == "ORDER_TYPE_BUY");
    if (isBuy) {
        outSl = roundTo(entry * (1 - slp), digits);
        outTp = roundTo(entry * (1 + tpp), digits);
    } else {
        outSl = roundTo(entry * (1 + slp), digits);
        outTp = roundTo(entry * (1 - tpp), digits);
    }
}

double currentExposure(TradingBackend &backend, long long magic)
{
    double total = 0;
    for (const Position &p : backend.positions())
        if (!magic || p.magic == magic)
            total += p.volume;
    return total;
}

int consecutiveLosses(TradingBackend &backend, long long magic)
{
    const QDateTime now = QDateTime::currentDateTimeUtc();
    QVector<Deal> deals = backend.historyDeals(now.addDays(-30), now);
    if (magic) {
        QVector<Deal> f;
        for (const Deal &d : deals)
            if (d.magic == magic)
                f << d;
        deals = f;
    }
    std::sort(deals.begin(), deals.end(),
              [](const Deal &a, const Deal &b) { return a.time > b.time; });
    int streak = 0;
    for (const Deal &d : deals) {
        if (d.netProfit < 0)
            ++streak;
        else if (d.netProfit > 0)
            break;
    }
    return streak;
}

int dailyTradeCount(TradingBackend &backend, long long magic)
{
    const QVector<Deal> deals = backend.historyDeals(todayStartUtc(), QDateTime::currentDateTimeUtc());
    if (magic) {
        int c = 0;
        for (const Deal &d : deals)
            if (d.magic == magic)
                ++c;
        return c;
    }
    return deals.size();
}

bool dailyDrawdownBreached(TradingBackend &backend, double maxDrawdown, long long magic,
                           double &outDd)
{
    outDd = 0.0;
    if (maxDrawdown <= 0)
        return false;
    const QVector<Deal> deals = backend.historyDeals(todayStartUtc(), QDateTime::currentDateTimeUtc());
    double closed = 0;
    for (const Deal &d : deals)
        if (!magic || d.magic == magic)
            closed += d.netProfit;
    double floating = 0;
    for (const Position &p : backend.positions())
        if (!magic || p.magic == magic)
            floating += p.profit;
    const double total = closed + floating;
    const Account acc = backend.accountInfo();
    const double balance = acc.balance;
    if (balance <= 0)
        return false;
    double startBalance = balance - closed;
    if (startBalance <= 0)
        startBalance = balance;
    if (total < 0) {
        outDd = std::abs(total) / startBalance;
        return outDd >= maxDrawdown;
    }
    return false;
}

bool passesRiskGates(TradingBackend &backend, const Settings &s, const QString &symbol,
                     QString &reason)
{
    reason.clear();
    if (!canOpenNewPosition(backend, symbol, s.magicNumber, s.maxOpenPositions)) {
        reason = QStringLiteral("Batas posisi (%1) untuk %2 tercapai.")
                     .arg(s.maxOpenPositions).arg(symbol);
        return false;
    }
    if (s.maxDailyTrades > 0 && dailyTradeCount(backend, s.magicNumber) >= s.maxDailyTrades) {
        reason = QStringLiteral("Batas trade harian (%1) tercapai.").arg(s.maxDailyTrades);
        return false;
    }
    if (s.dailyDrawdownLimit > 0) {
        double dd = 0;
        if (dailyDrawdownBreached(backend, s.dailyDrawdownLimit, s.magicNumber, dd)) {
            reason = QStringLiteral("Batas drawdown harian terlampaui (%1%).")
                         .arg(dd * 100, 0, 'f', 2);
            return false;
        }
    }
    if (s.maxSpreadPoints > 0) {
        bool ok = false;
        const double sp = backend.spreadPoints(symbol, &ok);
        int effMax = s.maxSpreadPoints;
        if (symbol.toUpper().contains("BTC") && s.maxSpreadPoints < 1000)
            effMax = std::max(s.maxSpreadPoints, 3000);
        if (ok && sp > effMax) {
            reason = QStringLiteral("Spread %1 pts melebihi batas %2 pts.")
                         .arg(sp, 0, 'f', 0).arg(effMax);
            return false;
        }
    }
    if (s.maxConsecutiveLosses > 0) {
        const int streak = consecutiveLosses(backend, s.magicNumber);
        if (streak >= s.maxConsecutiveLosses) {
            reason = QStringLiteral("Safety guard: %1 loss beruntun (batas %2), trading dijeda.")
                         .arg(streak).arg(s.maxConsecutiveLosses);
            return false;
        }
    }
    return true;
}

OrderResult openOrderIfAllowed(TradingBackend &backend, const Settings &s, const QString &symbol,
                               const QString &side, double volume, double sl, double tp,
                               const QString &comment)
{
    QString reason;
    if (!passesRiskGates(backend, s, symbol, reason)) {
        qInfo("Order %s %s dilewati oleh gerbang risiko: %s",
              qUtf8Printable(side), qUtf8Printable(symbol), qUtf8Printable(reason));
        OrderResult r;
        r.message = reason;
        return r;
    }
    if (s.maxExposureLots > 0) {
        if (currentExposure(backend, s.magicNumber) + volume > s.maxExposureLots + 1e-9) {
            OrderResult r;
            r.message = QStringLiteral("Total eksposur akan melebihi batas %1 lot.")
                            .arg(s.maxExposureLots);
            qInfo("Order %s %s dilewati: %s", qUtf8Printable(side),
                  qUtf8Printable(symbol), qUtf8Printable(r.message));
            return r;
        }
    }
    return backend.sendMarketOrder(symbol, side, volume, sl, tp, s.magicNumber,
                                   comment.left(31));
}

} // namespace TradeRules
