import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

// Candlestick chart + indikator teknikal MT5 + overlay + garis posisi + marker trade.
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

    // State indikator aktif (Default: EMA 9 & EMA 21 untuk scalping cepat)
    property var activeIndicatorIds: ["ema_9", "ema_21"]
    property var activeOverlays: []
    property var allIndicators: []
    property var groupedCategories: []

    function lastClose() { return candles.length > 0 ? candles[candles.length - 1].c : 0 }

    function updateOverlays() {
        if (!bot) return
        if (root.candles && root.candles.length > 1 && root.activeIndicatorIds && root.activeIndicatorIds.length > 0) {
            root.activeOverlays = bot.computeOverlays(root.candles, root.activeIndicatorIds)
        } else {
            root.activeOverlays = []
        }
        canvas.requestPaint()
    }

    function toggleIndicator(id) {
        var idx = activeIndicatorIds.indexOf(id)
        var copy = activeIndicatorIds.slice()
        if (idx >= 0) {
            copy.splice(idx, 1)
        } else {
            copy.push(id)
        }
        activeIndicatorIds = copy
        updateOverlays()
    }

    function buildGroupedCategories() {
        if (!allIndicators || allIndicators.length === 0) return
        var cats = {}
        for (var i = 0; i < allIndicators.length; i++) {
            var item = allIndicators[i]
            var cName = item.category || "Lainnya"
            if (!cats[cName]) cats[cName] = []
            cats[cName].push(item)
        }
        var res = []
        var order = ["Moving Averages", "Saluran & Volatilitas", "Level & Price Action", "Osilator"]
        for (var k = 0; k < order.length; k++) {
            if (cats[order[k]]) {
                res.push({ name: order[k], items: cats[order[k]] })
                delete cats[order[k]]
            }
        }
        for (var rem in cats) {
            res.push({ name: rem, items: cats[rem] })
        }
        groupedCategories = res
    }

    Component.onCompleted: {
        if (bot) {
            allIndicators = bot.availableIndicators()
            buildGroupedCategories()
            updateOverlays()
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 6

        // ================= Header Toolbar Chart =================
        Rectangle {
            Layout.fillWidth: true
            implicitHeight: 44
            radius: 8
            color: Theme.surfaceAlt
            border.color: Theme.divider
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 10
                spacing: 8

                // 1. Judul & Ikon
                RowLayout {
                    spacing: 6
                    Image {
                        source: "qrc:/assets/chart.svg"
                        sourceSize: Qt.size(15, 15)
                        Layout.preferredWidth: 15
                        Layout.preferredHeight: 15
                        opacity: 0.85
                    }
                    Text {
                        text: "Candlestick"
                        color: Theme.textPrimary
                        font.pixelSize: 13
                        font.bold: true
                    }
                }

                Rectangle { width: 1; height: 18; color: Theme.divider }

                // 2. Pemilih Simbol Pasar
                RowLayout {
                    spacing: 6
                    Text {
                        text: "Instrumen:"
                        color: Theme.textSecondary
                        font.pixelSize: 11
                        font.weight: Font.Medium
                    }

                    CCombo {
                        id: symbolBox
                        Layout.preferredWidth: 160
                        Layout.preferredHeight: 30
                        model: root.symbolModel
                        displayText: {
                            if (!bot || !bot.connected) return "Menunggu MT5..."
                            if (count > 0 && currentIndex >= 0) return currentText
                            return (bot.chartSymbol !== "") ? bot.chartSymbol : "Pilih Simbol"
                        }
                        onActivated: {
                            if (bot && currentText !== "") {
                                bot.setChartSymbol(currentText)
                            }
                        }

                        ToolTip.visible: hovered
                        ToolTip.text: "Pilih instrumen pasangan mata uang / aset MT5 untuk ditampilkan lilin candlestick & ditradingkan."
                    }
                }

                // 3. Pemilih Timeframe Lilin (M1, M5, M15, M30, H1, H4, D1)
                Rectangle {
                    id: tfBadge
                    radius: 4
                    color: tfArea.containsMouse || tfPopup.visible ? Theme.surfaceAlt : Theme.surface
                    border.color: tfPopup.visible ? Theme.accent : (tfArea.containsMouse ? Theme.accent : Theme.divider)
                    border.width: 1
                    Layout.preferredHeight: 28
                    Layout.preferredWidth: tfRow.implicitWidth + 14

                    RowLayout {
                        id: tfRow
                        anchors.centerIn: parent
                        spacing: 5
                        Text {
                            text: "⏱"
                            font.pixelSize: 11
                        }
                        Text {
                            text: (bot && bot.timeframe !== "") ? bot.timeframe : "M5"
                            color: Theme.accent
                            font.pixelSize: 11
                            font.bold: true
                        }
                        Text {
                            text: "▾"
                            color: Theme.textSecondary
                            font.pixelSize: 10
                        }
                    }

                    ToolTip.visible: tfArea.containsMouse && !tfPopup.visible
                    ToolTip.text: "Pilih Timeframe grafik lilin: " + ((bot && bot.timeframe !== "") ? bot.timeframe : "M5") + " (M1, M5, M15, M30, H1, H4, D1)"

                    MouseArea {
                        id: tfArea
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (tfPopup.visible) tfPopup.close()
                            else tfPopup.open()
                        }
                    }

                    Popup {
                        id: tfPopup
                        y: tfBadge.height + 4
                        x: 0
                        width: 175
                        padding: 6
                        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

                        background: Rectangle {
                            color: Theme.surface
                            radius: 8
                            border.color: Theme.accent
                            border.width: 1.5

                            Rectangle {
                                anchors.fill: parent
                                radius: 8
                                color: "transparent"
                                border.color: Theme.divider
                                border.width: 1
                                opacity: 0.5
                            }
                        }

                        contentItem: ColumnLayout {
                            spacing: 3

                            Text {
                                text: "PILIH TIMEFRAME"
                                color: Theme.textMuted
                                font.pixelSize: 9
                                font.weight: Font.Bold
                                font.letterSpacing: 0.5
                                Layout.leftMargin: 6
                                Layout.topMargin: 2
                                Layout.bottomMargin: 2
                            }

                            Repeater {
                                model: [
                                    { code: "M1", desc: "1 Menit (Kilat)" },
                                    { code: "M5", desc: "5 Menit (Scalp)" },
                                    { code: "M15", desc: "15 Menit (Intraday)" },
                                    { code: "M30", desc: "30 Menit (Intraday)" },
                                    { code: "H1", desc: "1 Jam (Hourly)" },
                                    { code: "H4", desc: "4 Jam (Swing)" },
                                    { code: "D1", desc: "1 Hari (Daily)" }
                                ]

                                Rectangle {
                                    id: itemTf
                                    Layout.fillWidth: true
                                    Layout.preferredHeight: 28
                                    radius: 5
                                    readonly property bool isCurrent: bot ? (bot.timeframe === modelData.code) : (modelData.code === "M5")
                                    color: isCurrent ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.18)
                                                     : (itemTfArea.containsMouse ? Theme.surfaceAlt : "transparent")
                                    border.color: isCurrent ? Theme.accent : "transparent"
                                    border.width: isCurrent ? 1 : 0

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: 8
                                        anchors.rightMargin: 8
                                        spacing: 6

                                        Text {
                                            text: modelData.code
                                            color: itemTf.isCurrent ? Theme.accent : Theme.textPrimary
                                            font.pixelSize: 11
                                            font.bold: true
                                            Layout.preferredWidth: 28
                                        }

                                        Text {
                                            text: modelData.desc
                                            color: itemTf.isCurrent ? Theme.textPrimary : Theme.textSecondary
                                            font.pixelSize: 10
                                            Layout.fillWidth: true
                                        }

                                        Text {
                                            text: itemTf.isCurrent ? "✓" : ""
                                            color: Theme.accent
                                            font.pixelSize: 11
                                            font.bold: true
                                            visible: itemTf.isCurrent
                                        }
                                    }

                                    MouseArea {
                                        id: itemTfArea
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: {
                                            if (bot) {
                                                bot.setTimeframe(modelData.code)
                                            }
                                            tfPopup.close()
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                // 4. Tombol Refresh Lilin Chart
                CButton {
                    text: ""
                    icon.source: "qrc:/assets/refresh.svg"
                    icon.width: 13
                    icon.height: 13
                    Layout.preferredWidth: 30
                    Layout.preferredHeight: 28
                    enabled: bot && bot.connected
                    onClicked: {
                        if (bot && bot.chartSymbol !== "") {
                            bot.setChartSymbol(bot.chartSymbol)
                        }
                    }
                    ToolTip.visible: hovered
                    ToolTip.text: "Segarkan (Refresh) lilin candlestick dari MT5 sekarang"
                }

                Rectangle { width: 1; height: 18; color: Theme.divider }

                // 5. Tombol Menu Indikator MT5 (Clean SVG Icon)
                CButton {
                    id: btnIndicators
                    text: root.activeIndicatorIds.length > 0
                          ? "Indikator (" + root.activeIndicatorIds.length + ")"
                          : "Indikator"
                    icon.source: "qrc:/assets/layers.svg"
                    icon.width: 13
                    icon.height: 13
                    Layout.preferredHeight: 28
                    Layout.preferredWidth: implicitWidth + 12
                    highlighted: root.activeIndicatorIds.length > 0
                    onClicked: {
                        if (indPopup.visible) indPopup.close()
                        else indPopup.open()
                    }
                    ToolTip.visible: hovered
                    ToolTip.text: "Pilih & tampilkan indikator teknikal MT5 (Moving Averages, Bollinger Bands, SuperTrend, PSAR, RSI, MACD, dll)"
                }

                Item { Layout.fillWidth: true }

                // 6. Card Harga Live & Pergerakan Lilin Terakhir
                RowLayout {
                    visible: root.candles.length > 0
                    spacing: 8

                    ColumnLayout {
                        spacing: 0
                        Text {
                            text: "HARGA TERAKHIR"
                            color: Theme.textMuted
                            font.pixelSize: 9
                            font.weight: Font.DemiBold
                            font.letterSpacing: 0.5
                            horizontalAlignment: Text.AlignRight
                            Layout.alignment: Qt.AlignRight
                        }
                        RowLayout {
                            spacing: 6
                            Layout.alignment: Qt.AlignRight
                            Text {
                                text: {
                                    if (root.candles.length === 0) return ""
                                    var last = root.candles[root.candles.length - 1]
                                    var diff = last.c - last.o
                                    var sign = diff >= 0 ? "▲" : "▼"
                                    var pct = last.o > 0 ? (diff / last.o * 100) : 0
                                    return sign + " " + (diff >= 0 ? "+" : "") + diff.toFixed(5) + " (" + (diff >= 0 ? "+" : "") + pct.toFixed(2) + "%)"
                                }
                                color: {
                                    if (root.candles.length === 0) return Theme.textMuted
                                    var last = root.candles[root.candles.length - 1]
                                    return last.c >= last.o ? Theme.up : Theme.down
                                }
                                font.pixelSize: 11
                                font.bold: true
                            }
                            Text {
                                text: root.candles.length > 0 ? root.lastClose().toFixed(5) : "—"
                                color: Theme.textPrimary
                                font.pixelSize: 14
                                font.bold: true
                            }
                        }
                    }
                }
            }
        }

        // ================= Legend Bar Indikator Aktif =================
        Flow {
            id: legendFlow
            Layout.fillWidth: true
            visible: root.activeOverlays.length > 0
            spacing: 6

            Repeater {
                model: root.activeOverlays
                Rectangle {
                    radius: 4
                    color: Theme.surfaceAlt
                    border.color: Theme.divider
                    border.width: 1
                    implicitHeight: 20
                    implicitWidth: chipRow.implicitWidth + 12

                    RowLayout {
                        id: chipRow
                        anchors.centerIn: parent
                        spacing: 5
                        Rectangle {
                            width: 7
                            height: 7
                            radius: 3.5
                            color: modelData.color || Theme.accent
                        }
                        Text {
                            text: {
                                var valStr = ""
                                if (modelData.lastValue !== undefined && modelData.lastValue !== 0) {
                                    var dg = (modelData.panel === "rsi" || modelData.panel === "stoch") ? 1 : 5
                                    valStr = ": " + modelData.lastValue.toFixed(dg)
                                }
                                return modelData.name + valStr
                            }
                            color: Theme.textSecondary
                            font.pixelSize: 10
                            font.bold: true
                        }
                    }
                }
            }
        }

        // ================= Area Canvas Grafik Candlestick & Indikator =================
        Canvas {
            id: canvas
            Layout.fillWidth: true
            Layout.fillHeight: true
            onWidthChanged: requestPaint()
            onHeightChanged: requestPaint()

            Connections {
                target: root
                function onCandlesChanged() { root.updateOverlays() }
                function onActiveOverlaysChanged() { canvas.requestPaint() }
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
                    ctx.fillStyle = cText; ctx.font = "bold 13px sans-serif"
                    var msg = bot && bot.connected 
                        ? "Memuat data lilin candlestick (" + (bot.chartSymbol || "EURUSDm") + ")..." 
                        : "Hubungkan MT5 di tab Login untuk melihat pergerakan candlestick & indikator secara live."
                    ctx.fillText(msg, 24, height / 2 - 8)
                    ctx.fillStyle = String(Theme.textMuted); ctx.font = "11px sans-serif"
                    var subMsg = bot && bot.connected
                        ? "Pilih instrumen di menu atas untuk beralih pasangan mata uang."
                        : "Daftar instrumen pasar broker akan otomatis termuat setelah terhubung."
                    ctx.fillText(subMsg, 24, height / 2 + 14)
                    return
                }

                var ov = root.activeOverlays || []
                var mainOv = [], subOv = []
                for (var oi = 0; oi < ov.length; oi++) {
                    if (ov[oi].type === "subchart") subOv.push(ov[oi])
                    else mainOv.push(ov[oi])
                }

                var hasSub = subOv.length > 0
                var subH = hasSub ? Math.min(100, Math.floor(height * 0.26)) : 0
                var mL = 6, mR = 64, mT = 8, mB = 20
                var plotW = width - mL - mR
                var plotH = height - mT - mB - (hasSub ? (subH + 12) : 0)
                var n = data.length

                // Hitung batas harga lilin & indikator overlay
                var minP = data[0].l, maxP = data[0].h
                function acc(v) { if (v !== null && v !== undefined && v > 0) { if (v < minP) minP = v; if (v > maxP) maxP = v } }
                for (var i = 0; i < n; i++) { acc(data[i].l); acc(data[i].h) }
                for (var mo = 0; mo < mainOv.length; mo++) {
                    var mpts = mainOv[mo].points || []
                    for (var pi = 0; pi < mpts.length; pi++) acc(mpts[pi])
                }
                var poss = root.positions || []
                for (var q = 0; q < poss.length; q++) { acc(poss[q].open); acc(poss[q].sl); acc(poss[q].tp) }
                if (maxP === minP) maxP = minP + 1
                var range = maxP - minP

                function yOf(p) { return mT + (maxP - p) / range * plotH }
                var colW = plotW / n
                function xOf(idx) { return mL + (idx + 0.5) * colW }
                var bodyW = Math.max(1, colW * 0.6)

                // 1. Grid Horizontal & Label Harga
                ctx.strokeStyle = cGrid; ctx.fillStyle = cText; ctx.font = "10px sans-serif"; ctx.lineWidth = 1
                for (var g = 0; g <= 4; g++) {
                    var price = minP + (range * g / 4), yy = yOf(price)
                    ctx.beginPath(); ctx.moveTo(mL, yy); ctx.lineTo(mL + plotW, yy); ctx.stroke()
                    ctx.fillText(price.toFixed(5), mL + plotW + 4, yy + 3)
                }

                // 2. Lilin Candlestick
                for (var k = 0; k < n; k++) {
                    var c = data[k], xc = xOf(k), up = c.c >= c.o, col = up ? cUp : cDown
                    ctx.strokeStyle = col; ctx.fillStyle = col; ctx.lineWidth = 1
                    ctx.beginPath(); ctx.moveTo(xc, yOf(c.h)); ctx.lineTo(xc, yOf(c.l)); ctx.stroke()
                    var yO = yOf(c.o), yC = yOf(c.c), top = Math.min(yO, yC), hgt = Math.max(1, Math.abs(yC - yO))
                    ctx.fillRect(xc - bodyW / 2, top, bodyW, hgt)
                }

                // 3. Garis Indikator Overlay (EMA, SMA, BB, SuperTrend, PSAR, Donchian, VWAP, Pivots)
                for (var mi = 0; mi < mainOv.length; mi++) {
                    var oItem = mainOv[mi]
                    var series = oItem.points || []
                    var oStyle = oItem.style || "line"
                    var oCol = String(oItem.color || "#888")

                    if (oStyle === "dots") {
                        // Parabolic SAR / Titik dot
                        ctx.fillStyle = oCol
                        for (var ds = 0; ds < series.length && ds < n; ds++) {
                            var dVal = series[ds]
                            if (dVal === null || dVal === undefined) continue
                            var dPx = xOf(ds), dPy = yOf(dVal)
                            ctx.beginPath()
                            ctx.arc(dPx, dPy, 2.0, 0, 2 * Math.PI)
                            ctx.fill()
                        }
                    } else {
                        // Garis solid / putus-putus
                        ctx.strokeStyle = oCol
                        ctx.lineWidth = (oStyle === "dash") ? 1.0 : 1.5
                        if (oStyle === "dash") ctx.setLineDash([4, 4])
                        else ctx.setLineDash([])

                        ctx.beginPath()
                        var started = false
                        for (var s = 0; s < series.length && s < n; s++) {
                            var val = series[s]
                            if (val === null || val === undefined) { started = false; continue }
                            var px = xOf(s), py = yOf(val)
                            if (!started) { ctx.moveTo(px, py); started = true } else { ctx.lineTo(px, py) }
                        }
                        ctx.stroke()
                        ctx.setLineDash([])
                    }
                }

                // 4. Garis Posisi Terbuka (Entry, SL, TP)
                function hline(pPrice, color, dash, label) {
                    if (pPrice === null || pPrice === undefined || pPrice <= 0) return
                    if (pPrice < minP || pPrice > maxP) return
                    var pyy = yOf(pPrice)
                    ctx.strokeStyle = color; ctx.setLineDash(dash); ctx.lineWidth = 1
                    ctx.beginPath(); ctx.moveTo(mL, pyy); ctx.lineTo(mL + plotW, pyy); ctx.stroke()
                    ctx.setLineDash([]); ctx.fillStyle = color; ctx.font = "9px sans-serif"
                    ctx.fillText(label, mL + 2, pyy - 2)
                }
                for (var pp = 0; pp < poss.length; pp++) {
                    var ps = poss[pp]
                    hline(ps.open, cLast, [2, 2], "Entry " + ps.type)
                    hline(ps.sl, cDown, [5, 3], "SL")
                    hline(ps.tp, cUp, [5, 3], "TP")
                }

                // 5. Garis Harga Terakhir
                var lastY = yOf(data[n - 1].c)
                ctx.strokeStyle = cLast; ctx.setLineDash([4, 3])
                ctx.beginPath(); ctx.moveTo(mL, lastY); ctx.lineTo(mL + plotW, lastY); ctx.stroke()
                ctx.setLineDash([])

                // 6. Sub-Window Osilator (RSI, MACD, Stoch, ATR)
                if (hasSub) {
                    var subY = mT + plotH + 10
                    // Background kotak sub-window
                    ctx.fillStyle = String(Theme.surfaceAlt)
                    ctx.fillRect(mL, subY, plotW, subH)
                    ctx.strokeStyle = String(Theme.divider)
                    ctx.lineWidth = 1
                    ctx.strokeRect(mL, subY, plotW, subH)

                    var firstSub = subOv[0]
                    var panel = firstSub.panel || "rsi"

                    if (panel === "rsi" || panel === "stoch") {
                        // Skala 0 - 100
                        function subYOf(sv) { return subY + (100 - sv) / 100 * subH }

                        // Level 70 (Overbought)
                        ctx.strokeStyle = "rgba(231, 76, 60, 0.4)"; ctx.setLineDash([3, 3])
                        ctx.beginPath(); ctx.moveTo(mL, subYOf(70)); ctx.lineTo(mL + plotW, subYOf(70)); ctx.stroke()
                        ctx.fillStyle = String(Theme.textMuted); ctx.font = "9px sans-serif"
                        ctx.fillText("70", mL + plotW + 4, subYOf(70) + 3)

                        // Level 50 (Mid)
                        ctx.strokeStyle = Theme.isDark ? "rgba(255, 255, 255, 0.12)" : "rgba(15, 23, 42, 0.14)"; ctx.setLineDash([2, 4])
                        ctx.beginPath(); ctx.moveTo(mL, subYOf(50)); ctx.lineTo(mL + plotW, subYOf(50)); ctx.stroke()
                        ctx.fillText("50", mL + plotW + 4, subYOf(50) + 3)

                        // Level 30 (Oversold)
                        ctx.strokeStyle = "rgba(46, 204, 113, 0.4)"; ctx.setLineDash([3, 3])
                        ctx.beginPath(); ctx.moveTo(mL, subYOf(30)); ctx.lineTo(mL + plotW, subYOf(30)); ctx.stroke()
                        ctx.setLineDash([])
                        ctx.fillText("30", mL + plotW + 4, subYOf(30) + 3)

                        // Gambar deret indikator osilator
                        for (var si = 0; si < subOv.length; si++) {
                            var sItem = subOv[si]
                            var sSeries = sItem.points || []
                            ctx.strokeStyle = String(sItem.color || "#9B59B6")
                            ctx.lineWidth = 1.4
                            ctx.beginPath()
                            var sStarted = false
                            for (var ss = 0; ss < sSeries.length && ss < n; ss++) {
                                var sVal = sSeries[ss]
                                if (sVal === null || sVal === undefined) { sStarted = false; continue }
                                var sPx = xOf(ss), sPy = subYOf(sVal)
                                if (!sStarted) { ctx.moveTo(sPx, sPy); sStarted = true } else { ctx.lineTo(sPx, sPy) }
                            }
                            ctx.stroke()
                        }
                    } else {
                        // MACD / ATR (Skala berbasis min-max data)
                        var subMin = 0, subMax = 0.001
                        for (var sj = 0; sj < subOv.length; sj++) {
                            var sjPts = subOv[sj].points || []
                            for (var sk = 0; sk < sjPts.length; sk++) {
                                var vVal = sjPts[sk]
                                if (vVal !== null && vVal !== undefined) {
                                    if (vVal < subMin) subMin = vVal
                                    if (vVal > subMax) subMax = vVal
                                }
                            }
                        }
                        if (subMax === subMin) subMax = subMin + 0.001
                        var subRng = subMax - subMin
                        function subDynY(dv) { return subY + (subMax - dv) / subRng * subH }

                        // Garis Zero
                        if (subMin <= 0 && subMax >= 0) {
                            var zY = subDynY(0)
                            ctx.strokeStyle = Theme.isDark ? "rgba(255, 255, 255, 0.2)" : "rgba(15, 23, 42, 0.22)"; ctx.setLineDash([2, 2])
                            ctx.beginPath(); ctx.moveTo(mL, zY); ctx.lineTo(mL + plotW, zY); ctx.stroke()
                            ctx.setLineDash([])
                        }

                        for (var mci = 0; mci < subOv.length; mci++) {
                            var mcItem = subOv[mci]
                            var mcPts = mcItem.points || []
                            ctx.strokeStyle = String(mcItem.color || "#00CEC9")
                            ctx.lineWidth = 1.3
                            ctx.beginPath()
                            var mcStarted = false
                            for (var mcs = 0; mcs < mcPts.length && mcs < n; mcs++) {
                                var mcVal = mcPts[mcs]
                                if (mcVal === null || mcVal === undefined) { mcStarted = false; continue }
                                var mcPx = xOf(mcs), mcPy = subDynY(mcVal)
                                if (!mcStarted) { ctx.moveTo(mcPx, mcPy); mcStarted = true } else { ctx.lineTo(mcPx, mcPy) }
                            }
                            ctx.stroke()
                        }
                    }

                    // Label Sub-Panel Header
                    ctx.fillStyle = String(Theme.textPrimary)
                    ctx.font = "bold 10px sans-serif"
                    ctx.fillText(firstSub.name + ": " + (firstSub.lastValue ? firstSub.lastValue.toFixed(2) : "—"), mL + 8, subY + 14)
                }

                // 7. Label Waktu di Bawah Canvas
                function hhmm(t) {
                    var d = new Date(t * 1000)
                    function p(x) { return (x < 10 ? "0" : "") + x }
                    return p(d.getHours()) + ":" + p(d.getMinutes())
                }
                ctx.fillStyle = cText; ctx.font = "10px sans-serif"
                ctx.fillText(hhmm(data[0].t), mL, height - 6)
                ctx.fillText(hhmm(data[n - 1].t), mL + plotW - 30, height - 6)
            }
        }
    }

    // ================= Popup Menu Indikator MT5 (Clean & Modern) =================
    Popup {
        id: indPopup
        parent: btnIndicators
        x: Math.min(0, btnIndicators.width - width)
        y: btnIndicators.height + 6
        width: 370
        height: 480
        padding: 0
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

        background: Rectangle {
            color: Theme.surface
            radius: 10
            border.color: Theme.accent
            border.width: 1.5

            Rectangle {
                anchors.fill: parent
                radius: 10
                color: "transparent"
                border.color: Theme.divider
                border.width: 1
                opacity: 0.5
            }
        }

        contentItem: ColumnLayout {
            spacing: 0

            // 1. Header Popup
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 46
                color: Theme.surfaceAlt
                radius: 10

                Rectangle {
                    anchors.bottom: parent.bottom
                    anchors.left: parent.left
                    anchors.right: parent.right
                    height: 10
                    color: Theme.surfaceAlt
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 10
                    spacing: 8

                    Rectangle {
                        width: 26
                        height: 26
                        radius: 6
                        color: Theme.surface
                        border.color: Theme.divider
                        border.width: 1

                        Image {
                            anchors.centerIn: parent
                            source: "qrc:/assets/layers.svg"
                            sourceSize: Qt.size(14, 14)
                        }
                    }

                    ColumnLayout {
                        spacing: 0
                        Text {
                            text: "Indikator Teknikal MT5"
                            color: Theme.textPrimary
                            font.pixelSize: 12
                            font.bold: true
                        }
                        Text {
                            text: "Pilih indikator untuk ditampilkan di grafik"
                            color: Theme.textMuted
                            font.pixelSize: 9
                        }
                    }

                    Item { Layout.fillWidth: true }

                    Rectangle {
                        width: 24
                        height: 24
                        radius: 5
                        color: closeMouse.containsMouse ? Theme.surface : "transparent"
                        border.color: closeMouse.containsMouse ? Theme.border : "transparent"

                        Image {
                            anchors.centerIn: parent
                            source: "qrc:/assets/close.svg"
                            sourceSize: Qt.size(10, 10)
                            opacity: 0.8
                        }

                        MouseArea {
                            id: closeMouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: indPopup.close()
                        }
                    }
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.divider }

            // 2. Baris Preset Cepat (Pill Buttons)
            Rectangle {
                Layout.fillWidth: true
                implicitHeight: 40
                color: Theme.surface

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    anchors.rightMargin: 8
                    spacing: 6

                    // Preset Scalper
                    Rectangle {
                        implicitHeight: 26
                        implicitWidth: p1Row.implicitWidth + 14
                        radius: 13
                        color: p1Mouse.containsMouse ? Theme.surfaceAlt : Theme.surface
                        border.color: Theme.divider
                        border.width: 1

                        RowLayout {
                            id: p1Row
                            anchors.centerIn: parent
                            spacing: 4
                            Image {
                                source: "qrc:/assets/bolt.svg"
                                sourceSize: Qt.size(10, 10)
                            }
                            Text {
                                text: "Scalper"
                                color: Theme.textPrimary
                                font.pixelSize: 10
                                font.bold: true
                            }
                        }
                        MouseArea {
                            id: p1Mouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.activeIndicatorIds = ["ema_9", "ema_21", "rsi"]
                                root.updateOverlays()
                            }
                        }
                    }

                    // Preset Trend
                    Rectangle {
                        implicitHeight: 26
                        implicitWidth: p2Row.implicitWidth + 14
                        radius: 13
                        color: p2Mouse.containsMouse ? Theme.surfaceAlt : Theme.surface
                        border.color: Theme.divider
                        border.width: 1

                        RowLayout {
                            id: p2Row
                            anchors.centerIn: parent
                            spacing: 4
                            Image {
                                source: "qrc:/assets/chart.svg"
                                sourceSize: Qt.size(10, 10)
                            }
                            Text {
                                text: "Trend & BB"
                                color: Theme.textPrimary
                                font.pixelSize: 10
                                font.bold: true
                            }
                        }
                        MouseArea {
                            id: p2Mouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.activeIndicatorIds = ["sma_50", "sma_200", "bbands"]
                                root.updateOverlays()
                            }
                        }
                    }

                    Item { Layout.fillWidth: true }

                    // Reset Semua
                    Rectangle {
                        implicitHeight: 26
                        implicitWidth: p3Row.implicitWidth + 14
                        radius: 13
                        color: p3Mouse.containsMouse ? "rgba(231, 76, 60, 0.15)" : Theme.surface
                        border.color: p3Mouse.containsMouse ? Theme.down : Theme.divider
                        border.width: 1

                        RowLayout {
                            id: p3Row
                            anchors.centerIn: parent
                            spacing: 4
                            Image {
                                source: "qrc:/assets/trash.svg"
                                sourceSize: Qt.size(10, 10)
                                opacity: 0.85
                            }
                            Text {
                                text: "Bersihkan"
                                color: p3Mouse.containsMouse ? Theme.down : Theme.textMuted
                                font.pixelSize: 10
                                font.bold: true
                            }
                        }
                        MouseArea {
                            id: p3Mouse
                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.activeIndicatorIds = []
                                root.updateOverlays()
                            }
                        }
                    }
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.divider }

            // 3. Daftar Indikator Berkelompok
            ScrollView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                ScrollBar.vertical: ThinScrollBar {}

                ColumnLayout {
                    width: parent.width
                    spacing: 12
                    Layout.margins: 10

                    Repeater {
                        model: root.groupedCategories

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 6

                            // Header Kategori
                            RowLayout {
                                spacing: 6
                                Rectangle {
                                    width: 3
                                    height: 12
                                    radius: 1.5
                                    color: Theme.accent
                                }
                                Text {
                                    text: modelData.name.toUpperCase()
                                    color: Theme.accent
                                    font.pixelSize: 10
                                    font.bold: true
                                    font.letterSpacing: 0.6
                                }
                            }

                            // Kartu Item Indikator
                            Repeater {
                                model: modelData.items

                                Rectangle {
                                    id: itemCard
                                    Layout.fillWidth: true
                                    implicitHeight: itemRow.implicitHeight + 10
                                    radius: 8
                                    color: itemMouse.containsMouse
                                           ? Theme.surfaceAlt
                                           : (isActive ? (Theme.isDark ? "rgba(255, 255, 255, 0.03)" : "rgba(2, 132, 199, 0.08)") : "transparent")
                                    border.color: isActive ? Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.45) : "transparent"
                                    border.width: 1

                                    readonly property bool isActive: root.activeIndicatorIds.indexOf(modelData.id) !== -1

                                    MouseArea {
                                        id: itemMouse
                                        anchors.fill: parent
                                        hoverEnabled: true
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: root.toggleIndicator(modelData.id)
                                    }

                                    RowLayout {
                                        id: itemRow
                                        anchors.fill: parent
                                        anchors.leftMargin: 10
                                        anchors.rightMargin: 10
                                        spacing: 10

                                        // Custom Checkbox Kotak Modern dengan SVG Centang
                                        Rectangle {
                                            width: 18
                                            height: 18
                                            radius: 5
                                            color: itemCard.isActive ? Theme.accent : "transparent"
                                            border.color: itemCard.isActive ? Theme.accent : Theme.divider
                                            border.width: 1.5

                                            Image {
                                                anchors.centerIn: parent
                                                source: "qrc:/assets/check.svg"
                                                sourceSize: Qt.size(11, 11)
                                                visible: itemCard.isActive
                                            }
                                        }

                                        // Color Pill Indikator
                                        Rectangle {
                                            width: 10
                                            height: 10
                                            radius: 5
                                            color: modelData.color
                                        }

                                        // Judul & Keterangan
                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            spacing: 1
                                            Text {
                                                text: modelData.name
                                                color: itemCard.isActive ? Theme.textPrimary : Theme.textSecondary
                                                font.pixelSize: 11
                                                font.bold: itemCard.isActive
                                            }
                                            Text {
                                                text: modelData.description
                                                color: Theme.textMuted
                                                font.pixelSize: 9
                                                elide: Text.ElideRight
                                                Layout.fillWidth: true
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    Connections {
        target: bot
        function onChartUpdated(symbol, payload) {
            if (symbol !== (bot ? bot.chartSymbol : "")) return
            var d = payload || {}
            root.candles = d.candles || []
            root.positions = d.positions || []
            root.trades = d.trades || []
            root.updateOverlays()
        }
        function onSymbolsAvailable(symbols) {
            root.symbolModel = symbols
            var idx = symbols.indexOf(bot.chartSymbol)
            if (idx >= 0) symbolBox.currentIndex = idx
        }
        function onChartSymbolChanged(sym) {
            root.candles = []; root.overlays = []; root.activeOverlays = []; root.positions = []; root.trades = []
            canvas.requestPaint()
        }
    }
}
