#include "app/BotController.h"

#include "app/Worker.h"
#include "backend/McpBackend.h"
#include "core/ConfigStore.h"
#include "core/SecureStore.h"
#include "core/Settings.h"
#include "engine/BotEngine.h"
#include "script/ScriptStrategy.h"
#include "strategy/Strategy.h"

#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>
#include <QTextStream>
#include <QThread>
#include <QUrl>

namespace {
const char *kScriptTemplate = R"JS(// Strategi kustom (Mode Programmer - JavaScript).
// Atur SETTINGS (opsional), PARAMS (opsional), dan fungsi on_bar(ctx).

var SETTINGS = {
    symbol: "EURUSDm",
    timeframe: "M5",
    volume: 0.01,
    sl_points: 300,
    tp_points: 600,
    max_positions: 1,
};

var PARAMS = { fast: 12, slow: 26 };

function on_bar(ctx) {
    var fast = ctx.ema(ctx.close, ctx.params.fast);
    var slow = ctx.ema(ctx.close, ctx.params.slow);
    if (ctx.crossover(fast, slow)) return ctx.buy();
    if (ctx.crossunder(fast, slow)) return ctx.sell();
    return null;
}
)JS";
} // namespace

BotController::BotController(QObject *parent) : QObject(parent)
{
    ConfigStore::load(settings());
    ConfigStore::loadMcpSecret(settings()); // auto-load API key MCP (mcp_secret.json)
    m_chartSymbol = settings().symbol;
}

BotController::~BotController()
{
    if (m_thread) {
        m_worker->requestStop();
        m_thread->quit();
        m_thread->wait(3000);
        delete m_worker;
        delete m_thread;
    }
    delete m_engine;
    if (m_ownBackend)
        delete m_backend;
    delete m_injectedBackend;
}

void BotController::setInjectedBackend(TradingBackend *backend)
{
    m_injectedBackend = backend;
}

QString BotController::backend() const { return settings().backend; }

void BotController::setStatus(const QString &s)
{
    if (m_status != s) {
        m_status = s;
        emit statusChanged(s);
    }
}
void BotController::setConnectedState(bool v)
{
    if (m_connected != v) {
        m_connected = v;
        emit connectedChanged(v);
    }
}
void BotController::setTradingState(bool v)
{
    if (m_trading != v) {
        m_trading = v;
        emit tradingChanged(v);
    }
}

void BotController::setBackend(const QString &nameIn)
{
    QString name = nameIn.toLower();
    if (name != "native" && name != "mcp")
        return;
    if (settings().backend != name) {
        settings().backend = name;
        emit backendChanged(name);
    }
}

void BotController::setMcpConfig(const QString &endpoint, const QString &apiKey)
{
    if (!endpoint.trimmed().isEmpty())
        settings().mcpEndpoint = endpoint.trimmed();
    if (!apiKey.trimmed().isEmpty())
        settings().mcpApiKey = apiKey.trimmed();
    setBackend(QStringLiteral("mcp"));
}

void BotController::buildStrategy()
{
    std::unique_ptr<Strategy> strat;
    if (settings().strategyName == "custom_script")
        strat = std::make_unique<ScriptStrategy>(settings().scriptSource);
    else {
        QHash<QString, double> params;
        const QVariantMap sp = settings().strategyParams;
        for (auto it = sp.constBegin(); it != sp.constEnd(); ++it)
            params.insert(it.key(), it.value().toDouble());
        strat = createStrategy(settings().strategyName, params);
        if (!strat)
            strat = createStrategy("ma_cross");
    }
    m_engine->setStrategy(std::move(strat));
}

void BotController::connectBot()
{
    if (m_connected || m_thread)
        return;
    // Backend Native belum tersedia di versi C++ (tak ada library MT5 untuk C++).
    if (settings().backend == "native" && !m_injectedBackend) {
        emit configError(QStringLiteral(
            "Backend Native belum tersedia di versi C++ ini (tidak ada library MetaTrader5 "
            "untuk C++). Profil tetap tersimpan, tetapi untuk connect gunakan metode MCP."));
        setStatus(QStringLiteral("Terputus"));
        return;
    }
    setStatus(QStringLiteral("Menghubungkan..."));

    // Backend: injeksi test, atau bangun McpBackend dari settings.
    if (m_injectedBackend) {
        m_backend = m_injectedBackend;
        m_ownBackend = false;
    } else {
        m_backend = new McpBackend(settings().mcpEndpoint, settings().mcpApiKey);
        m_ownBackend = true;
    }
    m_engine = new BotEngine(m_backend, &settings());
    buildStrategy();

    m_thread = new QThread();
    m_worker = new Worker(m_engine, &settings(), m_chartSymbol);
    m_worker->moveToThread(m_thread);

    connect(m_thread, &QThread::started, m_worker, &Worker::run);
    connect(m_worker, &Worker::accountUpdated, this, &BotController::onAccount);
    connect(m_worker, &Worker::positionsUpdated, this, &BotController::onPositions);
    connect(m_worker, &Worker::ordersUpdated, this, &BotController::onOrders);
    connect(m_worker, &Worker::journalUpdated, this, &BotController::onJournal);
    connect(m_worker, &Worker::candlesUpdated, this, &BotController::onCandles);
    connect(m_worker, &Worker::symbolsListed, this, &BotController::onSymbols);
    connect(m_worker, &Worker::statsUpdated, this, &BotController::onStats);
    connect(m_worker, &Worker::equityUpdated, this, &BotController::onEquity);
    connect(m_worker, &Worker::autoTradingDisabled, this, &BotController::onAutoDisabled);
    connect(m_worker, &Worker::connectedChanged, this, &BotController::onWorkerConnected);
    connect(m_worker, &Worker::chartSymbolChanged, this, &BotController::onWorkerChartSymbol);
    connect(m_worker, &Worker::stopped, this, &BotController::onWorkerStopped);

    m_thread->start();
}

void BotController::disconnectBot()
{
    if (m_worker) {
        setStatus(QStringLiteral("Memutus..."));
        setTradingState(false);
        m_worker->setTrading(false);
        m_worker->requestStop();
    }
}

void BotController::logoutAccount()
{
    disconnectBot();
    emit positionsChanged({});
    emit ordersChanged({});
    emit logMessage(QStringLiteral("[SISTEM] Akun logout / terputus."));
}

void BotController::setTrading(bool enabled)
{
    if (!m_connected) {
        emit configError(QStringLiteral("Hubungkan ke MT5 dulu sebelum mengaktifkan trading."));
        return;
    }
    setTradingState(enabled);
    if (m_worker)
        m_worker->setTrading(enabled);
    setStatus(enabled ? QStringLiteral("Trading aktif") : QStringLiteral("Terhubung"));
}

void BotController::closePosition(qlonglong ticket)
{
    if (!m_connected) {
        emit configError(QStringLiteral("Tidak terhubung ke MT5."));
        return;
    }
    if (m_worker)
        m_worker->enqueueClose(ticket);
}

void BotController::openManualOrder(const QString &symbol, const QString &side, double volume,
                                    double sl, double tp)
{
    if (!m_connected) {
        emit configError(QStringLiteral("Hubungkan ke MT5 dulu sebelum kirim order."));
        return;
    }
    if (volume <= 0) {
        emit configError(QStringLiteral("Volume harus > 0."));
        return;
    }
    ManualCommand c;
    c.action = "market";
    c.symbol = symbol;
    c.side = side.toLower();
    c.volume = volume;
    c.sl = sl;
    c.tp = tp;
    m_worker->enqueue(c);
}

void BotController::placePendingOrder(const QString &symbol, const QString &orderType,
                                      double volume, double price, double sl, double tp)
{
    if (!m_connected) {
        emit configError(QStringLiteral("Hubungkan ke MT5 dulu sebelum pasang pending order."));
        return;
    }
    if (volume <= 0 || price <= 0) {
        emit configError(QStringLiteral("Volume dan harga pending order harus > 0."));
        return;
    }
    ManualCommand c;
    c.action = "pending";
    c.symbol = symbol;
    c.orderType = orderType.toLower();
    c.volume = volume;
    c.price = price;
    c.sl = sl;
    c.tp = tp;
    m_worker->enqueue(c);
}

void BotController::closeAllPositions()
{
    if (!m_connected) {
        emit configError(QStringLiteral("Tidak terhubung ke MT5."));
        return;
    }
    ManualCommand c;
    c.action = "close_all";
    m_worker->enqueue(c);
}

void BotController::deletePendingOrder(qlonglong ticket)
{
    if (!m_connected) {
        emit configError(QStringLiteral("Tidak terhubung ke MT5."));
        return;
    }
    ManualCommand c;
    c.action = "delete_order";
    c.ticket = ticket;
    m_worker->enqueue(c);
}

void BotController::setChartSymbol(const QString &symbolIn)
{
    const QString symbol = symbolIn.trimmed();
    if (symbol.isEmpty())
        return;
    m_chartSymbol = symbol;
    settings().symbol = symbol;
    ConfigStore::save(settings());
    if (m_worker)
        m_worker->setChartSymbol(symbol);
    emit chartSymbolChanged(symbol);
}

QVariantMap BotController::getConfig()
{
    return ConfigStore::toJson(settings()).toVariantMap();
}

QVariantMap BotController::getMcpConfig()
{
    const QString ep = settings().mcpEndpoint.trimmed().isEmpty()
        ? QStringLiteral("http://127.0.0.1:22346/mcp")
        : settings().mcpEndpoint;
    const bool hasKey = !settings().mcpApiKey.trimmed().isEmpty();
    return QVariantMap{
        {"endpoint", ep},
        {"hasKey", hasKey},
        {"keyPlaceholder", hasKey ? QStringLiteral("●●●●●●●● (Tersimpan di mcp_secret.json)")
                                  : QStringLiteral("kosongkan jika pakai profil")}
    };
}

bool BotController::applyConfig(const QVariantMap &cfg)
{
    const QStringList errs = ConfigStore::apply(QJsonObject::fromVariantMap(cfg), settings());
    if (!errs.isEmpty()) {
        emit configError(errs.join("; "));
        return false;
    }
    ConfigStore::save(settings());
    return true;
}

QVariantList BotController::getStrategies()
{
    auto param = [](const QString &key, const QString &label, const QString &type,
                    double def, double minv) {
        return QVariantMap{{"key", key}, {"label", label}, {"type", type},
                           {"default", def}, {"min", minv}};
    };
    auto strat = [](const QString &name, const QString &display, const QVariantList &params) {
        return QVariantMap{{"name", name}, {"display_name", display}, {"params", params}};
    };
    QVariantList out;
    out << strat("ma_cross", "MA Crossover", {
        param("fast_period", "MA Cepat", "int", 10, 1),
        param("slow_period", "MA Lambat", "int", 30, 2)});
    out << strat("rsi", "RSI Oversold/Overbought", {
        param("period", "Periode RSI", "int", 14, 2),
        param("oversold", "Level Oversold", "float", 30.0, 1),
        param("overbought", "Level Overbought", "float", 70.0, 1)});
    out << strat("bollinger", "Bollinger Bands", {
        param("period", "Periode SMA", "int", 20, 2),
        param("std_dev", "Deviasi Standar", "float", 2.0, 0.5)});
    out << strat("macd", "MACD Crossover", {
        param("fast_ema", "Fast EMA", "int", 12, 2),
        param("slow_ema", "Slow EMA", "int", 26, 3),
        param("signal_period", "Signal Period", "int", 9, 1)});
    out << strat("multi_indicator", "Multi-Indicator (Trend + RSI)", {
        param("ma_fast", "MA Cepat (Tren)", "int", 20, 2),
        param("ma_slow", "MA Lambat (Tren)", "int", 50, 3),
        param("rsi_period", "Periode RSI", "int", 14, 2),
        param("rsi_buy_level", "RSI Trigger Buy", "float", 50.0, 10),
        param("rsi_sell_level", "RSI Trigger Sell", "float", 50.0, 10)});
    out << strat("stochastic", "Stochastic Oscillator", {
        param("k_period", "Periode %K", "int", 14, 2),
        param("d_period", "Periode %D", "int", 3, 1),
        param("oversold", "Level Oversold", "float", 20.0, 1),
        param("overbought", "Level Overbought", "float", 80.0, 1)});
    return out;
}

bool BotController::saveConfig(const QVariantMap &cfg)
{
    QVariantMap risk = cfg;
    const QString stratName = risk.take("strategy_name").toString();
    const QVariantMap stratParams = risk.take("strategy_params").toMap();
    const QStringList errs = ConfigStore::apply(QJsonObject::fromVariantMap(risk), settings());
    if (!errs.isEmpty()) {
        emit configError(errs.join("; "));
        return false;
    }
    if (!stratName.isEmpty())
        settings().strategyName = stratName;
    if (!stratParams.isEmpty())
        settings().strategyParams = stratParams;
    ConfigStore::save(settings());
    emit logMessage(QStringLiteral("[UI] Konfigurasi disimpan."));
    return true;
}

// ---------- Login / koneksi MCP + profil ----------
namespace {
QString mcpDir() { return QStringLiteral("mcp_profiles"); }
QString safeFileName(const QString &name)
{
    QString s = name;
    s.replace(QRegularExpression("[^A-Za-z0-9_-]+"), "_");
    return s.isEmpty() ? QStringLiteral("profil") : s;
}
QString urlToLocal(const QString &url)
{
    return url.startsWith("file:") ? QUrl(url).toLocalFile() : url;
}
} // namespace

bool BotController::connectMcp(const QVariantMap &cfg, const QString &saveName)
{
    QString endpoint = cfg.value("endpoint").toString().trimmed();
    QString apiKey = cfg.value("api_key").toString().trimmed();
    if (endpoint.isEmpty())
        endpoint = settings().mcpEndpoint;
    if (apiKey.isEmpty())
        apiKey = settings().mcpApiKey;
    if (apiKey.isEmpty()) {
        emit configError(QStringLiteral("API Key MCP kosong. Isi dari MT5 → Tools → Options → tab MCP."));
        return false;
    }
    setMcpConfig(endpoint, apiKey);

    const QString name = saveName.trimmed();
    if (!name.isEmpty()) {
        QDir().mkpath(mcpDir());
        QJsonObject o;
        o["name"] = name;
        o["endpoint"] = endpoint;
        o["api_key"] = SecureStore::encrypt(apiKey); // terenkripsi at-rest
        QFile f(mcpDir() + "/" + safeFileName(name) + ".json");
        if (f.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
            f.write(QJsonDocument(o).toJson(QJsonDocument::Indented));
            f.close();
            emit mcpProfilesChanged(listMcpProfiles());
        }
    }
    connectBot();
    return true;
}

QVariantList BotController::listMcpProfiles()
{
    QVariantList out;
    QDir dir(mcpDir());
    const QStringList files = dir.entryList({"*.json"}, QDir::Files, QDir::Name);
    for (const QString &fn : files) {
        const QString path = dir.filePath(fn);
        QFile f(path);
        if (!f.open(QIODevice::ReadOnly))
            continue;
        const QJsonObject o = QJsonDocument::fromJson(f.readAll()).object();
        f.close();
        out << QVariantMap{
            {"name", o.value("name").toString(fn.left(fn.size() - 5))}, {"file", path}};
    }
    return out;
}

QVariantMap BotController::loadMcpProfileFile(const QString &url)
{
    const QString path = urlToLocal(url);
    QFile f(path);
    if (!f.open(QIODevice::ReadOnly)) {
        emit configError(QStringLiteral("Gagal memuat profil MCP dari file."));
        return {};
    }
    const QJsonObject o = QJsonDocument::fromJson(f.readAll()).object();
    f.close();
    const QString endpoint = o.value("endpoint").toString();
    const QString apiKey = SecureStore::decrypt(o.value("api_key").toString());
    if (!endpoint.isEmpty())
        settings().mcpEndpoint = endpoint;
    if (!apiKey.isEmpty())
        settings().mcpApiKey = apiKey;
    setBackend(QStringLiteral("mcp"));
    emit logMessage(QStringLiteral("[UI] Profil MCP '%1' dimuat.").arg(o.value("name").toString()));
    return QVariantMap{
        {"name", o.value("name").toString()}, {"endpoint", endpoint},
        {"hasKey", !apiKey.isEmpty()}};
}

bool BotController::deleteMcpProfile(const QString &file)
{
    const bool ok = QFile::remove(urlToLocal(file));
    if (ok)
        emit mcpProfilesChanged(listMcpProfiles());
    return ok;
}

// ---------- Profil kredensial Native ----------
namespace {
QString nativeDir() { return QStringLiteral("profiles"); }
}

QVariantList BotController::listProfiles()
{
    QVariantList out;
    QDir dir(nativeDir());
    const QStringList files = dir.entryList({"*.json"}, QDir::Files, QDir::Name);
    for (const QString &fn : files) {
        QFile f(dir.filePath(fn));
        if (!f.open(QIODevice::ReadOnly))
            continue;
        const QJsonObject o = QJsonDocument::fromJson(f.readAll()).object();
        f.close();
        out << QVariantMap{
            {"name", o.value("name").toString(fn.left(fn.size() - 5))},
            {"login", o.value("login").toVariant()},
            {"file", dir.filePath(fn)}};
    }
    return out;
}

QVariantMap BotController::loadProfileFile(const QString &url)
{
    const QString path = urlToLocal(url);
    QFile f(path);
    if (!f.open(QIODevice::ReadOnly)) {
        emit configError(QStringLiteral("Gagal memuat profil dari file."));
        return {};
    }
    const QJsonObject o = QJsonDocument::fromJson(f.readAll()).object();
    f.close();
    settings().login = o.value("login").toVariant().toLongLong();
    settings().server = o.value("server").toString();
    settings().path = o.value("path").toString();
    const QString pw = SecureStore::decrypt(o.value("password").toString());
    if (!pw.isEmpty())
        settings().password = pw;
    setBackend(QStringLiteral("native"));
    emit logMessage(QStringLiteral("[UI] Profil '%1' dimuat.").arg(o.value("name").toString()));
    return QVariantMap{
        {"name", o.value("name").toString()}, {"login", o.value("login").toVariant()},
        {"server", settings().server}, {"path", settings().path},
        {"hasPassword", !settings().password.isEmpty()}};
}

bool BotController::deleteProfile(const QString &file)
{
    const bool ok = QFile::remove(urlToLocal(file));
    if (ok)
        emit profilesChanged(listProfiles());
    return ok;
}

bool BotController::loginAndConnect(const QVariantMap &creds, const QString &saveName)
{
    QVariantMap d = creds;
    if (d.value("password").toString().isEmpty())
        d["password"] = settings().password; // pakai password profil yg dimuat

    const long long login = d.value("login").toLongLong();
    const QString password = d.value("password").toString();
    const QString server = d.value("server").toString().trimmed();
    if (login <= 0 || password.isEmpty() || server.isEmpty()) {
        emit configError(QStringLiteral("Login, password, dan server wajib diisi."));
        return false;
    }
    settings().login = login;
    settings().password = password;
    settings().server = server;
    settings().path = d.value("path").toString();
    setBackend(QStringLiteral("native"));

    const QString name = saveName.trimmed();
    if (!name.isEmpty()) {
        QDir().mkpath(nativeDir());
        QJsonObject o;
        o["name"] = name;
        o["login"] = static_cast<qlonglong>(login);
        o["server"] = server;
        o["path"] = settings().path;
        o["password"] = SecureStore::encrypt(password);
        QFile f(nativeDir() + "/" + safeFileName(name) + ".json");
        if (f.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
            f.write(QJsonDocument(o).toJson(QJsonDocument::Indented));
            f.close();
            emit profilesChanged(listProfiles());
        }
    }
    connectBot();
    return true;
}

QString BotController::scriptTemplate() { return QString::fromUtf8(kScriptTemplate); }

QVariantMap BotController::validateScript(const QString &source)
{
    const ScriptValidation v = ScriptStrategy::validate(source);
    return {{"ok", v.ok}, {"line", v.line}, {"message", v.message}};
}

void BotController::setScript(const QString &source)
{
    settings().scriptSource = source;
    settings().strategyName = QStringLiteral("custom_script");
    ConfigStore::save(settings());
    emit logMessage(QStringLiteral("[UI] Skrip disimpan. Aktif saat (re)connect / mulai trading."));
}

QString BotController::currentScript() { return settings().scriptSource; }

// ---------- Manajemen file skrip (folder "scripts", *.js) ----------
namespace {
QString scriptsDir() { return QStringLiteral("scripts"); }
} // namespace

QVariantList BotController::listScripts()
{
    QVariantList out;
    QDir dir(scriptsDir());
    const QStringList files = dir.entryList({"*.js"}, QDir::Files, QDir::Name);
    for (const QString &fn : files) {
        QString base = fn;
        base.chop(3); // buang ".js"
        if (base.compare("README", Qt::CaseInsensitive) == 0)
            continue;
        out << base;
    }
    return out;
}

QString BotController::loadScript(const QString &name)
{
    QFile f(scriptsDir() + "/" + safeFileName(name) + ".js");
    if (!f.open(QIODevice::ReadOnly | QIODevice::Text))
        return {};
    return QString::fromUtf8(f.readAll());
}

QString BotController::loadScriptFile(const QString &url)
{
    QFile f(urlToLocal(url));
    if (!f.open(QIODevice::ReadOnly | QIODevice::Text))
        return {};
    return QString::fromUtf8(f.readAll());
}

bool BotController::saveScript(const QString &name, const QString &source)
{
    const QString n = name.trimmed();
    if (n.isEmpty())
        return false;
    QDir().mkpath(scriptsDir());
    QFile f(scriptsDir() + "/" + safeFileName(n) + ".js");
    if (!f.open(QIODevice::WriteOnly | QIODevice::Truncate | QIODevice::Text))
        return false;
    f.write(source.toUtf8());
    emit logMessage(QStringLiteral("[UI] Skrip '%1' disimpan ke folder scripts.").arg(n));
    return true;
}

void BotController::onJournal(const QVariantMap &entryIn)
{
    QVariantMap entry = entryIn;
    entry["time"] = QDateTime::currentDateTime().toString("HH:mm:ss");
    m_journal.append(entry);
    if (m_journal.size() > 1000)
        m_journal.removeFirst();
    emit journalEntry(entry);
    emit journalChanged();
}

void BotController::clearJournal()
{
    m_journal.clear();
    emit journalChanged();
}

void BotController::clearLogs()
{
    QFile f(QStringLiteral("logs/bot.log"));
    if (f.open(QIODevice::WriteOnly | QIODevice::Truncate)) {
        f.close();
    }
}

bool BotController::exportJournalCsv(const QString &pathIn)
{
    QString path = pathIn;
    if (path.startsWith("file:"))
        path = QUrl(path).toLocalFile();
    QFile f(path);
    if (!f.open(QIODevice::WriteOnly | QIODevice::Truncate | QIODevice::Text)) {
        emit configError(QStringLiteral("Gagal menulis CSV: %1").arg(path));
        return false;
    }
    QTextStream ts(&f);
    ts << "time,action,symbol,detail,ok\n";
    auto esc = [](const QString &v) {
        QString s = v;
        s.replace('"', "\"\"");
        return QStringLiteral("\"%1\"").arg(s);
    };
    for (const QVariant &v : m_journal) {
        const QVariantMap e = v.toMap();
        ts << esc(e.value("time").toString()) << ','
           << esc(e.value("action").toString()) << ','
           << esc(e.value("symbol").toString()) << ','
           << esc(e.value("detail").toString()) << ','
           << (e.value("ok").toBool() ? "OK" : "GAGAL") << '\n';
    }
    f.close();
    emit logMessage(QStringLiteral("[UI] Jurnal diekspor ke %1 (%2 baris).")
                        .arg(path).arg(m_journal.size()));
    return true;
}

bool BotController::exportLogs(const QString &pathIn)
{
    const QString path = urlToLocal(pathIn);
    QFile src(QStringLiteral("logs/bot.log"));
    if (!src.open(QIODevice::ReadOnly | QIODevice::Text)) {
        emit configError(QStringLiteral("Log belum tersedia (logs/bot.log)."));
        return false;
    }
    const QString content = QString::fromUtf8(src.readAll());
    src.close();

    QFile out(path);
    if (!out.open(QIODevice::WriteOnly | QIODevice::Truncate | QIODevice::Text)) {
        emit configError(QStringLiteral("Gagal menulis file log: %1").arg(path));
        return false;
    }
    QTextStream ts(&out);
    if (path.endsWith(".csv", Qt::CaseInsensitive)) {
        ts << "time,level,message\n";
        auto esc = [](QString v) { v.replace('"', "\"\""); return QStringLiteral("\"%1\"").arg(v); };
        const QStringList lines = content.split('\n', Qt::SkipEmptyParts);
        for (const QString &ln : lines) {
            // Format Logger: "HH:mm:ss | LEVEL | pesan".
            const QStringList parts = ln.split(QStringLiteral(" | "));
            if (parts.size() >= 3)
                ts << esc(parts[0]) << ',' << esc(parts[1]) << ','
                   << esc(parts.mid(2).join(QStringLiteral(" | "))) << '\n';
            else
                ts << ",," << esc(ln) << '\n';
        }
    } else {
        ts << content;
    }
    out.close();
    emit logMessage(QStringLiteral("[UI] Log diekspor ke %1.").arg(path));
    return true;
}

QVariantList BotController::apiReference()
{
    auto item = [](const QString &sig, const QString &desc, const QString &snippet) {
        return QVariantMap{{"signature", sig}, {"desc", desc}, {"snippet", snippet}};
    };
    auto group = [](const QString &name, const QVariantList &items) {
        return QVariantMap{{"group", name}, {"items", items}};
    };
    QVariantList out;
    out << group("Data Harga", {
        item("ctx.close", "Array harga close (lama→baru).", "ctx.close"),
        item("ctx.open / high / low", "Array OHLC.", "ctx.high"),
        item("ctx.volume", "Array volume tick.", "ctx.volume")});
    out << group("Harga Live & Simbol", {
        item("ctx.bid / ctx.ask", "Harga live.", "ctx.ask"),
        item("ctx.spread", "Spread (points).", "ctx.spread"),
        item("ctx.point / ctx.digits", "Ukuran point & desimal.", "ctx.point"),
        item("ctx.symbol", "Nama simbol aktif.", "ctx.symbol")});
    out << group("Akun & Posisi", {
        item("ctx.balance / ctx.equity", "Saldo & ekuitas.", "ctx.balance"),
        item("ctx.position", "Posisi aktif (objek) atau null.", "ctx.position"),
        item("ctx.positions", "Semua posisi (array).", "ctx.positions")});
    out << group("Waktu", {
        item("ctx.hour / ctx.minute", "Jam & menit bar.", "ctx.hour"),
        item("ctx.weekday", "0=Senin..6=Minggu.", "ctx.weekday")});
    out << group("Indikator", {
        item("ctx.sma(src, n)", "Simple MA.", "ctx.sma(ctx.close, 20)"),
        item("ctx.ema(src, n)", "Exponential MA.", "ctx.ema(ctx.close, 20)"),
        item("ctx.wma(src, n)", "Weighted MA.", "ctx.wma(ctx.close, 20)"),
        item("ctx.rsi(src, n)", "RSI 0..100.", "ctx.rsi(ctx.close, 14)"),
        item("ctx.atr(n)", "Average True Range.", "ctx.atr(14)"),
        item("ctx.stdev(src, n)", "Standar deviasi.", "ctx.stdev(ctx.close, 20)"),
        item("ctx.highest/lowest(src, n)", "Tertinggi/terendah n bar.", "ctx.highest(ctx.high, 20)"),
        item("ctx.bbands(src, n, mult)", "[upper, mid, lower].", "var b = ctx.bbands(ctx.close, 20, 2.0)"),
        item("ctx.macd(src, f, s, sig)", "[macd, signal, hist].", "var m = ctx.macd(ctx.close, 12, 26, 9)"),
        item("ctx.stochastic(k, d, smooth)", "[%K, %D].", "var s = ctx.stochastic(14, 3, 3)"),
        item("ctx.adx(n)", "[ADX, +DI, -DI].", "var a = ctx.adx(14)"),
        item("ctx.cci(n)", "Commodity Channel Index.", "ctx.cci(20)"),
        item("ctx.vwap(n)", "VWAP bergulir.", "ctx.vwap(14)"),
        item("ctx.williams_r(n)", "Williams %R.", "ctx.williams_r(14)"),
        item("ctx.obv()", "On-Balance Volume.", "ctx.obv()"),
        item("ctx.mfi(n)", "Money Flow Index.", "ctx.mfi(14)"),
        item("ctx.donchian(n)", "[upper, mid, lower].", "var d = ctx.donchian(20)"),
        item("ctx.parabolic_sar(step, max)", "Array Parabolic SAR.", "ctx.parabolic_sar(0.02, 0.2)"),
        item("ctx.supertrend(n, mult)", "[garis, arah].", "var st = ctx.supertrend(10, 3.0)"),
        item("ctx.ichimoku(...)", "[tenkan, kijun, sa, sb, chikou].", "var i = ctx.ichimoku()"),
        item("ctx.pivot_points()", "{pivot, r1, s1, ...}.", "var p = ctx.pivot_points()"),
        item("ctx.crossover(a, b)", "a memotong ke atas b.", "ctx.crossover(fast, slow)"),
        item("ctx.crossunder(a, b)", "a memotong ke bawah b.", "ctx.crossunder(fast, slow)")});
    out << group("Perintah Order", {
        item("ctx.buy(opts)", "Buka BUY (opts opsional).", "return ctx.buy({volume:0.01, sl_points:300, tp_points:600})"),
        item("ctx.sell(opts)", "Buka SELL.", "return ctx.sell({volume:0.01})"),
        item("ctx.close_position(opts)", "Tutup posisi (default: aktif).", "return ctx.close_position()"),
        item("ctx.close_all()", "Tutup semua posisi.", "return ctx.close_all()"),
        item("ctx.modify(opts)", "Ubah SL/TP.", "return ctx.modify({sl:1.09, tp:1.11})"),
        item("ctx.log(msg)", "Catat ke log/jurnal.", "ctx.log('halo')")});
    return out;
}

QVariantList BotController::settingsReference()
{
    auto item = [](const QString &key, const QString &desc, const QString &snippet) {
        return QVariantMap{{"signature", key}, {"desc", desc}, {"snippet", snippet}};
    };
    auto group = [](const QString &name, const QVariantList &items) {
        return QVariantMap{{"group", name}, {"items", items}};
    };
    QVariantList out;
    out << group("Order Dasar", {
        item("volume", "Lot tetap (mis. 0.01). Kosong = hitung dari risiko.", "volume: 0.01,"),
        item("risk_per_trade", "Risiko per trade (0.01 = 1%).", "risk_per_trade: 0.01,"),
        item("sl_points / tp_points", "Jarak SL/TP dalam points.", "sl_points: 300, tp_points: 600,"),
        item("comment", "Komentar order.", "comment: \"my_bot\",")});
    out << group("SL/TP Dinamis", {
        item("atr_sl_mult", "SL = ATR(14) × pengali.", "atr_sl_mult: 1.5,"),
        item("atr_tp_mult", "TP = ATR(14) × pengali.", "atr_tp_mult: 3.0,"),
        item("risk_reward_ratio", "TP = SL × rasio (bila TP tak diset).", "risk_reward_ratio: 2.0,")});
    out << group("Filter Waktu/Sesi", {
        item("trade_start_time", "Jam mulai trading \"HH:mm\" (UTC).", "trade_start_time: \"08:00\","),
        item("trade_end_time", "Jam berhenti \"HH:mm\" (UTC).", "trade_end_time: \"20:00\","),
        item("active_days", "Hari aktif [0=Sen..6=Min].", "active_days: [0,1,2,3,4],"),
        item("close_friday_hour", "Tutup semua di jam ini hari Jumat.", "close_friday_hour: 20,")});
    out << group("Manajemen Entry/Posisi", {
        item("max_holding_bars", "Auto-close posisi setelah N bar.", "max_holding_bars: 20,"),
        item("cooldown_bars", "Jeda N bar antar entry.", "cooldown_bars: 3,"),
        item("min_margin_level", "Batas minimal margin level (%).", "min_margin_level: 200,"),
        item("one_trade_per_bar", "Maks 1 entry per bar (default true).", "one_trade_per_bar: true,"),
        item("close_on_reversal", "Tutup posisi lawan sebelum entry (default true).", "close_on_reversal: true,")});
    out << group("Proteksi (Global)", {
        item("max_spread_points", "Tolak entry bila spread > batas.", "max_spread_points: 30,"),
        item("max_exposure_lots", "Batas total lot semua posisi.", "max_exposure_lots: 1.0,"),
        item("equity_stop_loss", "Cut-loss ekuitas (fraksi).", "equity_stop_loss: 0.1,"),
        item("max_consecutive_losses", "Pause setelah N loss beruntun.", "max_consecutive_losses: 3,"),
        item("daily_drawdown_limit", "Batas drawdown harian (fraksi).", "daily_drawdown_limit: 0.05,"),
        item("max_daily_trades", "Batas jumlah trade harian.", "max_daily_trades: 10,")});
    return out;
}

QString BotController::settingsTemplate()
{
    return QStringLiteral(
        "var SETTINGS = {\n"
        "  volume: 0.01,\n"
        "  risk_per_trade: 0.01,\n"
        "  sl_points: 300,\n"
        "  tp_points: 600,\n"
        "  // risk_reward_ratio: 2.0,\n"
        "  // atr_sl_mult: 1.5, atr_tp_mult: 3.0,\n"
        "  trade_start_time: \"08:00\",\n"
        "  trade_end_time: \"20:00\",\n"
        "  active_days: [0, 1, 2, 3, 4],\n"
        "  // close_friday_hour: 20,\n"
        "  max_holding_bars: 0,\n"
        "  cooldown_bars: 0,\n"
        "  min_margin_level: 0,\n"
        "  one_trade_per_bar: true,\n"
        "  close_on_reversal: true,\n"
        "  max_spread_points: 0,\n"
        "  comment: \"my_bot\"\n"
        "};\n");
}

// ----- Penerima sinyal worker -----

void BotController::onAccount(const QVariantMap &a)
{
    m_balance = a.value("balance").toDouble();
    m_equity = a.value("equity").toDouble();
    m_margin = a.value("margin").toDouble();
    m_freeMargin = a.value("free_margin").toDouble();
    m_profit = a.value("profit").toDouble();
    m_currency = a.value("currency").toString();
    m_accountType = a.value("account_type").toString();
    m_accountServer = a.value("server").toString();
    m_serverConnected = a.value("server_connected").toBool();
    m_tradeAllowed = a.value("trade_allowed").toBool();
    emit accountChanged();
}

void BotController::onPositions(const QVariantList &p) { emit positionsChanged(p); }
void BotController::onOrders(const QVariantList &o) { emit ordersChanged(o); }
void BotController::onCandles(const QString &symbol, const QVariant &payload)
{
    emit chartUpdated(symbol, payload);
}
void BotController::onSymbols(const QStringList &s) { emit symbolsAvailable(s); }
void BotController::onStats(const QVariantMap &s)
{
    m_stats = s;
    emit statsChanged();
}
void BotController::onEquity(const QVariantList &curve)
{
    m_equityCurve = curve;
    emit equityChanged();
}
void BotController::refreshStats()
{
    // Statistik diperbarui berkala oleh worker; ini memicu re-emit agar UI segar.
    emit statsChanged();
    emit equityChanged();
}
void BotController::onAutoDisabled(const QString &reason)
{
    setTradingState(false);
    setStatus(QStringLiteral("Terhubung"));
    emit logMessage(reason);
}
void BotController::onWorkerConnected(bool connected)
{
    setConnectedState(connected);
    if (connected) {
        setStatus(QStringLiteral("Terhubung"));
        // Auto-save rahasia MCP agar API key termuat otomatis saat startup berikutnya.
        if (settings().backend.compare("mcp", Qt::CaseInsensitive) == 0
            && !settings().mcpApiKey.isEmpty()) {
            if (ConfigStore::saveMcpSecret(settings()))
                emit logMessage(QStringLiteral("[UI] API Key MCP disimpan (mcp_secret.json) untuk sesi berikutnya."));
        }
    }
}
void BotController::onWorkerChartSymbol(const QString &symbol)
{
    m_chartSymbol = symbol;
    emit chartSymbolChanged(symbol);
}
void BotController::onWorkerStopped()
{
    if (m_thread) {
        m_thread->quit();
        m_thread->wait(3000);
        m_worker->deleteLater();
        m_thread->deleteLater();
        m_thread = nullptr;
        m_worker = nullptr;
    }
    delete m_engine;
    m_engine = nullptr;
    if (m_ownBackend)
        delete m_backend;
    m_backend = nullptr;
    m_ownBackend = false;
    setConnectedState(false);
    setTradingState(false);
    setStatus(QStringLiteral("Terputus"));
}
