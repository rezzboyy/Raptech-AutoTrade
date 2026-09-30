import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import QtQuick.Dialogs
import "."

// Panel Jurnal Aksi Trading: menampilkan log aksi real-time (order, sinyal, close, modify)
Rectangle {
    id: root
    color: Theme.surface
    radius: 10
    border.color: Theme.border

    property var journalEntries: bot ? bot.journal : []

    Connections {
        target: bot
        function onJournalChanged() {
            root.journalEntries = bot ? bot.journal : []
        }
        function onJournalEntry(entry) {
            root.journalEntries = bot ? bot.journal : []
        }
    }

    FileDialog {
        id: saveCsvDialog
        title: "Ekspor Jurnal ke CSV"
        fileMode: FileDialog.SaveFile
        nameFilters: ["CSV (*.csv)", "Semua File (*.*)"]
        defaultSuffix: "csv"
        onAccepted: {
            if (bot) {
                var path = selectedFile.toString()
                bot.exportJournalCsv(path)
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 8

        // Header
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            Image { source: "qrc:/assets/activity.svg"; sourceSize.width: 16; sourceSize.height: 16 }
            Text {
                text: "Jurnal Aksi Trading"
                color: Theme.textPrimary
                font.pixelSize: 14
                font.bold: true
            }

            Rectangle {
                color: Theme.surfaceAlt
                radius: 4
                Layout.preferredHeight: 20
                Layout.preferredWidth: countText.implicitWidth + 12
                Text {
                    id: countText
                    anchors.centerIn: parent
                    text: root.journalEntries.length + " aksi"
                    color: Theme.textSecondary
                    font.pixelSize: 10
                    font.bold: true
                }
            }

            Item { Layout.fillWidth: true }

            CButton {
                text: "Ekspor CSV"
                icon.source: "qrc:/assets/save.svg"
                icon.width: 13; icon.height: 13
                Layout.preferredHeight: 28
                enabled: root.journalEntries.length > 0
                onClicked: saveCsvDialog.open()
            }

            CButton {
                text: "Bersihkan"
                icon.source: "qrc:/assets/trash.svg"
                icon.width: 13; icon.height: 13
                Layout.preferredHeight: 28
                enabled: root.journalEntries.length > 0
                onClicked: if (bot) bot.clearJournal()
            }
        }

        // Table Header
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 26
            color: Theme.surfaceAlt
            radius: 4

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 6

                Text { text: "Waktu"; color: Theme.textMuted; font.pixelSize: 11; font.bold: true; Layout.preferredWidth: 70 }
                Text { text: "Aksi"; color: Theme.textMuted; font.pixelSize: 11; font.bold: true; Layout.preferredWidth: 60 }
                Text { text: "Simbol"; color: Theme.textMuted; font.pixelSize: 11; font.bold: true; Layout.preferredWidth: 70 }
                Text { text: "Status"; color: Theme.textMuted; font.pixelSize: 11; font.bold: true; Layout.preferredWidth: 50 }
                Text { text: "Detail Transaksi"; color: Theme.textMuted; font.pixelSize: 11; font.bold: true; Layout.fillWidth: true }
            }
        }

        // Table List
        ListView {
            id: journalList
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            model: root.journalEntries
            spacing: 3
            ScrollBar.vertical: ThinScrollBar {}

            delegate: Rectangle {
                width: journalList.width
                height: 28
                color: index % 2 === 0 ? "transparent" : Theme.surfaceAlt
                radius: 3

                readonly property var itemData: modelData || {}
                readonly property string act: String(itemData.action || "").toUpperCase()
                readonly property bool isOk: itemData.ok !== undefined ? itemData.ok : true

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 8
                    anchors.rightMargin: 8
                    spacing: 6

                    Text {
                        text: itemData.time ? itemData.time : ""
                        color: Theme.textSecondary
                        font.pixelSize: 11
                        Layout.preferredWidth: 70
                    }

                    Rectangle {
                        Layout.preferredWidth: 55
                        Layout.preferredHeight: 18
                        radius: 3
                        color: {
                            if (act.indexOf("BUY") >= 0) return Theme.up
                            if (act.indexOf("SELL") >= 0) return Theme.down
                            if (act.indexOf("CLOSE") >= 0) return Theme.warn
                            return Theme.surfaceAlt
                        }
                        Text {
                            anchors.centerIn: parent
                            text: act
                            color: "#ffffff"
                            font.pixelSize: 10
                            font.bold: true
                        }
                    }

                    Text {
                        text: itemData.symbol ? itemData.symbol : "-"
                        color: Theme.textPrimary
                        font.pixelSize: 11
                        font.bold: true
                        Layout.preferredWidth: 70
                    }

                    Rectangle {
                        Layout.preferredWidth: 42
                        Layout.preferredHeight: 18
                        radius: 3
                        color: isOk ? "#1e3a2f" : "#3b1e22"
                        border.color: isOk ? Theme.up : Theme.down
                        Text {
                            anchors.centerIn: parent
                            text: isOk ? "OK" : "GAGAL"
                            color: isOk ? Theme.up : Theme.down
                            font.pixelSize: 9
                            font.bold: true
                        }
                    }

                    Text {
                        text: itemData.detail ? itemData.detail : ""
                        color: isOk ? Theme.textPrimary : Theme.down
                        font.pixelSize: 11
                        elide: Text.ElideRight
                        Layout.fillWidth: true
                    }
                }
            }

            // Placeholder empty
            Text {
                anchors.centerIn: parent
                visible: root.journalEntries.length === 0
                horizontalAlignment: Text.AlignHCenter
                lineHeight: 1.3
                text: "Belum ada aksi trading yang dicatat dalam sesi ini.\nAksi strategi dan order manual akan terekam secara otomatis."
                color: Theme.textMuted
                font.pixelSize: 12
            }
        }
    }
}
