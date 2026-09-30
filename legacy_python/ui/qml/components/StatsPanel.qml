import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// Panel statistik trading (winrate, profit factor, total trade, dsb.)
Rectangle {
    id: root
    objectName: "statsPanel"
    color: Theme.surface
    radius: 10
    border.color: Theme.border

    readonly property var stats: (bot && bot.stats) ? bot.stats : ({
        total_trades: 0, wins: 0, losses: 0, breakeven: 0,
        win_rate: 0.0, profit_factor: 0.0, gross_profit: 0.0,
        gross_loss: 0.0, net_profit: 0.0, avg_profit: 0.0,
        avg_loss: 0.0, max_profit: 0.0, max_loss: 0.0
    })
    readonly property string cur: (bot && bot.currency) ? (" " + bot.currency) : ""

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
            Text {
                visible: subvalue.length > 0
                text: subvalue
                color: Theme.textSecondary
                font.pixelSize: 10
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
            spacing: 8

            RowLayout {
                Layout.fillWidth: true
                spacing: 7
                Image { source: "../../assets/stats.svg"; sourceSize.width: 16; sourceSize.height: 16 }
                Text { text: "Statistik Trading"; color: Theme.textPrimary; font.pixelSize: 14; font.bold: true }
                Item { Layout.fillWidth: true }
                Button {
                    text: "Refresh"
                    flat: true
                    icon.source: "../../assets/refresh.svg"; icon.width: 13; icon.height: 13
                    enabled: bot ? bot.connected : false
                    onClicked: bot.refreshStats()
                }
            }

            Text {
                text: "Riwayat akun MT5 (90 hari terakhir)"
                color: Theme.textMuted
                font.pixelSize: 10
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.divider }

            // Baris 1: Win Rate & Profit Factor
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                StatCard {
                    title: "WIN RATE"
                    value: (root.stats.win_rate || 0).toFixed(1) + "%"
                    subvalue: (root.stats.wins || 0) + "W / " + (root.stats.losses || 0) + "L"
                    valueColor: (root.stats.win_rate >= 50) ? Theme.up : Theme.warn
                }
                StatCard {
                    title: "PROFIT FACTOR"
                    value: (root.stats.profit_factor || 0).toFixed(2)
                    subvalue: "Gross P/L ratio"
                    valueColor: (root.stats.profit_factor >= 1.5) ? Theme.up : ((root.stats.profit_factor >= 1.0) ? Theme.warn : Theme.down)
                }
            }

            // Baris 2: Net Profit & Total Trades
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                StatCard {
                    title: "NET PROFIT"
                    value: ((root.stats.net_profit || 0) >= 0 ? "+" : "") + (root.stats.net_profit || 0).toFixed(2) + root.cur
                    subvalue: "Termasuk komisi & swap"
                    valueColor: (root.stats.net_profit >= 0) ? Theme.up : Theme.down
                }
                StatCard {
                    title: "TOTAL TRADE"
                    value: String(root.stats.total_trades || 0)
                    subvalue: (root.stats.breakeven || 0) + " Break-Even"
                }
            }

            // Baris 3: Gross Profit & Gross Loss
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                StatCard {
                    title: "GROSS PROFIT"
                    value: "+" + (root.stats.gross_profit || 0).toFixed(2) + root.cur
                    valueColor: Theme.up
                }
                StatCard {
                    title: "GROSS LOSS"
                    value: "-" + (root.stats.gross_loss || 0).toFixed(2) + root.cur
                    valueColor: Theme.down
                }
            }

            // Baris 4: Avg Profit & Avg Loss
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                StatCard {
                    title: "RATA-RATA WIN"
                    value: "+" + (root.stats.avg_profit || 0).toFixed(2) + root.cur
                    valueColor: Theme.up
                }
                StatCard {
                    title: "RATA-RATA LOSS"
                    value: "-" + (root.stats.avg_loss || 0).toFixed(2) + root.cur
                    valueColor: Theme.down
                }
            }

            // Baris 5: Max Win & Max Loss
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                StatCard {
                    title: "TRADE TERBAIK"
                    value: "+" + (root.stats.max_profit || 0).toFixed(2) + root.cur
                    valueColor: Theme.up
                }
                StatCard {
                    title: "TRADE TERBURUK"
                    value: (root.stats.max_loss || 0).toFixed(2) + root.cur
                    valueColor: Theme.down
                }
            }

            Item { Layout.fillHeight: true }
        }
    }
}
