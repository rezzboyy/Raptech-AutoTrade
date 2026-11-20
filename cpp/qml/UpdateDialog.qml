import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: root
    modal: true
    dim: true
    anchors.centerIn: parent
    width: Math.min(560, parent.width - 40)
    padding: 24
    closePolicy: updater && updater.downloading ? Popup.NoAutoClose : (Popup.CloseOnEscape | Popup.CloseOnPressOutside)

    background: Rectangle {
        color: Theme.surface
        radius: 12
        border.color: Theme.border
        border.width: 1
    }

    contentItem: ColumnLayout {
        spacing: 16

        // Header: Icon + Judul
        RowLayout {
            spacing: 12
            Layout.fillWidth: true

            Rectangle {
                width: 42
                height: 42
                radius: 10
                color: Qt.rgba(Theme.accent.r, Theme.accent.g, Theme.accent.b, 0.15)
                border.color: Theme.accent
                border.width: 1

                Image {
                    anchors.centerIn: parent
                    source: "qrc:/assets/download.svg"
                    sourceSize: Qt.size(22, 22)
                }
            }

            ColumnLayout {
                spacing: 2
                Layout.fillWidth: true

                Text {
                    text: "Pembaruan Aplikasi Tersedia!"
                    font.pixelSize: 16
                    font.bold: true
                    color: Theme.textPrimary
                }

                Text {
                    text: updater ? updater.releaseTitle : "Versi Baru"
                    font.pixelSize: 12
                    color: Theme.textSecondary
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }
            }
        }

        // Pill Badges: Versi Sekarang -> Versi Baru
        RowLayout {
            spacing: 10
            Layout.fillWidth: true

            Rectangle {
                height: 28
                radius: 6
                color: Theme.surfaceAlt
                border.color: Theme.border
                border.width: 1
                implicitWidth: curVerRow.implicitWidth + 16

                RowLayout {
                    id: curVerRow
                    anchors.centerIn: parent
                    spacing: 6
                    Text { text: "Saat Ini:"; font.pixelSize: 11; color: Theme.textMuted }
                    Text { text: "v" + (updater ? updater.currentVersion : "1.0.0"); font.pixelSize: 11; font.bold: true; color: Theme.textSecondary }
                }
            }

            Text { text: "➔"; font.pixelSize: 12; color: Theme.textMuted }

            Rectangle {
                height: 28
                radius: 6
                color: Qt.rgba(Theme.up.r, Theme.up.g, Theme.up.b, 0.15)
                border.color: Theme.up
                border.width: 1
                implicitWidth: newVerRow.implicitWidth + 16

                RowLayout {
                    id: newVerRow
                    anchors.centerIn: parent
                    spacing: 6
                    Text { text: "Terbaru:"; font.pixelSize: 11; color: Theme.up }
                    Text { text: "v" + (updater ? updater.latestVersion : "1.0.1"); font.pixelSize: 11; font.bold: true; color: Theme.up }
                }
            }

            Item { Layout.fillWidth: true }

            Rectangle {
                visible: updater && updater.fileSizeMb > 0
                height: 28
                radius: 6
                color: Theme.surfaceAlt
                border.color: Theme.border
                border.width: 1
                implicitWidth: sizeRow.implicitWidth + 16

                RowLayout {
                    id: sizeRow
                    anchors.centerIn: parent
                    spacing: 4
                    Text { text: "Ukuran:"; font.pixelSize: 11; color: Theme.textMuted }
                    Text { text: (updater ? updater.fileSizeMb : 0) + " MB"; font.pixelSize: 11; font.bold: true; color: Theme.textPrimary }
                }
            }
        }

        // Catatan Rilis (Changelog) Box
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 140
            color: Theme.bg
            radius: 8
            border.color: Theme.border
            border.width: 1

            Flickable {
                id: flick
                anchors.fill: parent
                anchors.margins: 10
                contentWidth: width
                contentHeight: changelogText.implicitHeight
                clip: true

                Text {
                    id: changelogText
                    width: flick.width
                    wrapMode: Text.Wrap
                    textFormat: Text.PlainText
                    text: (updater && updater.releaseNotes) ? updater.releaseNotes : "Pembaruan performa dan stabilitas aplikasi."
                    font.pixelSize: 11
                    color: Theme.textSecondary
                    lineHeight: 1.3
                }

                ScrollBar.vertical: ThinScrollBar {}
            }
        }

        // Progress Bar saat Sedang Mengunduh
        ColumnLayout {
            visible: updater ? updater.downloading : false
            Layout.fillWidth: true
            spacing: 6

            RowLayout {
                Layout.fillWidth: true
                Text {
                    text: updater ? updater.statusMessage : "Mengunduh pembaruan..."
                    font.pixelSize: 11
                    color: Theme.textSecondary
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }
                Text {
                    text: (updater ? updater.downloadProgress : 0) + "%"
                    font.pixelSize: 11
                    font.bold: true
                    color: Theme.accent
                }
            }

            ProgressBar {
                Layout.fillWidth: true
                from: 0
                to: 100
                value: updater ? updater.downloadProgress : 0
                Material.accent: Theme.accent
            }
        }

        // Tombol Aksi
        RowLayout {
            Layout.fillWidth: true
            spacing: 10

            Item { Layout.fillWidth: true }

            Button {
                visible: !(updater && updater.downloading)
                text: "Nanti Saja"
                flat: true
                onClicked: root.close()
            }

            Button {
                visible: updater && updater.downloading
                text: "Batalkan"
                flat: true
                onClicked: {
                    if (updater) updater.cancelDownload()
                }
            }

            Button {
                visible: !(updater && updater.downloading)
                text: "Perbarui Sekarang"
                highlighted: true
                Material.accent: Theme.accent
                onClicked: {
                    if (updater) updater.downloadAndInstallUpdate()
                }
            }
        }
    }
}
