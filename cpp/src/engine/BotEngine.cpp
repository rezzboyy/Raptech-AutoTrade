#include "engine/BotEngine.h"

#include "backend/TradingBackend.h"
#include "core/Settings.h"
#include "engine/TradeRules.h"
#include "indicators/Indicators.h"

#include <QDateTime>
#include <QLoggingCategory>
#include <QtGlobal>
#include <algorithm>
#include <cmath>

namespace {
double roundTo(double v, int digits)
{
    const double f = std::pow(10.0, digits);
    return std::round(v * f) / f;
}
} // namespace

BotEngine::BotEngine(TradingBackend *backend, Settings *settings)
    : m_backend(backend), m_settings(settings)
{
}

QDateTime BotEngine::nowUtc() const
{
    return m_nowOverride.isValid() ? m_nowOverride : QDateTime::currentDateTimeUtc();
}

void BotEngine::journal(const QString &action, const QString &symbol, const QString &detail, bool ok)
{
    if (onJournal)
        onJournal(action, symbol, detail, ok);
}

void BotEngine::manageOpenPositions()
{
    const Settings &s = *m_settings;

    // Auto-close berdasarkan umur posisi (max_holding_bars, dari SETTINGS skrip).
    const QVariantMap sc = m_strategy ? m_strategy->scriptSettings() : QVariantMap();
    const int mhb = sc.value("max_holding_bars", 0).toInt();
    if (mhb > 0) {
        static const QHash<QString, int> tfSec = {
            {"M1", 60}, {"M5", 300}, {"M15", 900}, {"M30", 1800},
            {"H1", 3600}, {"H4", 14400}, {"D1", 86400}};
        const int tf = tfSec.value(s.timeframeStr.toUpper(), 300);
        const qint64 nowSec = nowUtc().toSecsSinceEpoch();
        for (const Position &p : m_backend->positions()) {
            if (p.time > 0 && (nowSec - p.time) >= qint64(mhb) * tf && p.ticket) {
                qInfo("Posisi %lld ditutup otomatis (max_holding_bars=%d).", p.ticket, mhb);
                m_backend->closePosition(p.ticket, p.symbol);
                m_virtual.remove(p.ticket);
                journal("CLOSE", p.symbol,
                        QStringLiteral("tutup posisi %1 (max holding %2 bars)").arg(p.ticket).arg(mhb),
                        true);
            }
        }
    }

    if (s.virtualSltpEnabled)
        return; // trailing/BE dikelola di level virtual
    if (!s.breakEvenEnabled && !s.trailingStopEnabled)
        return;
    for (const Position &p : m_backend->positions()) {
        if (s.magicNumber > 0 && p.magic != s.magicNumber)
            continue;
        const SymbolSpec spec = m_backend->symbolSpec(p.symbol);
        if (!spec.valid)
            continue;
        if (s.breakEvenEnabled)
            TradeRules::applyBreakEven(*m_backend, p, spec,
                                       s.breakEvenTriggerPoints, s.breakEvenOffsetPoints);
        if (s.trailingStopEnabled)
            TradeRules::applyTrailingStop(*m_backend, p, spec,
                                          s.trailingStopPoints, s.trailingStepPoints);
    }
}

void BotEngine::computeSlTp(const QString &symbol, const QString &signal, double entry,
                            const Command &ov, double &outSl, double &outTp)
{
    outSl = 0.0;
    outTp = 0.0;
    const Settings &s = *m_settings;
    const SymbolSpec spec = m_backend->symbolSpec(symbol);
    if (!spec.valid || spec.point <= 0)
        return;
    const double point = spec.point;
    const int digits = spec.digits;

    // Mode persen (kecuali skrip beri points eksplisit).
    if (s.slTpMode == "percent" && !ov.hasSlPoints && !ov.hasTpPoints) {
        const double slp = s.slPercent / 100.0;
        const double tpp = s.tpPercent / 100.0;
        if (signal == sig::BUY) {
            outSl = roundTo(entry * (1 - slp), digits);
            outTp = roundTo(entry * (1 + tpp), digits);
        } else {
            outSl = roundTo(entry * (1 + slp), digits);
            outTp = roundTo(entry * (1 - tpp), digits);
        }
        return;
    }

    // Mode points. Prioritas mengikuti versi Python:
    //   SL: intent -> atr_sl_mult -> param strategi -> SETTINGS skrip -> settings.
    //   TP: intent -> atr_tp_mult -> risk_reward_ratio -> param -> SETTINGS -> settings.
    const QVariantMap sc = m_strategy ? m_strategy->scriptSettings() : QVariantMap();
    int slPts = s.slPoints;
    int tpPts = s.tpPoints;

    // Hitung ATR(14) dari 25 candle terakhir (lazy, hanya bila dibutuhkan).
    auto atrLast = [&]() -> double {
        const QVector<Candle> rates = m_backend->getRates(symbol, s.timeframeStr, 25);
        if (rates.size() < 15)
            return ind::nan();
        QVector<double> hi, lo, cl;
        hi.reserve(rates.size()); lo.reserve(rates.size()); cl.reserve(rates.size());
        for (const Candle &c : rates) { hi << c.h; lo << c.l; cl << c.c; }
        const QVector<double> a = ind::atr(hi, lo, cl, 14);
        return a.isEmpty() ? ind::nan() : a.last();
    };

    // ----- SL points -----
    if (sc.contains("atr_sl_mult") && !ov.hasSlPoints && !ov.hasSl) {
        slPts = s.slPoints; // fallback
        const double a = atrLast();
        if (!ind::isNan(a) && point > 0)
            slPts = int(std::round(a * sc.value("atr_sl_mult").toDouble() / point));
    } else if (ov.hasSlPoints) {
        slPts = ov.slPoints;
    } else if (m_strategy && m_strategy->hasParam("sl_points")) {
        slPts = int(m_strategy->param("sl_points", s.slPoints));
    } else if (sc.contains("sl_points")) {
        slPts = sc.value("sl_points").toInt();
    }

    // ----- TP points -----
    const bool paramHasTp = m_strategy && m_strategy->hasParam("tp_points");
    if (sc.contains("atr_tp_mult") && !ov.hasTpPoints && !ov.hasTp) {
        tpPts = s.tpPoints; // fallback
        const double a = atrLast();
        if (!ind::isNan(a) && point > 0)
            tpPts = int(std::round(a * sc.value("atr_tp_mult").toDouble() / point));
    } else if (sc.contains("risk_reward_ratio") && !ov.hasTpPoints && !paramHasTp
               && !sc.contains("tp_points")) {
        tpPts = int(std::round(slPts * sc.value("risk_reward_ratio").toDouble()));
    } else if (ov.hasTpPoints) {
        tpPts = ov.tpPoints;
    } else if (paramHasTp) {
        tpPts = int(m_strategy->param("tp_points", s.tpPoints));
    } else if (sc.contains("tp_points")) {
        tpPts = sc.value("tp_points").toInt();
    }

    // Proteksi batas minimal broker (cegah #10016 Invalid stops).
    const int stopLevel = spec.stopLevel;
    int currSpread = 0;
    bool ok = false;
    const double sp = m_backend->spreadPoints(symbol, &ok);
    if (ok && sp > 0)
        currSpread = int(std::round(sp));
    const int minStop = std::max({stopLevel, int(currSpread * 1.5), currSpread + 50, 20});
    if (slPts > 0 && slPts < minStop)
        slPts = minStop;
    if (tpPts > 0 && tpPts < minStop)
        tpPts = minStop;

    if (signal == sig::BUY) {
        outSl = roundTo(entry - slPts * point, digits);
        outTp = roundTo(entry + tpPts * point, digits);
    } else {
        outSl = roundTo(entry + slPts * point, digits);
        outTp = roundTo(entry - tpPts * point, digits);
    }
}

bool BotEngine::handleSignal(const QString &symbol, const QString &signal, const Command &ov)
{
    const Settings &s = *m_settings;
    const Tick tick = m_backend->getTick(symbol);
    if (!tick.valid) {
        qWarning("[MARKET TUTUP/DATA KOSONG] Harga %s tidak tersedia. Order %s dibatalkan.",
                 qUtf8Printable(symbol), qUtf8Printable(signal));
        return false;
    }
    const double entry = (signal == sig::BUY) ? tick.ask : tick.bid;

    double sl = 0, tp = 0;
    computeSlTp(symbol, signal, entry, ov, sl, tp);
    if (ov.hasSl)
        sl = ov.sl;
    if (ov.hasTp)
        tp = ov.tp;

    const SymbolSpec spec = m_backend->symbolSpec(symbol);
    const Account acc = m_backend->accountInfo();

    // Validasi jarak SL/TP absolut (cegah #10016).
    if (spec.valid && spec.point > 0) {
        const double pt = spec.point;
        const int dg = spec.digits;
        int sp = 0;
        bool ok = false;
        const double spRaw = m_backend->spreadPoints(symbol, &ok);
        if (ok && spRaw > 0)
            sp = int(std::round(spRaw));
        const double minDist = std::max({spec.stopLevel, int(sp * 1.5), sp + 50, 20}) * pt;
        if (signal == sig::BUY) {
            if (sl > 0 && (entry - sl) < minDist)
                sl = roundTo(entry - minDist, dg);
            if (tp > 0 && (tp - entry) < minDist)
                tp = roundTo(entry + minDist, dg);
        } else {
            if (sl > 0 && (sl - entry) < minDist)
                sl = roundTo(entry + minDist, dg);
            if (tp > 0 && (entry - tp) < minDist)
                tp = roundTo(entry - minDist, dg);
        }
    }

    // Volume: intent -> hitung dari risiko.
    double lot;
    if (ov.hasVolume) {
        lot = ov.volume;
    } else {
        const double riskFrac = ov.hasRisk ? ov.risk : s.riskPerTrade;
        lot = TradeRules::calcLotFromSpec(spec, acc.balance, riskFrac, sl, entry);
    }
    if (lot <= 0) {
        qWarning("Ukuran lot untuk %s tidak valid, order dibatalkan.", qUtf8Printable(symbol));
        return false;
    }

    const QString side = TradeRules::mapSignalToSide(signal);
    const QString cmt = !ov.comment.isEmpty() ? ov.comment : QStringLiteral("mt5bot");

    if (s.virtualSltpEnabled) {
        OrderResult res = TradeRules::openOrderIfAllowed(*m_backend, s, symbol, side, lot,
                                                         0.0, 0.0, cmt);
        if (res.ok && res.hasTicket) {
            VirtualSltp v;
            v.symbol = symbol;
            v.type = (signal == sig::BUY) ? "BUY" : "SELL";
            v.sl = sl;
            v.tp = tp;
            m_virtual.insert(res.ticket, v);
            qInfo("Virtual SL/TP diset posisi %lld: SL=%.5f TP=%.5f", res.ticket, sl, tp);
            return true;
        }
        return false;
    }
    OrderResult res = TradeRules::openOrderIfAllowed(*m_backend, s, symbol, side, lot, sl, tp, cmt);
    return res.ok;
}

void BotEngine::checkVirtualExits()
{
    if (m_virtual.isEmpty())
        return;
    QHash<long long, Position> positions;
    for (const Position &p : m_backend->positions())
        positions.insert(p.ticket, p);

    const QList<long long> tickets = m_virtual.keys();
    for (long long ticket : tickets) {
        if (!positions.contains(ticket)) {
            m_virtual.remove(ticket); // sudah tertutup di luar bot
            continue;
        }
        VirtualSltp &v = m_virtual[ticket];
        const SymbolSpec spec = m_backend->symbolSpec(v.symbol);
        const Tick tick = m_backend->getTick(v.symbol);
        if (!spec.valid || !tick.valid)
            continue;
        updateVirtualSl(positions[ticket], v, spec, tick);
        const QString hit = TradeRules::virtualExitHit(v.type, v.sl, v.tp, tick.bid, tick.ask);
        if (!hit.isEmpty()) {
            qInfo("Virtual %s tercapai posisi %lld (%s) -> tutup.",
                  qUtf8Printable(hit), ticket, qUtf8Printable(v.symbol));
            if (m_backend->closePosition(ticket, v.symbol).ok)
                m_virtual.remove(ticket);
        }
    }
}

void BotEngine::updateVirtualSl(const Position &pos, VirtualSltp &v, const SymbolSpec &spec,
                                const Tick &tick)
{
    const Settings &s = *m_settings;
    const double point = spec.point;
    const int digits = spec.digits;
    if (point <= 0)
        return;
    const double entry = pos.priceOpen;
    double curSl = v.sl;
    if (pos.type == "BUY") {
        const double price = tick.bid;
        if (s.breakEvenEnabled && s.breakEvenTriggerPoints > 0) {
            if ((price - entry) / point >= s.breakEvenTriggerPoints) {
                const double be = roundTo(entry + s.breakEvenOffsetPoints * point, digits);
                if (curSl == 0 || curSl < be) {
                    v.sl = be;
                    curSl = be;
                }
            }
        }
        if (s.trailingStopEnabled && s.trailingStopPoints > 0) {
            const double ideal = roundTo(price - s.trailingStopPoints * point, digits);
            if (ideal > entry && (curSl == 0 || (ideal - curSl) >= s.trailingStepPoints * point))
                v.sl = ideal;
        }
    } else {
        const double price = tick.ask;
        if (s.breakEvenEnabled && s.breakEvenTriggerPoints > 0) {
            if ((entry - price) / point >= s.breakEvenTriggerPoints) {
                const double be = roundTo(entry - s.breakEvenOffsetPoints * point, digits);
                if (curSl == 0 || curSl > be) {
                    v.sl = be;
                    curSl = be;
                }
            }
        }
        if (s.trailingStopEnabled && s.trailingStopPoints > 0) {
            const double ideal = roundTo(price + s.trailingStopPoints * point, digits);
            if (ideal < entry && (curSl == 0 || (curSl - ideal) >= s.trailingStepPoints * point))
                v.sl = ideal;
        }
    }
}

int BotEngine::closeAll(const QString &symbol)
{
    const Settings &s = *m_settings;
    int closed = 0;
    for (const Position &p : m_backend->positions(symbol)) {
        if (s.magicNumber > 0 && p.magic != s.magicNumber)
            continue;
        if (m_backend->closePosition(p.ticket, p.symbol).ok)
            ++closed;
    }
    qInfo("Tutup semua: %d posisi ditutup.", closed);
    return closed;
}

bool BotEngine::processTradingStep()
{
    const Settings &s = *m_settings;
    ++m_tradeSteps;

    manageOpenPositions();

    // ----- Filter waktu/sesi (dari SETTINGS skrip) -----
    const QVariantMap sc = m_strategy ? m_strategy->scriptSettings() : QVariantMap();
    if (!sc.isEmpty()) {
        const QDateTime nowU = nowUtc();
        const int pyWeekday = nowU.date().dayOfWeek() - 1; // Senin=0..Minggu=6
        const int hour = nowU.time().hour();

        // Filter penutupan Jumat (close_friday_hour).
        if (sc.contains("close_friday_hour")) {
            const int cfh = sc.value("close_friday_hour").toInt();
            if (pyWeekday == 4 && hour >= cfh) {
                if (!m_backend->positions().isEmpty()) {
                    qInfo("[FILTER JUMAT] Tutup semua posisi menjelang weekend (close_friday_hour=%d).",
                          cfh);
                    closeAll();
                }
                return true;
            }
        }

        // Filter hari aktif (active_days): daftar 0..6 (Senin..Minggu).
        if (sc.contains("active_days")) {
            const QVariantList days = sc.value("active_days").toList();
            bool active = false;
            for (const QVariant &d : days)
                if (d.toInt() == pyWeekday) { active = true; break; }
            if (!active)
                return true;
        }

        // Filter jam trading (trade_start_time & trade_end_time), format "HH:mm".
        const QString tStart = sc.value("trade_start_time").toString();
        const QString tEnd = sc.value("trade_end_time").toString();
        if (!tStart.isEmpty() || !tEnd.isEmpty()) {
            const QString curHm = nowU.toString("HH:mm");
            if (!tStart.isEmpty() && curHm < tStart)
                return true;
            if (!tEnd.isEmpty() && curHm > tEnd)
                return true;
        }
    }

    // Equity cut-loss.
    if (s.equityStopLoss > 0) {
        const Account acc = m_backend->accountInfo();
        if (acc.balance > 0 && acc.equity > 0) {
            const double dd = (acc.balance - acc.equity) / acc.balance;
            if (dd >= s.equityStopLoss) {
                qWarning("[EQUITY CUT-LOSS] Drawdown ekuitas %.2f%% >= %.2f%%. Tutup semua & stop.",
                         dd * 100, s.equityStopLoss * 100);
                closeAll();
                return false;
            }
        }
    }

    // Drawdown harian.
    if (s.dailyDrawdownLimit > 0) {
        double dd = 0;
        if (TradeRules::dailyDrawdownBreached(*m_backend, s.dailyDrawdownLimit, s.magicNumber, dd)) {
            qWarning("[PROTEKSI] Drawdown harian %.2f%% terlampaui. Auto trading nonaktif.", dd * 100);
            return false;
        }
    }

    // Batas trade harian.
    if (s.maxDailyTrades > 0
        && TradeRules::dailyTradeCount(*m_backend, s.magicNumber) >= s.maxDailyTrades) {
        return true;
    }

    // Evaluasi strategi per simbol.
    for (const QString &symv : s.symbolsList()) {
        const QVector<Candle> candles = m_backend->getRates(symv, s.timeframeStr, 200);
        if (candles.isEmpty())
            continue;
        if (!m_strategy)
            continue;
        const QString barTime = QString::number(candles.last().t);

        // Konteks runtime untuk strategi skrip (posisi, akun, tick, spec).
        RuntimeContext rt;
        rt.symbol = symv;
        rt.positions = m_backend->positions(symv);
        rt.account = m_backend->accountInfo();
        rt.tick = m_backend->getTick(symv);
        rt.spec = m_backend->symbolSpec(symv);

        QVector<Command> cmds = m_strategy->onBar(candles, rt);
        for (Command &cmd : cmds) {
            cmd.barTime = barTime;
            executeCommand(symv, cmd);
        }
    }
    return true;
}

void BotEngine::executeCommand(const QString &symbol, const Command &cmd)
{
    const Settings &s = *m_settings;
    const QString action = cmd.action;

    const QVariantMap sc = m_strategy ? m_strategy->scriptSettings() : QVariantMap();

    if (action == sig::BUY || action == sig::SELL) {
        // 1. Close on reversal (default aktif; bisa dimatikan via SETTINGS).
        if (sc.value("close_on_reversal", true).toBool()) {
            const QString oppType = (action == sig::BUY) ? "SELL" : "BUY";
            for (const Position &p : m_backend->positions(symbol)) {
                if (s.magicNumber > 0 && p.magic != s.magicNumber)
                    continue;
                if (p.type == oppType && p.ticket) {
                    m_backend->closePosition(p.ticket, symbol);
                    m_virtual.remove(p.ticket);
                    journal("REVERSAL", symbol,
                            QStringLiteral("tutup posisi %1 (%2) sebelum balik arah")
                                .arg(p.ticket).arg(oppType), true);
                }
            }
        }

        // 2. Filter minimal margin level (min_margin_level, %).
        const double minMl = sc.value("min_margin_level", 0.0).toDouble();
        if (minMl > 0) {
            const Account acc = m_backend->accountInfo();
            const double lvl = (acc.margin > 0) ? (acc.equity / acc.margin * 100.0) : 99999.0;
            if (lvl < minMl) {
                journal(action, symbol,
                        QStringLiteral("dilewati (margin level %1% < batas %2%)")
                            .arg(lvl, 0, 'f', 1).arg(minMl, 0, 'f', 1), false);
                return;
            }
        }

        // 3. One trade per bar (default aktif; bisa dimatikan via SETTINGS).
        if (sc.value("one_trade_per_bar", true).toBool()) {
            if (!cmd.barTime.isEmpty() && m_lastTradeBar.value(symbol) == cmd.barTime) {
                journal(action, symbol, "dilewati (one_trade_per_bar)", false);
                return;
            }
        }

        // 4. Cooldown antar entry (cooldown_bars). Hanya berlaku bila sudah pernah
        //    ada trade untuk simbol ini (agar entry pertama tidak ikut terblok).
        const int cdBars = sc.value("cooldown_bars", 0).toInt();
        if (cdBars > 0 && m_lastTradeStep.contains(symbol)) {
            if ((m_tradeSteps - m_lastTradeStep.value(symbol)) < cdBars) {
                journal(action, symbol,
                        QStringLiteral("dilewati (cooldown %1 bar)").arg(cdBars), false);
                return;
            }
        }

        // 5. Gerbang batas posisi + eksekusi.
        if (TradeRules::canOpenNewPosition(*m_backend, symbol, s.magicNumber, s.maxOpenPositions)) {
            if (handleSignal(symbol, action, cmd)) {
                journal(action, symbol, QStringLiteral("buka %1").arg(action), true);
                if (!cmd.barTime.isEmpty())
                    m_lastTradeBar.insert(symbol, cmd.barTime);
                m_lastTradeStep.insert(symbol, m_tradeSteps);
            }
        } else {
            journal(action, symbol, "dilewati (batas Maks Posisi tercapai)", false);
        }
    } else if (action == "CLOSE") {
        if (cmd.ticket) {
            const bool ok = m_backend->closePosition(cmd.ticket, symbol).ok;
            m_virtual.remove(cmd.ticket);
            journal("CLOSE", symbol, QStringLiteral("tutup posisi %1").arg(cmd.ticket), ok);
        }
    } else if (action == "CLOSE_ALL") {
        const int n = closeAll(symbol);
        journal("CLOSE_ALL", symbol, QStringLiteral("tutup semua (%1 posisi)").arg(n), true);
    } else if (action == "MODIFY") {
        if (cmd.ticket) {
            const bool ok = m_backend->modifySlTp(cmd.ticket, symbol, cmd.hasSl, cmd.sl,
                                                  cmd.hasTp, cmd.tp);
            if (m_virtual.contains(cmd.ticket)) {
                if (cmd.hasSl)
                    m_virtual[cmd.ticket].sl = cmd.sl;
                if (cmd.hasTp)
                    m_virtual[cmd.ticket].tp = cmd.tp;
            }
            journal("MODIFY", symbol, QStringLiteral("ubah SL/TP %1").arg(cmd.ticket), ok);
        }
    }
}

// ----- Siklus koneksi & monitoring -----

bool BotEngine::connect()
{
    if (!m_backend->connect())
        return false;
    Settings &s = *m_settings;
    QStringList valid;
    for (const QString &sym : s.symbolsList()) {
        const QString resolved = m_backend->resolveSymbol(sym);
        const QString target = resolved.isEmpty() ? sym : resolved;
        if (m_backend->ensureSymbol(target))
            valid << target;
        else if (m_backend->ensureSymbol(sym))
            valid << sym;
    }
    if (!valid.isEmpty())
        s.symbol = valid.first();
    else
        qWarning("Simbol '%s' tidak ditemukan; bot tetap terhubung, pilih simbol yang benar.",
                 qUtf8Printable(s.symbol));
    return true;
}

void BotEngine::disconnect() { m_backend->disconnect(); }

Account BotEngine::pollAccount() { return m_backend->accountInfo(); }
QVector<Position> BotEngine::pollPositions() { return m_backend->positions(); }
QVector<Order> BotEngine::pollOrders() { return m_backend->pendingOrders(); }

QVector<Candle> BotEngine::pollCandles(const QString &symbol, int count)
{
    return m_backend->getRates(symbol, m_settings->timeframeStr, count);
}

QStringList BotEngine::listSymbols(int limit) { return m_backend->listSymbols(limit); }

QVariantMap BotEngine::pollStats()
{
    QVariantMap out{
        {"total_trades", 0}, {"wins", 0}, {"losses", 0}, {"breakeven", 0},
        {"win_rate", 0.0}, {"profit_factor", 0.0}, {"gross_profit", 0.0},
        {"gross_loss", 0.0}, {"net_profit", 0.0}, {"avg_profit", 0.0},
        {"avg_loss", 0.0}, {"max_profit", 0.0}, {"max_loss", 0.0}};
    const QDateTime now = QDateTime::currentDateTimeUtc();
    QVector<Deal> deals = m_backend->historyDeals(now.addDays(-90), now.addDays(1));
    if (m_settings->magicNumber > 0) {
        QVector<Deal> matched;
        for (const Deal &d : deals)
            if (d.magic == m_settings->magicNumber)
                matched << d;
        if (!matched.isEmpty())
            deals = matched;
    }
    const int total = deals.size();
    if (total == 0)
        return out;
    int wins = 0, losses = 0;
    double grossProfit = 0, grossLoss = 0, net = 0, maxP = 0, maxL = 0;
    bool first = true;
    for (const Deal &d : deals) {
        net += d.netProfit;
        if (d.netProfit > 0) { ++wins; grossProfit += d.netProfit; }
        else if (d.netProfit < 0) { ++losses; grossLoss += -d.netProfit; }
        if (first) { maxP = maxL = d.netProfit; first = false; }
        else { maxP = std::max(maxP, d.netProfit); maxL = std::min(maxL, d.netProfit); }
    }
    auto r2 = [](double v) { return std::round(v * 100.0) / 100.0; };
    out["total_trades"] = total;
    out["wins"] = wins;
    out["losses"] = losses;
    out["breakeven"] = total - wins - losses;
    out["win_rate"] = std::round(double(wins) / total * 1000.0) / 10.0;
    out["profit_factor"] = grossLoss > 0 ? r2(grossProfit / grossLoss)
                                         : (grossProfit > 0 ? r2(grossProfit) : 0.0);
    out["gross_profit"] = r2(grossProfit);
    out["gross_loss"] = r2(grossLoss);
    out["net_profit"] = r2(net);
    out["avg_profit"] = wins ? r2(grossProfit / wins) : 0.0;
    out["avg_loss"] = losses ? r2(grossLoss / losses) : 0.0;
    out["max_profit"] = r2(maxP);
    out["max_loss"] = r2(maxL);
    return out;
}

QVariantList BotEngine::pollEquityCurve(double curBal, double curEq)
{
    QVariantList curve;
    const QDateTime now = QDateTime::currentDateTimeUtc();
    QVector<Deal> deals = m_backend->historyDeals(now.addDays(-90), now.addDays(1));
    if (m_settings->magicNumber > 0) {
        QVector<Deal> matched;
        for (const Deal &d : deals)
            if (d.magic == m_settings->magicNumber)
                matched << d;
        if (!matched.isEmpty())
            deals = matched;
    }
    std::sort(deals.begin(), deals.end(),
              [](const Deal &a, const Deal &b) { return a.time < b.time; });
    auto r2 = [](double v) { return std::round(v * 100.0) / 100.0; };
    if (!deals.isEmpty()) {
        double totalP = 0;
        for (const Deal &d : deals)
            totalP += d.netProfit;
        double runBal = curBal > 0 ? (curBal - totalP) : 0.0;
        for (const Deal &d : deals) {
            runBal += d.netProfit;
            curve << QVariantMap{{"t", static_cast<qlonglong>(d.time)},
                                 {"balance", r2(runBal)}, {"equity", r2(runBal)}};
        }
    }
    if (curBal > 0) {
        curve << QVariantMap{
            {"t", static_cast<qlonglong>(now.toSecsSinceEpoch())},
            {"balance", r2(curBal)}, {"equity", r2(curEq > 0 ? curEq : curBal)}};
    }
    if (curve.size() > 120)
        curve = curve.mid(curve.size() - 120);
    return curve;
}

OrderResult BotEngine::manualMarketOrder(const QString &symbol, const QString &side,
                                         double volume, double sl, double tp)
{
    const QString resolved = m_backend->resolveSymbol(symbol);
    const QString target = resolved.isEmpty() ? symbol : resolved;
    return m_backend->sendMarketOrder(target, side, volume, sl, tp,
                                      m_settings->magicNumber, "manual");
}

OrderResult BotEngine::placePendingOrder(const QString &symbol, const QString &orderType,
                                         double volume, double price, double sl, double tp)
{
    const QString resolved = m_backend->resolveSymbol(symbol);
    const QString target = resolved.isEmpty() ? symbol : resolved;
    return m_backend->sendPendingOrder(target, orderType, volume, price, sl, tp,
                                       m_settings->magicNumber, "manual");
}

bool BotEngine::closeTicket(long long ticket)
{
    QString symbol;
    for (const Position &p : m_backend->positions())
        if (p.ticket == ticket) {
            symbol = p.symbol;
            break;
        }
    if (symbol.isEmpty())
        return false;
    return m_backend->closePosition(ticket, symbol).ok;
}

bool BotEngine::deletePending(long long ticket)
{
    return m_backend->deletePendingOrder(ticket).ok;
}
