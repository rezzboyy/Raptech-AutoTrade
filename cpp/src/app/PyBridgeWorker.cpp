#include "PyBridgeWorker.h"

#include <QCoreApplication>
#include <QDir>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QPointer>
#include <QProcessEnvironment>
#include <QStandardPaths>

PyBridgeWorker::PyBridgeWorker(QObject *parent)
    : QObject(parent)
{
}

PyBridgeWorker::~PyBridgeWorker()
{
    stopBridge();
}

bool PyBridgeWorker::isRunning() const
{
    return m_process && m_process->state() != QProcess::NotRunning;
}

QString PyBridgeWorker::findStandaloneBridge() const
{
    const QString appDir = QCoreApplication::applicationDirPath();
    const QString cwd = QDir::currentPath();
    const QString canonApp = QFileInfo(appDir).canonicalFilePath();
    const QString canonCwd = QFileInfo(cwd).canonicalFilePath();

    const QStringList candidates = {
        appDir + QStringLiteral("/py_bridge/py_bridge.exe"),
        appDir + QStringLiteral("/py_bridge.exe"),
        cwd + QStringLiteral("/py_bridge/py_bridge.exe"),
        cwd + QStringLiteral("/py_bridge.exe"),
        appDir + QStringLiteral("/dist/XTradingEngine/py_bridge/py_bridge.exe"),
        cwd + QStringLiteral("/dist/XTradingEngine/py_bridge/py_bridge.exe"),
        appDir + QStringLiteral("/dist/XAVIQTradingEngine/py_bridge/py_bridge.exe"),
        cwd + QStringLiteral("/dist/XAVIQTradingEngine/py_bridge/py_bridge.exe"),
        canonApp + QStringLiteral("/py_bridge/py_bridge.exe"),
        canonCwd + QStringLiteral("/py_bridge/py_bridge.exe")
    };

    for (const QString &cand : candidates) {
        QFileInfo fi(cand);
        if (fi.exists() && fi.isFile() && fi.size() > 1024)
            return QDir::cleanPath(cand);
    }
    return QString();
}

QString PyBridgeWorker::findPythonExecutable() const
{
    const auto isValidExecutable = [](const QString &p) {
        if (p.isEmpty())
            return false;
        if (p.contains(QStringLiteral("WindowsApps"), Qt::CaseInsensitive))
            return false;
        QFileInfo fi(p);
        return fi.exists() && fi.isFile() && fi.size() > 1024;
    };

    // 0. Environment variable override
    const QString envPy = qEnvironmentVariable("XAVIQ_PYTHON");
    if (isValidExecutable(envPy))
        return QDir::cleanPath(envPy);

    // 1. Python portabel di samping direktori aplikasi
    const QString appDir = QCoreApplication::applicationDirPath();
    const QStringList localCandidates = {
        appDir + QStringLiteral("/python/python.exe"),
        appDir + QStringLiteral("/python312/python.exe"),
        appDir + QStringLiteral("/runtime/python.exe")
    };
    for (const QString &cand : localCandidates) {
        if (isValidExecutable(cand))
            return QDir::cleanPath(cand);
    }

    // 2. Cek python di PATH (abaikan stub WindowsApps / Microsoft Store 0-byte shim)
    QString pathPy = QStandardPaths::findExecutable(QStringLiteral("python.exe"));
    if (isValidExecutable(pathPy))
        return pathPy;

    pathPy = QStandardPaths::findExecutable(QStringLiteral("python"));
    if (isValidExecutable(pathPy))
        return pathPy;

    // 3. Cek py.exe launcher
    QString pyLauncher = QStandardPaths::findExecutable(QStringLiteral("py.exe"));
    if (isValidExecutable(pyLauncher))
        return pyLauncher;

    // 4. Cek lokasi instalasi standar pengguna Windows (LOCALAPPDATA & USERPROFILE)
    const QString home = QDir::homePath();
    const QString localAppData = qEnvironmentVariable("LOCALAPPDATA");
    const QStringList pyVersions = {
        QStringLiteral("Python312"),
        QStringLiteral("Python311"),
        QStringLiteral("Python310"),
        QStringLiteral("Python313"),
        QStringLiteral("Python314")
    };

    for (const QString &ver : pyVersions) {
        if (!localAppData.isEmpty()) {
            QString cand = localAppData + QStringLiteral("/Programs/Python/") + ver + QStringLiteral("/python.exe");
            if (isValidExecutable(cand))
                return QDir::cleanPath(cand);
        }
        QString cand = home + QStringLiteral("/AppData/Local/Programs/Python/") + ver + QStringLiteral("/python.exe");
        if (isValidExecutable(cand))
            return QDir::cleanPath(cand);
    }

    // 5. Cek lokasi Program Files & Drive Root
    const QString progFiles = qEnvironmentVariable("ProgramFiles");
    const QString progFilesX86 = qEnvironmentVariable("ProgramFiles(x86)");
    for (const QString &ver : pyVersions) {
        if (!progFiles.isEmpty()) {
            QString cand = progFiles + QStringLiteral("/Python/") + ver + QStringLiteral("/python.exe");
            if (isValidExecutable(cand))
                return QDir::cleanPath(cand);
            cand = progFiles + QStringLiteral("/") + ver + QStringLiteral("/python.exe");
            if (isValidExecutable(cand))
                return QDir::cleanPath(cand);
        }
        if (!progFilesX86.isEmpty()) {
            QString cand = progFilesX86 + QStringLiteral("/Python/") + ver + QStringLiteral("/python.exe");
            if (isValidExecutable(cand))
                return QDir::cleanPath(cand);
        }
        QString rootCand = QStringLiteral("C:/") + ver + QStringLiteral("/python.exe");
        if (isValidExecutable(rootCand))
            return rootCand;
    }

    return QStringLiteral("python");
}

QString PyBridgeWorker::findBridgeScript() const
{
    const QString envBackend = qEnvironmentVariable("XAVIQ_BACKEND_DIR");
    if (!envBackend.isEmpty()) {
        const QString envFile = QDir(envBackend).filePath(QStringLiteral("bridge_server.py"));
        if (QFileInfo::exists(envFile))
            return QDir::cleanPath(envFile);
    }

    const QString appDir = QCoreApplication::applicationDirPath();
    const QString cwd = QDir::currentPath();
    const QString canonApp = QDir(appDir).canonicalPath();
    const QString canonCwd = QDir(cwd).canonicalPath();

    const QStringList candidates = {
        appDir + QStringLiteral("/py_backend/bridge_server.py"),
        cwd + QStringLiteral("/py_backend/bridge_server.py"),
        appDir + QStringLiteral("/../py_backend/bridge_server.py"),
        appDir + QStringLiteral("/../../py_backend/bridge_server.py"),
        appDir + QStringLiteral("/../../../py_backend/bridge_server.py"),
        canonApp + QStringLiteral("/../../py_backend/bridge_server.py"),
        canonApp + QStringLiteral("/../py_backend/bridge_server.py"),
        canonApp + QStringLiteral("/py_backend/bridge_server.py"),
        canonCwd + QStringLiteral("/../../py_backend/bridge_server.py"),
        canonCwd + QStringLiteral("/../py_backend/bridge_server.py"),
        canonCwd + QStringLiteral("/py_backend/bridge_server.py"),
        QStringLiteral("C:/Users/Administrator/Desktop/My Produk/Auto Trade/Bot Trading/py_backend/bridge_server.py"),
        QStringLiteral("C:/Users/Administrator/Desktop/Auto Trade/Bot Trading/py_backend/bridge_server.py"),
        QStringLiteral("C:/Users/Administrator/Desktop/Bot Trading/py_backend/bridge_server.py"),
        QFileInfo(QStringLiteral("C:/XaviqCpp")).symLinkTarget() + QStringLiteral("/../py_backend/bridge_server.py"),
        cwd + QStringLiteral("/bridge_server.py")
    };

    for (const QString &cand : candidates) {
        if (QFileInfo::exists(cand))
            return QDir::cleanPath(cand);
    }

    return QStringLiteral("py_backend/bridge_server.py");
}

bool PyBridgeWorker::startBridge()
{
    if (isRunning())
        return true;

    const QString standaloneBridge = findStandaloneBridge();
    QString pythonPath;
    QString scriptPath;

    if (standaloneBridge.isEmpty()) {
        pythonPath = findPythonExecutable();
        scriptPath = findBridgeScript();

        if (pythonPath.isEmpty() || !QFileInfo::exists(scriptPath)) {
            emit logMessage(QStringLiteral("[ERROR] Backend Trading Engine tidak ditemukan. "
                                           "Silakan pastikan direktori 'py_bridge' ada di folder aplikasi "
                                           "atau pasang Python 3.12 via Install_Prerequisites.bat."));
            return false;
        }
    }

    m_process = new QProcess(this);

    QProcessEnvironment env = QProcessEnvironment::systemEnvironment();
    env.insert(QStringLiteral("PYTHONUNBUFFERED"), QStringLiteral("1"));
    env.insert(QStringLiteral("PYTHONIOENCODING"), QStringLiteral("utf-8"));

    QString workingDir;
    if (!standaloneBridge.isEmpty()) {
        workingDir = QFileInfo(standaloneBridge).absolutePath();
        const QString appDir = QCoreApplication::applicationDirPath();
        env.insert(QStringLiteral("XAVIQ_SCRIPTS_DIR"), appDir + QStringLiteral("/scripts"));
    } else {
        const QString scriptDir = QFileInfo(scriptPath).absolutePath();
        const QString sysPyPath = env.value(QStringLiteral("PYTHONPATH"));
        if (sysPyPath.isEmpty()) {
            env.insert(QStringLiteral("PYTHONPATH"), scriptDir);
        } else {
            env.insert(QStringLiteral("PYTHONPATH"), scriptDir + QDir::listSeparator() + sysPyPath);
        }
        workingDir = scriptDir;
    }

    m_process->setProcessEnvironment(env);
    m_process->setWorkingDirectory(workingDir);

    connect(m_process, &QProcess::readyReadStandardOutput, this, &PyBridgeWorker::onReadyReadStdout);
    connect(m_process, &QProcess::readyReadStandardError, this, &PyBridgeWorker::onReadyReadStderr);
    connect(m_process, QOverload<int, QProcess::ExitStatus>::of(&QProcess::finished),
            this, &PyBridgeWorker::onProcessFinished);
    connect(m_process, &QProcess::errorOccurred, this, &PyBridgeWorker::onProcessError);

    m_readBuffer.clear();

    if (!standaloneBridge.isEmpty()) {
        m_process->start(standaloneBridge, QStringList());
    } else {
        m_process->start(pythonPath, QStringList() << scriptPath);
    }

    if (!m_process->waitForStarted(5000)) {
        emit logMessage(QStringLiteral("[ERROR] Gagal meluncurkan engine trading: %1").arg(m_process->errorString()));
        m_process->deleteLater();
        m_process = nullptr;
        return false;
    }

    emit logMessage(QStringLiteral("[SISTEM] Backend Python Trading Engine berhasil diluncurkan%1.")
                        .arg(!standaloneBridge.isEmpty() ? QStringLiteral(" (Standalone Embedded)") : QStringLiteral("")));
    return true;
}

void PyBridgeWorker::stopBridge()
{
    if (!m_process || m_stopping)
        return;
    m_stopping = true;

    QProcess *proc = m_process;
    m_process = nullptr;
    // Putus semua sinyal QProcess lebih dulu agar waitForFinished() tidak memicu
    // onReadyReadStdout / onProcessFinished secara re-entrant (penyebab crash logout).
    proc->disconnect(this);

    if (proc->state() != QProcess::NotRunning) {
        QJsonObject exitObj;
        exitObj[QStringLiteral("id")] = static_cast<qint64>(m_nextId++);
        exitObj[QStringLiteral("method")] = QStringLiteral("exit");
        const QByteArray exitBytes = QJsonDocument(exitObj).toJson(QJsonDocument::Compact) + '\n';
        proc->write(exitBytes);
        proc->waitForBytesWritten(20);
        if (!proc->waitForFinished(1200)) {
            proc->terminate();
            if (!proc->waitForFinished(800)) {
                proc->kill();
            }
        }
    }

    proc->deleteLater();
    m_connected = false;
    m_trading = false;
    m_stopping = false;
}

void PyBridgeWorker::sendCommand(const QString &method, const QVariantMap &params)
{
    if (!m_process || m_process->state() == QProcess::NotRunning)
        return;

    QJsonObject obj;
    obj[QStringLiteral("id")] = static_cast<qint64>(m_nextId++);
    obj[QStringLiteral("method")] = method;
    if (!params.isEmpty())
        obj[QStringLiteral("params")] = QJsonObject::fromVariantMap(params);

    const QByteArray data = QJsonDocument(obj).toJson(QJsonDocument::Compact) + '\n';
    m_process->write(data);
    m_process->waitForBytesWritten(5);
}

void PyBridgeWorker::connectBackend(const QVariantMap &params)
{
    if (!isRunning()) {
        if (!startBridge()) {
            emit connectedChanged(false);
            emit stopped();
            return;
        }
    }
    sendCommand(QStringLiteral("connect"), params);
}

void PyBridgeWorker::disconnectBackend()
{
    if (isRunning()) {
        sendCommand(QStringLiteral("disconnect"));
    }
}

void PyBridgeWorker::setTrading(bool enabled)
{
    m_trading = enabled;
    QVariantMap p;
    p[QStringLiteral("enabled")] = enabled;
    sendCommand(QStringLiteral("set_trading"), p);
}

void PyBridgeWorker::reloadStrategy()
{
    sendCommand(QStringLiteral("reload_strategy"));
}

void PyBridgeWorker::setChartSymbol(const QString &symbol)
{
    m_chartSymbol = symbol;
    QVariantMap p;
    p[QStringLiteral("symbol")] = symbol;
    sendCommand(QStringLiteral("set_chart_symbol"), p);
}

void PyBridgeWorker::setTimeframe(const QString &tf)
{
    QVariantMap p;
    p[QStringLiteral("timeframe")] = tf.trimmed().toUpper();
    sendCommand(QStringLiteral("set_timeframe"), p);
}

void PyBridgeWorker::runScriptSimulation(const QVariantMap &params)
{
    if (!isRunning()) {
        if (!startBridge()) {
            QVariantMap err;
            err[QStringLiteral("ok")] = false;
            err[QStringLiteral("error")] = QStringLiteral("Gagal menjalankan engine Python simulasi.");
            emit simulationResult(err);
            return;
        }
    }
    sendCommand(QStringLiteral("run_script_simulation"), params);
}

void PyBridgeWorker::requestStop()
{
    disconnectBackend();
}

void PyBridgeWorker::enqueue(const ManualCommand &cmd)
{
    if (cmd.action == QLatin1String("market")) {
        QVariantMap p;
        p[QStringLiteral("symbol")] = cmd.symbol;
        p[QStringLiteral("side")] = cmd.side;
        p[QStringLiteral("volume")] = cmd.volume;
        p[QStringLiteral("sl")] = cmd.sl;
        p[QStringLiteral("tp")] = cmd.tp;
        sendCommand(QStringLiteral("manual_order"), p);
    } else if (cmd.action == QLatin1String("pending")) {
        QVariantMap p;
        p[QStringLiteral("symbol")] = cmd.symbol;
        p[QStringLiteral("order_type")] = cmd.orderType;
        p[QStringLiteral("volume")] = cmd.volume;
        p[QStringLiteral("price")] = cmd.price;
        p[QStringLiteral("sl")] = cmd.sl;
        p[QStringLiteral("tp")] = cmd.tp;
        sendCommand(QStringLiteral("pending_order"), p);
    } else if (cmd.action == QLatin1String("close_all")) {
        QVariantMap p;
        p[QStringLiteral("symbol")] = cmd.symbol;
        sendCommand(QStringLiteral("close_all"), p);
    } else if (cmd.action == QLatin1String("delete_order")) {
        QVariantMap p;
        p[QStringLiteral("ticket")] = static_cast<qint64>(cmd.ticket);
        sendCommand(QStringLiteral("delete_order"), p);
    } else if (cmd.action == QLatin1String("reset_stats")) {
        sendCommand(QStringLiteral("reset_stats"), QVariantMap());
    }
}

void PyBridgeWorker::enqueueClose(long long ticket)
{
    QVariantMap p;
    p[QStringLiteral("ticket")] = static_cast<qint64>(ticket);
    sendCommand(QStringLiteral("close_position"), p);
}

void PyBridgeWorker::wakeWorker()
{
    sendCommand(QStringLiteral("ping"));
}

void PyBridgeWorker::onReadyReadStdout()
{
    if (!m_process || m_stopping)
        return;

    QPointer<PyBridgeWorker> self(this);
    m_readBuffer.append(m_process->readAllStandardOutput());

    while (self && m_process && !m_stopping) {
        int idx = m_readBuffer.indexOf('\n');
        if (idx < 0)
            break;

        QByteArray line = m_readBuffer.left(idx).trimmed();
        m_readBuffer.remove(0, idx + 1);

        if (line.isEmpty())
            continue;

        QJsonParseError err;
        QJsonDocument doc = QJsonDocument::fromJson(line, &err);
        if (err.error != QJsonParseError::NoError || !doc.isObject())
            continue;

        QJsonObject root = doc.object();
        if (root.contains(QStringLiteral("event"))) {
            handleEvent(root.value(QStringLiteral("event")).toString(),
                        root.value(QStringLiteral("data")).toVariant());
        } else if (root.contains(QStringLiteral("id"))) {
            const long long id = root.value(QStringLiteral("id")).toVariant().toLongLong();
            const QVariant res = root.value(QStringLiteral("result")).toVariant();
            const QString errMsg = root.value(QStringLiteral("error")).toString();
            handleResponse(id, res, errMsg);
        }
    }
}

void PyBridgeWorker::onReadyReadStderr()
{
    if (!m_process)
        return;

    const QByteArray errData = m_process->readAllStandardError();
    const QString text = QString::fromUtf8(errData).trimmed();
    if (!text.isEmpty()) {
        const QStringList lines = text.split('\n', Qt::SkipEmptyParts);
        for (const QString &ln : lines) {
            const QString trimmed = ln.trimmed();
            if (trimmed.isEmpty() ||
                trimmed.contains(QLatin1String("QFontDatabase")) ||
                trimmed.contains(QLatin1String("QWindowsWindow"))) {
                continue;
            }
            if (trimmed.contains(QLatin1String("Traceback")) ||
                trimmed.contains(QLatin1String("Error")) ||
                trimmed.contains(QLatin1String("Exception")) ||
                trimmed.contains(QLatin1String("CRITICAL"))) {
                emit logMessage(QStringLiteral("[ERROR] %1").arg(trimmed));
            }
        }
    }
}

void PyBridgeWorker::onProcessFinished(int exitCode, QProcess::ExitStatus exitStatus)
{
    Q_UNUSED(exitCode);
    Q_UNUSED(exitStatus);
    if (m_stopping)
        return;
    if (m_process) {
        m_process->deleteLater();
        m_process = nullptr;
    }
    m_connected = false;
    m_trading = false;
    emit connectedChanged(false);
    emit stopped();
}

void PyBridgeWorker::onProcessError(QProcess::ProcessError error)
{
    emit logMessage(QStringLiteral("[ERROR] Kesalahan proses backend Python: %1").arg(static_cast<int>(error)));
}

void PyBridgeWorker::handleEvent(const QString &event, const QVariant &data)
{
    if (event == QLatin1String("ready")) {
        emit logMessage(QStringLiteral("[SISTEM] Engine trading siap beroperasi."));
    } else if (event == QLatin1String("connectedChanged")) {
        const bool conn = data.toMap().value(QStringLiteral("connected")).toBool();
        m_connected = conn;
        emit connectedChanged(conn);
    } else if (event == QLatin1String("accountUpdated")) {
        emit accountUpdated(data.toMap());
    } else if (event == QLatin1String("positionsUpdated")) {
        emit positionsUpdated(data.toList());
    } else if (event == QLatin1String("ordersUpdated")) {
        emit ordersUpdated(data.toList());
    } else if (event == QLatin1String("journalUpdated")) {
        emit journalUpdated(data.toMap());
    } else if (event == QLatin1String("candlesUpdated")) {
        const QVariantMap m = data.toMap();
        emit candlesUpdated(m.value(QStringLiteral("symbol")).toString(), m.value(QStringLiteral("payload")));
    } else if (event == QLatin1String("symbolsListed")) {
        emit symbolsListed(data.toStringList());
    } else if (event == QLatin1String("statsUpdated")) {
        emit statsUpdated(data.toMap());
    } else if (event == QLatin1String("equityUpdated")) {
        emit equityUpdated(data.toList());
    } else if (event == QLatin1String("autoTradingDisabled")) {
        m_trading = false;
        emit autoTradingDisabled(data.toMap().value(QStringLiteral("reason")).toString());
    } else if (event == QLatin1String("orderFeedback")) {
        const QVariantMap m = data.toMap();
        emit orderFeedback(m.value(QStringLiteral("ok")).toBool(), m.value(QStringLiteral("message")).toString());
    } else if (event == QLatin1String("chartSymbolChanged")) {
        m_chartSymbol = data.toMap().value(QStringLiteral("symbol")).toString();
        emit chartSymbolChanged(m_chartSymbol);
    } else if (event == QLatin1String("timeframeChanged")) {
        emit timeframeChanged(data.toMap().value(QStringLiteral("timeframe")).toString());
    } else if (event == QLatin1String("simulationResult")) {
        emit simulationResult(data.toMap());
    } else if (event == QLatin1String("logMessage")) {
        emit logMessage(data.toMap().value(QStringLiteral("message")).toString());
    } else if (event == QLatin1String("stopped")) {
        m_connected = false;
        m_trading = false;
        emit stopped();
    }
}

void PyBridgeWorker::handleResponse(long long id, const QVariant &result, const QString &error)
{
    Q_UNUSED(id);
    if (!error.isEmpty()) {
        emit logMessage(QStringLiteral("[ERROR] %1").arg(error));
    }
    Q_UNUSED(result);
}
