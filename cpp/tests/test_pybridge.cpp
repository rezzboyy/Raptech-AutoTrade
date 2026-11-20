#include <QSignalSpy>
#include <QTest>
#include <QThread>

#include "app/PyBridgeWorker.h"
#include "core/Logger.h"

class TestPyBridge : public QObject
{
    Q_OBJECT
private slots:
    void initTestCase()
    {
        Logger::init();
    }

    void testStartAndPing()
    {
        PyBridgeWorker worker;
        QVERIFY(worker.startBridge());
        QVERIFY(worker.isRunning());

        QSignalSpy logSpy(&worker, &PyBridgeWorker::logMessage);
        worker.wakeWorker();

        // Tunggu respons dari backend Python
        QTest::qWait(1000);
        QVERIFY(worker.isRunning());

        worker.stopBridge();
        QVERIFY(!worker.isRunning());
    }

    void testManualCommandQueueing()
    {
        PyBridgeWorker worker;
        QVERIFY(worker.startBridge());

        ManualCommand cmd;
        cmd.action = QStringLiteral("market");
        cmd.symbol = QStringLiteral("EURUSDm");
        cmd.side = QStringLiteral("buy");
        cmd.volume = 0.01;
        cmd.sl = 1.05000;
        cmd.tp = 1.07000;

        // Kirim perintah manual ke Python worker
        worker.enqueue(cmd);
        QTest::qWait(500);

        worker.stopBridge();
        QVERIFY(!worker.isRunning());
    }
};

QTEST_MAIN(TestPyBridge)
#include "test_pybridge.moc"
