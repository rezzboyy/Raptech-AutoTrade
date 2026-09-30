import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

// Tabel posisi terbuka + tombol tutup.
Rectangle {
    id: root
    color: Theme.surface
    radius: 10
    border.color: Theme.border

    ListModel { id: posModel }
    Connections {
        target: bot
        function onPositionsChanged(positions) {
            posModel.clear()
            for (var i = 0; i < positions.length; i++)
                posModel.append(positions[i])
        }
    }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 8
        spacing: 4

        RowLayout {
            Layout.fillWidth: true
            spacing: 7
            Image { source: "qrc:/assets/positions.svg"; sourceSize.width: 14; sourceSize.height: 14 }
            Text { text: "Posisi Terbuka"; color: Theme.textPrimary; font.pixelSize: 13; font.bold: true }
            Item { Layout.fillWidth: true }
            Text { text: posModel.count + " posisi"; color: Theme.textMuted; font.pixelSize: 10 }
            CButton {
                text: "Tutup Semua"
                icon.source: "qrc:/assets/close.svg"; icon.width: 11; icon.height: 11
                font.pixelSize: 11
                Layout.preferredWidth: 104
                Layout.preferredHeight: 26
                enabled: (bot ? bot.connected : false) && posModel.count > 0
                onClicked: bot.closeAllPositions()
            }
        }

        RowLayout {
            Layout.fillWidth: true; spacing: 0
            Text { text: "Ticket"; color: Theme.textMuted; font.pixelSize: 10; Layout.preferredWidth: 78 }
            Text { text: "Simbol"; color: Theme.textMuted; font.pixelSize: 10; Layout.preferredWidth: 68 }
            Text { text: "Tipe"; color: Theme.textMuted; font.pixelSize: 10; Layout.preferredWidth: 46 }
            Text { text: "Vol"; color: Theme.textMuted; font.pixelSize: 10; Layout.preferredWidth: 46 }
            Text { text: "Profit"; color: Theme.textMuted; font.pixelSize: 10; Layout.fillWidth: true }
            Text { text: ""; Layout.preferredWidth: 66 }
        }
        Rectangle { Layout.fillWidth: true; height: 1; color: Theme.divider }

        ListView {
            id: posView
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 1
            ScrollBar.vertical: ThinScrollBar {}
            model: posModel
            delegate: RowLayout {
                width: posView.width; spacing: 0
                Text { text: model.ticket; color: Theme.textPrimary; font.pixelSize: 11; Layout.preferredWidth: 78 }
                Text { text: model.symbol; color: Theme.textPrimary; font.pixelSize: 11; Layout.preferredWidth: 68 }
                Text { text: model.type; color: model.type === "BUY" ? Theme.up : Theme.down; font.pixelSize: 11; Layout.preferredWidth: 46 }
                Text { text: Number(model.volume).toFixed(2); color: Theme.textPrimary; font.pixelSize: 11; Layout.preferredWidth: 46 }
                Text { text: Number(model.profit).toFixed(2); color: model.profit < 0 ? Theme.down : Theme.up; font.pixelSize: 11; Layout.fillWidth: true }
                CButton {
                    text: "Tutup"
                    bg: Theme.down; fg: "#ffffff"
                    font.pixelSize: 11
                    Layout.preferredWidth: 66
                    Layout.preferredHeight: 24
                    onClicked: bot.closePosition(model.ticket)
                }
            }
        }
    }
}
