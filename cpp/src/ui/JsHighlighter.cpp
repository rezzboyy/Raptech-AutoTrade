#include "ui/JsHighlighter.h"

#include <QQuickTextDocument>
#include <QTextDocument>

JsHighlighter::JsHighlighter(QObject *parent) : QSyntaxHighlighter(parent)
{
    // Keyword JavaScript.
    QTextCharFormat keywordFormat;
    keywordFormat.setForeground(QColor("#c084fc"));
    keywordFormat.setFontWeight(QFont::Bold);
    const QStringList keywords = {
        "\\bvar\\b", "\\blet\\b", "\\bconst\\b", "\\bfunction\\b", "\\breturn\\b",
        "\\bif\\b", "\\belse\\b", "\\bfor\\b", "\\bwhile\\b", "\\bdo\\b", "\\bbreak\\b",
        "\\bcontinue\\b", "\\bnew\\b", "\\btypeof\\b", "\\bthis\\b", "\\btrue\\b",
        "\\bfalse\\b", "\\bnull\\b", "\\bundefined\\b", "\\bswitch\\b", "\\bcase\\b"};
    for (const QString &k : keywords)
        m_rules.append({QRegularExpression(k), keywordFormat});

    // Objek ctx & Math (built-in yang umum dipakai).
    QTextCharFormat builtinFormat;
    builtinFormat.setForeground(QColor("#38bdf8"));
    m_rules.append({QRegularExpression("\\bctx\\b"), builtinFormat});
    m_rules.append({QRegularExpression("\\bMath\\b"), builtinFormat});

    // Angka.
    QTextCharFormat numberFormat;
    numberFormat.setForeground(QColor("#f59e0b"));
    m_rules.append({QRegularExpression("\\b[0-9]+(\\.[0-9]+)?\\b"), numberFormat});

    // String (single & double quote) — diproses terpisah agar menang atas angka/keyword.
    m_stringFormat.setForeground(QColor("#4ade80"));
    // Komentar // ... akhir baris.
    m_commentFormat.setForeground(QColor("#6b7280"));
    m_commentFormat.setFontItalic(true);
}

void JsHighlighter::setQuickDocument(QQuickTextDocument *doc)
{
    if (m_quickDoc == doc)
        return;
    m_quickDoc = doc;
    setDocument(doc ? doc->textDocument() : nullptr);
    emit documentChanged();
    rehighlight();
}

void JsHighlighter::setErrorLine(int line)
{
    if (m_errorLine == line)
        return;
    m_errorLine = line;
    emit errorLineChanged();
    rehighlight();
}

void JsHighlighter::highlightBlock(const QString &text)
{
    // 1) Aturan reguler (keyword, angka, ctx/Math).
    for (const Rule &r : m_rules) {
        QRegularExpressionMatchIterator it = r.pattern.globalMatch(text);
        while (it.hasNext()) {
            const QRegularExpressionMatch m = it.next();
            setFormat(m.capturedStart(), m.capturedLength(), r.format);
        }
    }

    // 2) String "..." atau '...'.
    static const QRegularExpression strRe("\"[^\"]*\"|'[^']*'");
    QRegularExpressionMatchIterator sit = strRe.globalMatch(text);
    while (sit.hasNext()) {
        const QRegularExpressionMatch m = sit.next();
        setFormat(m.capturedStart(), m.capturedLength(), m_stringFormat);
    }

    // 3) Komentar // sampai akhir baris (menang atas semua).
    const int c = text.indexOf("//");
    if (c >= 0)
        setFormat(c, text.length() - c, m_commentFormat);

    // 4) Tandai baris error (garis bawah merah), pertahankan warna sintaks.
    if (m_errorLine > 0 && currentBlock().blockNumber() == m_errorLine - 1 && !text.isEmpty()) {
        for (int i = 0; i < text.length(); ++i) {
            QTextCharFormat f = format(i);
            f.setUnderlineStyle(QTextCharFormat::WaveUnderline);
            f.setUnderlineColor(QColor("#ef4444"));
            setFormat(i, 1, f);
        }
    }
}
