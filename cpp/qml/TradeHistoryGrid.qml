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

    property int selectedIndex: 7 // Default highlight baris sesuai foto referensi pengguna

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

    // Model riwayat transaksi (mendukung data real bot.journal & default sample riwayat)
    ListModel {
        id: historyModel

        Component.onCompleted: {
            // Data awal default sesuai tabel foto referensi pengguna
            append({ time: "20/11 12:01", ticket: "20307485738", source: "M5",   reason: "Momentum Break SELL",   lot: "0.01", closePrice: "3535.81", pnl: -5.98 })
            append({ time: "20/11 10:22", ticket: "20307296688", source: "M5",   reason: "EMA Pullback SELL",     lot: "0.01", closePrice: "3584.33", pnl: 6.32 })
            append({ time: "20/11 10:16", ticket: "20307287822", source: "M5",   reason: "EMA Pullback SELL",     lot: "0.01", closePrice: "3588.62", pnl: 5.89 })
            append({ time: "20/11 10:05", ticket: "20307239658", source: "M5",   reason: "Momentum Break SELL",   lot: "0.01", closePrice: "3584.54", pnl: 1.47 })
            append({ time: "20/11 10:00", ticket: "20307250196", source: "Step", reason: "-50% SL #20307239658",  lot: "0.02", closePrice: "3601.99", pnl: -5.14 })
            append({ time: "20/11 09:45", ticket: "20307221622", source: "M5",   reason: "Momentum Break SELL",   lot: "0.01", closePrice: "3590.16", pnl: 5.27 })
            append({ time: "20/11 09:42", ticket: "20307215298", source: "M5",   reason: "Momentum Break SELL",   lot: "0.01", closePrice: "3598.05", pnl: -5.40 })
            append({ time: "20/11 09:35", ticket: "20307204282", source: "M5",   reason: "EMA Pullback SELL",     lot: "0.01", closePrice: "3607.25", pnl: 4.99 })
            append({ time: "20/11 09:28", ticket: "20307199931", source: "M5",   reason: "Momentum Break SELL",   lot: "0.01", closePrice: "3614.36", pnl: 4.20 })
            append({ time: "20/11 06:19", ticket: "20307063055", source: "M5",   reason: "Momentum Break SELL",   lot: "0.01", closePrice: "3655.26", pnl: 4.66 })
            append({ time: "20/11 05:57", ticket: "20307052134", source: "M5",   reason: "Momentum Break SELL",   lot: "0.01", closePrice: "3660.41", pnl: 4.38 })
            append({ time: "20/11 05:44", ticket: "20307043377", source: "M5",   reason: "EMA Pullback SELL",     lot: "0.01", closePrice: "3663.57", pnl: -4.43 })
            append({ time: "20/11 05:31", ticket: "20307040801", source: "M5",   reason: "EMA Pullback SELL",     lot: "0.01", closePrice: "3664.94", pnl: 4.79 })
            append({ time: "20/11 05:01", ticket: "20307021982", source: "M15",  reason: "Momentum Break SELL",   lot: "0.01", closePrice: "3662.62", pnl: 3.79 })
            append({ time: "20/11 04:49", ticket: "20307008214", source: "M5",   reason: "Momentum Break SELL",   lot: "0.01", closePrice: "3670.67", pnl: 3.79 })
            append({ time: "20/11 04:48", ticket: "20306996327", source: "M15",  reason: "EMA Pullback SELL",     lot: "0.01", closePrice: "3671.19", pnl: 3.91 })
            append({ time: "20/11 04:47", ticket: "20306989190", source: "M5",   reason: "EMA Pullback SELL",     lot: "0.01", closePrice: "3672.22", pnl: 3.64 })
            append({ time: "20/11 04:47", ticket: "20306949761", source: "M15",  reason: "EMA Pullback SELL",     lot: "0.01", closePrice: "3672.60", pnl: -3.51 })
            append({ time: "20/11 04:05", ticket: "20306975102", source: "M5",   reason: "EMA Pullback SELL",     lot: "0.01", closePrice: "3675.15", pnl: -3.79 })
        }
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
                    text: "Win Rate: " + ((bot && bot.stats && bot.stats.win_rate) ? bot.stats.win_rate.toFixed(1) : "73.7") + "%"
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
                            text: "Bersihkan"
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

                Item { Layout.fillWidth: true }

                Text {
                    text: "Net Realized PnL: "
                    color: Theme.textSecondary
                    font.pixelSize: 11
                }

                Text {
                    readonly property double totalPnL: (bot && bot.stats && bot.stats.net_profit) ? bot.stats.net_profit : 97.85
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
