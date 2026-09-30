import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Ringkasan akun ringkas untuk header (binding reaktif).
RowLayout {
    id: root
    spacing: 18

    readonly property bool live: bot ? (bot.connected && bot.serverConnected) : false
    readonly property bool connected: bot ? bot.connected : false

    component Chip: ColumnLayout {
        property string label: ""
        property string value: "-"
        property color valueColor: Theme.textPrimary
        spacing: 0
        Text { text: label; color: Theme.textMuted; font.pixelSize: 10 }
        Text { text: value; color: valueColor; font.pixelSize: 14; font.bold: true }
    }

    // Placeholder saat belum terhubung.
    Text {
        visible: !root.connected
        text: "XAVIQ Trading Engine — belum terhubung ke MT5"
        color: Theme.textMuted
        font.pixelSize: 13
    }

    // Info akun (tampil hanya saat terhubung).
    RowLayout {
        visible: root.connected
        spacing: 18

        Rectangle {
            visible: bot && bot.accountType !== "?"
            radius: 4
            color: {
                if (!bot) return Theme.surface
                if (bot.accountType === "REAL") return Theme.down
                if (bot.accountType === "CONTEST") return "#c9922e"
                return Theme.up
            }
            Layout.preferredHeight: 22
            Layout.preferredWidth: badgeText.implicitWidth + 16
            Text {
                id: badgeText
                anchors.centerIn: parent
                text: bot ? bot.accountType : ""
                color: "#ffffff"; font.pixelSize: 11; font.bold: true
            }
        }

        Chip { label: "Balance"; value: root.live ? (bot.balance.toFixed(2) + " " + bot.currency) : "—" }
        Chip { label: "Equity";  value: root.live ? bot.equity.toFixed(2) : "—" }
        Chip { label: "Margin";  value: root.live ? bot.margin.toFixed(2) : "—" }
        Chip { label: "Free";    value: root.live ? bot.freeMargin.toFixed(2) : "—" }
        Chip {
            label: "Profit"
            value: root.live ? bot.profit.toFixed(2) : "—"
            valueColor: (root.live && bot.profit < 0) ? Theme.down : Theme.up
        }

        RowLayout {
            spacing: 5
            Rectangle { width: 9; height: 9; radius: 5; color: root.live ? Theme.up : "#c9922e" }
            ColumnLayout {
                spacing: 0
                Text { text: "Broker"; color: Theme.textMuted; font.pixelSize: 10 }
                Text {
                    text: root.live ? "Terhubung" : "Menunggu broker"
                    color: root.live ? Theme.up : "#c9922e"
                    font.pixelSize: 12; font.bold: true
                }
            }
        }

        Item {
            implicitWidth: algoRow.implicitWidth
            implicitHeight: algoRow.implicitHeight
            RowLayout {
                id: algoRow
                anchors.fill: parent
                spacing: 5
                Rectangle { width: 9; height: 9; radius: 5; color: (bot && bot.tradeAllowed) ? Theme.up : Theme.down }
                ColumnLayout {
                    spacing: 0
                    Text { text: "Algo Trading"; color: Theme.textMuted; font.pixelSize: 10 }
                    Text {
                        text: (bot && bot.tradeAllowed) ? "Aktif" : "Mati (Ctrl+E)"
                        color: (bot && bot.tradeAllowed) ? Theme.up : Theme.down
                        font.pixelSize: 12; font.bold: true
                    }
                }
            }
            MouseArea { id: algoArea; anchors.fill: parent; hoverEnabled: true }
            ToolTip.visible: algoArea.containsMouse
            ToolTip.text: (bot && bot.tradeAllowed)
                ? "Algo Trading di MT5 aktif. Order otomatis & manual diizinkan."
                : "Tombol 'Algo Trading' di toolbar MT5 nonaktif! Tekan Ctrl+E di MT5."
        }
    }
}
