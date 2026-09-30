import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

// Candlestick chart + overlay indikator + garis posisi + marker trade.
Rectangle {
    id: root
    color: Theme.surface
    radius: 10
    border.color: Theme.border

    property var candles: []
    property var overlays: []
    property var positions: []
    property var trades: []
    property var symbolModel: []

    function lastClose() { return candles.length > 0 ? candles[candles.length - 1].c : 0 }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 5

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Image { source: "qrc:/assets/chart.svg"; sourceSize.width: 15; sourceSize.height: 15 }
            Text { text: "Chart"; color: Theme.textPrimary; font.pixelSize: 13; font.bold: true }
            Text { text: "Simbol"; color: Theme.textMuted; font.pixelSize: 11; Layout.leftMargin: 6 }
            ComboBox {
                id: symbolBox
                Layout.preferredWidth: 170
                Layout.preferredHeight: 30
                font.pixelSize: 12
                model: root.symbolModel
                displayText: (count > 0 && currentIndex >= 0) ? currentText : "pilih simbol"
                onActivated: bot.setChartSymbol(currentText)
            }
            Item { Layout.fillWidth: true }
            Text {
                text: root.candles.length > 0 ? "Last: " + root.lastClose().toFixed(5) : "—"
                color: Theme.textPrimary; font.pixelSize: 13; font.bold: true
            }
        }

        Canvas {
            id: canvas
            Layout.fillWidth: true
            Layout.fillHeight: true
            onWidthChanged: requestPaint()
            onHeightChanged: requestPaint()

            Connections {
                target: root
                function onCandlesChanged() { canvas.requestPaint() }
                function onOverlaysChanged() { canvas.requestPaint() }
                function onPositionsChanged() { canvas.requestPaint() }
                function onTradesChanged() { canvas.requestPaint() }
            }
            Connections {
                target: Theme
                function onIsDarkChanged() { canvas.requestPaint() }
            }

            onPaint: {
                var ctx = getContext("2d")
                ctx.reset()
                ctx.clearRect(0, 0, width, height)
                var cGrid = String(Theme.divider), cText = String(Theme.textMuted)
                var cUp = String(Theme.up), cDown = String(Theme.down), cLast = String(Theme.textSecondary)

                var data = root.candles
                if (!data || data.length < 2) {
                    ctx.fillStyle = cText; ctx.font = "13px sans-serif"
                    ctx.fillText(bot && bot.connected ? "Menunggu data candle..." : "Hubungkan MT5 untuk melihat chart", 16, height / 2)
                    return
                }
                var mL = 6, mR = 62, mT = 8, mB = 20
                var plotW = width - mL - mR, plotH = height - mT - mB, n = data.length
                var minP = data[0].l, maxP = data[0].h
                function acc(v) { if (v !== null && v !== undefined && v > 0) { if (v < minP) minP = v; if (v > maxP) maxP = v } }
                for (var i = 0; i < n; i++) { acc(data[i].l); acc(data[i].h) }
                var ov = root.overlays || []
                for (var o = 0; o < ov.length; o++) { var pts = ov[o].points || []; for (var pi = 0; pi < pts.length; pi++) acc(pts[pi]) }
                var poss = root.positions || []
                for (var q = 0; q < poss.length; q++) { acc(poss[q].open); acc(poss[q].sl); acc(poss[q].tp) }
                if (maxP === minP) maxP = minP + 1
                var range = maxP - minP
                function yOf(p) { return mT + (maxP - p) / range * plotH }
                var colW = plotW / n
                function xOf(idx) { return mL + (idx + 0.5) * colW }
                var bodyW = Math.max(1, colW * 0.6)

                ctx.strokeStyle = cGrid; ctx.fillStyle = cText; ctx.font = "10px sans-serif"; ctx.lineWidth = 1
                for (var g = 0; g <= 4; g++) {
                    var price = minP + (range * g / 4), yy = yOf(price)
                    ctx.beginPath(); ctx.moveTo(mL, yy); ctx.lineTo(mL + plotW, yy); ctx.stroke()
                    ctx.fillText(price.toFixed(5), mL + plotW + 4, yy + 3)
                }
                for (var k = 0; k < n; k++) {
                    var c = data[k], xc = xOf(k), up = c.c >= c.o, col = up ? cUp : cDown
                    ctx.strokeStyle = col; ctx.fillStyle = col; ctx.lineWidth = 1
                    ctx.beginPath(); ctx.moveTo(xc, yOf(c.h)); ctx.lineTo(xc, yOf(c.l)); ctx.stroke()
                    var yO = yOf(c.o), yC = yOf(c.c), top = Math.min(yO, yC), hgt = Math.max(1, Math.abs(yC - yO))
                    ctx.fillRect(xc - bodyW / 2, top, bodyW, hgt)
                }
                ctx.lineWidth = 1.4
                for (var oi = 0; oi < ov.length; oi++) {
                    var series = ov[oi].points || []
                    ctx.strokeStyle = String(ov[oi].color || "#888"); ctx.beginPath()
                    var started = false
                    for (var s = 0; s < series.length && s < n; s++) {
                        var val = series[s]
                        if (val === null || val === undefined) { started = false; continue }
                        var px = xOf(s), py = yOf(val)
                        if (!started) { ctx.moveTo(px, py); started = true } else { ctx.lineTo(px, py) }
                    }
                    ctx.stroke()
                }
                function hline(price, color, dash, label) {
                    if (price === null || price === undefined || price <= 0) return
                    if (price < minP || price > maxP) return
                    var y = yOf(price)
                    ctx.strokeStyle = color; ctx.setLineDash(dash); ctx.lineWidth = 1
                    ctx.beginPath(); ctx.moveTo(mL, y); ctx.lineTo(mL + plotW, y); ctx.stroke()
                    ctx.setLineDash([]); ctx.fillStyle = color; ctx.font = "9px sans-serif"
                    ctx.fillText(label, mL + 2, y - 2)
                }
                for (var pp = 0; pp < poss.length; pp++) {
                    var ps = poss[pp]
                    hline(ps.open, cLast, [2, 2], "Entry " + ps.type)
                    hline(ps.sl, cDown, [5, 3], "SL")
                    hline(ps.tp, cUp, [5, 3], "TP")
                }
                var lastY = yOf(data[n - 1].c)
                ctx.strokeStyle = cLast; ctx.setLineDash([4, 3])
                ctx.beginPath(); ctx.moveTo(mL, lastY); ctx.lineTo(mL + plotW, lastY); ctx.stroke()
                ctx.setLineDash([])
                function hhmm(t) { var d = new Date(t * 1000); function p(x) { return (x < 10 ? "0" : "") + x } return p(d.getHours()) + ":" + p(d.getMinutes()) }
                ctx.fillStyle = cText; ctx.font = "10px sans-serif"
                ctx.fillText(hhmm(data[0].t), mL, height - 6)
                ctx.fillText(hhmm(data[n - 1].t), mL + plotW - 30, height - 6)
            }
        }
    }

    Connections {
        target: bot
        function onChartUpdated(symbol, payload) {
            if (symbol !== (bot ? bot.chartSymbol : "")) return
            var d = payload || {}
            root.candles = d.candles || []
            root.overlays = d.overlays || []
            root.positions = d.positions || []
            root.trades = d.trades || []
        }
        function onSymbolsAvailable(symbols) {
            root.symbolModel = symbols
            var idx = symbols.indexOf(bot.chartSymbol)
            if (idx >= 0) symbolBox.currentIndex = idx
        }
        function onChartSymbolChanged(sym) {
            root.candles = []; root.overlays = []; root.positions = []; root.trades = []
            canvas.requestPaint()
        }
    }
}
