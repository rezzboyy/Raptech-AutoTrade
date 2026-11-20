import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Ringkasan akun komprehensif untuk header dengan ikon SVG dan saldo otomatis terbaca (Flat Clean Header).
RowLayout {
    id: root
    spacing: 16

    readonly property bool live: bot ? (bot.connected && bot.serverConnected) : false
    readonly property bool connected: bot ? bot.connected : false

    // Komponen Chip Metrik Akun Flat tanpa background badge
    component AccountChip: Item {
        property string iconSource: ""
        property string label: ""
        property string value: "—"
        property color valueColor: Theme.textPrimary

        implicitHeight: 38
        implicitWidth: chipRow.implicitWidth + 8

        RowLayout {
            id: chipRow
            anchors.centerIn: parent
            spacing: 7

            Image {
                source: iconSource
                sourceSize: Qt.size(15, 15)
                Layout.preferredWidth: 15
                Layout.preferredHeight: 15
                fillMode: Image.PreserveAspectFit
                opacity: 0.85
            }

            ColumnLayout {
                spacing: 1
                Text {
                    text: label
                    color: Theme.textMuted
                    font.pixelSize: 9
                    font.weight: Font.DemiBold
                    font.letterSpacing: 0.5
                }
                Text {
                    text: value
                    color: valueColor
                    font.pixelSize: 12
                    font.bold: true
                }
            }
        }
    }

    // 1. Identitas Akun & Server (Dengan SVG Account - Flat Clean)
    Item {
        implicitHeight: 38
        implicitWidth: idRow.implicitWidth + 8

        RowLayout {
            id: idRow
            anchors.centerIn: parent
            spacing: 8

            Image {
                source: "qrc:/assets/account.svg"
                sourceSize: Qt.size(16, 16)
                Layout.preferredWidth: 16
                Layout.preferredHeight: 16
                fillMode: Image.PreserveAspectFit
                opacity: 0.9
            }

            // Teks Status (REAL / DEMO / OFFLINE) Flat tanpa background badge
            Text {
                text: {
                    if (!root.connected) return "OFFLINE"
                    if (bot && bot.accountType !== "?") return bot.accountType
                    return "DEMO"
                }
                color: {
                    if (!root.connected) return Theme.textMuted
                    if (bot && bot.accountType === "REAL") return Theme.down
                    if (bot && bot.accountType === "CONTEST") return "#c9922e"
                    return Theme.up
                }
                font.pixelSize: 10
                font.bold: true
            }

            // Login & Server Info
            ColumnLayout {
                spacing: 1
                Text {
                    text: {
                        if (!root.connected) return "MT5 Terputus"
                        if (bot && bot.accountLogin > 0) return "#" + bot.accountLogin
                        return "Akun MT5"
                    }
                    color: root.connected ? Theme.textPrimary : Theme.textMuted
                    font.pixelSize: 11
                    font.bold: true
                }
                Text {
                    text: {
                        if (!root.connected) return "Klik Login"
                        if (bot && bot.accountServer !== "") return bot.accountServer
                        return "Exness MT5"
                    }
                    color: Theme.textMuted
                    font.pixelSize: 9
                    elide: Text.ElideRight
                    Layout.maximumWidth: 120
                }
            }
        }
    }

    Rectangle { Layout.preferredHeight: 18; Layout.preferredWidth: 1; color: Theme.divider }

    // 2. Chip Saldo (Balance) — Otomatis Terbaca
    AccountChip {
        iconSource: "qrc:/assets/wallet.svg"
        label: "SALDO"
        value: root.live ? (bot.balance.toLocaleString(Qt.locale(), 'f', 2) + " " + (bot.currency || "USD")) : (root.connected ? "Membaca..." : "0.00 USD")
        valueColor: root.live ? Theme.textPrimary : Theme.textMuted
    }

    // 3. Chip Equity
    AccountChip {
        iconSource: "qrc:/assets/chart.svg"
        label: "EQUITY"
        value: root.live ? (bot.equity.toLocaleString(Qt.locale(), 'f', 2) + " " + (bot.currency || "USD")) : (root.connected ? "Membaca..." : "0.00 USD")
        valueColor: root.live ? Theme.textPrimary : Theme.textMuted
    }

    // 4. Chip Margin Bebas (Free Margin)
    AccountChip {
        iconSource: "qrc:/assets/shield.svg"
        label: "FREE MARGIN"
        value: root.live ? (bot.freeMargin.toLocaleString(Qt.locale(), 'f', 2) + " " + (bot.currency || "USD")) : (root.connected ? "Membaca..." : "0.00 USD")
        valueColor: root.live ? Theme.textSecondary : Theme.textMuted
    }

    // 5. Chip Floating P/L (Profit)
    AccountChip {
        iconSource: "qrc:/assets/activity.svg"
        label: "FLOATING P/L"
        value: {
            if (!root.live) return root.connected ? "0.00" : "—"
            var sign = bot.profit > 0 ? "+" : ""
            return sign + bot.profit.toLocaleString(Qt.locale(), 'f', 2) + " " + (bot.currency || "USD")
        }
        valueColor: {
            if (!root.live) return Theme.textMuted
            return bot.profit < 0 ? Theme.down : (bot.profit > 0 ? Theme.up : Theme.textPrimary)
        }
    }

    Rectangle { Layout.preferredHeight: 18; Layout.preferredWidth: 1; color: Theme.divider }

    // 6. Indikator Status Broker (Flat)
    Item {
        implicitHeight: 38
        implicitWidth: brokerRow.implicitWidth + 8

        RowLayout {
            id: brokerRow
            anchors.centerIn: parent
            spacing: 6

            Rectangle {
                width: 8
                height: 8
                radius: 4
                color: root.live ? Theme.up : (root.connected ? "#c9922e" : Theme.down)
            }

            ColumnLayout {
                spacing: 1
                Text { text: "BROKER"; color: Theme.textMuted; font.pixelSize: 9; font.letterSpacing: 0.5 }
                Text {
                    text: root.live ? "Terhubung" : (root.connected ? "Menunggu" : "Offline")
                    color: root.live ? Theme.up : (root.connected ? "#c9922e" : Theme.textMuted)
                    font.pixelSize: 11
                    font.bold: true
                }
            }
        }
    }

    // 7. Indikator Algo Trading MT5 (Flat)
    Item {
        implicitWidth: algoContent.implicitWidth + 8
        implicitHeight: 38

        RowLayout {
            id: algoContent
            anchors.centerIn: parent
            spacing: 6

            Image {
                source: "qrc:/assets/bolt.svg"
                sourceSize: Qt.size(14, 14)
                Layout.preferredWidth: 14
                Layout.preferredHeight: 14
                fillMode: Image.PreserveAspectFit
                opacity: (!root.connected) ? 0.3 : 1.0
            }

            ColumnLayout {
                spacing: 1
                RowLayout {
                    spacing: 3
                    Text { text: "ALGO TRADING"; color: Theme.textMuted; font.pixelSize: 9; font.letterSpacing: 0.5 }
                    Text { text: "🔍"; font.pixelSize: 8; opacity: 0.7 }
                }
                Text {
                    text: {
                        if (!root.connected) return "Offline"
                        if (bot && bot.tradeBlocked) return "Ditolak MT5"
                        if (bot && !bot.tradeAllowed) return "Mati (Ctrl+E)"
                        return "Aktif"
                    }
                    color: {
                        if (!root.connected) return Theme.textMuted
                        if (bot && bot.tradeBlocked) return Theme.down
                        if (bot && !bot.tradeAllowed) return "#c9922e"
                        return Theme.up
                    }
                    font.pixelSize: 11
                    font.bold: true
                }
            }
        }

        MouseArea {
            id: algoArea
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: Qt.PointingHandCursor
            onClicked: {
                if (typeof algoVerificationDialog !== "undefined" && algoVerificationDialog)
                    algoVerificationDialog.openDialog()
            }
        }
        ToolTip.visible: algoArea.containsMouse
        ToolTip.text: {
            if (!root.connected) return "Klik untuk membuka Menu Verifikasi Algo Trading."
            if (bot && bot.tradeBlocked) return "Trading ditolak terminal MT5 ('trading is not permitted'). Klik untuk diagnosa & solusi!"
            if (bot && !bot.tradeAllowed) return "Tombol 'Algo Trading' di MT5 nonaktif (Ctrl+E). Klik untuk verifikasi status."
            return "Algo Trading di MT5 aktif. Klik untuk melihat verifikasi & diagnostik lengkap."
        }
    }
}
