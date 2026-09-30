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
    title: "XAVIQ Trading Engine"
    color: Theme.bg
    font.pixelSize: 12

    Material.theme: Theme.isDark ? Material.Dark : Material.Light
    Material.accent: Theme.accent

    readonly property bool botConnected: bot ? bot.connected : false
    readonly property string botStatus: bot ? bot.status : "Terputus"
    readonly property color statusColor: botConnected ? Theme.up : Theme.down

    // Log terkumpul dari sinyal controller.
    ListModel { id: logModel }
    Connections {
        target: bot
        function onLogMessage(msg) {
            logModel.append({ line: msg })
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
            Layout.preferredHeight: 52
            color: Theme.header
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 14
                spacing: 12

                AccountBar {}
                Item { Layout.fillWidth: true }

                Button {
                    visible: window.botConnected
                    flat: true
                    icon.source: "qrc:/assets/link-off.svg"; icon.width: 14; icon.height: 14
                    text: "Logout"
                    onClicked: if (bot) bot.logoutAccount()
                    ToolTip.visible: hovered
                    ToolTip.text: "Putus koneksi & logout dari akun MT5"
                }
                Rectangle { visible: window.botConnected; width: 1; height: 18; color: Theme.divider }

                Button {
                    text: Theme.isDark ? "Dark" : "Light"
                    flat: true
                    icon.source: Theme.isDark ? "qrc:/assets/moon.svg" : "qrc:/assets/sun.svg"
                    icon.width: 14; icon.height: 14
                    onClicked: Theme.isDark = !Theme.isDark
                }
                Rectangle { width: 1; height: 18; color: Theme.divider }

                Rectangle { width: 11; height: 11; radius: 6; color: window.statusColor }
                Text { text: window.botStatus; color: Theme.textSecondary; font.pixelSize: 13 }
            }
        }
        Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.divider }

        // ================= Konten utama =================
        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: 8
            spacing: 8

            // ----- Kiri: kontrol + log -----
            ColumnLayout {
                Layout.preferredWidth: 440
                Layout.minimumWidth: 380
                Layout.maximumWidth: 540
                Layout.fillHeight: true
                spacing: 6

                TabBar {
                    id: leftTabs
                    Layout.fillWidth: true
                    TabButton { text: "Login" }
                    TabButton { text: "Manual" }
                    TabButton { text: "Order" }
                    TabButton { text: "Programmer" }
                    TabButton { text: "Statistik" }
                }
                StackLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    currentIndex: leftTabs.currentIndex
                    LoginPanel {}
                    ConfigPanel {}
                    ManualTradePanel {}
                    ProgrammerPanel {}
                    StatsPanel {}
                }
                LogPanel {
                    logModel: logModel
                    Layout.fillWidth: true
                    Layout.preferredHeight: 210
                    Layout.minimumHeight: 120
                }
            }

            // ----- Kanan: chart + posisi -----
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 8

                TabBar {
                    id: chartTabs
                    Layout.preferredWidth: 240
                    TabButton { text: "Candlestick" }
                    TabButton { text: "Equity Curve" }
                }
                StackLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumHeight: 240
                    currentIndex: chartTabs.currentIndex
                    CandleChart {}
                    EquityChart {}
                }
                PositionsPanel {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 230
                    Layout.minimumHeight: 150
                }
            }
        }
    }

    // ================= Dialog error =================
    Dialog {
        id: errorDialog
        title: "Peringatan"
        modal: true
        standardButtons: Dialog.Ok
        anchors.centerIn: parent
        Text { id: errorText; color: Theme.textPrimary; wrapMode: Text.Wrap }
    }
}
