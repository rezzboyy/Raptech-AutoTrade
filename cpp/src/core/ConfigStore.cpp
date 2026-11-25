#include "core/ConfigStore.h"
#include "core/Settings.h"

#include <QFile>
#include <QJsonDocument>
#include <QSet>

namespace {
const QSet<QString> kValidTimeframes = {"M1", "M5", "M15", "M30", "H1", "H4", "D1"};

// Ambil nilai dengan fallback bila key tak ada.
double numOr(const QJsonObject &o, const QString &k, double def)
{
    return o.contains(k) ? o.value(k).toDouble(def) : def;
}
int intOr(const QJsonObject &o, const QString &k, int def)
{
    return o.contains(k) ? o.value(k).toInt(def) : def;
}
QString strOr(const QJsonObject &o, const QString &k, const QString &def)
{
    return o.contains(k) ? o.value(k).toString(def) : def;
}
bool boolOr(const QJsonObject &o, const QString &k, bool def)
{
    return o.contains(k) ? o.value(k).toBool(def) : def;
}
} // namespace

namespace ConfigStore {

QJsonObject toJson(const Settings &s)
{
    QJsonObject o;
    o["symbol"] = s.symbol;
    o["timeframe_str"] = s.timeframeStr;
    o["magic_number"] = s.magicNumber;
    o["risk_per_trade"] = s.riskPerTrade;
    o["max_open_positions"] = s.maxOpenPositions;
    o["sl_tp_mode"] = s.slTpMode;
    o["sl_points"] = s.slPoints;
    o["tp_points"] = s.tpPoints;
    o["sl_percent"] = s.slPercent;
    o["tp_percent"] = s.tpPercent;
    o["virtual_sltp_enabled"] = s.virtualSltpEnabled;
    o["trailing_stop_enabled"] = s.trailingStopEnabled;
    o["trailing_stop_points"] = s.trailingStopPoints;
    o["trailing_step_points"] = s.trailingStepPoints;
    o["break_even_enabled"] = s.breakEvenEnabled;
    o["break_even_trigger_points"] = s.breakEvenTriggerPoints;
    o["break_even_offset_points"] = s.breakEvenOffsetPoints;
    o["daily_drawdown_limit"] = s.dailyDrawdownLimit;
    o["max_daily_trades"] = s.maxDailyTrades;
    o["max_spread_points"] = s.maxSpreadPoints;
    o["max_exposure_lots"] = s.maxExposureLots;
    o["equity_stop_loss"] = s.equityStopLoss;
    o["max_consecutive_losses"] = s.maxConsecutiveLosses;
    o["strategy_name"] = s.strategyName;
    o["strategy_params"] = QJsonObject::fromVariantMap(s.strategyParams);
    o["script_name"] = s.scriptName;
    o["script_source"] = s.scriptSource;
    o["loop_interval"] = s.loopInterval;
    o["theme"] = s.theme;
    o["backend"] = s.backend;
    o["mcp_endpoint"] = s.mcpEndpoint;
    // CATATAN: mcp_api_key & kredensial sengaja TIDAK disertakan.
    return o;
}

QStringList validate(const QJsonObject &o, const Settings &c)
{
    QStringList errors;

    const QString tf = strOr(o, "timeframe_str", c.timeframeStr).toUpper();
    if (!kValidTimeframes.contains(tf))
        errors << QStringLiteral("Timeframe tidak valid: %1").arg(tf);

    const double risk = numOr(o, "risk_per_trade", c.riskPerTrade);
    if (!(risk > 0.0 && risk <= 1.0))
        errors << QStringLiteral("Risiko per trade harus antara 0 dan 1 (mis. 0.01 = 1%).");

    if (intOr(o, "max_open_positions", c.maxOpenPositions) < 1)
        errors << QStringLiteral("Maksimum posisi harus >= 1.");

    if (intOr(o, "loop_interval", c.loopInterval) < 1)
        errors << QStringLiteral("Interval loop harus >= 1 detik.");

    const QString mode = strOr(o, "sl_tp_mode", c.slTpMode).toLower();
    if (mode != "points" && mode != "percent")
        errors << QStringLiteral("Mode SL/TP harus 'points' atau 'percent'.");
    if (mode == "percent") {
        if (numOr(o, "sl_percent", c.slPercent) <= 0 || numOr(o, "tp_percent", c.tpPercent) <= 0)
            errors << QStringLiteral("SL% dan TP% harus > 0 saat mode percent.");
    } else {
        if (intOr(o, "sl_points", c.slPoints) < 10 || intOr(o, "tp_points", c.tpPoints) < 10)
            errors << QStringLiteral("SL dan TP points minimal 10 points.");
    }

    const double dd = numOr(o, "daily_drawdown_limit", c.dailyDrawdownLimit);
    if (dd < 0 || dd > 1)
        errors << QStringLiteral("Batas drawdown harian harus antara 0 dan 1.");

    if (intOr(o, "max_daily_trades", c.maxDailyTrades) < 0)
        errors << QStringLiteral("Batas trade harian harus >= 0.");

    if (strOr(o, "symbol", c.symbol).trimmed().isEmpty())
        errors << QStringLiteral("Simbol tidak boleh kosong.");

    if (intOr(o, "max_spread_points", c.maxSpreadPoints) < 0)
        errors << QStringLiteral("Max spread points harus >= 0.");
    if (numOr(o, "max_exposure_lots", c.maxExposureLots) < 0)
        errors << QStringLiteral("Max exposure lots harus >= 0.");
    const double esl = numOr(o, "equity_stop_loss", c.equityStopLoss);
    if (esl < 0 || esl > 1)
        errors << QStringLiteral("Equity stop loss harus antara 0 dan 1.");
    if (intOr(o, "max_consecutive_losses", c.maxConsecutiveLosses) < 0)
        errors << QStringLiteral("Max consecutive losses harus >= 0.");

    const QString theme = strOr(o, "theme", c.theme).toLower();
    if (theme != "dark" && theme != "light")
        errors << QStringLiteral("Theme harus 'dark' atau 'light'.");

    const QString backend = strOr(o, "backend", c.backend).toLower();
    if (backend != "native" && backend != "mcp" && backend != "sim")
        errors << QStringLiteral("Backend harus 'native', 'mcp', atau 'sim'.");

    return errors;
}

QStringList apply(const QJsonObject &o, Settings &s)
{
    const QStringList errors = validate(o, s);
    if (!errors.isEmpty())
        return errors;

    if (o.contains("symbol")) s.symbol = o["symbol"].toString();
    if (o.contains("timeframe_str")) s.timeframeStr = o["timeframe_str"].toString().toUpper();
    if (o.contains("magic_number")) s.magicNumber = o["magic_number"].toInt();
    if (o.contains("risk_per_trade")) s.riskPerTrade = o["risk_per_trade"].toDouble();
    if (o.contains("max_open_positions")) s.maxOpenPositions = o["max_open_positions"].toInt();
    if (o.contains("sl_tp_mode")) s.slTpMode = o["sl_tp_mode"].toString().toLower();
    if (o.contains("sl_points")) s.slPoints = o["sl_points"].toInt();
    if (o.contains("tp_points")) s.tpPoints = o["tp_points"].toInt();
    if (o.contains("sl_percent")) s.slPercent = o["sl_percent"].toDouble();
    if (o.contains("tp_percent")) s.tpPercent = o["tp_percent"].toDouble();
    if (o.contains("virtual_sltp_enabled")) s.virtualSltpEnabled = o["virtual_sltp_enabled"].toBool();
    if (o.contains("trailing_stop_enabled")) s.trailingStopEnabled = o["trailing_stop_enabled"].toBool();
    if (o.contains("trailing_stop_points")) s.trailingStopPoints = o["trailing_stop_points"].toInt();
    if (o.contains("trailing_step_points")) s.trailingStepPoints = o["trailing_step_points"].toInt();
    if (o.contains("break_even_enabled")) s.breakEvenEnabled = o["break_even_enabled"].toBool();
    if (o.contains("break_even_trigger_points")) s.breakEvenTriggerPoints = o["break_even_trigger_points"].toInt();
    if (o.contains("break_even_offset_points")) s.breakEvenOffsetPoints = o["break_even_offset_points"].toInt();
    if (o.contains("daily_drawdown_limit")) s.dailyDrawdownLimit = o["daily_drawdown_limit"].toDouble();
    if (o.contains("max_daily_trades")) s.maxDailyTrades = o["max_daily_trades"].toInt();
    if (o.contains("max_spread_points")) s.maxSpreadPoints = o["max_spread_points"].toInt();
    if (o.contains("max_exposure_lots")) s.maxExposureLots = o["max_exposure_lots"].toDouble();
    if (o.contains("equity_stop_loss")) s.equityStopLoss = o["equity_stop_loss"].toDouble();
    if (o.contains("max_consecutive_losses")) s.maxConsecutiveLosses = o["max_consecutive_losses"].toInt();
    s.strategyName = QStringLiteral("custom_script");
    if (o.contains("strategy_params")) s.strategyParams = o["strategy_params"].toObject().toVariantMap();
    if (o.contains("script_name")) s.scriptName = o["script_name"].toString();
    if (o.contains("script_source")) s.scriptSource = o["script_source"].toString();
    if (o.contains("loop_interval")) s.loopInterval = o["loop_interval"].toInt();
    if (o.contains("theme")) s.theme = o["theme"].toString().toLower();
    if (o.contains("backend")) s.backend = o["backend"].toString().toLower();
    if (o.contains("mcp_endpoint")) s.mcpEndpoint = o["mcp_endpoint"].toString();
    return {};
}

bool save(const Settings &s, const QString &path)
{
    QFile f(path);
    if (!f.open(QIODevice::WriteOnly | QIODevice::Truncate))
        return false;
    f.write(QJsonDocument(toJson(s)).toJson(QJsonDocument::Indented));
    f.close();
    return true;
}

bool load(Settings &s, const QString &path)
{
    QFile f(path);
    if (!f.exists() || !f.open(QIODevice::ReadOnly))
        return false;
    const QByteArray data = f.readAll();
    f.close();
    QJsonParseError err{};
    const QJsonDocument doc = QJsonDocument::fromJson(data, &err);
    if (err.error != QJsonParseError::NoError || !doc.isObject())
        return false;
    return apply(doc.object(), s).isEmpty();
}

bool loadMcpSecret(Settings &s, const QString &path)
{
    QFile f(path);
    if (!f.exists() || !f.open(QIODevice::ReadOnly))
        return false;
    const QJsonObject o = QJsonDocument::fromJson(f.readAll()).object();
    f.close();
    // Nilai yang sudah diset (mis. dari env/config) tidak ditimpa.
    const QString key = o.value("mcp_api_key").toString();
    const QString ep = o.value("mcp_endpoint").toString();
    if (s.mcpApiKey.isEmpty() && !key.isEmpty())
        s.mcpApiKey = key;
    if (!ep.isEmpty())
        s.mcpEndpoint = ep;
    return true;
}

bool saveMcpSecret(const Settings &s, const QString &path)
{
    if (s.mcpApiKey.isEmpty())
        return false; // tak ada yang perlu disimpan
    QJsonObject o;
    o["mcp_endpoint"] = s.mcpEndpoint;
    o["mcp_api_key"] = s.mcpApiKey; // teks biasa (berkas ini gitignored)
    QFile f(path);
    if (!f.open(QIODevice::WriteOnly | QIODevice::Truncate))
        return false;
    f.write(QJsonDocument(o).toJson(QJsonDocument::Indented));
    f.close();
    return true;
}

} // namespace ConfigStore
