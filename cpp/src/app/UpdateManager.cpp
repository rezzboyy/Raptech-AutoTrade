#include "UpdateManager.h"
#include "core/Version.h"
#include "core/Logger.h"

#include <QCoreApplication>
#include <QDir>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QNetworkRequest>
#include <QProcess>
#include <QStandardPaths>
#include <QTimer>

UpdateManager::UpdateManager(QObject *parent)
    : QObject(parent)
    , m_nam(new QNetworkAccessManager(this))
{
    // Auto-check for updates 2.5 detik setelah GUI terbuka di background
    QTimer::singleShot(2500, this, [this]() {
        checkForUpdates(false);
    });
}

UpdateManager::~UpdateManager()
{
    cancelDownload();
}

QString UpdateManager::currentVersion() const
{
    return Xaviq::APP_VERSION;
}

QList<int> UpdateManager::parseSemver(const QString &vStr)
{
    QString clean = vStr.trimmed();
    while (clean.startsWith('v') || clean.startsWith('V')) {
        clean.remove(0, 1);
    }

    QList<int> result;
    const QStringList parts = clean.split('.');
    for (const QString &part : parts) {
        QString digits;
        for (QChar ch : part) {
            if (ch.isDigit()) digits.append(ch);
        }
        result.append(digits.isEmpty() ? 0 : digits.toInt());
    }
    return result;
}

bool UpdateManager::isNewerVersion(const QString &remote, const QString &current)
{
    QList<int> rParts = parseSemver(remote);
    QList<int> cParts = parseSemver(current);

    int maxLen = std::max(rParts.size(), cParts.size());
    while (rParts.size() < maxLen) rParts.append(0);
    while (cParts.size() < maxLen) cParts.append(0);

    for (int i = 0; i < maxLen; ++i) {
        if (rParts[i] > cParts[i]) return true;
        if (rParts[i] < cParts[i]) return false;
    }
    return false;
}

void UpdateManager::setChecking(bool val)
{
    if (m_checking != val) {
        m_checking = val;
        emit checkingChanged();
    }
}

void UpdateManager::setDownloading(bool val)
{
    if (m_downloading != val) {
        m_downloading = val;
        emit downloadingChanged();
    }
}

void UpdateManager::setDownloadProgress(int val)
{
    if (m_downloadProgress != val) {
        m_downloadProgress = val;
        emit downloadProgressChanged();
    }
}

void UpdateManager::setStatusMessage(const QString &msg)
{
    if (m_statusMessage != msg) {
        m_statusMessage = msg;
        emit statusMessageChanged();
    }
}

void UpdateManager::checkForUpdates(bool manual)
{
    if (m_checking || m_downloading) return;

    m_manualCheck = manual;
    setChecking(true);
    setStatusMessage(QStringLiteral("Memeriksa pembaruan di GitHub..."));

    QString apiUrl = QStringLiteral("https://api.github.com/repos/%1/releases/latest")
                         .arg(Xaviq::GITHUB_REPO_FULL);

    QNetworkRequest request(apiUrl);
    request.setHeader(QNetworkRequest::UserAgentHeader, QStringLiteral("Raptech-AutoTrade-OTA-Engine"));
    request.setRawHeader("Accept", "application/vnd.github.v3+json");

    if (m_checkReply) {
        m_checkReply->abort();
        m_checkReply->deleteLater();
    }

    m_checkReply = m_nam->get(request);
    connect(m_checkReply, &QNetworkReply::finished, this, &UpdateManager::onCheckFinished);
}

void UpdateManager::onCheckFinished()
{
    if (!m_checkReply) {
        setChecking(false);
        return;
    }

    setChecking(false);

    if (m_checkReply->error() != QNetworkReply::NoError) {
        QString err = m_checkReply->errorString();
        qInfo("OTA Update check: %s (kode %d)", err.toUtf8().constData(), (int)m_checkReply->error());
        setStatusMessage(QStringLiteral("Tidak dapat memeriksa pembaruan: %1").arg(err));
        if (m_manualCheck) {
            emit updateError(err);
        }
        m_checkReply->deleteLater();
        m_checkReply = nullptr;
        return;
    }

    QByteArray data = m_checkReply->readAll();
    m_checkReply->deleteLater();
    m_checkReply = nullptr;

    QJsonParseError parseErr;
    QJsonDocument doc = QJsonDocument::fromJson(data, &parseErr);
    if (!doc.isObject()) {
        setStatusMessage(QStringLiteral("Format respons rilis tidak valid"));
        if (m_manualCheck) emit updateError(QStringLiteral("Format respons rilis tidak valid"));
        return;
    }

    QJsonObject root = doc.object();
    QString tagName = root.value(QStringLiteral("tag_name")).toString().trimmed();
    QString cleanVer = tagName;
    while (cleanVer.startsWith('v') || cleanVer.startsWith('V')) {
        cleanVer.remove(0, 1);
    }

    if (tagName.isEmpty()) {
        setStatusMessage(QStringLiteral("Belum ada rilis yang dipublikasikan"));
        if (m_manualCheck) emit updateNotFound(true);
        return;
    }

    if (!isNewerVersion(tagName, currentVersion())) {
        m_updateAvailable = false;
        emit updateAvailableChanged();
        setStatusMessage(QStringLiteral("Versi Anda sudah yang terbaru (v%1)").arg(currentVersion()));
        if (m_manualCheck) emit updateNotFound(true);
        return;
    }

    // Ada versi baru
    m_latestVersion = cleanVer;
    m_releaseTitle = root.value(QStringLiteral("name")).toString();
    if (m_releaseTitle.isEmpty()) {
        m_releaseTitle = QStringLiteral("Raptech AutoTrade v%1").arg(m_latestVersion);
    }
    m_releaseNotes = root.value(QStringLiteral("body")).toString();

    // Cari aset biner: prioritaskan .zip paket lengkap, atau .exe standalone
    m_downloadUrl.clear();
    m_fileSizeBytes = 0;
    m_fileSizeMb = 0.0;

    QJsonArray assets = root.value(QStringLiteral("assets")).toArray();
    for (const QJsonValue &val : assets) {
        QJsonObject assetObj = val.toObject();
        QString name = assetObj.value(QStringLiteral("name")).toString().toLower();
        if (name.endsWith(QStringLiteral(".zip"))) {
            m_downloadUrl = assetObj.value(QStringLiteral("browser_download_url")).toString();
            m_fileSizeBytes = (qint64)assetObj.value(QStringLiteral("size")).toDouble();
            break; // Prioritaskan paket rilis ZIP
        }
    }

    if (m_downloadUrl.isEmpty()) {
        for (const QJsonValue &val : assets) {
            QJsonObject assetObj = val.toObject();
            QString name = assetObj.value(QStringLiteral("name")).toString().toLower();
            if (name.endsWith(QStringLiteral(".exe"))) {
                m_downloadUrl = assetObj.value(QStringLiteral("browser_download_url")).toString();
                m_fileSizeBytes = (qint64)assetObj.value(QStringLiteral("size")).toDouble();
                break;
            }
        }
    }

    if (m_fileSizeBytes > 0) {
        m_fileSizeMb = std::round((m_fileSizeBytes / (1024.0 * 1024.0)) * 10.0) / 10.0;
    }

    m_updateAvailable = true;
    emit updateAvailableChanged();
    setStatusMessage(QStringLiteral("Versi baru v%1 tersedia!").arg(m_latestVersion));
    emit updateFound(m_latestVersion, m_releaseNotes);
}

void UpdateManager::downloadAndInstallUpdate()
{
    if (m_downloading || m_downloadUrl.isEmpty()) return;

    setDownloading(true);
    setDownloadProgress(0);
    setStatusMessage(QStringLiteral("Menghubungkan server unduhan..."));

    // Siapkan direktori temporary di AppData / Temp
    QString tempDir = QStandardPaths::writableLocation(QStandardPaths::TempLocation) + QStringLiteral("/XaviqUpdate");
    QDir().mkpath(tempDir);

    QUrl url(m_downloadUrl);
    QString fileName = url.fileName();
    if (fileName.isEmpty()) {
        fileName = QStringLiteral("update_pack.zip");
    }

    m_tempFilePath = tempDir + QStringLiteral("/") + fileName;

    if (m_tempFile) {
        m_tempFile->close();
        delete m_tempFile;
        m_tempFile = nullptr;
    }

    m_tempFile = new QFile(m_tempFilePath, this);
    if (!m_tempFile->open(QIODevice::WriteOnly)) {
        setDownloading(false);
        setStatusMessage(QStringLiteral("Gagal membuat file sementara untuk pembaruan"));
        emit updateError(QStringLiteral("Gagal membuka file download sementara"));
        delete m_tempFile;
        m_tempFile = nullptr;
        return;
    }

    QNetworkRequest request(url);
    request.setHeader(QNetworkRequest::UserAgentHeader, QStringLiteral("Raptech-AutoTrade-OTA-Engine"));
    request.setAttribute(QNetworkRequest::RedirectPolicyAttribute, QNetworkRequest::NoLessSafeRedirectPolicy);

    m_downloadReply = m_nam->get(request);
    connect(m_downloadReply, &QNetworkReply::readyRead, this, &UpdateManager::onDownloadDataRead);
    connect(m_downloadReply, &QNetworkReply::downloadProgress, this, &UpdateManager::onDownloadProgress);
    connect(m_downloadReply, &QNetworkReply::finished, this, &UpdateManager::onDownloadFinished);
}

void UpdateManager::onDownloadDataRead()
{
    if (m_downloadReply && m_tempFile && m_tempFile->isOpen()) {
        m_tempFile->write(m_downloadReply->readAll());
    }
}

void UpdateManager::onDownloadProgress(qint64 bytesReceived, qint64 bytesTotal)
{
    if (bytesTotal > 0) {
        int percent = (int)((bytesReceived * 100) / bytesTotal);
        setDownloadProgress(percent);
        double mbDone = std::round((bytesReceived / (1024.0 * 1024.0)) * 10.0) / 10.0;
        double mbTotal = std::round((bytesTotal / (1024.0 * 1024.0)) * 10.0) / 10.0;
        setStatusMessage(QStringLiteral("Mengunduh: %1 MB / %2 MB (%3%)")
                             .arg(mbDone)
                             .arg(mbTotal)
                             .arg(percent));
    }
}

void UpdateManager::onDownloadFinished()
{
    if (!m_downloadReply) {
        setDownloading(false);
        return;
    }

    if (m_downloadReply->error() != QNetworkReply::NoError) {
        QString err = m_downloadReply->errorString();
        setStatusMessage(QStringLiteral("Unduhan gagal: %1").arg(err));
        emit updateError(err);
        cancelDownload();
        return;
    }

    // Tulis sisa buffer
    if (m_tempFile && m_tempFile->isOpen()) {
        m_tempFile->write(m_downloadReply->readAll());
        m_tempFile->flush();
        m_tempFile->close();
    }

    m_downloadReply->deleteLater();
    m_downloadReply = nullptr;

    setDownloading(false);
    setDownloadProgress(100);
    setStatusMessage(QStringLiteral("Unduhan selesai! Memulai proses pembaruan..."));
    emit downloadCompleted();

    // Jalankan updater
    applyUpdateWindows(m_tempFilePath);
}

void UpdateManager::cancelDownload()
{
    if (m_downloadReply) {
        m_downloadReply->abort();
        m_downloadReply->deleteLater();
        m_downloadReply = nullptr;
    }
    if (m_tempFile) {
        m_tempFile->close();
        m_tempFile->remove();
        delete m_tempFile;
        m_tempFile = nullptr;
    }
    setDownloading(false);
    setDownloadProgress(0);
}

void UpdateManager::applyUpdateWindows(const QString &downloadedFilePath)
{
    QString currentExePath = QCoreApplication::applicationFilePath();
    QFileInfo exeInfo(currentExePath);
    QString appDir = exeInfo.absolutePath();
    QString exeName = exeInfo.fileName();

    QString batchPath = appDir + QStringLiteral("/_finish_update.bat");
    QFile batchFile(batchPath);

    if (!batchFile.open(QIODevice::WriteOnly | QIODevice::Text)) {
        setStatusMessage(QStringLiteral("Gagal menyiapkan skrip instalasi update"));
        emit updateError(QStringLiteral("Akses izin ditolak saat menyiapkan instalasi"));
        return;
    }

    bool isZip = downloadedFilePath.endsWith(QStringLiteral(".zip"), Qt::CaseInsensitive);

    QString scriptContent;
    if (isZip) {
        // Ekstrak arsip ZIP menggunakan tar (bawaan Windows 10/11 / Windows Server)
        scriptContent = QStringLiteral(
            "@echo off\r\n"
            "chcp 65001 >nul\r\n"
            "echo Menunggu aplikasi tertutup...\r\n"
            "timeout /t 2 /nobreak >nul\r\n"
            ":retry\r\n"
            "tar -xf \"%1\" -C \"%2\" >nul 2>&1\r\n"
            "if errorlevel 1 (\r\n"
            "    timeout /t 1 /nobreak >nul\r\n"
            "    goto retry\r\n"
            ")\r\n"
            "echo Memperbarui file berhasil!\r\n"
            "start \"\" \"%3\"\r\n"
            "del \"%1\" >nul 2>&1\r\n"
            "del \"%%~f0\"\r\n"
            "exit\r\n"
        ).arg(QDir::toNativeSeparators(downloadedFilePath),
             QDir::toNativeSeparators(appDir),
             QDir::toNativeSeparators(currentExePath));
    } else {
        // Timpa file EXE langsung
        scriptContent = QStringLiteral(
            "@echo off\r\n"
            "chcp 65001 >nul\r\n"
            "echo Menunggu aplikasi tertutup...\r\n"
            "timeout /t 2 /nobreak >nul\r\n"
            ":retry\r\n"
            "move /y \"%1\" \"%2\" >nul 2>&1\r\n"
            "if errorlevel 1 (\r\n"
            "    timeout /t 1 /nobreak >nul\r\n"
            "    goto retry\r\n"
            ")\r\n"
            "echo Memperbarui file berhasil!\r\n"
            "start \"\" \"%2\"\r\n"
            "del \"%%~f0\"\r\n"
            "exit\r\n"
        ).arg(QDir::toNativeSeparators(downloadedFilePath),
             QDir::toNativeSeparators(currentExePath));
    }

    batchFile.write(scriptContent.toUtf8());
    batchFile.close();

    qInfo("Memulai transisi pembaruan in-place via %s", batchPath.toUtf8().constData());

    // Jalankan batch script detached dan keluar dari aplikasi
    QProcess::startDetached(QStringLiteral("cmd.exe"), QStringList() << QStringLiteral("/c") << batchPath);
    QCoreApplication::quit();
}
