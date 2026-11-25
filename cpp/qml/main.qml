import QtQuick
import QtQuick.Window
import QtQuick.Layouts
import QtQuick.Controls
import QtQuick.Controls.Material
import "."

ApplicationWindow {
    id: window
    visible: true
    width: 1240
    height: 820
    minimumWidth: 980
    minimumHeight: 660
    title: "X Trading Engine v" + (bot ? bot.appVersion : "3.2.0")
    color: Theme.bg
    font.pixelSize: 12

    Material.theme: Theme.isDark ? Material.Dark : Material.Light
    Material.accent: Theme.accent

    readonly property bool botConnected: bot ? bot.connected : false
    readonly property bool authBusy: bot ? bot.authBusy : false
    readonly property string authAction: bot ? bot.authAction : ""
    readonly property string botStatus: bot ? bot.status : "Terputus"
    readonly property color statusColor: authBusy ? Theme.warn : (botConnected ? Theme.up : Theme.down)

    // Log terkumpul dari sinyal controller.
    ListModel { id: logModel }
    Connections {
        target: bot
        function onLogMessage(msg) {
            var raw = String(msg || "").trim()
            if (!raw) return

            var now = new Date()
            var timeStr = Qt.formatTime(now, "HH:mm:ss")
            var tagStr = "INFO"
            var content = raw

            // Cek jika sudah memiliki timestamp: [HH:mm:ss] atau HH:mm:ss
            var timeMatch = raw.match(/^\[?(\d{2}:\d{2}:\d{2})\]?\s*(.*)$/)
            if (timeMatch) {
                timeStr = timeMatch[1]
                content = timeMatch[2].trim()
            }

            // Cek jika memiliki format [TAG]
            var tagMatch = content.match(/^\[([^\]]+)\]\s*(.*)$/)
            if (tagMatch) {
                tagStr = tagMatch[1].trim().toUpperCase()
                content = tagMatch[2].trim()
            }

            var fullLine = "[" + timeStr + "] [" + tagStr + "] " + content
            logModel.append({
                time: timeStr,
                tag: tagStr,
                message: content,
                line: fullLine
            })
            if (logModel.count > 500) logModel.remove(0)
        }
        function onConfigError(msg) {
            errorText.text = msg
            errorDialog.open()
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ================= Header =================
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 56
            color: Theme.header
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 14
                spacing: 12

                AccountBar {}
                Item { Layout.fillWidth: true }

                Button {
                    visible: window.botConnected || (window.authBusy && window.authAction === "logout")
                    enabled: !(window.authBusy)
                    flat: true
                    icon.source: "qrc:/assets/link-off.svg"; icon.width: 14; icon.height: 14
                    text: (window.authBusy && window.authAction === "logout") ? "Logout..." : "Logout"
                    onClicked: if (bot) bot.logoutAccount()
                    ToolTip.visible: hovered
                    ToolTip.text: (window.authBusy && window.authAction === "logout")
                                  ? "Sedang memutus koneksi dan menutup sesi..."
                                  : "Putus koneksi & logout dari akun MT5"
                }
                Rectangle { visible: window.botConnected || (window.authBusy && window.authAction === "logout"); width: 1; height: 18; color: Theme.divider }

                // Tombol Toggle Mode Gelap / Terang
                Button {
                    flat: true
                    icon.source: Theme.isDark ? "qrc:/assets/sun.svg" : "qrc:/assets/moon.svg"
                    icon.width: 14; icon.height: 14
                    text: Theme.isDark ? "Light" : "Dark"
                    Layout.preferredHeight: 30
                    onClicked: if (bot) bot.setTheme(Theme.isDark ? "light" : "dark")
                    ToolTip.visible: hovered
                    ToolTip.text: Theme.isDark ? "Ubah ke Mode Terang (Soft Slate Light Mode)" : "Ubah ke Mode Gelap (Dark Mode)"
                }

                Rectangle { width: 1; height: 18; color: Theme.divider }

                // Indikator Pembaruan Aplikasi (OTA)
                Button {
                    visible: updater ? updater.updateAvailable : false
                    flat: false
                    highlighted: true
                    Material.accent: Theme.accent
                    icon.source: "qrc:/assets/download.svg"
                    icon.width: 14; icon.height: 14
                    text: "Update v" + (updater ? updater.latestVersion : "")
                    Layout.preferredHeight: 30
                    onClicked: updateDialog.open()
                    ToolTip.visible: hovered
                    ToolTip.text: "Versi baru tersedia! Klik untuk melihat catatan rilis & memperbarui."
                }

                Button {
                    visible: !(updater && updater.updateAvailable)
                    flat: true
                    icon.source: "qrc:/assets/refresh.svg"
                    icon.width: 13; icon.height: 13
                    text: (updater && updater.checking) ? "Memeriksa..." : "Cek Update"
                    enabled: !(updater && updater.checking)
                    Layout.preferredHeight: 30
                    onClicked: {
                        if (updater) updater.checkForUpdates(true)
                    }
                    ToolTip.visible: hovered
                    ToolTip.text: (updater && updater.checking) ? "Sedang memeriksa pembaruan di GitHub..." : "Periksa ketersediaan versi baru di GitHub"
                }

                Rectangle { width: 1; height: 18; color: Theme.divider }

                Rectangle {
                    radius: 4
                    color: Theme.surfaceAlt
                    border.color: Theme.divider
                    border.width: 1
                    Layout.preferredHeight: 22
                    Layout.preferredWidth: verTxt.implicitWidth + 12
                    Text {
                        id: verTxt
                        anchors.centerIn: parent
                        text: "v" + (bot ? bot.appVersion : "1.0.0")
                        color: Theme.textMuted
                        font.pixelSize: 10
                        font.bold: true
                    }
                    MouseArea {
                        id: verHover
                        anchors.fill: parent
                        hoverEnabled: true
                    }
                    ToolTip.visible: verHover.containsMouse
                    ToolTip.text: "X Trading Engine v" + (bot ? bot.appVersion : "3.2.0") + " (Release)"
                }
                Rectangle { width: 1; height: 18; color: Theme.divider }

                BusyIndicator {
                    running: window.authBusy
                    visible: window.authBusy
                    Layout.preferredWidth: 18
                    Layout.preferredHeight: 18
                }
                Rectangle { visible: !window.authBusy; width: 11; height: 11; radius: 6; color: window.statusColor }
                Text {
                    text: window.authBusy && bot && bot.authMessage ? bot.authMessage : window.botStatus
                    color: window.authBusy ? Theme.warn : Theme.textSecondary
                    font.pixelSize: 13
                }
            }
        }
        Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.divider }

        // ================= Konten utama =================
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: 6
            spacing: 6

            // ----- Kiri: Sidebar Controls & Telemetry (360px) -----
            SidebarControls {
                id: sidebarControls
                Layout.preferredWidth: 360
                Layout.minimumWidth: 360
                Layout.maximumWidth: 360
                Layout.fillHeight: true
            }

            // ----- Kanan: Workspace Multi-Tab Area -----
            WorkspaceArea {
                id: workspaceArea
                Layout.fillWidth: true
                Layout.fillHeight: true
                logModelRef: logModel
            }
        }
    }

    // ================= Dialog Verifikasi Algo Trading =================
    AlgoVerificationDialog {
        id: algoVerificationDialog
    }

    // ================= Dialog Pembaruan Aplikasi (OTA) =================
    UpdateDialog {
        id: updateDialog
    }

    Connections {
        target: updater
        function onUpdateFound(version, notes) {
            updateDialog.open()
        }
        function onUpdateNotFound(manual) {
            if (manual) {
                errorText.text = "Aplikasi Anda sudah menggunakan versi paling mutakhir (v" + (updater ? updater.currentVersion : "") + "). Tidak ada pembaruan baru di GitHub saat ini."
                errorDialog.title = "Informasi Pembaruan"
                errorDialog.open()
            }
        }
        function onUpdateError(message) {
            errorText.text = "Gagal memeriksa pembaruan di GitHub:\n" + message
            errorDialog.title = "Pembaruan Gagal"
            errorDialog.open()
        }
    }

    // ================= Dialog error =================
    Dialog {
        id: errorDialog
        title: "Peringatan"
        modal: true
        standardButtons: Dialog.Ok
        anchors.centerIn: parent
        width: Math.min(500, parent ? parent.width - 32 : 500)

        contentItem: ColumnLayout {
            spacing: 12
            Text {
                id: errorText
                Layout.fillWidth: true
                color: Theme.textPrimary
                wrapMode: Text.Wrap
                lineHeight: 1.2
            }
            CButton {
                visible: errorText.text.indexOf("trading is not permitted") !== -1 || errorText.text.indexOf("Algo Trading") !== -1
                text: "Buka Menu Verifikasi Algo Trading"
                icon.source: "qrc:/assets/bolt.svg"
                icon.width: 14
                icon.height: 14
                Layout.fillWidth: true
                Layout.preferredHeight: 34
                bg: Theme.accent
                fg: "#ffffff"
                font.bold: true
                onClicked: {
                    errorDialog.close()
                    algoVerificationDialog.openDialog()
                }
            }
        }
    }
}
