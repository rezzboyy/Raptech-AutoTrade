#include "app/BotController.h"

#include "app/PyBridgeWorker.h"
#include "core/ConfigStore.h"
#include "core/SecureStore.h"
#include "core/Settings.h"
#include "indicators/Indicators.h"

#include <QCoreApplication>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QPointer>
#include <QProcess>
#include <QRegularExpression>
#include <QSet>
#include <QStandardPaths>
#include <QTextStream>
#include <QThread>
#include <QTimer>
#include <QUrl>

#ifdef Q_OS_WIN
#include <windows.h>
#include <tlhelp32.h>
static bool isTerminalRunning()
{
    PROCESSENTRY32W entry;
    entry.dwSize = sizeof(PROCESSENTRY32W);
    HANDLE snapshot = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snapshot == INVALID_HANDLE_VALUE)
        return false;
    bool found = false;
    if (Process32FirstW(snapshot, &entry)) {
        do {
            if (_wcsicmp(entry.szExeFile, L"terminal64.exe") == 0 ||
                _wcsicmp(entry.szExeFile, L"terminal.exe") == 0) {
                found = true;
                break;
            }
        } while (Process32NextW(snapshot, &entry));
    }
    CloseHandle(snapshot);
    return found;
}
#else
static bool isTerminalRunning() { return false; }
#endif

namespace {
static QString findTerminalPath(const QString &customPath)
{
    const QString p = customPath.trimmed();
    if (!p.isEmpty() && QFile::exists(p))
        return p;

    // Cek terminal di PATH jika ada
    QString inPath = QStandardPaths::findExecutable(QStringLiteral("terminal64.exe"));
    if (!inPath.isEmpty() && QFile::exists(inPath))
        return inPath;

    const QString progFiles = qEnvironmentVariable("ProgramFiles");
    const QString progFilesX86 = qEnvironmentVariable("ProgramFiles(x86)");

    QStringList candidates = {
        QStringLiteral("C:\\Program Files\\MetaTrader 5 EXNESS\\terminal64.exe"),
        QStringLiteral("C:\\Program Files\\MetaTrader 5\\terminal64.exe"),
        QStringLiteral("C:\\Program Files (x86)\\MetaTrader 5\\terminal64.exe"),
        QStringLiteral("C:\\MetaTrader 5\\terminal64.exe"),
        QStringLiteral("D:\\Program Files\\MetaTrader 5\\terminal64.exe"),
        QStringLiteral("D:\\MetaTrader 5\\terminal64.exe")
    };

    if (!progFiles.isEmpty()) {
        candidates.prepend(progFiles + QStringLiteral("\\MetaTrader 5 EXNESS\\terminal64.exe"));
        candidates.prepend(progFiles + QStringLiteral("\\MetaTrader 5\\terminal64.exe"));
    }
    if (!progFilesX86.isEmpty()) {
        candidates << progFilesX86 + QStringLiteral("\\MetaTrader 5\\terminal64.exe");
    }

    for (const QString &cand : candidates) {
        if (QFile::exists(cand))
            return cand;
    }

    // Dynamic scanning: periksa folder di ProgramFiles yang bernama *MetaTrader* atau *MT5*
    auto scanDir = [](const QString &baseDir) -> QString {
        if (baseDir.isEmpty()) return QString();
        QDir dir(baseDir);
        if (!dir.exists()) return QString();
        const QStringList entries = dir.entryList(QDir::Dirs | QDir::NoDotAndDotDot);
        for (const QString &entry : entries) {
            if (entry.contains(QStringLiteral("MetaTrader"), Qt::CaseInsensitive) ||
                entry.contains(QStringLiteral("MT5"), Qt::CaseInsensitive)) {
                QString term = dir.filePath(entry + QStringLiteral("/terminal64.exe"));
                if (QFile::exists(term))
                    return QDir::toNativeSeparators(term);
            }
        }
        return QString();
    };

    QString found = scanDir(progFiles);
    if (!found.isEmpty()) return found;
    found = scanDir(progFilesX86);
    if (!found.isEmpty()) return found;
    found = scanDir(QStringLiteral("C:\\Program Files"));
    if (!found.isEmpty()) return found;

    return QString();
}

const char *kScriptTemplate = R"PY("""Strategi kustom (Mode Programmer - Python).
Atur SETTINGS (opsional), PARAMS (opsional), dan fungsi on_bar(ctx).
"""

SETTINGS = {
    "symbol": "EURUSDm",          # Simbol aktif (mis. EURUSDm, XAUUSDm, BTCUSDm)
    "timeframe": "M5",            # Timeframe M1, M5, M15, M30, H1, H4, D1
    "volume": 0.01,               # Ukuran lot per order
    "sl_points": 300,             # Stop Loss dalam points
    "tp_points": 600,             # Take Profit dalam points
    "max_positions": 1,           # Maksimal posisi terbuka bersamaan
    "trailing_stop_points": 200,  # Trailing stop points (0 = nonaktif)
    "trailing_step_points": 50,
    "break_even_points": 150,     # Break-even stop points (0 = nonaktif)
    "break_even_offset_points": 10,
    "max_spread_points": 35,      # Batas maksimal spread points
}

PARAMS = [
    {"key": "fast", "label": "EMA Cepat", "type": "int", "default": 12, "min": 1},
    {"key": "slow", "label": "EMA Lambat", "type": "int", "default": 26, "min": 2},
]

def on_bar(ctx):
    fast = ctx.ema(ctx.close, ctx.params.fast)
    slow = ctx.ema(ctx.close, ctx.params.slow)
    if ctx.crossover(fast, slow):
        return ctx.buy()
    if ctx.crossunder(fast, slow):
        return ctx.sell()
    return None
)PY";
} // namespace

BotController::BotController(QObject *parent) : QObject(parent)
{
    ConfigStore::load(settings());
    ConfigStore::loadMcpSecret(settings()); // auto-load API key MCP (mcp_secret.json)
    m_chartSymbol = settings().symbol;
}

BotController::~BotController()
{
    if (m_pyWorker) {
        m_pyWorker->requestStop();
        delete m_pyWorker;
        m_pyWorker = nullptr;
    }
}

QString BotController::backend() const { return settings().backend; }

QString BotController::theme() const { return settings().theme; }

void BotController::setTheme(const QString &themeName)
{
    const QString t = (themeName.trimmed().compare(QStringLiteral("light"), Qt::CaseInsensitive) == 0)
                          ? QStringLiteral("light")
                          : QStringLiteral("dark");
    if (settings().theme != t) {
        settings().theme = t;
        ConfigStore::save(settings());
        emit themeChanged(t);
    }
}

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

void BotController::setAuthState(bool busy, const QString &action, const QString &message)
{
    if (m_authBusy == busy && m_authAction == action && m_authMessage == message)
        return;
    m_authBusy = busy;
    m_authAction = action;
    m_authMessage = message;
    emit authStateChanged();
}

void BotController::resetSessionTelemetry()
{
    m_balance = 0.0;
    m_equity = 0.0;
    m_margin = 0.0;
    m_freeMargin = 0.0;
    m_profit = 0.0;
    m_accountLogin = 0;
    m_currency.clear();
    m_accountType = QStringLiteral("?");
    m_accountServer.clear();
    m_serverConnected = false;
    m_tradeAllowed = false;
    if (m_tradeBlocked || !m_tradeRejectReason.isEmpty()) {
        m_tradeBlocked = false;
        m_tradeRejectReason.clear();
        emit tradeBlockedChanged();
    }
    emit accountChanged();
    emit positionsChanged({});
    emit ordersChanged({});
}

void BotController::setBackend(const QString &nameIn)
{
    QString name = nameIn.toLower();
    if (name != "native" && name != "mcp" && name != "sim")
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

void BotController::ensureBridgeWorker()
{
    if (m_pyWorker)
        return;

    m_pyWorker = new PyBridgeWorker(this);
    connect(m_pyWorker, &PyBridgeWorker::accountUpdated, this, &BotController::onAccount);
    connect(m_pyWorker, &PyBridgeWorker::positionsUpdated, this, &BotController::onPositions);
    connect(m_pyWorker, &PyBridgeWorker::ordersUpdated, this, &BotController::onOrders);
    connect(m_pyWorker, &PyBridgeWorker::journalUpdated, this, &BotController::onJournal);
    connect(m_pyWorker, &PyBridgeWorker::candlesUpdated, this, &BotController::onCandles);
    connect(m_pyWorker, &PyBridgeWorker::symbolsListed, this, &BotController::onSymbols);
    connect(m_pyWorker, &PyBridgeWorker::statsUpdated, this, &BotController::onStats);
    connect(m_pyWorker, &PyBridgeWorker::equityUpdated, this, &BotController::onEquity);
    connect(m_pyWorker, &PyBridgeWorker::autoTradingDisabled, this, &BotController::onAutoDisabled);
    connect(m_pyWorker, &PyBridgeWorker::orderFeedback, this, &BotController::onOrderFeedback);
    connect(m_pyWorker, &PyBridgeWorker::connectedChanged, this, &BotController::onWorkerConnected);
    connect(m_pyWorker, &PyBridgeWorker::chartSymbolChanged, this, &BotController::onWorkerChartSymbol);
    connect(m_pyWorker, &PyBridgeWorker::timeframeChanged, this, &BotController::onWorkerTimeframe);
    connect(m_pyWorker, &PyBridgeWorker::simulationResult, this, &BotController::onSimulationResult);
    connect(m_pyWorker, &PyBridgeWorker::logMessage, this, &BotController::logMessage);
    connect(m_pyWorker, &PyBridgeWorker::stopped, this, &BotController::onWorkerStopped);
}

void BotController::connectBot()
{
    if (m_connected || (m_authBusy && m_authAction == QStringLiteral("login")))
        return;

    const QString bLower = settings().backend.toLower();
    QString loginDesc = QStringLiteral("Menghubungkan ke MCP Server MetaTrader 5...");
    if (bLower == QStringLiteral("native")) {
        loginDesc = QStringLiteral("Meluncurkan terminal MT5 & memverifikasi akun...");
    } else if (bLower == QStringLiteral("sim")) {
        loginDesc = QStringLiteral("Menyiapkan lingkungan Simulasi Paper-Trading...");
    }
    const int serial = ++m_authSerial;
    setAuthState(true, QStringLiteral("login"), loginDesc);
    setStatus(QStringLiteral("Menghubungkan..."));
    emit logMessage(QStringLiteral("[SISTEM] %1").arg(loginDesc));

    // Backend Native: hubungkan ke terminal MT5 lokal via kredensial akun
    if (settings().backend == "native") {
        const QString termPath = findTerminalPath(settings().path);
        const bool alreadyRunning = isTerminalRunning();
        if (alreadyRunning) {
            emit logMessage(QStringLiteral("[MT5] Terminal MT5 sudah berjalan. Menghubungkan ke sesi aktif..."));
        } else if (!termPath.isEmpty() && settings().login > 0 && !settings().server.isEmpty() && !settings().password.isEmpty()) {
            emit logMessage(QStringLiteral("[MT5] Meluncurkan terminal MT5 (Akun #%1)...")
                               .arg(settings().login));
            QStringList args;
            args << QStringLiteral("/login:%1").arg(settings().login);
            args << QStringLiteral("/server:%1").arg(settings().server);
            args << QStringLiteral("/password:%1").arg(settings().password);
            QProcess::startDetached(termPath, args);
        }
    }

    ensureBridgeWorker();

    QVariantMap p;
    p[QStringLiteral("backend")] = settings().backend; // "native" | "mcp" | "sim"
    p[QStringLiteral("login")] = static_cast<qlonglong>(settings().login);
    p[QStringLiteral("password")] = settings().password;
    p[QStringLiteral("server")] = settings().server;
    p[QStringLiteral("path")] = settings().path;
    p[QStringLiteral("mcp_endpoint")] = settings().mcpEndpoint;
    p[QStringLiteral("mcp_api_key")] = settings().mcpApiKey;
    p[QStringLiteral("symbol")] = m_chartSymbol.isEmpty() ? settings().symbol : m_chartSymbol;
    p[QStringLiteral("chart_symbol")] = m_chartSymbol.isEmpty() ? settings().symbol : m_chartSymbol;
    p[QStringLiteral("sim_balance")] = settings().simBalance;
    p[QStringLiteral("sim_scenario")] = settings().simScenario;
    p[QStringLiteral("sim_spread_points")] = settings().simSpreadPoints;

    m_pyWorker->connectBackend(p);

    // Timeout pengaman agar indikator loading login tidak berputar selamanya bila terminal gagal merespons
    QPointer<BotController> self(this);
    QTimer::singleShot(25000, this, [self, serial]() {
        if (!self || self->m_authSerial != serial)
            return;
        if (self->m_authBusy && self->m_authAction == QStringLiteral("login") && !self->m_connected) {
            self->setAuthState(false, QString(),
                               QStringLiteral("Waktu koneksi habis — periksa terminal MT5 atau pengaturan koneksi."));
            self->setStatus(QStringLiteral("Gagal terhubung"));
            emit self->logMessage(QStringLiteral("[ERROR] Timeout saat menghubungkan sesi login."));
        }
    });
}

void BotController::disconnectBot()
{
    setStatus(QStringLiteral("Sedang logout..."));
    setTradingState(false);
    if (m_pyWorker && m_pyWorker->isRunning()) {
        m_pyWorker->setTrading(false);
        m_pyWorker->requestStop();
    } else {
        onWorkerStopped();
    }
}

void BotController::logoutAccount()
{
    if (m_authBusy && m_authAction == QStringLiteral("logout"))
        return;

    const int serial = ++m_authSerial;
    setAuthState(true, QStringLiteral("logout"), QStringLiteral("Sedang logout & memutus koneksi sesi..."));
    emit logMessage(QStringLiteral("[SISTEM] Sedang logout dan menutup koneksi akun..."));

    disconnectBot();

    // Pengaman: pastikan status & loading logout selalu selesai meski worker tidak mengirim event balik
    QPointer<BotController> self(this);
    QTimer::singleShot(2500, this, [self, serial]() {
        if (!self || self->m_authSerial != serial)
            return;
        if (self->m_authBusy && self->m_authAction == QStringLiteral("logout")) {
            self->setConnectedState(false);
            self->setTradingState(false);
            self->resetSessionTelemetry();
            self->setStatus(QStringLiteral("Terputus"));
            self->setAuthState(false, QString(), QStringLiteral("Logout berhasil — sesi akun ditutup dengan aman."));
            emit self->logMessage(QStringLiteral("[SISTEM] Logout berhasil — sesi akun ditutup dengan aman."));
        }
    });
}

void BotController::setTrading(bool enabled)
{
    if (!m_connected) {
        emit configError(QStringLiteral("Hubungkan ke MT5 dulu sebelum mengaktifkan trading."));
        return;
    }
    setTradingState(enabled);
    if (m_pyWorker) {
        if (enabled) {
            m_pyWorker->reloadStrategy();
        }
        m_pyWorker->setTrading(enabled);
    }
    setStatus(enabled ? QStringLiteral("Trading aktif") : QStringLiteral("Terhubung"));

    const QString sym = settings().symbol;
    const QString tf = settings().timeframeStr;
    QString strat = settings().strategyName;
    if (strat.isEmpty() || strat == QStringLiteral("custom_script"))
        strat = QStringLiteral("Mode Programmer");

    QVariantMap jEntry;
    jEntry["symbol"] = sym;
    jEntry["ok"] = true;

    if (enabled) {
        jEntry["action"] = QStringLiteral("START");
        jEntry["detail"] = QStringLiteral("Mode Programmer aktif — Skrip strategi berjalan (Simbol: %1, Timeframe: %2)").arg(sym, tf);
        emit logMessage(QStringLiteral("[SKRIP] Mode Programmer aktif — Skrip strategi berjalan (%1, TF: %2).").arg(sym, tf));
    } else {
        jEntry["action"] = QStringLiteral("STOP");
        jEntry["detail"] = QStringLiteral("Mode Programmer dinonaktifkan — Auto-trading dihentikan pengguna");
        emit logMessage(QStringLiteral("[SKRIP] Mode Programmer dinonaktifkan — Auto-trading dihentikan."));
    }
    onJournal(jEntry);
}

void BotController::closePosition(qlonglong ticket)
{
    if (!m_connected) {
        emit configError(QStringLiteral("Tidak terhubung ke MT5."));
        return;
    }
    if (m_pyWorker)
        m_pyWorker->enqueueClose(ticket);
    emit logMessage(QStringLiteral("[ORDER] Meminta penutupan posisi ticket #%1...").arg(ticket));
}

void BotController::openManualOrder(const QString &symbolIn, const QString &side, double volume,
                                    double sl, double tp)
{
    if (!m_connected) {
        emit configError(QStringLiteral("Hubungkan ke MT5 dulu sebelum kirim order."));
        return;
    }
    QString symbol = symbolIn.trimmed();
    if (symbol.isEmpty())
        symbol = m_chartSymbol.isEmpty() ? settings().symbol : m_chartSymbol;
    if (symbol.isEmpty()) {
        emit configError(QStringLiteral("Simbol belum ditentukan. Masukkan nama simbol (misal EURUSDm)."));
        return;
    }
    if (volume <= 0) {
        emit configError(QStringLiteral("Volume lot harus > 0 (contoh: 0.01)."));
        return;
    }
    ManualCommand c;
    c.action = "market";
    c.symbol = symbol;
    c.side = side.toLower();
    c.volume = volume;
    c.sl = sl;
    c.tp = tp;
    if (m_pyWorker)
        m_pyWorker->enqueue(c);
    emit logMessage(QStringLiteral("[ORDER] Mengirim order manual %1 %2 (vol: %3)...")
                        .arg(side.toUpper(), symbol).arg(volume, 0, 'f', 2));
}

void BotController::placePendingOrder(const QString &symbolIn, const QString &orderType,
                                      double volume, double price, double sl, double tp)
{
    if (!m_connected) {
        emit configError(QStringLiteral("Hubungkan ke MT5 dulu sebelum pasang pending order."));
        return;
    }
    QString symbol = symbolIn.trimmed();
    if (symbol.isEmpty())
        symbol = m_chartSymbol.isEmpty() ? settings().symbol : m_chartSymbol;
    if (symbol.isEmpty()) {
        emit configError(QStringLiteral("Simbol belum ditentukan. Masukkan nama simbol (misal EURUSDm)."));
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
    if (m_pyWorker)
        m_pyWorker->enqueue(c);
    emit logMessage(QStringLiteral("[ORDER] Memasang pending order %1 %2 @ %3 (vol: %4)...")
                        .arg(orderType.toUpper(), symbol).arg(price).arg(volume, 0, 'f', 2));
}

void BotController::openHedgeOrder(const QString &symbolIn, double volume)
{
    if (!m_connected) {
        emit configError(QStringLiteral("Hubungkan ke MT5 dulu sebelum kirim order hedge."));
        return;
    }
    QString symbol = symbolIn.trimmed();
    if (symbol.isEmpty())
        symbol = m_chartSymbol.isEmpty() ? settings().symbol : m_chartSymbol;
    if (symbol.isEmpty()) {
        emit configError(QStringLiteral("Simbol belum ditentukan untuk order hedge."));
        return;
    }
    if (volume <= 0.0) {
        emit configError(QStringLiteral("Volume lot hedge harus > 0 (contoh: 0.01)."));
        return;
    }

    emit logMessage(QStringLiteral("[HEDGE] Eksekusi ganda BUY & SELL serentak (%1 lot %2)...")
                        .arg(QString::number(volume, 'f', 2), symbol));
    openManualOrder(symbol, QStringLiteral("BUY"), volume, 0.0, 0.0);
    openManualOrder(symbol, QStringLiteral("SELL"), volume, 0.0, 0.0);
}

void BotController::closeAllPositions()
{
    if (!m_connected) {
        emit configError(QStringLiteral("Tidak terhubung ke MT5."));
        return;
    }
    ManualCommand c;
    c.action = "close_all";
    if (m_pyWorker)
        m_pyWorker->enqueue(c);
    emit logMessage(QStringLiteral("[ORDER] Meminta penutupan semua posisi aktif..."));
}

void BotController::emergencyCloseAllReset()
{
    closeAllPositions();
    emit logMessage(QStringLiteral("[RESET] Emergency Close All & State Reset berhasil dipicu."));
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
    if (m_pyWorker)
        m_pyWorker->enqueue(c);
    emit logMessage(QStringLiteral("[ORDER] Meminta hapus pending order ticket #%1...").arg(ticket));
}

void BotController::setChartSymbol(const QString &symbolIn)
{
    const QString symbol = symbolIn.trimmed();
    if (symbol.isEmpty())
        return;
    m_chartSymbol = symbol;
    settings().symbol = symbol;
    ConfigStore::save(settings());
    if (m_pyWorker)
        m_pyWorker->setChartSymbol(symbol);
    emit chartSymbolChanged(symbol);
}

QString BotController::timeframe() const
{
    return settings().timeframeStr;
}

void BotController::setTimeframe(const QString &tfIn)
{
    const QString tf = tfIn.trimmed().toUpper();
    static const QSet<QString> validTfs = {"M1", "M5", "M15", "M30", "H1", "H4", "D1"};
    if (!validTfs.contains(tf))
        return;
    if (tf == settings().timeframeStr)
        return;
    settings().timeframeStr = tf;
    ConfigStore::save(settings());
    if (m_pyWorker)
        m_pyWorker->setTimeframe(tf);
    emit timeframeChanged(tf);
    emit logMessage(QStringLiteral("[CHART] Timeframe lilin diubah ke %1").arg(tf));
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
    if (m_pyWorker && m_pyWorker->isRunning()) {
        QVariantMap p;
        p[QStringLiteral("config")] = ConfigStore::toJson(settings()).toVariantMap();
        m_pyWorker->sendCommand(QStringLiteral("apply_config"), p);
    }
    return true;
}

QVariantList BotController::getStrategies()
{
    QVariantList out;
    out << QVariantMap{
        {QStringLiteral("name"), QStringLiteral("custom_script")},
        {QStringLiteral("display_name"), QStringLiteral("Mode Programmer (Custom Script)")},
        {QStringLiteral("params"), QVariantList()}
    };
    return out;
}

bool BotController::saveConfig(const QVariantMap &cfg)
{
    QVariantMap risk = cfg;
    risk.take("strategy_name");
    risk.take("strategy_params");
    const QStringList errs = ConfigStore::apply(QJsonObject::fromVariantMap(risk), settings());
    if (!errs.isEmpty()) {
        emit configError(errs.join("; "));
        return false;
    }
    settings().strategyName = QStringLiteral("custom_script");
    ConfigStore::save(settings());
    if (m_pyWorker && m_pyWorker->isRunning()) {
        QVariantMap p;
        p[QStringLiteral("config")] = ConfigStore::toJson(settings()).toVariantMap();
        m_pyWorker->sendCommand(QStringLiteral("apply_config"), p);
    }
    if (cfg.contains(QStringLiteral("timeframe_str"))) {
        emit timeframeChanged(settings().timeframeStr);
    }
    emit logMessage(QStringLiteral("[SISTEM] Konfigurasi berhasil disimpan."));
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

bool BotController::connectSim(const QVariantMap &cfg)
{
    const double bal = cfg.value(QStringLiteral("balance"), settings().simBalance).toDouble();
    const QString sym = cfg.value(QStringLiteral("symbol")).toString().trimmed();
    const QString scen = cfg.value(QStringLiteral("scenario"), settings().simScenario).toString().trimmed().toLower();
    const int spread = cfg.value(QStringLiteral("spread_points"), settings().simSpreadPoints).toInt();

    settings().simBalance = (bal >= 100.0) ? bal : 10000.0;
    if (!scen.isEmpty())
        settings().simScenario = scen;
    settings().simSpreadPoints = (spread >= 1) ? spread : 25;
    if (!sym.isEmpty()) {
        settings().symbol = sym;
        m_chartSymbol = sym;
        emit chartSymbolChanged(sym);
    }
    setBackend(QStringLiteral("sim"));
    ConfigStore::save(settings());
    connectBot();
    return true;
}

void BotController::runScriptSimulation(const QString &source,
                                          const QString &scenario,
                                          int bars,
                                          double initialBalance,
                                          int spreadPoints)
{
    const QVariantMap v = validateScript(source);
    if (!v.value(QStringLiteral("ok")).toBool()) {
        QVariantMap fail;
        fail[QStringLiteral("ok")] = false;
        fail[QStringLiteral("error")] = v.value(QStringLiteral("error")).toString();
        emit simulationFinished(fail);
        return;
    }

    ensureBridgeWorker();
    QVariantMap p;
    p[QStringLiteral("source")] = source;
    p[QStringLiteral("symbol")] = m_chartSymbol.isEmpty() ? settings().symbol : m_chartSymbol;
    p[QStringLiteral("timeframe")] = settings().timeframeStr;
    p[QStringLiteral("scenario")] = scenario.trimmed().isEmpty() ? settings().simScenario : scenario.trimmed().toLower();
    p[QStringLiteral("bars")] = (bars > 0) ? bars : 120;
    p[QStringLiteral("initial_balance")] = (initialBalance >= 100.0) ? initialBalance : settings().simBalance;
    p[QStringLiteral("spread_points")] = (spreadPoints >= 1) ? spreadPoints : settings().simSpreadPoints;
    m_pyWorker->runScriptSimulation(p);
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
    emit logMessage(QStringLiteral("[PROFIL] Profil MCP '%1' berhasil dimuat.").arg(o.value("name").toString()));
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
QString nativeDir()
{
    const QString appProf = QCoreApplication::applicationDirPath() + QStringLiteral("/profiles");
    if (QDir(appProf).exists())
        return appProf;
    if (QDir(QStringLiteral("profiles")).exists())
        return QStringLiteral("profiles");
    if (QDir(QStringLiteral("C:/XaviqCpp/profiles")).exists())
        return QStringLiteral("C:/XaviqCpp/profiles");
    return QStringLiteral("profiles");
}
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
    emit logMessage(QStringLiteral("[PROFIL] Profil Native '%1' berhasil dimuat.").arg(o.value("name").toString()));
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

bool BotController::saveProfile(const QVariantMap &creds, const QString &saveNameIn)
{
    const long long login = creds.value("login").toLongLong();
    const QString server = creds.value("server").toString().trimmed();
    QString password = creds.value("password").toString();
    if (password.isEmpty())
        password = settings().password;

    if (login <= 0 || server.isEmpty()) {
        emit configError(QStringLiteral("Login dan server wajib diisi untuk menyimpan profil."));
        return false;
    }

    QString name = saveNameIn.trimmed();
    if (name.isEmpty()) {
        QString srvClean = server;
        srvClean.replace(QRegularExpression("[^a-zA-Z0-9_-]"), "_");
        name = QStringLiteral("%1_%2").arg(srvClean, QString::number(login));
    }

    QDir().mkpath(nativeDir());
    QJsonObject o;
    o["name"] = name;
    o["login"] = static_cast<qlonglong>(login);
    o["server"] = server;
    o["path"] = creds.value("path").toString();
    if (!password.isEmpty())
        o["password"] = SecureStore::encrypt(password);

    QFile f(nativeDir() + "/" + safeFileName(name) + ".json");
    if (!f.open(QIODevice::WriteOnly | QIODevice::Truncate | QIODevice::Text)) {
        emit configError(QStringLiteral("Gagal menyimpan file profil: %1").arg(f.errorString()));
        return false;
    }
    f.write(QJsonDocument(o).toJson(QJsonDocument::Indented));
    f.close();
    emit logMessage(QStringLiteral("[PROFIL] Profil Native '%1' berhasil disimpan.").arg(name));
    emit profilesChanged(listProfiles());
    return true;
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

    // PASTIKAN OTOMATIS TERSIMPAN SEBUAH FILE:
    // Jika saveName kosong, otomatis buatkan nama profil dari server dan nomor login.
    QString name = saveName.trimmed();
    if (name.isEmpty()) {
        QString srvClean = server;
        srvClean.replace(QRegularExpression("[^a-zA-Z0-9_-]"), "_");
        name = QStringLiteral("%1_%2").arg(srvClean, QString::number(login));
    }
    saveProfile(d, name);

    connectBot();
    return true;
}

QString BotController::scriptTemplate() { return QString::fromUtf8(kScriptTemplate); }

QVariantMap BotController::validateScript(const QString &source)
{
    if (source.trimmed().isEmpty()) {
        return {{"ok", false}, {"line", 1}, {"message", QStringLiteral("Skrip tidak boleh kosong.")}};
    }
    int parens = 0, braces = 0, brackets = 0;
    int line = 1;
    bool inLineComment = false;
    bool inBlockComment = false;
    QChar inStringQuote;

    for (int i = 0; i < source.length(); ++i) {
        QChar c = source[i];
        QChar next = (i + 1 < source.length()) ? source[i + 1] : QChar();

        if (c == QLatin1Char('\n')) {
            line++;
            inLineComment = false;
            continue;
        }

        if (inLineComment) continue;

        if (inBlockComment) {
            if (c == QLatin1Char('*') && next == QLatin1Char('/')) {
                inBlockComment = false;
                ++i;
            }
            continue;
        }

        if (inStringQuote != QChar()) {
            if (c == QLatin1Char('\\')) {
                ++i; // skip escaped character
            } else if (c == inStringQuote) {
                inStringQuote = QChar();
            }
            continue;
        }

        // Cek awalan komentar
        if (c == QLatin1Char('#') || (c == QLatin1Char('/') && next == QLatin1Char('/'))) {
            inLineComment = true;
            if (c == QLatin1Char('/')) ++i;
            continue;
        }
        if (c == QLatin1Char('/') && next == QLatin1Char('*')) {
            inBlockComment = true;
            ++i;
            continue;
        }

        // Cek string quote
        if (c == QLatin1Char('"') || c == QLatin1Char('\'') || c == QLatin1Char('`')) {
            inStringQuote = c;
            continue;
        }

        if (c == QLatin1Char('(')) parens++;
        else if (c == QLatin1Char(')')) { if (--parens < 0) return {{"ok", false}, {"line", line}, {"message", QStringLiteral("Tutup kurung ')' tanpa pembuka")}}; }
        else if (c == QLatin1Char('{')) braces++;
        else if (c == QLatin1Char('}')) { if (--braces < 0) return {{"ok", false}, {"line", line}, {"message", QStringLiteral("Tutup kurawal '}' tanpa pembuka")}}; }
        else if (c == QLatin1Char('[')) brackets++;
        else if (c == QLatin1Char(']')) { if (--brackets < 0) return {{"ok", false}, {"line", line}, {"message", QStringLiteral("Kurung siku '[' tanpa pembuka")}}; }
    }
    if (parens > 0) return {{"ok", false}, {"line", line}, {"message", QStringLiteral("Kurung '(' belum ditutup")}};
    if (braces > 0) return {{"ok", false}, {"line", line}, {"message", QStringLiteral("Kurawal '{' belum ditutup")}};
    if (brackets > 0) return {{"ok", false}, {"line", line}, {"message", QStringLiteral("Kurung siku '[' belum ditutup")}};

    return {{"ok", true}, {"line", 0}, {"message", QStringLiteral("Sintaks valid")}};
}

QVariantMap BotController::inspectScriptVariables(const QString &source)
{
    const QVariantMap base = validateScript(source);
    const bool syntaxOk = base.value(QStringLiteral("ok")).toBool();
    const int syntaxLine = base.value(QStringLiteral("line")).toInt();
    const QString syntaxMsg = base.value(QStringLiteral("message")).toString();

    static const QSet<QString> kValidSettings = {
        "symbol", "timeframe", "timeframe_str", "volume", "lot", "risk", "risk_per_trade",
        "sl_points", "sl", "tp_points", "tp", "sl_percent", "tp_percent", "sl_tp_mode",
        "max_positions", "max_open_positions", "magic_number", "magic",
        "trailing_stop_points", "trailing_stop", "trailing_step_points", "trailing_step",
        "trailing_stop_enabled", "break_even_trigger_points", "break_even_points", "break_even",
        "break_even_offset_points", "break_even_offset", "break_even_enabled",
        "max_spread_points", "max_spread", "daily_drawdown_limit", "equity_stop_loss",
        "max_consecutive_losses", "max_daily_trades", "max_exposure_lots",
        "virtual_sltp_enabled", "loop_interval", "comment", "name", "strategy_name",
        "trade_start_time", "start_time", "trade_end_time", "end_time",
        "close_friday_hour", "active_days", "risk_reward_ratio", "rr_ratio", "risk_reward",
        "atr_sl_mult", "atr_sl_multiplier", "atr_tp_mult", "atr_tp_multiplier",
        "max_slippage_points", "slippage", "cooldown_bars", "min_bars_between_trades",
        "one_trade_per_bar", "close_on_reversal", "min_margin_level",
        "max_holding_bars", "holding_bars"
    };

    static const QSet<QString> kValidCtxMembers = {
        "open", "high", "low", "close", "volume", "rates", "params", "settings", "symbol",
        "position", "positions", "pending_orders", "state",
        "balance", "equity", "margin", "free_margin", "margin_level",
        "floating_profit", "unrealized_profit",
        "bid", "ask", "point", "digits", "volume_min", "volume_max", "volume_step",
        "stop_level", "freeze_level", "contract_size", "spread",
        "time", "now", "hour", "minute", "weekday", "log",
        "sma", "ema", "rsi", "stdev", "atr", "highest", "lowest",
        "bbands", "macd", "wma", "stochastic", "adx", "cci", "vwap",
        "williams_r", "obv", "mfi", "donchian", "parabolic_sar", "supertrend",
        "ichimoku", "pivot_points", "crossover", "crossunder",
        "buy", "sell", "close_position", "close_all", "close_side",
        "buy_stop", "sell_stop", "buy_limit", "sell_limit",
        "modify_order", "delete_order", "modify"
    };

    // Strip komentar (# dan //) untuk scanning identifier akurat
    QString stripped;
    stripped.reserve(source.size());
    const QStringList rawLines = source.split('\n');
    for (const QString &ln : rawLines) {
        QString clean = ln;
        bool inSq = false, inDq = false;
        for (int i = 0; i < clean.size(); ++i) {
            const QChar ch = clean[i];
            if (ch == '\\') { ++i; continue; }
            if (ch == '\'' && !inDq) inSq = !inSq;
            else if (ch == '"' && !inSq) inDq = !inDq;
            else if (!inSq && !inDq) {
                if (ch == '#' || (ch == '/' && i + 1 < clean.size() && clean[i + 1] == '/')) {
                    clean = clean.left(i);
                    break;
                }
            }
        }
        stripped += clean + '\n';
    }

    const bool hasOnBar = QRegularExpression(QStringLiteral("\\b(def|function)\\s+on_bar\\s*\\(")).match(stripped).hasMatch();

    // Ekstrak blok SETTINGS = { ... } bila ada
    QStringList detectedSettings, unknownSettings;
    const QRegularExpression reSettingsBlock(QStringLiteral("\\bSETTINGS\\s*=\\s*\\{([\\s\\S]*?)\\}"));
    const QRegularExpressionMatch sm = reSettingsBlock.match(stripped);
    if (sm.hasMatch()) {
        const QString body = sm.captured(1);
        const QRegularExpression reKey(QStringLiteral("[\"']([A-Za-z_][A-Za-z0-9_]*)[\"']\\s*:|\\b([A-Za-z_][A-Za-z0-9_]*)\\s*:"));
        auto it = reKey.globalMatch(body);
        while (it.hasNext()) {
            const QRegularExpressionMatch km = it.next();
            const QString k = (!km.captured(1).isEmpty() ? km.captured(1) : km.captured(2)).trimmed();
            if (k.isEmpty() || detectedSettings.contains(k))
                continue;
            detectedSettings << k;
            if (!kValidSettings.contains(k))
                unknownSettings << k;
        }
    }

    // Ekstrak PARAMS declared keys — mendukung format list [{"key": "..."}, ...]
    // maupun format dict {"nama_param": nilai_default, ...} (seperti GMG V1.1).
    QStringList declaredParams;
    const QRegularExpression reParamsList(QStringLiteral("\\bPARAMS\\s*=\\s*\\[([\\s\\S]*?)\\]"));
    const QRegularExpressionMatch pml = reParamsList.match(stripped);
    if (pml.hasMatch()) {
        const QRegularExpression rePKey(QStringLiteral("[\"']key[\"']\\s*:\\s*[\"']([A-Za-z_][A-Za-z0-9_]*)[\"']"));
        auto it = rePKey.globalMatch(pml.captured(1));
        while (it.hasNext()) {
            const QString pk = it.next().captured(1);
            if (!declaredParams.contains(pk))
                declaredParams << pk;
        }
    } else {
        const QRegularExpression reParamsDict(QStringLiteral("\\bPARAMS\\s*=\\s*\\{([\\s\\S]*?)\\}"));
        const QRegularExpressionMatch pmd = reParamsDict.match(stripped);
        if (pmd.hasMatch()) {
            const QRegularExpression reDKey(QStringLiteral("[\"']([A-Za-z_][A-Za-z0-9_]*)[\"']\\s*:|\\b([A-Za-z_][A-Za-z0-9_]*)\\s*:"));
            auto it = reDKey.globalMatch(pmd.captured(1));
            while (it.hasNext()) {
                const QRegularExpressionMatch km = it.next();
                const QString pk = (!km.captured(1).isEmpty() ? km.captured(1) : km.captured(2)).trimmed();
                if (!pk.isEmpty() && !declaredParams.contains(pk))
                    declaredParams << pk;
            }
        }
    }

    // Ekstrak semua ctx.<member> dan ctx.params.<paramKey>
    QStringList detectedCtx, unknownCtx, usedParams, undeclaredParams;
    const QRegularExpression reCtx(QStringLiteral("\\bctx\\.([A-Za-z_][A-Za-z0-9_]*)"));
    auto cit = reCtx.globalMatch(stripped);
    while (cit.hasNext()) {
        const QString mem = cit.next().captured(1);
        if (!detectedCtx.contains(mem))
            detectedCtx << mem;
        if (!kValidCtxMembers.contains(mem) && !unknownCtx.contains(mem))
            unknownCtx << mem;
    }

    const QRegularExpression reCtxParam(QStringLiteral("\\bctx\\.params\\.([A-Za-z_][A-Za-z0-9_]*)"));
    auto cpit = reCtxParam.globalMatch(stripped);
    while (cpit.hasNext()) {
        const QString pk = cpit.next().captured(1);
        if (!usedParams.contains(pk))
            usedParams << pk;
        if (!declaredParams.contains(pk) && !undeclaredParams.contains(pk))
            undeclaredParams << pk;
    }

    const bool hasForbidden = QRegularExpression(QStringLiteral("\\b(__import__|eval|exec)\\b")).match(stripped).hasMatch();
    const bool hasErrors = !syntaxOk || !hasOnBar || hasForbidden;
    const bool hasWarnings = !unknownSettings.isEmpty() || !unknownCtx.isEmpty() || !undeclaredParams.isEmpty();

    QString status = QStringLiteral("VALID");
    if (hasErrors) status = QStringLiteral("ERROR");
    else if (hasWarnings) status = QStringLiteral("PERINGATAN");

    QString summary;
    if (!syntaxOk) {
        summary = QStringLiteral("Baris %1: %2").arg(syntaxLine).arg(syntaxMsg);
    } else if (hasForbidden) {
        summary = QStringLiteral("Ditemukan fungsi terlarang (__import__/eval/exec).");
    } else if (!hasOnBar) {
        summary = QStringLiteral("Fungsi wajib 'def on_bar(ctx):' belum didefinisikan.");
    } else if (hasWarnings) {
        summary = QStringLiteral("Sintaks OK, namun ada %1 variabel/atribut belum sesuai.")
                      .arg(unknownSettings.size() + unknownCtx.size() + undeclaredParams.size());
    } else {
        summary = QStringLiteral("Sintaks valid, on_bar(ctx) siap, dan semua %1 variabel ctx/SETTINGS sesuai.")
                      .arg(detectedSettings.size() + detectedCtx.size());
    }

    return QVariantMap{
        {"ok", !hasErrors},
        {"hasWarnings", hasWarnings},
        {"status", status},
        {"summary", summary},
        {"syntaxOk", syntaxOk},
        {"syntaxLine", syntaxLine},
        {"syntaxMessage", syntaxMsg},
        {"hasOnBar", hasOnBar},
        {"hasForbidden", hasForbidden},
        {"detectedSettings", detectedSettings},
        {"unknownSettings", unknownSettings},
        {"detectedCtxMembers", detectedCtx},
        {"unknownCtxMembers", unknownCtx},
        {"declaredParams", declaredParams},
        {"usedParams", usedParams},
        {"undeclaredParams", undeclaredParams}
    };
}

void BotController::setScript(const QString &source)
{
    settings().scriptSource = source;
    settings().strategyName = QStringLiteral("custom_script");
    ConfigStore::save(settings());
    if (m_pyWorker)
        m_pyWorker->reloadStrategy();
    emit logMessage(QStringLiteral("[SKRIP] Skrip strategi disimpan & diperbarui di runtime engine."));
}

QString BotController::currentScript()
{
    QString src = settings().scriptSource;
    if (src.trimmed().isEmpty()) {
        src = scriptTemplate();
    }
    return src;
}

// ---------- Manajemen file skrip (folder "scripts", *.js / *.py) ----------
namespace {
QString scriptsDir()
{
    // Prioritas 1: folder scripts di samping direktori aplikasi (dist/portable standalone)
    const QString appScripts = QCoreApplication::applicationDirPath() + QStringLiteral("/scripts");
    if (QDir(appScripts).exists())
        return appScripts;
    // Prioritas 2: folder scripts di current working directory
    if (QDir(QStringLiteral("scripts")).exists())
        return QStringLiteral("scripts");
    // Prioritas 3: Lingkungan development junction C:/XaviqCpp/scripts
    if (QDir(QStringLiteral("C:/XaviqCpp/scripts")).exists())
        return QStringLiteral("C:/XaviqCpp/scripts");
    // Prioritas 4: folder cpp/scripts (saat dijalankan dari root repositori)
    if (QDir(QStringLiteral("cpp/scripts")).exists())
        return QStringLiteral("cpp/scripts");
    return QStringLiteral("scripts");
}
} // namespace

QVariantList BotController::listScripts()
{
    QVariantList out;
    QSet<QString> seen;
    auto scan = [&](const QString &dirPath, const QString &ext) {
        QDir dir(dirPath);
        if (!dir.exists()) return;
        const QStringList files = dir.entryList({QStringLiteral("*.") + ext}, QDir::Files, QDir::Name);
        for (const QString &fn : files) {
            QString base = fn;
            base.chop(ext.length() + 1);
            if (base.compare(QStringLiteral("README"), Qt::CaseInsensitive) == 0 || base.startsWith(QLatin1String("__")))
                continue;
            if (!seen.contains(base)) {
                seen.insert(base);
                out << base;
            }
        }
    };
    scan(scriptsDir(), QStringLiteral("js"));
    scan(scriptsDir(), QStringLiteral("py"));
    scan(QStringLiteral("py_backend/strategies/scripts"), QStringLiteral("py"));
    scan(QStringLiteral("strategies/scripts"), QStringLiteral("py"));
    return out;
}

QString BotController::loadScript(const QString &name)
{
    const QString base = safeFileName(name);
    const QStringList paths = {
        QStringLiteral("py_backend/strategies/scripts/") + base + QStringLiteral(".py"),
        QStringLiteral("strategies/scripts/") + base + QStringLiteral(".py"),
        scriptsDir() + "/" + base + QStringLiteral(".py"),
        scriptsDir() + "/" + base + QStringLiteral(".js")
    };
    for (const QString &p : paths) {
        QFile f(p);
        if (f.open(QIODevice::ReadOnly | QIODevice::Text))
            return QString::fromUtf8(f.readAll());
    }
    return {};
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
    const QString base = safeFileName(n);
    const bool isPy = source.contains(QStringLiteral("def on_bar")) || source.contains(QStringLiteral("import "));
    const QString ext = isPy ? QStringLiteral(".py") : QStringLiteral(".js");
    QFile f(scriptsDir() + "/" + base + ext);
    if (!f.open(QIODevice::WriteOnly | QIODevice::Truncate | QIODevice::Text))
        return false;
    f.write(source.toUtf8());
    f.close();

    // Jika skrip Python, salin juga ke py_backend/strategies/scripts/ bila foldernya ada
    if (isPy) {
        const QString pyDir = QStringLiteral("py_backend/strategies/scripts");
        if (QDir(pyDir).exists()) {
            QFile fPy(pyDir + "/" + base + QStringLiteral(".py"));
            if (fPy.open(QIODevice::WriteOnly | QIODevice::Truncate | QIODevice::Text)) {
                fPy.write(source.toUtf8());
                fPy.close();
            }
        }
    }

    emit logMessage(QStringLiteral("[SKRIP] Skrip '%1' berhasil disimpan.").arg(n));
    return true;
}

bool BotController::deleteScript(const QString &name)
{
    const QString n = name.trimmed();
    if (n.isEmpty())
        return false;
    const QString base = safeFileName(n);
    bool ok = false;
    QFile fJs(scriptsDir() + "/" + base + QStringLiteral(".js"));
    if (fJs.exists()) ok |= fJs.remove();
    QFile fPy(scriptsDir() + "/" + base + QStringLiteral(".py"));
    if (fPy.exists()) ok |= fPy.remove();
    QFile fPyBack(QStringLiteral("py_backend/strategies/scripts/") + base + QStringLiteral(".py"));
    if (fPyBack.exists()) ok |= fPyBack.remove();
    if (ok)
        emit logMessage(QStringLiteral("[SKRIP] Skrip '%1' telah dihapus.").arg(n));
    return ok;
}

void BotController::onJournal(const QVariantMap &entryIn)
{
    QVariantMap entry = entryIn;
    if (!entry.contains("time") || entry.value("time").toString().isEmpty()) {
        entry["time"] = QDateTime::currentDateTime().toString("HH:mm:ss");
    }
    m_journal.append(entry);
    if (m_journal.size() > 1000)
        m_journal.removeFirst();
    emit journalEntry(entry);
    emit journalChanged();

    const QString action = entry.value("action").toString();
    const QString symbol = entry.value("symbol").toString();
    const QString detail = entry.value("detail").toString();
    const bool ok = entry.value("ok", true).toBool();
    emit logMessage(QStringLiteral("[%1] %2 %3 — %4")
                        .arg(ok ? QStringLiteral("JURNAL") : QStringLiteral("JURNAL DITOLAK"),
                             action, symbol, detail));
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
    emit logMessage(QStringLiteral("[SISTEM] Jurnal diekspor ke %1 (%2 baris).")
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
    emit logMessage(QStringLiteral("[SISTEM] Log berhasil diekspor ke %1.").arg(path));
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
        item("ctx.volume", "Array volume tick.", "ctx.volume"),
        item("ctx.rates(tf, count)", "OHLCV multi-timeframe ('H1', 'M15', dll).", "ctx.rates(\"H1\", 200)")});
    out << group("Harga Live & Simbol", {
        item("ctx.bid / ctx.ask", "Harga live.", "ctx.ask"),
        item("ctx.spread", "Spread (points).", "ctx.spread"),
        item("ctx.point / ctx.digits", "Ukuran point & desimal.", "ctx.point"),
        item("ctx.volume_min / step / max", "Batas & step lot broker.", "ctx.volume_step"),
        item("ctx.stop_level / freeze_level", "Batas jarak stop broker (points).", "ctx.stop_level"),
        item("ctx.symbol", "Nama simbol aktif.", "ctx.symbol")});
    out << group("Akun, Posisi & State", {
        item("ctx.balance / ctx.equity", "Saldo & ekuitas.", "ctx.balance"),
        item("ctx.position", "Posisi aktif (objek) atau null.", "ctx.position"),
        item("ctx.positions", "Semua posisi (array).", "ctx.positions"),
        item("ctx.pending_orders", "Semua pending order aktif (array).", "ctx.pending_orders"),
        item("ctx.state", "State persisten skrip antar-bar & restart.", "ctx.state")});
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
        item("ctx.buy(...)", "Buka BUY.", "return ctx.buy(volume=0.01, sl_points=300, tp_points=600)"),
        item("ctx.sell(...)", "Buka SELL.", "return ctx.sell(volume=0.01)"),
        item("ctx.buy_stop / sell_stop(...)", "Pasang pending Stop order.", "ctx.buy_stop(price, volume=0.05)"),
        item("ctx.buy_limit / sell_limit(...)", "Pasang pending Limit order.", "ctx.buy_limit(price, volume=0.05)"),
        item("ctx.modify_order(ord, price)", "Ubah harga pending order.", "ctx.modify_order(ord, new_price)"),
        item("ctx.delete_order(ord)", "Hapus pending order.", "ctx.delete_order(ord)"),
        item("ctx.close_position(pos)", "Tutup posisi (default: aktif).", "return ctx.close_position()"),
        item("ctx.close_side(side)", "Tutup semua posisi 'BUY' atau 'SELL'.", "ctx.close_side(\"BUY\")"),
        item("ctx.close_all()", "Tutup semua posisi.", "return ctx.close_all()"),
        item("ctx.modify(pos, sl, tp)", "Ubah SL/TP posisi.", "return ctx.modify(ctx.position, sl=1.09, tp=1.11)"),
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
    m_accountLogin = a.value("login").toLongLong();
    m_balance = a.value("balance").toDouble();
    m_equity = a.value("equity").toDouble();
    m_margin = a.value("margin").toDouble();
    m_freeMargin = a.value("free_margin").toDouble();
    m_profit = a.value("profit").toDouble();
    m_currency = a.value("currency").toString();
    m_accountType = a.value("account_type").toString();
    m_accountServer = a.value("server").toString();
    m_serverConnected = a.value("server_connected").toBool();
    m_expertsTradeAllowed = a.value("experts_trade_allowed", true).toBool();
    m_mcpTradeAllowed = a.value("mcp_trade_allowed", true).toBool();
    m_accountTradeAllowed = a.value("account_trade_allowed", true).toBool();
    const bool termTrade = a.value("trade_allowed").toBool();
    m_tradeAllowed = termTrade && !m_tradeBlocked;
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
void BotController::resetStats()
{
    m_stats = QVariantMap{
        {QStringLiteral("total_trades"), 0},
        {QStringLiteral("wins"), 0},
        {QStringLiteral("losses"), 0},
        {QStringLiteral("breakeven"), 0},
        {QStringLiteral("win_rate"), 0.0},
        {QStringLiteral("profit_factor"), 0.0},
        {QStringLiteral("gross_profit"), 0.0},
        {QStringLiteral("gross_loss"), 0.0},
        {QStringLiteral("net_profit"), 0.0},
        {QStringLiteral("avg_profit"), 0.0},
        {QStringLiteral("avg_loss"), 0.0},
        {QStringLiteral("max_profit"), 0.0},
        {QStringLiteral("max_loss"), 0.0}
    };
    m_equityCurve.clear();
    emit statsChanged();
    emit equityChanged();
    if (m_pyWorker) {
        ManualCommand c;
        c.action = "reset_stats";
        m_pyWorker->enqueue(c);
    }
    emit logMessage(QStringLiteral("[STATS] Statistik performa trading dan kurva equity berhasil direset ke 0."));
}
void BotController::onAutoDisabled(const QString &reason)
{
    setTradingState(false);
    setStatus(QStringLiteral("Terhubung"));
    emit logMessage(QStringLiteral("[RISIKO] Auto-trading dihentikan: %1").arg(reason));

    QVariantMap jEntry;
    jEntry["symbol"] = settings().symbol;
    jEntry["action"] = QStringLiteral("STOP");
    jEntry["ok"] = false;
    jEntry["detail"] = QStringLiteral("Proteksi risiko: %1").arg(reason);
    onJournal(jEntry);
}
void BotController::onOrderFeedback(bool ok, const QString &message)
{
    if (ok) {
        if (m_tradeBlocked) {
            m_tradeBlocked = false;
            m_tradeRejectReason.clear();
            emit tradeBlockedChanged();
            emit accountChanged();
        }
        emit logMessage(QStringLiteral("[ORDER] Sukses: %1").arg(message));
    } else {
        emit logMessage(QStringLiteral("[ORDER] Ditolak: %1").arg(message));
        const QString lower = message.toLower();
        if (lower.contains("trading is not permitted") || lower.contains("trade is disabled")
            || lower.contains("autotrading disabled") || lower.contains("investor")) {
            m_tradeBlocked = true;
            m_tradeRejectReason = message;
            m_tradeAllowed = false;
            emit tradeBlockedChanged();
            emit accountChanged();
        }
        emit configError(message);
    }
}
void BotController::onWorkerConnected(bool connected)
{
    setConnectedState(connected);
    if (connected) {
        ++m_authSerial;
        setStatus(QStringLiteral("Terhubung"));
        if (settings().backend.compare("native", Qt::CaseInsensitive) == 0) {
            emit logMessage(QStringLiteral("[MT5] Berhasil terhubung ke terminal MetaTrader 5."));
            setAuthState(false, QString(), QStringLiteral("Login berhasil — terhubung ke terminal MetaTrader 5."));
        } else if (settings().backend.compare("sim", Qt::CaseInsensitive) == 0) {
            emit logMessage(QStringLiteral("[SIMULASI] Terhubung ke mode Simulasi Paper-Trading (saldo virtual $%1, skenario '%2').")
                                .arg(settings().simBalance, 0, 'f', 2)
                                .arg(settings().simScenario));
            setAuthState(false, QString(), QStringLiteral("Mode Simulasi aktif — siap menguji skrip & order."));
        } else {
            emit logMessage(QStringLiteral("[MT5] Berhasil terhubung ke MCP MetaTrader 5."));
            setAuthState(false, QString(), QStringLiteral("Login berhasil — terhubung ke MCP MetaTrader 5."));
        }
        // Auto-save rahasia MCP agar API key termuat otomatis saat startup berikutnya.
        if (!settings().mcpApiKey.isEmpty()) {
            if (ConfigStore::saveMcpSecret(settings()))
                emit logMessage(QStringLiteral("[MT5] Kunci sesi MT5 tersimpan untuk sesi berikutnya."));
        }
    } else if (m_authAction == QStringLiteral("login")) {
        ++m_authSerial;
        setStatus(QStringLiteral("Terputus"));
        setAuthState(false, QString(), QStringLiteral("Gagal terhubung ke MT5 — periksa kredensial atau terminal."));
    }
}
void BotController::onWorkerChartSymbol(const QString &symbol)
{
    m_chartSymbol = symbol;
    emit chartSymbolChanged(symbol);
}
void BotController::onWorkerTimeframe(const QString &timeframe)
{
    const QString clean = timeframe.trimmed().toUpper();
    if (clean.isEmpty() || clean == settings().timeframeStr)
        return;
    settings().timeframeStr = clean;
    emit timeframeChanged(clean);
}
void BotController::onSimulationResult(const QVariantMap &result)
{
    if (result.value(QStringLiteral("ok")).toBool()) {
        emit logMessage(
            QStringLiteral("[SIMULASI] Selesai (%1/%2 | %3): Trades=%4, Open=%5, Pending=%6, Net=$%7, WinRate=%8%, MaxDD=%9%")
                .arg(result.value(QStringLiteral("symbol")).toString())
                .arg(result.value(QStringLiteral("timeframe")).toString())
                .arg(result.value(QStringLiteral("scenario")).toString())
                .arg(result.value(QStringLiteral("trades_count")).toInt())
                .arg(result.value(QStringLiteral("open_positions")).toInt())
                .arg(result.value(QStringLiteral("pending_orders")).toInt())
                .arg(result.value(QStringLiteral("net_profit")).toDouble(), 0, 'f', 2)
                .arg(result.value(QStringLiteral("win_rate")).toDouble(), 0, 'f', 1)
                .arg(result.value(QStringLiteral("max_drawdown_pct")).toDouble(), 0, 'f', 2));
    } else {
        emit logMessage(QStringLiteral("[SIMULASI] Gagal: %1").arg(result.value(QStringLiteral("error")).toString()));
    }
    emit simulationFinished(result);
}
void BotController::onWorkerStopped()
{
    // PENTING: JANGAN memanggil stopBridge() / deleteLater() di sini karena sinyal
    // stopped() bisa dipancarkan dari dalam PyBridgeWorker::onReadyReadStdout()
    // atau onProcessFinished() — menghancurkan m_pyWorker di tengah stack itu
    // menyebabkan crash/force-close saat logout. Biarkan m_pyWorker tetap hidup
    // sebagai bridge siap pakai sampai aplikasi ditutup (~BotController).
    const QString prevAction = m_authAction;
    ++m_authSerial;

    setConnectedState(false);
    setTradingState(false);
    resetSessionTelemetry();
    setStatus(QStringLiteral("Terputus"));

    if (prevAction == QStringLiteral("logout")) {
        setAuthState(false, QString(), QStringLiteral("Logout berhasil — sesi akun ditutup dengan aman."));
        emit logMessage(QStringLiteral("[SISTEM] Logout berhasil — sesi akun ditutup dengan aman."));
    } else if (prevAction == QStringLiteral("login")) {
        setAuthState(false, QString(), QStringLiteral("Koneksi gagal atau ditutup sebelum login selesai."));
    } else {
        setAuthState(false, QString(), QString());
    }
}

static QVariantList toVariantPoints(const QVector<double> &series)
{
    QVariantList list;
    list.reserve(series.size());
    for (double v : series) {
        if (ind::isNan(v))
            list << QVariant();
        else
            list << v;
    }
    return list;
}

static double getLastValid(const QVector<double> &series)
{
    for (int i = series.size() - 1; i >= 0; --i) {
        if (!ind::isNan(series[i]))
            return series[i];
    }
    return 0.0;
}

QVariantList BotController::availableIndicators() const
{
    QVariantList list;

    auto addInd = [&](const QString &id, const QString &name, const QString &cat,
                      const QString &color, const QString &style, const QString &type,
                      const QString &desc, bool def = false) {
        QVariantMap m;
        m["id"] = id;
        m["name"] = name;
        m["category"] = cat;
        m["color"] = color;
        m["style"] = style; // "line", "dots", "dash"
        m["type"] = type;   // "overlay" atau "subchart"
        m["description"] = desc;
        m["isDefault"] = def;
        list << m;
    };

    // 1. Moving Averages (Overlay)
    addInd("ema_9", "EMA 9 (Fast Scalper)", "Moving Averages", "#00D2D3", "line", "overlay",
           "Exponential Moving Average periode 9 untuk deteksi momentum kilat", true);
    addInd("ema_21", "EMA 21 (Trend Confirmation)", "Moving Averages", "#FF9F43", "line", "overlay",
           "Exponential Moving Average periode 21 untuk konfirmasi arah tren", true);
    addInd("sma_50", "SMA 50 (Mid-term Trend)", "Moving Averages", "#54A0FF", "line", "overlay",
           "Simple Moving Average periode 50 untuk filter tren menengah", false);
    addInd("sma_200", "SMA 200 (Major Trend)", "Moving Averages", "#EE5253", "line", "overlay",
           "Simple Moving Average periode 200 garis batas tren utama institusional", false);
    addInd("wma_20", "WMA 20 (Weighted)", "Moving Averages", "#F368E0", "line", "overlay",
           "Weighted Moving Average periode 20 memberi bobot lilin terbaru", false);

    // 2. Saluran & Volatilitas (Overlay)
    addInd("bbands", "Bollinger Bands (20, 2)", "Saluran & Volatilitas", "#10B981", "line", "overlay",
           "Bollinger Bands periode 20 deviasi 2.0 (Upper, Mid, Lower)", false);
    addInd("supertrend", "SuperTrend (10, 3)", "Saluran & Volatilitas", "#2ECC71", "line", "overlay",
           "SuperTrend ATR 10 Multiplier 3 (Hijau Bullish / Merah Bearish)", false);
    addInd("donchian", "Donchian Channel (20)", "Saluran & Volatilitas", "#F59E0B", "line", "overlay",
           "Donchian 20-bar breakout channel harga tertinggi & terendah", false);
    addInd("ichimoku", "Ichimoku Cloud (9, 26, 52)", "Saluran & Volatilitas", "#0984E3", "line", "overlay",
           "Ichimoku Kinko Hyo: Tenkan-sen & Kijun-sen cloud baseline", false);

    // 3. Level & Price Action (Overlay)
    addInd("psar", "Parabolic SAR (0.02, 0.2)", "Level & Price Action", "#FD79A8", "dots", "overlay",
           "Parabolic Stop and Reverse dot-points trailing & reversal", false);
    addInd("vwap", "VWAP (14)", "Level & Price Action", "#A29BFE", "line", "overlay",
           "Volume Weighted Average Price rata-rata tertimbang volume", false);
    addInd("pivots", "Pivot Points (Classic)", "Level & Price Action", "#F1C40F", "dash", "overlay",
           "Level Pivot, Resistance 1/2, Support 1/2 harian", false);

    // 4. Osilator (Sub-Window Bawah)
    addInd("rsi", "RSI 14 (Relative Strength)", "Osilator", "#9B59B6", "line", "subchart",
           "RSI 14 dengan batas momentum Overbought 70 & Oversold 30", false);
    addInd("macd", "MACD (12, 26, 9)", "Osilator", "#00CEC9", "line", "subchart",
           "MACD garis sinyal & histogram pembalikan momentum", false);
    addInd("stoch", "Stochastic (14, 3, 3)", "Osilator", "#E17055", "line", "subchart",
           "Stochastic Oscillator %K & %D momentum jenuh jual/beli", false);
    addInd("atr", "ATR 14 (Volatilitas)", "Osilator", "#6C5CE7", "line", "subchart",
           "Average True Range mengukur volatilitas pergerakan harga dalam poin", false);

    return list;
}

QVariantList BotController::computeOverlays(const QVariantList &candles, const QStringList &activeIds) const
{
    QVariantList overlays;
    if (candles.size() < 2 || activeIds.isEmpty())
        return overlays;

    const int n = candles.size();
    QVector<double> open, high, low, close, volume;
    open.reserve(n);
    high.reserve(n);
    low.reserve(n);
    close.reserve(n);
    volume.reserve(n);

    for (const QVariant &cv : candles) {
        const QVariantMap m = cv.toMap();
        open << m.value("o").toDouble();
        high << m.value("h").toDouble();
        low << m.value("l").toDouble();
        close << m.value("c").toDouble();
        volume << m.value("v").toDouble();
    }

    auto makeOverlay = [](const QString &id, const QString &name, const QString &color,
                          const QString &style, const QString &type, const QVector<double> &series,
                          const QString &panel = QString()) {
        QVariantMap ov;
        ov["id"] = id;
        ov["name"] = name;
        ov["color"] = color;
        ov["style"] = style;
        ov["type"] = type;
        ov["panel"] = panel.isEmpty() ? id : panel;
        ov["lastValue"] = getLastValid(series);
        ov["points"] = toVariantPoints(series);
        return ov;
    };

    for (const QString &id : activeIds) {
        if (id == "ema_9") {
            overlays << makeOverlay("ema_9", "EMA 9", "#00D2D3", "line", "overlay", ind::ema(close, 9));
        } else if (id == "ema_21") {
            overlays << makeOverlay("ema_21", "EMA 21", "#FF9F43", "line", "overlay", ind::ema(close, 21));
        } else if (id == "sma_50") {
            overlays << makeOverlay("sma_50", "SMA 50", "#54A0FF", "line", "overlay", ind::sma(close, 50));
        } else if (id == "sma_200") {
            overlays << makeOverlay("sma_200", "SMA 200", "#EE5253", "line", "overlay", ind::sma(close, 200));
        } else if (id == "wma_20") {
            overlays << makeOverlay("wma_20", "WMA 20", "#F368E0", "line", "overlay", ind::wma(close, 20));
        } else if (id == "bbands") {
            const ind::Band bb = ind::bbands(close, 20, 2.0);
            overlays << makeOverlay("bb_upper", "BB Upper", "#10B981", "line", "overlay", bb.upper);
            overlays << makeOverlay("bb_mid", "BB Mid", "#059669", "dash", "overlay", bb.mid);
            overlays << makeOverlay("bb_lower", "BB Lower", "#10B981", "line", "overlay", bb.lower);
        } else if (id == "supertrend") {
            const ind::SuperTrendResult st = ind::supertrend(high, low, close, 10, 3.0);
            QVariantMap ov = makeOverlay("supertrend", "SuperTrend", "#2ECC71", "line", "overlay", st.line);
            QVariantList dirList;
            dirList.reserve(st.direction.size());
            for (int d : st.direction)
                dirList << d;
            ov["directions"] = dirList;
            overlays << ov;
        } else if (id == "donchian") {
            const ind::Band dc = ind::donchian(high, low, 20);
            overlays << makeOverlay("dc_upper", "Donchian Up", "#F59E0B", "line", "overlay", dc.upper);
            overlays << makeOverlay("dc_lower", "Donchian Low", "#F59E0B", "line", "overlay", dc.lower);
        } else if (id == "ichimoku") {
            const ind::IchimokuResult ic = ind::ichimoku(high, low, close, 9, 26, 52);
            overlays << makeOverlay("ichi_tenkan", "Tenkan-sen", "#E84393", "line", "overlay", ic.tenkan);
            overlays << makeOverlay("ichi_kijun", "Kijun-sen", "#0984E3", "line", "overlay", ic.kijun);
        } else if (id == "psar") {
            overlays << makeOverlay("psar", "Parabolic SAR", "#FD79A8", "dots", "overlay", ind::parabolicSar(high, low, 0.02, 0.2));
        } else if (id == "vwap") {
            overlays << makeOverlay("vwap", "VWAP", "#A29BFE", "line", "overlay", ind::vwap(high, low, close, volume, 14));
        } else if (id == "pivots") {
            const ind::Pivots pv = ind::pivotPoints(high, low, close);
            if (pv.valid) {
                QVector<double> sP(n, pv.pivot), sR1(n, pv.r1), sS1(n, pv.s1);
                overlays << makeOverlay("pivot_p", "Pivot", "#F1C40F", "dash", "overlay", sP);
                overlays << makeOverlay("pivot_r1", "R1", "#E74C3C", "dash", "overlay", sR1);
                overlays << makeOverlay("pivot_s1", "S1", "#2ECC71", "dash", "overlay", sS1);
            }
        } else if (id == "rsi") {
            overlays << makeOverlay("rsi", "RSI 14", "#9B59B6", "line", "subchart", ind::rsi(close, 14), "rsi");
        } else if (id == "macd") {
            const ind::MacdResult md = ind::macd(close, 12, 26, 9);
            overlays << makeOverlay("macd_line", "MACD", "#00CEC9", "line", "subchart", md.macd, "macd");
            overlays << makeOverlay("macd_sig", "Signal", "#FF7675", "line", "subchart", md.signal, "macd");
            QVariantMap histOv = makeOverlay("macd_hist", "Hist", "#2ECC71", "histogram", "subchart", md.hist, "macd");
            overlays << histOv;
        } else if (id == "stoch") {
            const ind::StochResult sc = ind::stochastic(high, low, close, 14, 3, 3);
            overlays << makeOverlay("stoch_k", "%K", "#E17055", "line", "subchart", sc.k, "stoch");
            overlays << makeOverlay("stoch_d", "%D", "#FDCB6E", "dash", "subchart", sc.d, "stoch");
        } else if (id == "atr") {
            overlays << makeOverlay("atr", "ATR 14", "#6C5CE7", "line", "subchart", ind::atr(high, low, close, 14), "atr");
        }
    }

    return overlays;
}

QVariantMap BotController::verifyAlgoTrading(const QString &symbolIn)
{
    QVariantMap res;
    if (!m_connected) {
        res["status"] = QStringLiteral("OFFLINE");
        res["ok"] = false;
        res["connected"] = false;
        res["summary"] = QStringLiteral("Bot belum terhubung ke terminal MT5.");
        res["issues"] = QStringList{QStringLiteral("Koneksi ke MT5 belum aktif.")};
        res["solutions"] = QStringList{QStringLiteral("Buka tab Login dan klik tombol 'Login & Connect'.")};
        return res;
    }

    QString sym = symbolIn.trimmed();
    if (sym.isEmpty())
        sym = m_chartSymbol.isEmpty() ? settings().symbol : m_chartSymbol;
    if (sym.isEmpty())
        sym = QStringLiteral("EURUSDm");

    if (m_pyWorker) {
        m_pyWorker->wakeWorker();
    }

    QStringList issues;
    QStringList solutions;
    bool ok = true;

    // 1. Cek koneksi server broker
    if (!m_serverConnected) {
        ok = false;
        issues << QStringLiteral("Terminal MT5 belum tersambung ke server broker (%1).")
                      .arg(m_accountServer.isEmpty() ? QStringLiteral("Exness") : m_accountServer);
        solutions << QStringLiteral("Pastikan koneksi internet aktif dan terminal MT5 sudah login ke broker (status koneksi kanan bawah MT5 tidak 0/0 kb).");
    }

    // 2. Cek saklar Algo Trading di toolbar MT5
    if (!m_expertsTradeAllowed) {
        ok = false;
        issues << QStringLiteral("Tombol 'Algo Trading' di toolbar MT5 NONAKTIF (experts_trade_allowed=false).");
        solutions << QStringLiteral("Klik tombol 'Algo Trading' di toolbar atas MT5 sampai berwarna HIJAU (atau tekan shortcut Ctrl+E).");
    }

    // 3. Cek server MCP
    if (!m_mcpTradeAllowed) {
        ok = false;
        issues << QStringLiteral("Server MCP MT5 belum mengizinkan eksekusi trading (mcp_trade_allowed=false).");
        solutions << QStringLiteral("Buka MT5 -> Tools -> Options -> tab MCP -> pastikan 'Enable internal server' aktif.");
    }

    // 4. Cek hak trading akun (Master vs Investor / Read-Only)
    if (!m_accountTradeAllowed) {
        ok = false;
        issues << QStringLiteral("Akun berstatus Read-Only / Investor Password (trade_allowed=false).");
        solutions << QStringLiteral("Buka MT5 -> File -> Login to Trade Account -> Masukkan Master Trading Password (bukan investor password) & centang 'Save password'.");
    }

    // 5. Cek riwayat penolakan terakhir (jika ada order yang ditolak terminal)
    if (m_tradeBlocked) {
        ok = false;
        issues << QStringLiteral("Order sebelumnya ditolak terminal: %1").arg(m_tradeRejectReason);
        solutions << QStringLiteral("Periksa tab Journal di MT5 untuk kode error lengkap broker. Jika sudah diperbaiki di MT5, klik 'Reset Status Tolak'.");
    }

    res["ok"] = ok;
    res["connected"] = true;
    res["server_connected"] = m_serverConnected;
    res["experts_trade_allowed"] = m_expertsTradeAllowed;
    res["mcp_trade_allowed"] = m_mcpTradeAllowed;
    res["account_trade_allowed"] = m_accountTradeAllowed && !m_tradeBlocked;
    res["login"] = m_accountLogin;
    res["server"] = m_accountServer;
    res["account_type"] = m_accountType;
    res["symbol"] = sym;
    res["symbol_valid"] = true;
    res["trade_blocked"] = m_tradeBlocked;
    res["reject_reason"] = m_tradeRejectReason;

    if (ok) {
        res["status"] = QStringLiteral("OK");
        res["summary"] = QStringLiteral("Semua izin aktif! Terminal MT5 siap menerima eksekusi order.");
    } else if (m_tradeBlocked || !m_accountTradeAllowed) {
        res["status"] = QStringLiteral("ERROR");
        res["summary"] = QStringLiteral("Trading DITOLAK oleh terminal MT5 ('trading is not permitted').");
    } else {
        res["status"] = QStringLiteral("WARNING");
        res["summary"] = QStringLiteral("Izin trading belum lengkap. Periksa panduan di bawah.");
    }

    res["issues"] = issues;
    res["solutions"] = solutions;

    return res;
}

void BotController::clearTradeRejection()
{
    m_tradeBlocked = false;
    m_tradeRejectReason.clear();
    m_tradeAllowed = m_serverConnected && m_expertsTradeAllowed && m_mcpTradeAllowed && m_accountTradeAllowed;
    if (m_pyWorker)
        m_pyWorker->wakeWorker();
    emit tradeBlockedChanged();
    emit accountChanged();
    emit logMessage(QStringLiteral("[SISTEM] Status penolakan trading direset."));
}
