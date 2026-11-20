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
            spacing: 6
            Image { source: "qrc:/assets/log.svg"; sourceSize.width: 14; sourceSize.height: 14 }
            Text { text: "Log"; color: Theme.textPrimary; font.pixelSize: 13; font.bold: true }
            Item { Layout.fillWidth: true }
            CButton {
                text: "Ekspor"
                icon.source: "qrc:/assets/save.svg"
                icon.width: 12; icon.height: 12
                font.pixelSize: 10
                Layout.preferredHeight: 24
                leftPadding: 8; rightPadding: 8
                ToolTip.visible: hovered
                ToolTip.text: "Ekspor log ke CSV atau TXT"
                onClicked: logSaveDialog.open()
            }
            CButton {
                text: "Bersihkan"
                icon.source: "qrc:/assets/trash.svg"
                icon.width: 12; icon.height: 12
                font.pixelSize: 10
                Layout.preferredHeight: 24
                leftPadding: 8; rightPadding: 8
                enabled: list.count > 0
                ToolTip.visible: hovered
                ToolTip.text: "Bersihkan seluruh tampilan log"
                onClicked: {
                    if (bot) bot.clearLogs()
                    if (logModel) logModel.clear()
                }
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
                spacing: 4
                ScrollBar.vertical: ThinScrollBar {}
                delegate: RowLayout {
                    width: list.width
                    spacing: 6

                    // Timestamp
                    Text {
                        text: (model && model.time) ? model.time : ""
                        color: Theme.textMuted
                        font.family: "Consolas, monospace"
                        font.pixelSize: 10
                        Layout.preferredWidth: 50
                        Layout.alignment: Qt.AlignTop
                    }

                    // Tag Badge
                    Rectangle {
                        readonly property string tagStr: String((model && model.tag) ? model.tag : "INFO").toUpperCase()
                        Layout.preferredHeight: 18
                        Layout.preferredWidth: tagLabel.implicitWidth + 8
                        Layout.alignment: Qt.AlignTop
                        radius: 3
                        color: {
                            if (tagStr === "ORDER" || tagStr === "SUKSES") return "#163a24"
                            if (tagStr === "ERROR" || tagStr === "DITOLAK" || tagStr === "GAGAL") return "#3b1a1f"
                            if (tagStr === "RISIKO" || tagStr === "PERINGATAN") return "#3a2a14"
                            if (tagStr === "SKRIP" || tagStr === "SINYAL") return "#142d42"
                            if (tagStr === "MT5" || tagStr === "PROFIL") return "#281b3d"
                            if (tagStr === "JURNAL") return "#133830"
                            return Theme.surfaceAlt
                        }
                        border.color: {
                            if (tagStr === "ORDER" || tagStr === "SUKSES") return Theme.up
                            if (tagStr === "ERROR" || tagStr === "DITOLAK" || tagStr === "GAGAL") return Theme.down
                            if (tagStr === "RISIKO" || tagStr === "PERINGATAN") return Theme.warn
                            if (tagStr === "SKRIP" || tagStr === "SINYAL") return "#60a5fa"
                            if (tagStr === "MT5" || tagStr === "PROFIL") return "#a78bfa"
                            if (tagStr === "JURNAL") return "#34d399"
                            return Theme.border
                        }
                        Text {
                            id: tagLabel
                            anchors.centerIn: parent
                            text: parent.tagStr
                            font.family: "Consolas, monospace"
                            font.pixelSize: 9
                            font.bold: true
                            color: {
                                if (parent.tagStr === "ORDER" || parent.tagStr === "SUKSES") return Theme.up
                                if (parent.tagStr === "ERROR" || parent.tagStr === "DITOLAK" || parent.tagStr === "GAGAL") return Theme.down
                                if (parent.tagStr === "RISIKO" || parent.tagStr === "PERINGATAN") return Theme.warn
                                if (parent.tagStr === "SKRIP" || parent.tagStr === "SINYAL") return "#60a5fa"
                                if (parent.tagStr === "MT5" || parent.tagStr === "PROFIL") return "#a78bfa"
                                if (parent.tagStr === "JURNAL") return "#34d399"
                                return Theme.textSecondary
                            }
                        }
                    }

                    // Pesan
                    Text {
                        text: (model && model.message) ? model.message : (model && model.line ? model.line : "")
                        color: Theme.textPrimary
                        font.family: "Consolas, monospace"
                        font.pixelSize: 11
                        wrapMode: Text.WrapAnywhere
                        Layout.fillWidth: true
                        Layout.alignment: Qt.AlignVCenter
                    }
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
