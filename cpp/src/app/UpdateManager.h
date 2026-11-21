#pragma once

#include <QObject>
#include <QString>
#include <QUrl>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QFile>

class UpdateManager : public QObject
{
    Q_OBJECT
    Q_PROPERTY(bool checking READ checking NOTIFY checkingChanged)
    Q_PROPERTY(bool updateAvailable READ updateAvailable NOTIFY updateAvailableChanged)
    Q_PROPERTY(bool isInstalledMode READ isInstalledMode CONSTANT)
    Q_PROPERTY(QString currentVersion READ currentVersion CONSTANT)
    Q_PROPERTY(QString latestVersion READ latestVersion NOTIFY updateAvailableChanged)
    Q_PROPERTY(QString releaseTitle READ releaseTitle NOTIFY updateAvailableChanged)
    Q_PROPERTY(QString releaseNotes READ releaseNotes NOTIFY updateAvailableChanged)
    Q_PROPERTY(QString downloadUrl READ downloadUrl NOTIFY updateAvailableChanged)
    Q_PROPERTY(double fileSizeMb READ fileSizeMb NOTIFY updateAvailableChanged)
    Q_PROPERTY(bool downloading READ downloading NOTIFY downloadingChanged)
    Q_PROPERTY(int downloadProgress READ downloadProgress NOTIFY downloadProgressChanged)
    Q_PROPERTY(QString statusMessage READ statusMessage NOTIFY statusMessageChanged)

public:
    explicit UpdateManager(QObject *parent = nullptr);
    ~UpdateManager() override;

    bool checking() const { return m_checking; }
    bool updateAvailable() const { return m_updateAvailable; }
    bool isInstalledMode() const;
    QString currentVersion() const;
    QString latestVersion() const { return m_latestVersion; }
    QString releaseTitle() const { return m_releaseTitle; }
    QString releaseNotes() const { return m_releaseNotes; }
    QString downloadUrl() const { return m_downloadUrl; }
    double fileSizeMb() const { return m_fileSizeMb; }
    bool downloading() const { return m_downloading; }
    int downloadProgress() const { return m_downloadProgress; }
    QString statusMessage() const { return m_statusMessage; }

    static bool isNewerVersion(const QString &remote, const QString &current);
    static QList<int> parseSemver(const QString &vStr);

public slots:
    void checkForUpdates(bool manual = false);
    void downloadAndInstallUpdate();
    void cancelDownload();

signals:
    void checkingChanged();
    void updateAvailableChanged();
    void downloadingChanged();
    void downloadProgressChanged();
    void statusMessageChanged();
    void updateFound(const QString &version, const QString &notes);
    void updateNotFound(bool manual);
    void updateError(const QString &message);
    void downloadCompleted();

private slots:
    void onCheckFinished();
    void onDownloadDataRead();
    void onDownloadProgress(qint64 bytesReceived, qint64 bytesTotal);
    void onDownloadFinished();

private:
    void setChecking(bool val);
    void setDownloading(bool val);
    void setDownloadProgress(int val);
    void setStatusMessage(const QString &msg);
    void applyUpdateWindows(const QString &downloadedFilePath);

    QNetworkAccessManager *m_nam{nullptr};
    QNetworkReply *m_checkReply{nullptr};
    QNetworkReply *m_downloadReply{nullptr};
    QFile *m_tempFile{nullptr};
    QString m_tempFilePath;

    bool m_checking{false};
    bool m_updateAvailable{false};
    bool m_manualCheck{false};
    QString m_latestVersion;
    QString m_releaseTitle;
    QString m_releaseNotes;
    QString m_downloadUrl;
    double m_fileSizeMb{0.0};
    qint64 m_fileSizeBytes{0};
    bool m_downloading{false};
    int m_downloadProgress{0};
    QString m_statusMessage;
};
