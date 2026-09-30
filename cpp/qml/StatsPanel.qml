import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

// Panel statistik trading (winrate, profit factor, distribusi trade, dsb).
Rectangle {
    id: root
    color: Theme.surface
    radius: 10
    border.color: Theme.border

    property var statsSource: (bot && bot.stats) ? bot.stats : ({})
    property string currencySource: (bot && bot.currency) ? (" " + bot.currency) : ""

    readonly property var stats: statsSource ? statsSource : ({})
    readonly property string cur: currencySource

    function num(k) {
        var v = root.stats[k];
        return (v === undefined || isNaN(v)) ? 0 : v;
    }

    readonly property int totalTrades: root.num("total_trades")
    readonly property int wins: root.num("wins")
    readonly property int losses: root.num("losses")
    readonly property int be: root.num("breakeven")
    readonly property double winRate: root.num("win_rate")
    readonly property double pf: root.num("profit_factor")
    readonly property double netProfit: root.num("net_profit")
    readonly property double grossProfit: root.num("gross_profit")
    readonly property double grossLoss: root.num("gross_loss")
    readonly property double avgProfit: root.num("avg_profit")
    readonly property double avgLoss: root.num("avg_loss")
    readonly property double maxProfit: root.num("max_profit")
    readonly property double maxLoss: root.num("max_loss")

    // Helper format uang & tanda (bebas dari -0.00 atau +0.00 palsu)
    function fmtMoney(val, forcePlus) {
        if (Math.abs(val) < 0.0001) return "0.00" + root.cur;
        var s = val > 0 ? (forcePlus ? "+" : "") : "-";
        return s + Math.abs(val).toFixed(2) + root.cur;
    }

    // Helper warna profit/loss (netral saat belum ada trade / nilai 0)
    function moneyColor(val) {
        if (root.totalTrades === 0 || Math.abs(val) < 0.0001) return Theme.textPrimary;
        return val > 0 ? Theme.up : Theme.down;
    }

    // Kartu Metrik Utama (Hero Card)
    component HeroCard: Rectangle {
        property string title: ""
        property string value: "—"
        property string subtitle: ""
        property color valueColor: Theme.textPrimary
        property color accentBarColor: "transparent"

        Layout.fillWidth: true
        Layout.preferredHeight: 74
        color: Theme.surfaceAlt
        radius: 8
        border.color: Theme.border
        border.width: 1

        Rectangle {
            visible: accentBarColor !== "transparent"
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: 3
            radius: 2
            color: accentBarColor
        }

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 10
            anchors.leftMargin: accentBarColor !== "transparent" ? 14 : 10
            spacing: 3

            Text {
                text: title
                color: Theme.textMuted
                font.pixelSize: 10
                font.bold: true
                font.letterSpacing: 0.5
            }
            Text {
                text: value
                color: valueColor
                font.pixelSize: 17
                font.bold: true
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
            Text {
                text: subtitle
                color: Theme.textSecondary
                font.pixelSize: 10
                elide: Text.ElideRight
                Layout.fillWidth: true
            }
        }
    }

    // Baris rincian di dalam kartu grup
    component DetailRow: RowLayout {
        property string label: ""
        property string valText: ""
        property color valColor: Theme.textPrimary
        property color dotColor: "transparent"

        Layout.fillWidth: true
        spacing: 6

        Rectangle {
            width: 6
            height: 6
            radius: 3
            color: dotColor
            visible: dotColor !== "transparent"
            Layout.alignment: Qt.AlignVCenter
        }

        Text {
            text: label
            color: Theme.textSecondary
            font.pixelSize: 11
            Layout.fillWidth: true
            elide: Text.ElideRight
        }

        Text {
            text: valText
            color: valColor
            font.pixelSize: 11
            font.bold: true
        }
    }

    ScrollView {
        id: panelScroll
        anchors.fill: parent
        anchors.margins: 10
        clip: true
        ScrollBar.vertical: ThinScrollBar {}

        ColumnLayout {
            width: panelScroll.width - (panelScroll.ScrollBar.vertical.visible ? 10 : 0)
            spacing: 10

            // ================= HEADER =================
            RowLayout {
                Layout.fillWidth: true
                spacing: 6

                Image {
                    source: "qrc:/assets/stats.svg"
                    sourceSize.width: 15
                    sourceSize.height: 15
                    Layout.alignment: Qt.AlignVCenter
                }
                Text {
                    text: "Statistik Trading"
                    color: Theme.textPrimary
                    font.pixelSize: 13
                    font.bold: true
                    Layout.alignment: Qt.AlignVCenter
                }
                Rectangle {
                    color: Theme.surfaceAlt
                    radius: 4
                    Layout.preferredHeight: 18
                    Layout.preferredWidth: badgeText.implicitWidth + 8
                    Layout.alignment: Qt.AlignVCenter
                    Text {
                        id: badgeText
                        anchors.centerIn: parent
                        text: "90 Hari"
                        color: Theme.textMuted
                        font.pixelSize: 9
                        font.bold: true
                    }
                }
                Item { Layout.fillWidth: true }
                CButton {
                    text: "Refresh"
                    icon.source: "qrc:/assets/refresh.svg"
                    icon.width: 12
                    icon.height: 12
                    font.pixelSize: 10
                    Layout.preferredHeight: 24
                    leftPadding: 8
                    rightPadding: 8
                    enabled: bot ? bot.connected : false
                    ToolTip.visible: hovered
                    ToolTip.text: "Perbarui data statistik dari terminal MT5"
                    onClicked: bot.refreshStats()
                }
            }

            Rectangle { Layout.fillWidth: true; height: 1; color: Theme.divider }

            // ================= 4 HERO CARDS =================
            GridLayout {
                Layout.fillWidth: true
                columns: 2
                rowSpacing: 8
                columnSpacing: 8

                // 1. Net Profit
                HeroCard {
                    title: "NET PROFIT"
                    value: root.fmtMoney(root.netProfit, true)
                    subtitle: root.totalTrades === 0 ? "Termasuk komisi & swap"
                            : (root.netProfit > 0 ? "Akun bertumbuh (net profit)"
                            : (root.netProfit < 0 ? "Mengalami penurunan bersih" : "Impas (Break-even)"))
                    valueColor: root.moneyColor(root.netProfit)
                    accentBarColor: root.totalTrades === 0 ? "transparent" : (root.netProfit >= 0 ? Theme.up : Theme.down)
                }

                // 2. Win Rate
                HeroCard {
                    title: "WIN RATE"
                    value: root.winRate.toFixed(1) + "%"
                    subtitle: root.totalTrades === 0 ? "0W • 0L • 0BE"
                            : (root.wins + "W • " + root.losses + "L • " + root.be + "BE")
                    valueColor: root.totalTrades === 0 ? Theme.textPrimary : (root.winRate >= 50.0 ? Theme.up : Theme.warn)
                    accentBarColor: root.totalTrades === 0 ? "transparent" : (root.winRate >= 50.0 ? Theme.up : Theme.warn)
                }

                // 3. Profit Factor
                HeroCard {
                    title: "PROFIT FACTOR"
                    value: root.pf.toFixed(2)
                    subtitle: root.totalTrades === 0 ? "Gross P/L ratio"
                            : (root.pf >= 2.0 ? "Performa Sangat Kuat"
                            : (root.pf >= 1.5 ? "Bagus & Konsisten"
                            : (root.pf >= 1.0 ? "Moderat (Waspada)" : "Perlu Evaluasi Strategi")))
                    valueColor: root.totalTrades === 0 ? Theme.textPrimary : (root.pf >= 1.5 ? Theme.up : (root.pf >= 1.0 ? Theme.warn : Theme.down))
                    accentBarColor: root.totalTrades === 0 ? "transparent" : (root.pf >= 1.5 ? Theme.up : (root.pf >= 1.0 ? Theme.warn : Theme.down))
                }

                // 4. Total Trades
                HeroCard {
                    title: "TOTAL TRADES"
                    value: String(root.totalTrades)
                    subtitle: root.totalTrades === 0 ? "Belum ada trade closed"
                            : (root.wins + " Menang (" + root.winRate.toFixed(0) + "%)")
                    valueColor: Theme.textPrimary
                    accentBarColor: root.totalTrades === 0 ? "transparent" : Theme.border
                }
            }

            // ================= VISUAL RATIO BAR =================
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 38
                color: Theme.surfaceAlt
                radius: 8
                border.color: Theme.border
                border.width: 1

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 4

                    // Progress bar
                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 6
                        radius: 3
                        color: Theme.divider
                        clip: true

                        Row {
                            anchors.fill: parent
                            spacing: 0
                            Rectangle {
                                width: root.totalTrades > 0 ? (parent.width * (root.wins / root.totalTrades)) : 0
                                height: parent.height
                                color: Theme.up
                            }
                            Rectangle {
                                width: root.totalTrades > 0 ? (parent.width * (root.be / root.totalTrades)) : 0
                                height: parent.height
                                color: Theme.warn
                            }
                            Rectangle {
                                width: root.totalTrades > 0 ? (parent.width * (root.losses / root.totalTrades)) : 0
                                height: parent.height
                                color: Theme.down
                            }
                        }
                    }

                    // Teks Rasio
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 8
                        Text {
                            text: "● Menang: " + root.wins + (root.totalTrades > 0 ? (" (" + Math.round(root.wins * 100 / root.totalTrades) + "%)") : "")
                            color: root.wins > 0 ? Theme.up : Theme.textMuted
                            font.pixelSize: 10
                        }
                        Text {
                            text: "● BE: " + root.be
                            color: root.be > 0 ? Theme.warn : Theme.textMuted
                            font.pixelSize: 10
                        }
                        Text {
                            text: "● Kalah: " + root.losses + (root.totalTrades > 0 ? (" (" + Math.round(root.losses * 100 / root.totalTrades) + "%)") : "")
                            color: root.losses > 0 ? Theme.down : Theme.textMuted
                            font.pixelSize: 10
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: root.totalTrades === 0 ? "Belum ada riwayat order" : (root.totalTrades + " selesai")
                            color: Theme.textMuted
                            font.pixelSize: 10
                        }
                    }
                }
            }

            // ================= RINCIAN KEUNTUNGAN & KERUGIAN =================
            GridLayout {
                Layout.fillWidth: true
                columns: 2
                rowSpacing: 8
                columnSpacing: 8

                // Grup Keuntungan
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 110
                    color: Theme.surfaceAlt
                    radius: 8
                    border.color: Theme.border
                    border.width: 1

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 6

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 4
                            Rectangle { width: 3; height: 12; radius: 1.5; color: Theme.up }
                            Text {
                                text: "Performa Keuntungan"
                                color: Theme.textPrimary
                                font.pixelSize: 11
                                font.bold: true
                            }
                        }

                        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.divider }

                        DetailRow {
                            label: "Gross Profit"
                            valText: root.fmtMoney(root.grossProfit, true)
                            valColor: root.totalTrades > 0 && root.grossProfit > 0 ? Theme.up : Theme.textPrimary
                            dotColor: Theme.up
                        }
                        DetailRow {
                            label: "Rata-rata Win"
                            valText: root.fmtMoney(root.avgProfit, true)
                            valColor: root.totalTrades > 0 && root.avgProfit > 0 ? Theme.up : Theme.textPrimary
                            dotColor: Theme.up
                        }
                        DetailRow {
                            label: "Trade Terbaik"
                            valText: root.fmtMoney(root.maxProfit, true)
                            valColor: root.totalTrades > 0 && root.maxProfit > 0 ? Theme.up : Theme.textPrimary
                            dotColor: Theme.up
                        }
                    }
                }

                // Grup Kerugian & Risiko
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 110
                    color: Theme.surfaceAlt
                    radius: 8
                    border.color: Theme.border
                    border.width: 1

                    ColumnLayout {
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 6

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 4
                            Rectangle { width: 3; height: 12; radius: 1.5; color: Theme.down }
                            Text {
                                text: "Risiko & Kerugian"
                                color: Theme.textPrimary
                                font.pixelSize: 11
                                font.bold: true
                            }
                        }

                        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.divider }

                        DetailRow {
                            label: "Gross Loss"
                            valText: root.fmtMoney(root.grossLoss > 0 ? -root.grossLoss : 0, false)
                            valColor: root.totalTrades > 0 && root.grossLoss > 0 ? Theme.down : Theme.textPrimary
                            dotColor: Theme.down
                        }
                        DetailRow {
                            label: "Rata-rata Loss"
                            valText: root.fmtMoney(root.avgLoss > 0 ? -root.avgLoss : 0, false)
                            valColor: root.totalTrades > 0 && root.avgLoss > 0 ? Theme.down : Theme.textPrimary
                            dotColor: Theme.down
                        }
                        DetailRow {
                            label: "Trade Terburuk"
                            valText: root.fmtMoney(root.maxLoss < 0 ? root.maxLoss : (root.maxLoss > 0 ? -root.maxLoss : 0), false)
                            valColor: root.totalTrades > 0 && Math.abs(root.maxLoss) > 0.0001 ? Theme.down : Theme.textPrimary
                            dotColor: Theme.down
                        }
                    }
                }
            }

            // ================= RINGKASAN METRIK TAMBAHAN =================
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 46
                color: Theme.surfaceAlt
                radius: 8
                border.color: Theme.border
                border.width: 1

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    spacing: 12

                    // Win / Loss Payoff Ratio
                    ColumnLayout {
                        spacing: 1
                        Layout.fillWidth: true
                        Text { text: "PAYOFF RATIO"; color: Theme.textMuted; font.pixelSize: 9; font.bold: true }
                        Text {
                            text: (root.totalTrades > 0 && root.avgLoss > 0.0001)
                                ? (root.avgProfit / root.avgLoss).toFixed(2) + " : 1"
                                : "—"
                            color: Theme.textPrimary
                            font.pixelSize: 12
                            font.bold: true
                        }
                    }

                    Rectangle { width: 1; height: 24; color: Theme.divider }

                    // Expected Payoff (Expectancy)
                    ColumnLayout {
                        spacing: 1
                        Layout.fillWidth: true
                        Text { text: "EXPECTED PAYOFF"; color: Theme.textMuted; font.pixelSize: 9; font.bold: true }
                        Text {
                            text: root.totalTrades > 0
                                ? root.fmtMoney(root.netProfit / root.totalTrades, true)
                                : "—"
                            color: root.totalTrades > 0 ? root.moneyColor(root.netProfit) : Theme.textPrimary
                            font.pixelSize: 12
                            font.bold: true
                        }
                    }

                    Rectangle { width: 1; height: 24; color: Theme.divider }

                    // Status Trading
                    ColumnLayout {
                        spacing: 1
                        Layout.fillWidth: true
                        Text { text: "EVALUASI"; color: Theme.textMuted; font.pixelSize: 9; font.bold: true }
                        Text {
                            text: root.totalTrades === 0 ? "Belum Ada Data"
                                : (root.netProfit > 0 && root.pf >= 1.5 ? "Menguntungkan"
                                : (root.netProfit >= 0 ? "Impas / Netral" : "Perlu Optimasi"))
                            color: root.totalTrades === 0 ? Theme.textMuted
                                 : (root.netProfit > 0 && root.pf >= 1.5 ? Theme.up : (root.netProfit >= 0 ? Theme.warn : Theme.down))
                            font.pixelSize: 12
                            font.bold: true
                            elide: Text.ElideRight
                        }
                    }
                }
            }

            Item { Layout.preferredHeight: 6 }
        }
    }
}
