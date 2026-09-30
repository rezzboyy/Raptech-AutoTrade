import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

// Panel statistik trading (winrate, profit factor, dsb).
Rectangle {
    id: root
    color: Theme.surface
    radius: 10
    border.color: Theme.border

    readonly property var stats: (bot && bot.stats) ? bot.stats : ({})
    readonly property string cur: (bot && bot.currency) ? (" " + bot.currency) : ""

    function num(k) { var v = root.stats[k]; return v === undefined ? 0 : v }

    component StatCard: Rectangle {
        property string title: ""
        property string value: "—"
        property string subvalue: ""
        property color valueColor: Theme.textPrimary
        Layout.fillWidth: true
        Layout.preferredHeight: subvalue ? 58 : 50
        color: Theme.surfaceAlt
        radius: 8
        border.color: Theme.border
        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 8
            spacing: 2
            Text { text: title; color: Theme.textMuted; font.pixelSize: 10; font.bold: true }
            Text { text: value; color: valueColor; font.pixelSize: 15; font.bold: true }
            Text { visible: subvalue.length > 0; text: subvalue; color: Theme.textSecondary; font.pixelSize: 10 }
        }
    }

    ScrollView {
        id: panelScroll
        anchors.fill: parent
        anchors.margins: 10
        clip: true
        ScrollBar.vertical: ThinScrollBar {}

        ColumnLayout {
            width: panelScroll.availableWidth > 0 ? panelScroll.availableWidth : (root.width - 20)
            spacing: 8

            RowLayout {
                Layout.fillWidth: true
                spacing: 7
                Image { source: "qrc:/assets/stats.svg"; sourceSize.width: 16; sourceSize.height: 16 }
                Text { text: "Statistik Trading"; color: Theme.textPrimary; font.pixelSize: 14; font.bold: true }
                Item { Layout.fillWidth: true }
                CButton { text: "Refresh"; icon.source: "qrc:/assets/refresh.svg"; icon.width: 13; icon.height: 13; font.pixelSize: 11; Layout.preferredHeight: 28; enabled: bot ? bot.connected : false; onClicked: bot.refreshStats() }
            }
            Text { text: "Riwayat akun MT5 (90 hari terakhir)"; color: Theme.textMuted; font.pixelSize: 10 }
            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.divider }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                StatCard { title: "WIN RATE"; value: root.num("win_rate").toFixed(1) + "%"; subvalue: root.num("wins") + "W / " + root.num("losses") + "L"; valueColor: root.num("win_rate") >= 50 ? Theme.up : Theme.warn }
                StatCard { title: "PROFIT FACTOR"; value: root.num("profit_factor").toFixed(2); subvalue: "Gross P/L ratio"; valueColor: root.num("profit_factor") >= 1.5 ? Theme.up : (root.num("profit_factor") >= 1.0 ? Theme.warn : Theme.down) }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                StatCard { title: "NET PROFIT"; value: (root.num("net_profit") >= 0 ? "+" : "") + root.num("net_profit").toFixed(2) + root.cur; subvalue: "Termasuk komisi & swap"; valueColor: root.num("net_profit") >= 0 ? Theme.up : Theme.down }
                StatCard { title: "TOTAL TRADE"; value: String(root.num("total_trades")); subvalue: root.num("breakeven") + " Break-Even" }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                StatCard { title: "GROSS PROFIT"; value: "+" + root.num("gross_profit").toFixed(2) + root.cur; valueColor: Theme.up }
                StatCard { title: "GROSS LOSS"; value: "-" + root.num("gross_loss").toFixed(2) + root.cur; valueColor: Theme.down }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                StatCard { title: "RATA-RATA WIN"; value: "+" + root.num("avg_profit").toFixed(2) + root.cur; valueColor: Theme.up }
                StatCard { title: "RATA-RATA LOSS"; value: "-" + root.num("avg_loss").toFixed(2) + root.cur; valueColor: Theme.down }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                StatCard { title: "TRADE TERBAIK"; value: "+" + root.num("max_profit").toFixed(2) + root.cur; valueColor: Theme.up }
                StatCard { title: "TRADE TERBURUK"; value: root.num("max_loss").toFixed(2) + root.cur; valueColor: Theme.down }
            }
            Item { Layout.fillHeight: true }
        }
    }
}
