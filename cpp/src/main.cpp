// XAVIQ Trading Engine (C++/Qt6) — entry point.

#include <QGuiApplication>
#include <QQmlApplicationEngine>
#include <QQmlContext>
#include <qqml.h>
#include <QQuickStyle>
#include <QQuickWindow>
#include <QTimer>
#include <QImage>
#include <QUrl>

#include "app/BotController.h"
#include "core/Logger.h"
#include "ui/JsHighlighter.h"

int main(int argc, char *argv[])
{
    // Mode grab (screenshot) butuh backend software agar bisa render offscreen
    // tanpa GPU. Deteksi argumen sebelum membuat aplikasi.
    bool grabMode = false;
    for (int i = 1; i < argc; ++i)
        if (qstrcmp(argv[i], "--grab") == 0) grabMode = true;
    if (grabMode) qputenv("QT_QUICK_BACKEND", "software");

    QGuiApplication app(argc, argv);
    app.setApplicationName("XAVIQ Trading Engine");
    app.setOrganizationName("XAVIQ");

    Logger::init();
    QQuickStyle::setStyle("Material");

    // Tipe QML kustom: highlighter JS untuk editor Mode Programmer.
    qmlRegisterType<JsHighlighter>("Xaviq", 1, 0, "JsHighlighter");

    BotController controller;

    // Parsing argumen: --grab <png>, --qml <file> (opsional untuk demo).
    const QStringList args = app.arguments();
    QString grabPath, altQml;
    int gi = args.indexOf(QStringLiteral("--grab"));
    if (gi >= 0 && gi + 1 < args.size()) grabPath = args.at(gi + 1);
    int qi = args.indexOf(QStringLiteral("--qml"));
    if (qi >= 0 && qi + 1 < args.size()) altQml = args.at(qi + 1);

    QQmlApplicationEngine engine;
    engine.rootContext()->setContextProperty("bot", &controller);
    const QUrl url = altQml.isEmpty()
        ? QUrl(QStringLiteral("qrc:/qml/main.qml"))
        : QUrl::fromLocalFile(altQml);
    engine.load(url);
    if (engine.rootObjects().isEmpty())
        return -1;

    // Mode grab: render window ke PNG lalu keluar. Untuk audit visual.
    if (!grabPath.isEmpty()) {
        auto *win = qobject_cast<QQuickWindow *>(engine.rootObjects().first());
        if (!win) return 2;
        win->show();
        QTimer::singleShot(900, [win, grabPath]() {
            QImage img = win->grabWindow();
            bool ok = !img.isNull() && img.save(grabPath);
            qInfo("GRAB_SAVED=%d %s", ok ? 1 : 0, qPrintable(grabPath));
            QGuiApplication::exit(ok ? 0 : 3);
        });
        return app.exec();
    }

    // Mode smoke test: UI berhasil dimuat (rootObjects tidak kosong) -> keluar 0.
    // Dipicu via argumen "--smoke" atau env XAVIQ_SMOKE.
    if (app.arguments().contains(QStringLiteral("--smoke"))
        || qEnvironmentVariableIsSet("XAVIQ_SMOKE"))
        return 0;

    return app.exec();
}
