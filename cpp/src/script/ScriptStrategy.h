#pragma once
#include <QJSEngine>
#include <QJSValue>
#include <QVariantMap>
#include <memory>

#include "strategy/Strategy.h"

class ScriptContext;

// Hasil validasi skrip untuk editor (garis merah real-time).
struct ScriptValidation {
    bool ok = false;
    int line = 0;
    QString message;
};

// Strategi berbasis skrip JavaScript (Programmer Mode) via QJSEngine.
// Padanan ScriptStrategy di strategies/script_runtime.py, tapi bahasa skrip = JS.
class ScriptStrategy : public Strategy
{
public:
    explicit ScriptStrategy(const QString &source, const QVariantMap &params = {},
                            int timeoutMs = 2000);
    ~ScriptStrategy() override;

    QString name() const override { return QStringLiteral("custom_script"); }
    QVariantMap scriptSettings() const override { return m_settings; }
    QVector<Command> onBar(const QVector<Candle> &candles, const RuntimeContext &rt) override;

    bool compiled() const { return m_ok; }
    QString error() const { return m_error; }
    QStringList takeLogs();

    // Validasi statis skrip (kompilasi + cek on_bar) untuk editor.
    static ScriptValidation validate(const QString &source);

private:
    QVector<Command> parseResult(const QJSValue &r);
    static bool parseCommand(const QJSValue &o, Command &out);

    std::unique_ptr<QJSEngine> m_engine;
    ScriptContext *m_ctx = nullptr; // di-parent ke m_engine
    QJSValue m_ctxValue;
    QJSValue m_onBar;
    QVariantMap m_settings;
    QVariantMap m_params;
    bool m_ok = false;
    QString m_error;
    int m_timeoutMs;
};
