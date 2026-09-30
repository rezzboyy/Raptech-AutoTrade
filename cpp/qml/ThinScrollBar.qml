import QtQuick
import QtQuick.Controls

// ScrollBar tipis + auto-hide (fade).
ScrollBar {
    id: sb
    policy: ScrollBar.AsNeeded
    padding: 2
    implicitWidth: 8
    implicitHeight: 8

    contentItem: Rectangle {
        implicitWidth: 6
        implicitHeight: 6
        radius: 3
        color: Theme.textMuted
        opacity: sb.pressed ? 0.85 : (sb.hovered ? 0.6 : (sb.active ? 0.45 : 0.0))
        Behavior on opacity { NumberAnimation { duration: 250 } }
    }
    background: Item {}
}
