import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import ".."

// Panel order manual: market & pending order + daftar pending order.
Rectangle {
    id: root
    objectName: "manualTradePanel"
    color: Theme.surface
    radius: 10
    border.color: Theme.border

    readonly property bool botConnected: bot ? bot.connected : false
    // 0=Market Buy,1=Market Sell,2=Buy Limit,3=Sell Limit,4=Buy Stop,5=Sell Stop
    readonly property bool isPending: kindBox.currentIndex >= 2
    readonly property int labelWidth: 95
    readonly property int ctrlHeight: 32

    function submit() {
        var sym = symbolField.text.trim()
        var vol = parseFloat(volumeField.text || "0")
        var sl = parseFloat(slField.text || "0")
        var tp = parseFloat(tpField.text || "0")
        if (isPending) {
            var price = parseFloat(priceField.text || "0")
            var types = ["", "", "buy_limit", "sell_limit", "buy_stop", "sell_stop"]
            bot.placePendingOrder(sym, types[kindBox.currentIndex], vol, price, sl, tp)
        } else {
            var side = (kindBox.currentIndex === 0) ? "buy" : "sell"
            bot.openManualOrder(sym, side, vol, sl, tp)
        }
    }

    Connections {
        target: bot
        function onChartSymbolChanged(sym) {
            if (sym && symbolField) {
                symbolField.text = sym
            }
        }
    }

    ScrollView {
        id: panelScroll
        anchors.fill: parent
        anchors.margins: 10
        clip: true
        ScrollBar.vertical: ThinScrollBar {}
        ScrollBar.horizontal: ThinScrollBar {}

        ColumnLayout {
            width: panelScroll.availableWidth > 0 ? panelScroll.availableWidth : (root.width - 20)
            spacing: 6

            RowLayout {
                spacing: 7
                Image { source: "../../assets/bolt.svg"; sourceSize.width: 16; sourceSize.height: 16 }
                Text { text: "Order Manual"; color: Theme.textPrimary; font.pixelSize: 14; font.bold: true }
            }

            GridLayout {
                Layout.fillWidth: true
                columns: 2
                rowSpacing: 5
                columnSpacing: 10

                Label { text: "Simbol"; color: Theme.textSecondary; Layout.preferredWidth: root.labelWidth }
                CField {
                    id: symbolField
                    Layout.fillWidth: true
                    Layout.preferredHeight: root.ctrlHeight
                    enabled: root.botConnected
                    text: (bot && bot.chartSymbol) ? bot.chartSymbol : "EURUSDm"
                }

                Label { text: "Tipe"; color: Theme.textSecondary; Layout.preferredWidth: root.labelWidth }
                CCombo {
                    id: kindBox
                    Layout.fillWidth: true
                    Layout.preferredHeight: root.ctrlHeight
                    enabled: root.botConnected
                    model: ["Market Buy", "Market Sell", "Buy Limit", "Sell Limit", "Buy Stop", "Sell Stop"]
                }

                Label { text: "Volume (lot)"; color: Theme.textSecondary; Layout.preferredWidth: root.labelWidth }
                CField {
                    id: volumeField
                    Layout.fillWidth: true
                    Layout.preferredHeight: root.ctrlHeight
                    enabled: root.botConnected
                    text: "0.01"
                    inputMethodHints: Qt.ImhFormattedNumbersOnly
                }

                Label { text: "Harga"; color: Theme.textSecondary; opacity: root.isPending ? 1 : 0.4; Layout.preferredWidth: root.labelWidth }
                CField {
                    id: priceField
                    Layout.fillWidth: true
                    Layout.preferredHeight: root.ctrlHeight
                    enabled: root.botConnected && root.isPending
                    placeholderText: root.isPending ? "harga pending" : "(market)"
                    inputMethodHints: Qt.ImhFormattedNumbersOnly
                }

                Label { text: "SL (harga)"; color: Theme.textSecondary; Layout.preferredWidth: root.labelWidth }
                CField {
                    id: slField
                    Layout.fillWidth: true
                    Layout.preferredHeight: root.ctrlHeight
                    enabled: root.botConnected
                    placeholderText: "0 = tanpa SL"
                    inputMethodHints: Qt.ImhFormattedNumbersOnly
                }

                Label { text: "TP (harga)"; color: Theme.textSecondary; Layout.preferredWidth: root.labelWidth }
                CField {
                    id: tpField
                    Layout.fillWidth: true
                    Layout.preferredHeight: root.ctrlHeight
                    enabled: root.botConnected
                    placeholderText: "0 = tanpa TP"
                    inputMethodHints: Qt.ImhFormattedNumbersOnly
                }
            }

            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 34
                visible: root.botConnected && bot && !bot.tradeAllowed
                color: Theme.down
                radius: 4
                opacity: 0.95
                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 6
                    spacing: 6
                    Text {
                        text: "⚠ Algo Trading di MT5 NONAKTIF. Aktifkan di toolbar MT5 (Ctrl+E) agar order dapat dieksekusi."
                        color: "#ffffff"
                        font.pixelSize: 10
                        font.bold: true
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                    }
                }
            }

            Button {
                text: root.isPending ? "Pasang Pending Order" : "Kirim Market Order"
                icon.source: "../../assets/power.svg"; icon.width: 14; icon.height: 14
                Layout.fillWidth: true
                Layout.preferredHeight: 38
                highlighted: root.botConnected
                Material.background: root.botConnected ? Theme.accent : Theme.surfaceAlt
                Material.foreground: "#ffffff"
                font.bold: true
                enabled: root.botConnected
                onClicked: root.submit()
            }

            Text {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                color: Theme.textMuted
                font.pixelSize: 10
                text: "Order butuh terminal tersambung broker (server_connected). Bila tidak, order ditolak otomatis (fail-safe)."
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.divider }

            // ----- Daftar pending order -----
            RowLayout {
                spacing: 7
                Text { text: "Pending Order"; color: Theme.textPrimary; font.pixelSize: 13; font.bold: true }
                Item { Layout.fillWidth: true }
                Text { text: orderModel.count + " order"; color: Theme.textMuted; font.pixelSize: 11 }
            }

            ListView {
                id: orderView
                Layout.fillWidth: true
                Layout.preferredHeight: 150
                clip: true
                model: ListModel { id: orderModel }
                delegate: RowLayout {
                    width: orderView.width; spacing: 6
                    Text { text: model.ticket; color: Theme.textPrimary; font.pixelSize: 11; Layout.preferredWidth: 80 }
                    Text { text: model.symbol; color: Theme.textPrimary; font.pixelSize: 11; Layout.preferredWidth: 70 }
                    Text { text: model.type; color: Theme.textSecondary; font.pixelSize: 11; Layout.fillWidth: true }
                    Text { text: model.price; color: Theme.textPrimary; font.pixelSize: 11; Layout.preferredWidth: 70 }
                    Button {
                        text: "Hapus"
                        icon.source: "../../assets/trash.svg"; icon.width: 12; icon.height: 12
                        Layout.preferredWidth: 78
                        onClicked: bot.deletePendingOrder(model.ticket)
                    }
                }
            }

            Item { Layout.fillHeight: true }
        }
    }

    Connections {
        target: bot
        function onOrdersChanged(orders) {
            orderModel.clear()
            for (var i = 0; i < orders.length; i++)
                orderModel.append(orders[i])
        }
    }
}
