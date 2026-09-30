import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Controls.Material
import "."
import "components"

ApplicationWindow {
    id: window
    visible: true
    width: 1180
    height: 800
    minimumWidth: 940
    minimumHeight: 640
    title: "XAVIQ Trading Engine"
    color: Theme.bg
    font.pixelSize: 12

    // Tema Material dinamis (Dark / Light) + varian Dense.
    Material.theme: Theme.isDark ? Material.Dark : Material.Light
    Material.accent: Theme.accent
    Material.background: Theme.surface
    Material.foreground: Theme.textPrimary

    readonly property bool botConnected: bot ? bot.connected : false
    readonly property string botStatus: bot ? bot.status : "Terputus"
    readonly property color accent: botConnected ? Theme.up : Theme.down

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ================= Header =================
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 50
            color: Theme.header
            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 14
                spacing: 12
                AccountBar {}
                Item { Layout.fillWidth: true }

                // Tombol Logout Akun (aktif bila bot terhubung)
                Button {
                    visible: bot ? bot.connected : false
                    flat: true
                    icon.source: "../assets/link-off.svg"
                    icon.width: 14
                    icon.height: 14
                    contentItem: RowLayout {
                        spacing: 4
                        Image {
                            source: "../assets/link-off.svg"
                            sourceSize.width: 14
                            sourceSize.height: 14
                        }
                        Text {
                            text: "Logout"
                            color: Theme.down
                            font.pixelSize: 12
                            font.bold: true
                        }
                    }
                    onClicked: {
                        if (bot) bot.logoutAccount()
                    }
                    ToolTip.visible: hovered
                    ToolTip.text: "Putus koneksi dan logout dari akun MT5 saat ini"
                }

                Rectangle {
                    visible: bot ? bot.connected : false
                    width: 1; height: 18; color: Theme.divider
                }

                // Tombol toggle mode Gelap / Terang
                Button {
                    text: Theme.isDark ? "Dark" : "Light"
                    flat: true
                    icon.source: Theme.isDark ? "../assets/moon.svg" : "../assets/sun.svg"
                    icon.width: 14
                    icon.height: 14
                    onClicked: Theme.isDark = !Theme.isDark
                }

                Rectangle { width: 1; height: 18; color: Theme.divider }

                Rectangle { width: 11; height: 11; radius: 6; color: window.accent }
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

            // ----- Kolom kiri: kontrol (Login, Konfigurasi, Statistik) -----
            ColumnLayout {
                Layout.preferredWidth: 420
                Layout.minimumWidth: 360
                Layout.maximumWidth: 500
                Layout.fillHeight: true
                spacing: 6

                TabBar {
                    id: leftTabs
                    objectName: "leftTabs"
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
                    ScriptPanel {}
                    StatsPanel {}
                }

                // Log ditaruh di bawah kolom kiri -> lebar mengikuti panel login.
                LogPanel {
                    Layout.fillWidth: true
                }
            }

            // ----- Kolom kanan: chart (Candlestick / Equity) + posisi -----
            ColumnLayout {
                Layout.fillWidth: true
                Layout.fillHeight: true
                spacing: 8

                TabBar {
                    id: chartTabs
                    Layout.preferredWidth: 220
                    TabButton { text: "Candlestick" }
                    TabButton { text: "Equity Curve" }
                }

                StackLayout {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumHeight: 240
                    currentIndex: chartTabs.currentIndex

                    CandleChart {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                    }

                    EquityChart {
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                    }
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
    Connections {
        target: bot
        function onConfigError(msg) {
            errorText.text = msg
            errorDialog.open()
        }
    }

    Dialog {
        id: errorDialog
        title: "Peringatan"
        modal: true
        standardButtons: Dialog.Ok
        anchors.centerIn: parent
        Text { id: errorText; color: Theme.textPrimary; wrapMode: Text.Wrap }
    }
}
