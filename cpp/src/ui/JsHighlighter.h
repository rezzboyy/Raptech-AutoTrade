#pragma once
#include <QQuickTextDocument>
#include <QRegularExpression>
#include <QSyntaxHighlighter>
#include <QTextCharFormat>
#include <QVector>

// Syntax highlighter JavaScript untuk editor Mode Programmer (dipakai dari QML).
// Menyorot: keyword, string, angka, komentar, dan menandai baris error (garis merah).
class JsHighlighter : public QSyntaxHighlighter
{
    Q_OBJECT
    Q_PROPERTY(QQuickTextDocument *document READ quickDocument WRITE setQuickDocument
                   NOTIFY documentChanged)
    Q_PROPERTY(int errorLine READ errorLine WRITE setErrorLine NOTIFY errorLineChanged)

public:
    explicit JsHighlighter(QObject *parent = nullptr);

    QQuickTextDocument *quickDocument() const { return m_quickDoc; }
    void setQuickDocument(QQuickTextDocument *doc);

    int errorLine() const { return m_errorLine; }
    void setErrorLine(int line);

signals:
    void documentChanged();
    void errorLineChanged();

protected:
    void highlightBlock(const QString &text) override;

private:
    struct Rule { QRegularExpression pattern; QTextCharFormat format; };
    QVector<Rule> m_rules;
    QTextCharFormat m_commentFormat;
    QTextCharFormat m_stringFormat;
    QQuickTextDocument *m_quickDoc = nullptr;
    int m_errorLine = 0;
};
