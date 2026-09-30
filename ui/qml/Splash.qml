import QtQuick
import QtQuick.Controls
import "."

Window {
    id: splashWindow
    visible: true
    width: 380
    height: 220
    flags: Qt.SplashScreen | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
    color: "transparent"

    Rectangle {
        anchors.fill: parent
        radius: 12
        color: Theme.surface
        border.color: Theme.border
        border.width: 1

        Column {
            anchors.centerIn: parent
            spacing: 12

            Image {
                source: "../assets/icon.png"
                width: 52
                height: 52
                mipmap: true
                smooth: true
                anchors.horizontalCenter: parent.horizontalCenter
            }

            Text {
                text: "XAVIQ Trading Engine"
                color: Theme.textPrimary
                font.pixelSize: 19
                font.bold: true
                anchors.horizontalCenter: parent.horizontalCenter
            }

            Text {
                text: "Automated Algorithmic Trading Platform"
                color: Theme.textMuted
                font.pixelSize: 11
                anchors.horizontalCenter: parent.horizontalCenter
            }

            ProgressBar {
                id: pbar
                indeterminate: true
                width: 200
                anchors.horizontalCenter: parent.horizontalCenter
            }

            Text {
                text: "Memuat strategi, konfigurasi, dan antarmuka..."
                color: Theme.textSecondary
                font.pixelSize: 11
                anchors.horizontalCenter: parent.horizontalCenter
            }
        }
    }
}
