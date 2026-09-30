import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Dialogs
import ".."

// Panel log yang bisa dilipat (hemat ruang).
Rectangle {
    id: root
    color: Theme.surface
    radius: 10
    border.color: Theme.border

    property bool expanded: true
    implicitHeight: expanded ? 128 : 34

    Behavior on implicitHeight { NumberAnimation { duration: 120 } }

    // Tombol ikon ringkas (hemat lebar untuk kolom sempit).
    component IconBtn: Button {
        flat: true
        display: AbstractButton.IconOnly
        icon.width: 14
        icon.height: 14
        Layout.preferredWidth: 32
        Layout.preferredHeight: 30
        ToolTip.visible: hovered
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 3

        RowLayout {
            Layout.fillWidth: true
            spacing: 2
            Image { source: "../../assets/log.svg"; sourceSize.width: 15; sourceSize.height: 15 }
            Text { text: "Log"; color: Theme.textPrimary; font.pixelSize: 13; font.bold: true }
            Item { Layout.fillWidth: true }
            IconBtn {
                icon.source: "../../assets/download.svg"
                ToolTip.text: "Ekspor log"
                onClicked: exportDialog.open()
            }
            IconBtn {
                icon.source: "../../assets/trash.svg"
                ToolTip.text: "Bersihkan log"
                onClicked: logArea.text = ""
            }
            IconBtn {
                icon.source: root.expanded ? "../../assets/chevron-down.svg" : "../../assets/chevron-right.svg"
                ToolTip.text: root.expanded ? "Sembunyikan" : "Tampilkan"
                onClicked: root.expanded = !root.expanded
            }
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.expanded
            clip: true
            ScrollBar.vertical: ThinScrollBar {}
            ScrollBar.horizontal: ThinScrollBar {}
            TextArea {
                id: logArea
                readOnly: true
                wrapMode: TextArea.Wrap
                color: Theme.logText
                font.family: "Consolas, monospace"
                font.pixelSize: 11
                background: null
                text: "Log akan muncul di sini...\n"
            }
        }
    }

    FileDialog {
        id: exportDialog
        title: "Ekspor Log Bot MT5"
        fileMode: FileDialog.SaveFile
        nameFilters: ["File Teks (*.txt)", "File CSV (*.csv)", "Semua File (*)"]
        defaultSuffix: "txt"
        onAccepted: bot.exportLogs(selectedFile.toString())
    }

    Connections {
        target: bot
        function onLogMessage(msg) { logArea.append(msg) }
    }
}
