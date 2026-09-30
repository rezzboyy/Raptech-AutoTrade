import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import QtQuick.Dialogs
import "."

Rectangle {
    property alias logModel: list.model
    radius: 10
    color: Theme.surface
    border.color: Theme.border

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 4

        RowLayout {
            Layout.fillWidth: true
            spacing: 7
            Image { source: "qrc:/assets/log.svg"; sourceSize.width: 14; sourceSize.height: 14 }
            Text { text: "Log"; color: Theme.textPrimary; font.pixelSize: 13; font.bold: true }
            Item { Layout.fillWidth: true }
            CButton {
                text: "Ekspor"; icon.source: "qrc:/assets/save.svg"; icon.width: 12; icon.height: 12
                font.pixelSize: 10; Layout.preferredHeight: 24; Layout.preferredWidth: 92
                onClicked: logSaveDialog.open()
            }
        }

        Rectangle {
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: Theme.logBg
            radius: 6

            Text {
                anchors.centerIn: parent
                visible: list.count === 0
                text: "Log aktivitas akan muncul di sini..."
                color: Theme.textMuted
                font.pixelSize: 11
            }

            ListView {
                id: list
                anchors.fill: parent
                anchors.margins: 6
                clip: true
                spacing: 1
                ScrollBar.vertical: ThinScrollBar {}
                delegate: Text {
                    width: list.width
                    text: line
                    color: Theme.logText
                    font.family: "Consolas, monospace"
                    font.pixelSize: 11
                    wrapMode: Text.WrapAnywhere
                }
                onCountChanged: positionViewAtEnd()
            }
        }
    }

    FileDialog {
        id: logSaveDialog
        title: "Simpan log sebagai"
        fileMode: FileDialog.SaveFile
        nameFilters: ["CSV (*.csv)", "Teks (*.txt)"]
        onAccepted: if (bot) bot.exportLogs(selectedFile.toString())
    }
}
