#include "script/ScriptStrategy.h"

#include "script/ScriptContext.h"

#include <QJSValueIterator>
#include <QLoggingCategory>
#include <QSet>
#include <QtGlobal>
#include <atomic>
#include <chrono>
#include <thread>

namespace {
const QSet<QString> kValidActions = {"BUY", "SELL", "CLOSE", "CLOSE_ALL", "MODIFY"};
} // namespace

ScriptStrategy::ScriptStrategy(const QString &source, const QVariantMap &params, int timeoutMs)
    : m_params(params), m_timeoutMs(timeoutMs)
{
    m_engine = std::make_unique<QJSEngine>();
    m_engine->installExtensions(QJSEngine::ConsoleExtension); // console.log aman

    const QJSValue result = m_engine->evaluate(source, QStringLiteral("<strategy_script>"));
    if (result.isError()) {
        m_ok = false;
        m_error = QStringLiteral("Baris %1: %2")
                      .arg(result.property("lineNumber").toInt())
                      .arg(result.toString());
        return;
    }

    m_onBar = m_engine->globalObject().property("on_bar");
    if (!m_onBar.isCallable()) {
        m_ok = false;
        m_error = QStringLiteral("Skrip harus mendefinisikan fungsi on_bar(ctx).");
        return;
    }

    // Baca SETTINGS global (objek) bila ada.
    const QJSValue settings = m_engine->globalObject().property("SETTINGS");
    if (settings.isObject())
        m_settings = settings.toVariant().toMap();

    // Baca PARAMS (objek dict) sebagai default, ditimpa params pengguna.
    QVariantMap mergedParams;
    const QJSValue prm = m_engine->globalObject().property("PARAMS");
    if (prm.isObject() && !prm.isArray())
        mergedParams = prm.toVariant().toMap();
    for (auto it = m_params.constBegin(); it != m_params.constEnd(); ++it)
        mergedParams.insert(it.key(), it.value());
    m_params = mergedParams;

    m_ctx = new ScriptContext(m_engine.get());
    m_engine->setObjectOwnership(m_ctx, QJSEngine::CppOwnership);
    m_ctx->setParams(m_params);
    m_ctx->setSettings(m_settings);
    m_ctxValue = m_engine->newQObject(m_ctx);
    m_ok = true;
}

ScriptStrategy::~ScriptStrategy() = default;

QStringList ScriptStrategy::takeLogs()
{
    return m_ctx ? m_ctx->takeLogs() : QStringList{};
}

ScriptValidation ScriptStrategy::validate(const QString &source)
{
    ScriptValidation v;
    if (source.trimmed().isEmpty()) {
        v.message = QStringLiteral("Skrip kosong.");
        return v;
    }
    QJSEngine engine;
    const QJSValue result = engine.evaluate(source, QStringLiteral("<strategy_script>"));
    if (result.isError()) {
        v.line = result.property("lineNumber").toInt();
        v.message = result.toString();
        return v;
    }
    if (!engine.globalObject().property("on_bar").isCallable()) {
        v.message = QStringLiteral("Skrip harus mendefinisikan fungsi on_bar(ctx).");
        return v;
    }
    v.ok = true;
    return v;
}

QVector<Command> ScriptStrategy::onBar(const QVector<Candle> &candles, const RuntimeContext &rt)
{
    if (!m_ok || !m_ctx)
        return {};
    m_ctx->setCandles(candles);
    m_ctx->setRuntime(rt);

    // Watchdog anti loop tak terbatas: interupsi engine setelah timeout.
    std::atomic<bool> done{false};
    QJSEngine *eng = m_engine.get();
    const int timeout = m_timeoutMs;
    std::thread watch([&done, eng, timeout]() {
        int waited = 0;
        while (!done.load() && waited < timeout) {
            std::this_thread::sleep_for(std::chrono::milliseconds(5));
            waited += 5;
        }
        if (!done.load())
            eng->setInterrupted(true);
    });

    const QJSValue r = m_onBar.call(QJSValueList{m_ctxValue});
    done.store(true);
    watch.join();
    m_engine->setInterrupted(false);

    return parseResult(r);
}

QVector<Command> ScriptStrategy::parseResult(const QJSValue &r)
{
    QVector<Command> out;
    if (r.isError()) {
        qCritical("Skrip on_bar error: %s", qUtf8Printable(r.toString()));
        return out;
    }
    if (r.isNull() || r.isUndefined())
        return out;
    if (r.isString()) {
        const QString s = r.toString();
        if (s == "BUY" || s == "SELL") {
            Command c;
            c.action = s;
            out << c;
        }
        return out;
    }
    if (r.isArray()) {
        const int len = r.property("length").toInt();
        for (int i = 0; i < len; ++i) {
            Command c;
            if (parseCommand(r.property(i), c))
                out << c;
        }
        return out;
    }
    if (r.isObject()) {
        Command c;
        if (parseCommand(r, c))
            out << c;
    }
    return out;
}

bool ScriptStrategy::parseCommand(const QJSValue &o, Command &out)
{
    if (!o.isObject())
        return false;
    const QString action = o.property("action").toString();
    if (!kValidActions.contains(action))
        return false;
    out.action = action;

    auto has = [&](const char *k) {
        const QJSValue v = o.property(k);
        return !v.isUndefined() && !v.isNull();
    };
    if (has("volume")) { out.hasVolume = true; out.volume = o.property("volume").toNumber(); }
    if (has("sl")) { out.hasSl = true; out.sl = o.property("sl").toNumber(); }
    if (has("tp")) { out.hasTp = true; out.tp = o.property("tp").toNumber(); }
    if (has("sl_points")) { out.hasSlPoints = true; out.slPoints = o.property("sl_points").toInt(); }
    if (has("tp_points")) { out.hasTpPoints = true; out.tpPoints = o.property("tp_points").toInt(); }
    if (has("risk")) { out.hasRisk = true; out.risk = o.property("risk").toNumber(); }
    if (has("ticket")) out.ticket = static_cast<long long>(o.property("ticket").toNumber());
    if (has("comment")) out.comment = o.property("comment").toString();
    return true;
}
