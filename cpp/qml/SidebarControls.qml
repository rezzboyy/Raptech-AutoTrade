import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Controls.Material
import "."

// SidebarControls.qml — Sidebar Kontrol Eksekusi Instan & Telemetri Real-Time
// Desain 100% presisi mengikuti workstation Dark Cyber-Trading Terminal (Width: 320px)
Rectangle {
    id: root
    width: 320
    color: Theme.surface
    border.color: Theme.border
    border.width: 1

    property string currentSymbol: (bot && bot.chartSymbol && bot.chartSymbol.length > 0) ? bot.chartSymbol : "XAUUSD.vx"
    property var sessionStart: new Date()
    property string uptimeString: "00:00:00"

    // Timer Uptime Bot (Detak tiap 1 detik)
    Timer {
        interval: 1000
        running: true
        repeat: true
        onTriggered: {
            var diffSec = Math.floor((new Date() - root.sessionStart) / 1000)
            var h = Math.floor(diffSec / 3600)
            var m = Math.floor((diffSec % 3600) / 60)
            var s = diffSec % 60
            root.uptimeString = (h < 10 ? "0" + h : h) + ":" +
                                (m < 10 ? "0" + m : m) + ":" +
                                (s < 10 ? "0" + s : s)
        }
    }

    Connections {
        target: bot
        function onChartSymbolChanged(sym) {
            if (sym && sym.length > 0) {
                root.currentSymbol = sym
                for (var i = 0; i < symbolBox.model.length; i++) {
                    if (symbolBox.model[i] === sym) {
                        symbolBox.currentIndex = i
                        break
                    }
                }
            }
        }
        function onSymbolsAvailable(symbols) {
            if (symbols && symbols.length > 0) {
                symbolBox.model = symbols
                for (var i = 0; i < symbols.length; i++) {
                    if (symbols[i] === root.currentSymbol) {
                        symbolBox.currentIndex = i
                        break
                    }
                }
            }
        }
    }

    // Defensive lot parser
    function parseLot() {
        var raw = lotInput.text.trim()
        var val = parseFloat(raw)
        if (isNaN(val) || val <= 0.0) {
            val = 0.01
            lotInput.text = "0.01"
        } else if (val > 100.0) {
            val = 100.0
            lotInput.text = "100.00"
        }
        return val
    }

    ScrollView {
        id: scroll
        anchors.fill: parent
        anchors.margins: 12
        contentWidth: availableWidth
        clip: true
        ScrollBar.vertical: ThinScrollBar {}

        ColumnLayout {
            width: scroll.availableWidth
            spacing: 10

            // ================= 1. Controls Header =================
            Text {
                text: "Controls"
                font.pixelSize: 13
                font.bold: true
                color: Theme.textPrimary
                Layout.topMargin: 2
            }

            // Symbol Selector & Refresh
            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                Text {
                    text: "Symbol:"
                    font.pixelSize: 11
                    color: Theme.textSecondary
                    Layout.preferredWidth: 46
                }

                ComboBox {
                    id: symbolBox
                    Layout.fillWidth: true
                    implicitHeight: 30
                    font.pixelSize: 11
                    model: ["XAUUSD.vx", "EURUSDm", "GBPUSDm", "USDJPYm", "BTCUSDm"]
                    currentIndex: 0
                    onActivated: function(index) {
                        var sym = model[index]
                        root.currentSymbol = sym
                        if (bot) bot.setChartSymbol(sym)
                    }
                }

                Button {
                    flat: true
                    Layout.preferredWidth: 30
                    Layout.preferredHeight: 30
                    icon.source: "qrc:/assets/refresh.svg"
                    icon.width: 13
                    icon.height: 13
                    icon.color: Theme.textSecondary
                    ToolTip.visible: hovered
                    ToolTip.text: "Refresh daftar simbol & harga"
                    onClicked: {
                        if (bot) bot.setChartSymbol(root.currentSymbol)
                    }
                }
            }

            // Uptime Display
            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                Text {
                    text: "Uptime:"
                    font.pixelSize: 11
                    color: Theme.textSecondary
                    Layout.preferredWidth: 46
                }

                Item { Layout.fillWidth: true }

                Text {
                    text: root.uptimeString
                    font.pixelSize: 12
                    font.bold: true
                    font.family: "Consolas"
                    color: Theme.up
                }
            }

            // ================= 2. START / STOP Big Buttons =================
            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                // START Button
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 36
                    radius: Theme.radiusSmall
                    color: Theme.btnStart
                    border.color: (bot && bot.trading) ? Theme.updateGlow : "transparent"
                    border.width: (bot && bot.trading) ? 2 : 0
                    opacity: (bot && bot.connected) ? 1.0 : 0.6

                    Text {
                        anchors.centerIn: parent
                        text: "START"
                        font.pixelSize: 12
                        font.bold: true
                        color: "#FFFFFF"
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        enabled: bot ? bot.connected : false
                        onClicked: {
                            if (bot) bot.setTrading(true)
                        }
                    }
                }

                // STOP Button
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 36
                    radius: Theme.radiusSmall
                    color: Theme.btnStop
                    border.color: (bot && !bot.trading && bot.connected) ? "#FF8A80" : "transparent"
                    border.width: (bot && !bot.trading && bot.connected) ? 2 : 0
                    opacity: (bot && bot.connected) ? 1.0 : 0.6

                    Text {
                        anchors.centerIn: parent
                        text: "STOP"
                        font.pixelSize: 12
                        font.bold: true
                        color: "#FFFFFF"
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        enabled: bot ? bot.connected : false
                        onClicked: {
                            if (bot) bot.setTrading(false)
                        }
                    }
                }
            }

            // ================= 3. Quick Trade (Lot + BUY + SELL) =================
            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                // Lot Field
                Rectangle {
                    Layout.preferredWidth: 72
                    Layout.preferredHeight: 36
                    radius: Theme.radiusSmall
                    color: Theme.surfaceAlt
                    border.color: Theme.border
                    border.width: 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 4
                        spacing: 2

                        Text {
                            text: "Lot:"
                            font.pixelSize: 10
                            color: Theme.textMuted
                        }

                        TextInput {
                            id: lotInput
                            Layout.fillWidth: true
                            text: "0.01"
                            font.pixelSize: 11
                            font.bold: true
                            font.family: "Consolas"
                            color: Theme.textPrimary
                            selectByMouse: true
                            validator: DoubleValidator { bottom: 0.01; top: 100.0; decimals: 2 }
                        }
                    }
                }

                // BUY Button
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 36
                    radius: Theme.radiusSmall
                    color: Theme.btnBuy
                    opacity: (bot && bot.connected) ? 1.0 : 0.6

                    Text {
                        anchors.centerIn: parent
                        text: "BUY"
                        font.pixelSize: 12
                        font.bold: true
                        color: "#FFFFFF"
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        enabled: bot ? bot.connected : false
                        onClicked: {
                            var lotVal = root.parseLot()
                            if (bot) bot.openManualOrder(root.currentSymbol, "BUY", lotVal)
                        }
                    }
                }

                // SELL Button
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 36
                    radius: Theme.radiusSmall
                    color: Theme.btnSell
                    opacity: (bot && bot.connected) ? 1.0 : 0.6

                    Text {
                        anchors.centerIn: parent
                        text: "SELL"
                        font.pixelSize: 12
                        font.bold: true
                        color: "#FFFFFF"
                    }

                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        enabled: bot ? bot.connected : false
                        onClicked: {
                            var lotVal = root.parseLot()
                            if (bot) bot.openManualOrder(root.currentSymbol, "SELL", lotVal)
                        }
                    }
                }
            }

            // ================= 4. HEDGE Action Button =================
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 36
                radius: Theme.radiusSmall
                color: Theme.btnHedge
                opacity: (bot && bot.connected) ? 1.0 : 0.6

                Text {
                    anchors.centerIn: parent
                    text: "HEDGE BUY+SELL"
                    font.pixelSize: 12
                    font.bold: true
                    color: "#FFFFFF"
                }

                MouseArea {
                    id: hedgeHover
                    anchors.fill: parent
                    cursorShape: Qt.PointingHandCursor
                    hoverEnabled: true
                    enabled: bot ? bot.connected : false
                    onClicked: {
                        var lotVal = root.parseLot()
                        if (bot) bot.openHedgeOrder(root.currentSymbol, lotVal)
                    }
                }

                ToolTip.visible: hedgeHover.containsMouse
                ToolTip.text: "Buka 2 posisi berlawanan serentak (BUY + SELL) dengan lot tertera untuk hedging/locking"
            }

            // ================= 5. Max OP & Emergency Reset =================
            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                // Max OP SpinBox
                Rectangle {
                    Layout.preferredWidth: 72
                    Layout.preferredHeight: 36
                    radius: Theme.radiusSmall
                    color: Theme.surfaceAlt
                    border.color: Theme.border
                    border.width: 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.margins: 4
                        spacing: 2

                        Text {
                            text: "Max:"
                            font.pixelSize: 10
                            color: Theme.textMuted
                        }

                        TextInput {
                            id: maxOpInput
                            Layout.fillWidth: true
                            text: "6"
                            font.pixelSize: 11
                            font.bold: true
                            font.family: "Consolas"
                            color: Theme.textPrimary
                            selectByMouse: true
                            validator: IntValidator { bottom: 1; top: 50 }
                        }
                    }
                }

                // CLOSE ALL RESET Button
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 36
                    radius: Theme.radiusSmall
                    color: Theme.btnCloseAll
                    opacity: (bot && bot.connected) ? 1.0 : 0.6

                    Text {
                        anchors.centerIn: parent
                        text: "CLOSE ALL RESET"
                        font.pixelSize: 11
                        font.bold: true
                        color: "#FFFFFF"
                    }

                    MouseArea {
                        id: closeAllHover
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        hoverEnabled: true
                        enabled: bot ? bot.connected : false
                        onClicked: {
                            if (bot) bot.emergencyCloseAllReset()
                        }
                    }

                    ToolTip.visible: closeAllHover.containsMouse
                    ToolTip.text: "Likuidasi darurat seluruh floating order dan reset state"
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.divider }

            // ================= 6. Card: Market Risk =================
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 84
                radius: Theme.radiusCard
                color: Theme.surfaceAlt
                border.color: Theme.border
                border.width: 1

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 4

                    Text {
                        text: "Market Risk"
                        font.pixelSize: 11
                        font.bold: true
                        color: Theme.accent
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "Bid:"; font.pixelSize: 10; color: Theme.textMuted }
                        Text {
                            id: bidText
                            text: "3530.87"
                            font.pixelSize: 11
                            font.bold: true
                            font.family: "Consolas"
                            color: Theme.accent
                        }
                        Item { Layout.fillWidth: true }
                        Text { text: "Ask:"; font.pixelSize: 10; color: Theme.textMuted }
                        Text {
                            id: askText
                            text: "3531.18"
                            font.pixelSize: 11
                            font.bold: true
                            font.family: "Consolas"
                            color: Theme.down
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "Spread:"; font.pixelSize: 10; color: Theme.textMuted }
                        Text { text: "31"; font.pixelSize: 11; font.bold: true; color: Theme.textPrimary }
                        Item { Layout.fillWidth: true }
                        Text { text: "Target:"; font.pixelSize: 10; color: Theme.textMuted }
                        Text { text: "SL 20.0% / TP 3.0%"; font.pixelSize: 10; font.bold: true; color: Theme.up }
                    }
                }
            }

            // ================= 7. Card: Account Telemetry =================
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 110
                radius: Theme.radiusCard
                color: Theme.surfaceAlt
                border.color: Theme.border
                border.width: 1

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 3

                    RowLayout {
                        Layout.fillWidth: true
                        Text {
                            text: "Account"
                            font.pixelSize: 11
                            font.bold: true
                            color: Theme.accent
                        }
                        Item { Layout.fillWidth: true }
                        Rectangle {
                            height: 18
                            radius: 3
                            color: resetSideMouse.containsMouse ? Theme.hoverSurface : Theme.surface
                            border.color: resetSideMouse.containsMouse ? Theme.accent : Theme.border
                            border.width: 1
                            implicitWidth: resetSideText.implicitWidth + 12
                            RowLayout {
                                anchors.centerIn: parent
                                spacing: 3
                                Image {
                                    source: "qrc:/assets/refresh.svg"
                                    sourceSize: Qt.size(9, 9)
                                    Layout.preferredWidth: 9
                                    Layout.preferredHeight: 9
                                    opacity: resetSideMouse.containsMouse ? 1.0 : 0.7
                                }
                                Text {
                                    id: resetSideText
                                    text: "Reset Stats"
                                    font.pixelSize: 9
                                    font.bold: true
                                    color: resetSideMouse.containsMouse ? Theme.accent : Theme.textMuted
                                }
                            }
                            MouseArea {
                                id: resetSideMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: if (bot) bot.resetStats()
                            }
                            ToolTip.visible: resetSideMouse.containsMouse
                            ToolTip.text: "Reset statistik performa (Daily PnL, Win Rate) ke 0"
                        }
                        Rectangle {
                            height: 16
                            radius: 3
                            color: (bot && bot.accountType === "REAL") ? Theme.down
                                 : ((bot && (bot.accountType === "SIMULASI" || bot.accountType === "SIM")) ? Theme.warn : Theme.btnStart)
                            implicitWidth: typeLabel.implicitWidth + 8
                            Text {
                                id: typeLabel
                                anchors.centerIn: parent
                                text: (bot && bot.accountType) ? bot.accountType : "DEMO"
                                font.pixelSize: 9
                                font.bold: true
                                color: "#FFFFFF"
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "Balance:"; font.pixelSize: 10; color: Theme.textMuted }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: bot ? ("$" + bot.balance.toFixed(2)) : "$0.00"
                            font.pixelSize: 11
                            font.bold: true
                            font.family: "Consolas"
                            color: Theme.textPrimary
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "Equity:"; font.pixelSize: 10; color: Theme.textMuted }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: bot ? ("$" + bot.equity.toFixed(2)) : "$0.00"
                            font.pixelSize: 11
                            font.bold: true
                            font.family: "Consolas"
                            color: Theme.textPrimary
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "Open PnL:"; font.pixelSize: 10; color: Theme.textMuted }
                        Item { Layout.fillWidth: true }
                        Text {
                            readonly property double pnl: bot ? bot.profit : 0.0
                            text: (pnl >= 0 ? "$+" : "$-") + Math.abs(pnl).toFixed(2)
                            font.pixelSize: 11
                            font.bold: true
                            font.family: "Consolas"
                            color: pnl >= 0 ? Theme.up : Theme.down
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "Daily PnL:"; font.pixelSize: 10; color: Theme.textMuted }
                        Item { Layout.fillWidth: true }
                        Text {
                            readonly property double dpnl: (bot && bot.stats && bot.stats.net_profit) ? bot.stats.net_profit : 0.0
                            text: (dpnl >= 0 ? "$+" : "$-") + Math.abs(dpnl).toFixed(2)
                            font.pixelSize: 11
                            font.bold: true
                            font.family: "Consolas"
                            color: dpnl >= 0 ? Theme.up : Theme.down
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "Win Rate:"; font.pixelSize: 10; color: Theme.textMuted }
                        Item { Layout.fillWidth: true }
                        Text {
                            readonly property double wr: (bot && bot.stats && bot.stats.win_rate) ? bot.stats.win_rate : 0.0
                            text: wr.toFixed(1) + "%"
                            font.pixelSize: 11
                            font.bold: true
                            font.family: "Consolas"
                            color: Theme.textPrimary
                        }
                    }
                }
            }

            // ================= 8. Card: Momentum Scanner =================
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 96
                radius: Theme.radiusCard
                color: Theme.surfaceAlt
                border.color: Theme.border
                border.width: 1

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 4

                    Text {
                        text: "Momentum Scanner (M5/M15/M30)"
                        font.pixelSize: 10
                        font.bold: true
                        color: Theme.accent
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "Signal:"; font.pixelSize: 10; color: Theme.textMuted }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: "EMA Pullback SELL"
                            font.pixelSize: 10
                            font.bold: true
                            color: Theme.down
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "Source:"; font.pixelSize: 10; color: Theme.textMuted }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: "TF: M5"
                            font.pixelSize: 10
                            color: Theme.textPrimary
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "Trend:"; font.pixelSize: 10; color: Theme.textMuted }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: "M15: Bearish"
                            font.pixelSize: 10
                            color: Theme.down
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        Text { text: "M5 ATR:"; font.pixelSize: 10; color: Theme.textMuted }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: "ATR: 13.74"
                            font.pixelSize: 10
                            font.family: "Consolas"
                            color: Theme.textPrimary
                        }
                    }
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.divider }

            // ================= 9. Engine Status & OTA Footer =================
            RowLayout {
                Layout.fillWidth: true
                Layout.preferredHeight: 28
                spacing: 6

                Rectangle {
                    width: 8
                    height: 8
                    radius: 4
                    color: (bot && bot.connected) ? Theme.up : Theme.down
                }

                Text {
                    text: (bot && bot.connected) ? "IPC: 0.004 ms" : "Terputus"
                    font.pixelSize: 10
                    font.family: "Consolas"
                    color: Theme.textSecondary
                }

                Item { Layout.fillWidth: true }

                // OTA Badge / Tombol Update
                Button {
                    flat: true
                    implicitHeight: 24
                    leftPadding: 6
                    rightPadding: 6
                    icon.source: (updater && updater.updateAvailable) ? "qrc:/assets/download.svg" : "qrc:/assets/refresh.svg"
                    icon.width: 11
                    icon.height: 11
                    icon.color: (updater && updater.updateAvailable) ? Theme.updateGlow : Theme.textMuted
                    text: (updater && updater.updateAvailable) ? ("Update v" + updater.latestVersion) : ("v" + (bot ? bot.appVersion : "1.0.0"))
                    font.pixelSize: 9
                    font.bold: (updater && updater.updateAvailable)
                    onClicked: {
                        if (updater && updater.updateAvailable) {
                            updateDialog.open()
                        } else if (updater) {
                            updater.checkForUpdates(true)
                        }
                    }
                    ToolTip.visible: hovered
                    ToolTip.text: (updater && updater.updateAvailable) ? "Versi baru tersedia! Klik untuk memperbarui." : "Versi saat ini. Klik untuk periksa pembaruan di GitHub."
                }
            }
        }
    }
}
