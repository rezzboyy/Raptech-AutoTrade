import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

// Tombol dengan warna eksplisit (bypass kuirk auto-color Material Dark) agar
// teks selalu kontras & terbaca. Set `bg`/`fg` untuk tombol beraksen.
//
// PENTING: contentItem memakai RowLayout + dua spacer fillWidth untuk
// menengahkan ikon+teks sebagai satu grup. JANGAN mereferensikan
// `availableWidth`/`width` untuk menghitung ukuran isi, dan jangan memakai
// anchors di dalam positioner — keduanya bisa memicu siklus layout (polish
// loop) yang membuat window blank putih & grabWindow menggantung.
Button {
    id: control
    property color bg: Theme.surfaceAlt
    property color fg: Theme.textPrimary
    readonly property bool hasIcon: String(icon.source).length > 0
    font.pixelSize: 12
    implicitHeight: 32
    leftPadding: 10
    rightPadding: 10
    hoverEnabled: true

    contentItem: RowLayout {
        spacing: 0
        Item { Layout.fillWidth: true }
        Image {
            visible: control.hasIcon
            source: control.icon.source
            sourceSize.width: control.icon.width > 0 ? control.icon.width : 14
            sourceSize.height: control.icon.height > 0 ? control.icon.height : 14
            Layout.alignment: Qt.AlignVCenter
            Layout.rightMargin: (control.hasIcon && control.text.length > 0) ? 6 : 0
        }
        Text {
            visible: control.text.length > 0
            text: control.text
            color: control.enabled ? control.fg : Theme.textMuted
            font: control.font
            verticalAlignment: Text.AlignVCenter
            Layout.alignment: Qt.AlignVCenter
        }
        Item { Layout.fillWidth: true }
    }

    background: Rectangle {
        radius: 6
        color: !control.enabled ? Qt.darker(control.bg, 1.15)
             : (control.down ? Qt.darker(control.bg, 1.2)
             : (control.hovered ? Qt.lighter(control.bg, 1.12) : control.bg))
        border.color: Theme.border
        border.width: 1
    }
}
