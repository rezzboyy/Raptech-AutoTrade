import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

// OpenTradesGrid.qml — High-Contrast Data Grid Posisi Terbuka (Active Orders)
// Menampilkan seluruh transaksi yang sedang berjalan dengan aksi tutup per tiket & tutup semua
Rectangle {
    id: root
    color: Theme.bg
    border.color: Theme.border
    border.width: 1

    ListModel { id: posModel }

    Connections {
        target: bot
        function onPositionsChanged(positions) {
            posModel.clear()
            for (var i = 0; i < positions.length; i++) {
                posModel.append(positions[i])
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ================= Header Tabel =================
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 32
            color: Theme.tableHeader
            border.color: Theme.border
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 6

                Text { text: "Ticket"; color: Theme.textMuted; font.pixelSize: 11; font.bold: true; Layout.preferredWidth: 100 }
                Text { text: "Simbol"; color: Theme.textMuted; font.pixelSize: 11; font.bold: true; Layout.preferredWidth: 80 }
                Text { text: "Tipe"; color: Theme.textMuted; font.pixelSize: 11; font.bold: true; Layout.preferredWidth: 60 }
                Text { text: "Lot"; color: Theme.textMuted; font.pixelSize: 11; font.bold: true; horizontalAlignment: Text.AlignRight; Layout.preferredWidth: 50 }
                Text { text: "Open Price"; color: Theme.textMuted; font.pixelSize: 11; font.bold: true; horizontalAlignment: Text.AlignRight; Layout.preferredWidth: 90 }
                Text { text: "SL / TP"; color: Theme.textMuted; font.pixelSize: 11; font.bold: true; horizontalAlignment: Text.AlignHCenter; Layout.preferredWidth: 110 }
                Text { text: "Floating PnL"; color: Theme.textMuted; font.pixelSize: 11; font.bold: true; horizontalAlignment: Text.AlignRight; Layout.fillWidth: true }
                Text { text: "Aksi"; color: Theme.textMuted; font.pixelSize: 11; font.bold: true; horizontalAlignment: Text.AlignHCenter; Layout.preferredWidth: 70 }
            }
        }

        // ================= Data Grid Rows / Empty State =================
        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            // Tampilan saat kosong
            ColumnLayout {
                anchors.centerIn: parent
                spacing: 8
                visible: posModel.count === 0

                Image {
                    source: "qrc:/assets/positions.svg"
                    sourceSize: Qt.size(36, 36)
                    Layout.alignment: Qt.AlignHCenter
                    opacity: 0.4
                }

                Text {
                    text: "Tidak ada posisi terbuka saat ini"
                    font.pixelSize: 13
                    color: Theme.textMuted
                    Layout.alignment: Qt.AlignHCenter
                }

                Text {
                    text: "Gunakan tombol BUY / SELL / HEDGE pada sidebar kiri untuk mengeksekusi order"
                    font.pixelSize: 11
                    color: Theme.textSecondary
                    Layout.alignment: Qt.AlignHCenter
                }
            }

            ListView {
                id: openPosView
                anchors.fill: parent
                clip: true
                visible: posModel.count > 0
                model: posModel
                ScrollBar.vertical: ThinScrollBar {}

                delegate: Rectangle {
                    width: openPosView.width
                    height: 32
                    color: index % 2 === 0 ? Theme.rowEven : Theme.rowOdd

                    readonly property double pnl: model.profit !== undefined ? Number(model.profit) : 0.0
                    readonly property string sideStr: String(model.type || "").toUpperCase()
                    readonly property bool isBuy: sideStr.indexOf("BUY") !== -1

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 12
                        anchors.rightMargin: 12
                        spacing: 6

                        Text {
                            text: String(model.ticket || "")
                            color: Theme.textSecondary
                            font.pixelSize: 11
                            font.family: "Consolas"
                            Layout.preferredWidth: 100
                        }

                        Text {
                            text: String(model.symbol || "")
                            color: Theme.textPrimary
                            font.pixelSize: 11
                            font.bold: true
                            Layout.preferredWidth: 80
                        }

                        // Badge Tipe Order (BUY hijau, SELL merah)
                        Rectangle {
                            Layout.preferredWidth: 50
                            Layout.preferredHeight: 18
                            radius: 3
                            color: isBuy ? Qt.rgba(Theme.up.r, Theme.up.g, Theme.up.b, Theme.isDark ? 0.15 : 0.12)
                                         : Qt.rgba(Theme.down.r, Theme.down.g, Theme.down.b, Theme.isDark ? 0.15 : 0.12)
                            border.color: isBuy ? Theme.up : Theme.down

                            Text {
                                anchors.centerIn: parent
                                text: isBuy ? "BUY" : "SELL"
                                font.pixelSize: 9
                                font.bold: true
                                color: isBuy ? Theme.up : Theme.down
                            }
                        }

                        Text {
                            text: model.volume !== undefined ? Number(model.volume).toFixed(2) : "0.01"
                            color: Theme.textSecondary
                            font.pixelSize: 11
                            font.family: "Consolas"
                            horizontalAlignment: Text.AlignRight
                            Layout.preferredWidth: 50
                        }

                        Text {
                            text: model.price_open !== undefined ? Number(model.price_open).toFixed(2) : "0.00"
                            color: Theme.textPrimary
                            font.pixelSize: 11
                            font.family: "Consolas"
                            horizontalAlignment: Text.AlignRight
                            Layout.preferredWidth: 90
                        }

                        Text {
                            text: (model.sl ? Number(model.sl).toFixed(2) : "-") + " / " + (model.tp ? Number(model.tp).toFixed(2) : "-")
                            color: Theme.textMuted
                            font.pixelSize: 10
                            horizontalAlignment: Text.AlignHCenter
                            Layout.preferredWidth: 110
                        }

                        Text {
                            text: (pnl >= 0 ? "+$" : "-$") + Math.abs(pnl).toFixed(2)
                            color: pnl >= 0 ? Theme.profit : Theme.loss
                            font.pixelSize: 11
                            font.bold: true
                            font.family: "Consolas"
                            horizontalAlignment: Text.AlignRight
                            Layout.fillWidth: true
                        }

                        Button {
                            flat: false
                            text: "Tutup"
                            font.pixelSize: 10
                            implicitHeight: 22
                            Layout.preferredWidth: 60
                            onClicked: {
                                if (bot) bot.closePosition(Number(model.ticket))
                            }
                        }
                    }
                }
            }
        }

        // ================= Summary Footer Bar =================
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 32
            color: Theme.surface
            border.color: Theme.border
            border.width: 1

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 12
                anchors.rightMargin: 12
                spacing: 16

                Text {
                    text: "Total Posisi: " + posModel.count
                    color: Theme.textSecondary
                    font.pixelSize: 11
                }

                Item { Layout.fillWidth: true }

                Text {
                    text: "Total Floating PnL: "
                    color: Theme.textSecondary
                    font.pixelSize: 11
                }

                Text {
                    readonly property double totalProfit: bot ? bot.profit : 0.0
                    text: (totalProfit >= 0 ? "$+" : "$-") + Math.abs(totalProfit).toFixed(2)
                    color: totalProfit >= 0 ? Theme.profit : Theme.loss
                    font.pixelSize: 12
                    font.bold: true
                    font.family: "Consolas"
                }

                Button {
                    text: "Tutup Semua"
                    flat: false
                    implicitHeight: 22
                    font.pixelSize: 10
                    enabled: posModel.count > 0 && (bot ? bot.connected : false)
                    onClicked: {
                        if (bot) bot.closeAllPositions()
                    }
                }
            }
        }
    }
}
