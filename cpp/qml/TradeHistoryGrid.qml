import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

// TradeHistoryGrid.qml — High-Contrast Data Grid Riwayat Transaksi
// 100% presisi mengikuti tata letak, kolom, dan highlight foto referensi pengguna (Dark Terminal)
Rectangle {
    id: root
    color: Theme.bg
    border.color: Theme.border
    border.width: 1

    property int selectedIndex: -1 // Tidak ada baris terpilih saat riwayat kosong

    // Menu Klik Kanan (Context Menu Trash / Clear)
    Menu {
        id: historyContextMenu
        MenuItem {
            text: "Hapus Baris Ini"
            icon.source: "qrc:/assets/trash.svg"
            onTriggered: {
                if (root.selectedIndex >= 0 && root.selectedIndex < historyModel.count) {
                    historyModel.remove(root.selectedIndex)
                }
            }
        }
        MenuItem {
            text: "Bersihkan Semua Riwayat"
            icon.source: "qrc:/assets/trash.svg"
            onTriggered: {
                if (bot) bot.clearJournal()
                historyModel.clear()
            }
        }
    }

    // Model riwayat transaksi (dimuat murni dari bot.journal & transaksi real broker)
    ListModel {
        id: historyModel
    }

    Connections {
        target: bot
        function onJournalEntry(entry) {
            if (entry && entry.action && entry.action.indexOf("CLOSE") !== -1) {
                historyModel.insert(0, {
                    time: entry.time || "",
                    ticket: String(entry.ticket || ""),
                    source: "Bot",
                    reason: entry.action + (entry.details ? " " + entry.details : ""),
                    lot: entry.volume ? Number(entry.volume).toFixed(2) : "0.01",
                    closePrice: entry.price ? Number(entry.price).toFixed(2) : "0.00",
                    pnl: entry.profit ? Number(entry.profit) : 0.0
                })
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ================= Header Tabel (Slate Navy) =================
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 32
            color: "#101622"
            border.color: Theme.border
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 6

                Text { text: "Time"; color: Theme.textMuted; font.pixelSize: 11; font.bold: true; Layout.preferredWidth: 110 }
                Text { text: "Ticket"; color: Theme.textMuted; font.pixelSize: 11; font.bold: true; Layout.preferredWidth: 110 }
                Text { text: "Source"; color: Theme.textMuted; font.pixelSize: 11; font.bold: true; Layout.preferredWidth: 70 }
                Text { text: "Reason"; color: Theme.textMuted; font.pixelSize: 11; font.bold: true; Layout.fillWidth: true }
                Text { text: "Lot"; color: Theme.textMuted; font.pixelSize: 11; font.bold: true; horizontalAlignment: Text.AlignRight; Layout.preferredWidth: 60 }
                Text { text: "Close Price"; color: Theme.textMuted; font.pixelSize: 11; font.bold: true; horizontalAlignment: Text.AlignRight; Layout.preferredWidth: 100 }
                Text { text: "Profit / Loss"; color: Theme.textMuted; font.pixelSize: 11; font.bold: true; horizontalAlignment: Text.AlignRight; Layout.preferredWidth: 100 }
            }
        }

        // ================= Data Grid Rows =================
        ListView {
            id: gridView
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: historyModel
            ScrollBar.vertical: ThinScrollBar {}

            Text {
                anchors.centerIn: parent
                visible: historyModel.count === 0
                text: "Belum ada riwayat transaksi."
                color: Theme.textMuted
                font.pixelSize: 12
            }

            delegate: Rectangle {
                id: rowDelegate
                width: gridView.width
                height: 28
                color: {
                    if (index === root.selectedIndex) return Theme.selectedRow
                    if (rowMouseArea.containsMouse) return Theme.surfaceHighlight
                    return index % 2 === 0 ? "#0B0E14" : "#0E121A"
                }

                readonly property bool isSelected: index === root.selectedIndex
                readonly property double profitVal: model.pnl !== undefined ? Number(model.pnl) : 0.0

                MouseArea {
                    id: rowMouseArea
                    anchors.fill: parent
                    hoverEnabled: true
                    acceptedButtons: Qt.LeftButton | Qt.RightButton
                    cursorShape: Qt.PointingHandCursor
                    onClicked: function(mouse) {
                        root.selectedIndex = index
                        if (mouse.button === Qt.RightButton) {
                            historyContextMenu.popup()
                        }
                    }
                }

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 12
                    anchors.rightMargin: 12
                    spacing: 6

                    Text {
                        text: model.time
                        color: isSelected ? "#FFFFFF" : Theme.textSecondary
                        font.pixelSize: 11
                        font.family: "Consolas"
                        Layout.preferredWidth: 110
                    }

                    Text {
                        text: model.ticket
                        color: isSelected ? "#FFFFFF" : Theme.textSecondary
                        font.pixelSize: 11
                        font.family: "Consolas"
                        Layout.preferredWidth: 110
                    }

                    Text {
                        text: model.source
                        color: isSelected ? "#FFFFFF" : Theme.textMuted
                        font.pixelSize: 11
                        Layout.preferredWidth: 70
                    }

                    Text {
                        text: model.reason
                        color: isSelected ? "#FFFFFF" : Theme.textPrimary
                        font.pixelSize: 11
                        font.bold: isSelected
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }

                    Text {
                        text: model.lot
                        color: isSelected ? "#FFFFFF" : Theme.textSecondary
                        font.pixelSize: 11
                        font.family: "Consolas"
                        horizontalAlignment: Text.AlignRight
                        Layout.preferredWidth: 60
                    }

                    Text {
                        text: model.closePrice
                        color: isSelected ? "#FFFFFF" : Theme.textPrimary
                        font.pixelSize: 11
                        font.family: "Consolas"
                        horizontalAlignment: Text.AlignRight
                        Layout.preferredWidth: 100
                    }

                    Text {
                        text: (profitVal >= 0 ? "+" : "") + profitVal.toFixed(2)
                        color: {
                            if (isSelected) return "#FFFFFF"
                            return profitVal >= 0 ? Theme.profit : Theme.loss
                        }
                        font.pixelSize: 11
                        font.bold: true
                        font.family: "Consolas"
                        horizontalAlignment: Text.AlignRight
                        Layout.preferredWidth: 100
                    }
                }
            }
        }

        // ================= Summary Footer Bar =================
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 32
            color: "#0E121A"
            border.color: Theme.border
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 16

                Text {
                    text: "Total Trades: " + historyModel.count
                    color: Theme.textSecondary
                    font.pixelSize: 11
                }

                Text {
                    text: "Win Rate: " + ((bot && bot.stats && bot.stats.win_rate !== undefined) ? Number(bot.stats.win_rate).toFixed(1) : "0.0") + "%"
                    color: Theme.textSecondary
                    font.pixelSize: 11
                }

                // Tombol Trash Bersihkan Riwayat
                Rectangle {
                    Layout.preferredHeight: 22
                    Layout.preferredWidth: clearBtnContent.implicitWidth + 14
                    radius: 4
                    color: trashMouse.containsMouse ? "#331616" : Theme.surfaceAlt
                    border.color: trashMouse.containsMouse ? Theme.down : Theme.divider
                    border.width: 1

                    RowLayout {
                        id: clearBtnContent
                        anchors.centerIn: parent
                        spacing: 5

                        Image {
                            source: "qrc:/assets/trash.svg"
                            sourceSize: Qt.size(11, 11)
                            Layout.preferredWidth: 11
                            Layout.preferredHeight: 11
                            opacity: historyModel.count > 0 ? (trashMouse.containsMouse ? 1.0 : 0.75) : 0.3
                        }

                        Text {
                            text: "Bersihkan Riwayat"
                            color: historyModel.count > 0 ? (trashMouse.containsMouse ? Theme.down : Theme.textSecondary) : Theme.textMuted
                            font.pixelSize: 10
                            font.bold: true
                        }
                    }

                    MouseArea {
                        id: trashMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: historyModel.count > 0 ? Qt.PointingHandCursor : Qt.ArrowCursor
                        enabled: historyModel.count > 0
                        onClicked: {
                            if (bot) bot.clearJournal()
                            historyModel.clear()
                        }
                    }

                    ToolTip.visible: trashMouse.containsMouse
                    ToolTip.text: "Hapus seluruh catatan riwayat transaksi (Clear History)"
                }

                // Tombol Reset Stats
                Rectangle {
                    Layout.preferredHeight: 22
                    Layout.preferredWidth: resetStatsBtnContent.implicitWidth + 14
                    radius: 4
                    color: resetStatsMouse.containsMouse ? "#1E293B" : Theme.surfaceAlt
                    border.color: resetStatsMouse.containsMouse ? Theme.accent : Theme.divider
                    border.width: 1

                    RowLayout {
                        id: resetStatsBtnContent
                        anchors.centerIn: parent
                        spacing: 5

                        Image {
                            source: "qrc:/assets/refresh.svg"
                            sourceSize: Qt.size(11, 11)
                            Layout.preferredWidth: 11
                            Layout.preferredHeight: 11
                            opacity: resetStatsMouse.containsMouse ? 1.0 : 0.75
                        }

                        Text {
                            text: "Reset Stats"
                            color: resetStatsMouse.containsMouse ? Theme.accent : Theme.textSecondary
                            font.pixelSize: 10
                            font.bold: true
                        }
                    }

                    MouseArea {
                        id: resetStatsMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: {
                            if (bot) bot.resetStats()
                        }
                    }

                    ToolTip.visible: resetStatsMouse.containsMouse
                    ToolTip.text: "Reset seluruh statistik performa (Win Rate, Daily PnL, Total Trades) ke 0"
                }

                Item { Layout.fillWidth: true }

                Text {
                    text: "Net Realized PnL: "
                    color: Theme.textSecondary
                    font.pixelSize: 11
                }

                Text {
                    readonly property double totalPnL: (bot && bot.stats && bot.stats.net_profit !== undefined) ? Number(bot.stats.net_profit) : 0.0
                    text: (totalPnL >= 0 ? "$+" : "$-") + Math.abs(totalPnL).toFixed(2)
                    color: totalPnL >= 0 ? Theme.profit : Theme.loss
                    font.pixelSize: 12
                    font.bold: true
                    font.family: "Consolas"
                }
            }
        }
    }
}
