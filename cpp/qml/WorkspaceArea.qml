import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

// WorkspaceArea.qml — Area Kerja Multi-Tab Sisi Kanan
// Menyatukan seluruh fitur utama dengan tema murni Dark Cyber-Trading Terminal
Rectangle {
    id: root
    color: Theme.bg
    border.color: Theme.border
    border.width: 1

    property var logModelRef: null
    property alias currentTabIndex: workspaceTabs.currentIndex

    // Komponen TabButton Kustom dengan Styling Dark Workstation Presisi
    component StyledTab: TabButton {
        id: tabBtn
        implicitHeight: 38
        font.pixelSize: 11
        font.bold: workspaceTabs.currentIndex === TabBar.index

        contentItem: Text {
            text: tabBtn.text
            font: tabBtn.font
            color: tabBtn.checked ? Theme.textPrimary : Theme.textSecondary
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
        }

        background: Rectangle {
            color: tabBtn.checked ? Theme.surfaceAlt : (tabBtn.hovered ? Theme.surfaceHighlight : Theme.bg)

            // Garis Aksen Bawah (Sky Blue saat Tab Aktif)
            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width
                height: tabBtn.checked ? 2 : 0
                color: Theme.accent
            }
        }
    }

    ColumnLayout {
        anchors.fill: parent
        spacing: 0

        // ================= TabBar Navigasi Horizontal =================
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 38
            color: Theme.bg
            border.color: Theme.border
            border.width: 1

            TabBar {
                id: workspaceTabs
                anchors.fill: parent
                currentIndex: 1 // Default tab 1: Trade History (sesuai foto referensi pengguna)
                background: Rectangle { color: Theme.bg }

                StyledTab { text: "Open Trades" }
                StyledTab { text: "Trade History" }
                StyledTab { text: "Candlestick Chart" }
                StyledTab { text: "Equity Curve" }
                StyledTab { text: "Programmer Studio" }
                StyledTab { text: "Expert Log" }
                StyledTab { text: "Login MT5" }
            }
        }

        // ================= StackLayout Konten Multi-Tab =================
        StackLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            currentIndex: workspaceTabs.currentIndex

            // Tab 0: Open Trades
            OpenTradesGrid {}

            // Tab 1: Trade History (Tabel referensi pengguna)
            TradeHistoryGrid {}

            // Tab 2: Candlestick Chart interaktif C++
            CandleChart {}

            // Tab 3: Equity Curve grafik saldo & drawdown
            EquityChart {}

            // Tab 4: Programmer Studio IDE editor
            ProgrammerPanel {}

            // Tab 5: Expert Log real-time console
            LogPanel {
                logModel: root.logModelRef
            }

            // Tab 6: Login MT5 & Profil Koneksi
            LoginPanel {}
        }
    }
}
