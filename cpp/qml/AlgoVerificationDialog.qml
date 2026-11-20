import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import "."

// Dialog Verifikasi Algo Trading & Hak Eksekusi MT5
Dialog {
    id: root
    title: ""
    modal: true
    anchors.centerIn: parent
    width: Math.min(560, parent ? parent.width - 24 : 560)
    height: Math.min(620, parent ? parent.height - 24 : 620)
    padding: 0
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside

    background: Rectangle {
        color: Theme.surface
        radius: 12
        border.color: Theme.border
        border.width: 1
    }

    property var diagData: ({
        ok: false,
        status: "OFFLINE",
        summary: "Memeriksa izin...",
        server_connected: false,
        experts_trade_allowed: false,
        mcp_trade_allowed: false,
        account_trade_allowed: false,
        login: 0,
        server: "",
        account_type: "",
        symbol: "",
        trade_blocked: false,
        reject_reason: "",
        issues: [],
        solutions: []
    })

    function openDialog() {
        refreshData()
        open()
    }

    function refreshData() {
        if (!bot) return
        var sym = (bot.chartSymbol && bot.chartSymbol !== "") ? bot.chartSymbol : "EURUSDm"
        diagData = bot.verifyAlgoTrading(sym)
    }

    contentItem: ColumnLayout {
        spacing: 0

        // ===== Header =====
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 52
            color: Theme.surfaceAlt
            radius: 12
            Rectangle {
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                anchors.right: parent.right
                height: 12
                color: Theme.surfaceAlt
            }
            Rectangle {
                anchors.bottom: parent.bottom
                anchors.left: parent.left
                anchors.right: parent.right
                height: 1
                color: Theme.divider
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 16
                anchors.rightMargin: 16
                spacing: 10

                Image {
                    source: "qrc:/assets/bolt.svg"
                    sourceSize: Qt.size(20, 20)
                    Layout.preferredWidth: 20
                    Layout.preferredHeight: 20
                }

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 1
                    Text {
                        text: "Verifikasi Algo Trading & Izin MT5"
                        color: Theme.textPrimary
                        font.pixelSize: 14
                        font.bold: true
                    }
                    Text {
                        text: "Diagnostik status saklar terminal, izin akun broker, dan protokol MCP."
                        color: Theme.textMuted
                        font.pixelSize: 10
                    }
                }

                CButton {
                    icon.source: "qrc:/assets/close.svg"
                    icon.width: 14
                    icon.height: 14
                    text: ""
                    bg: "transparent"
                    Layout.preferredWidth: 28
                    Layout.preferredHeight: 28
                    onClicked: root.close()
                }
            }
        }

        // ===== Body Scroll =====
        ScrollView {
            id: bodyScroll
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            ScrollBar.vertical: ThinScrollBar {}
            ScrollBar.horizontal: ThinScrollBar {}

            ColumnLayout {
                width: bodyScroll.availableWidth > 0 ? bodyScroll.availableWidth : (root.width - 24)
                anchors.margins: 14
                spacing: 12

                // Banner Status Utama
                Rectangle {
                    Layout.fillWidth: true
                    Layout.topMargin: 12
                    implicitHeight: bannerCol.implicitHeight + 16
                    radius: 8
                    color: {
                        if (root.diagData.status === "OK") return "#163828"
                        if (root.diagData.status === "ERROR") return "#3d1818"
                        if (root.diagData.status === "WARNING") return "#3d2e12"
                        return Theme.surfaceAlt
                    }
                    border.color: {
                        if (root.diagData.status === "OK") return Theme.up
                        if (root.diagData.status === "ERROR") return Theme.down
                        if (root.diagData.status === "WARNING") return "#c9922e"
                        return Theme.border
                    }
                    border.width: 1

                    RowLayout {
                        id: bannerCol
                        anchors.fill: parent
                        anchors.margins: 12
                        spacing: 12

                        Rectangle {
                            width: 36
                            height: 36
                            radius: 18
                            color: {
                                if (root.diagData.status === "OK") return Theme.up
                                if (root.diagData.status === "ERROR") return Theme.down
                                if (root.diagData.status === "WARNING") return "#c9922e"
                                return Theme.textMuted
                            }
                            Image {
                                anchors.centerIn: parent
                                source: (root.diagData.status === "OK") ? "qrc:/assets/check.svg" : "qrc:/assets/bolt.svg"
                                sourceSize: Qt.size(18, 18)
                            }
                        }

                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 3
                            Text {
                                text: {
                                    if (root.diagData.status === "OK") return "LULUS VERIFIKASI — SIAP TRADING"
                                    if (root.diagData.status === "ERROR") return "DITOLAK TERMINAL MT5 ('trading is not permitted')"
                                    if (root.diagData.status === "WARNING") return "ALGO TRADING NONAKTIF DI MT5"
                                    return "BELUM TERHUBUNG KE TERMINAL MT5"
                                }
                                color: {
                                    if (root.diagData.status === "OK") return Theme.up
                                    if (root.diagData.status === "ERROR") return Theme.down
                                    if (root.diagData.status === "WARNING") return "#ffb84d"
                                    return Theme.textSecondary
                                }
                                font.pixelSize: 13
                                font.bold: true
                            }
                            Text {
                                text: root.diagData.summary || ""
                                color: Theme.textSecondary
                                font.pixelSize: 11
                                wrapMode: Text.WordWrap
                                Layout.fillWidth: true
                            }
                        }
                    }
                }

                // Checklist Parameter
                Rectangle {
                    Layout.fillWidth: true
                    color: Theme.surfaceAlt
                    radius: 8
                    border.color: Theme.divider
                    border.width: 1
                    implicitHeight: checkCol.implicitHeight + 16

                    ColumnLayout {
                        id: checkCol
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 8

                        Text {
                            text: "Checklist Status Komponen:"
                            color: Theme.textPrimary
                            font.pixelSize: 11
                            font.bold: true
                        }

                        // 1. Koneksi Server Broker
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            Text {
                                text: root.diagData.server_connected ? "✓" : "✗"
                                color: root.diagData.server_connected ? Theme.up : Theme.down
                                font.bold: true
                                font.pixelSize: 13
                            }
                            Text {
                                text: "Koneksi Terminal & Broker:"
                                color: Theme.textSecondary
                                font.pixelSize: 11
                                Layout.preferredWidth: 160
                            }
                            Text {
                                text: root.diagData.server_connected
                                    ? ((root.diagData.server || "Exness") + " (#" + (root.diagData.login || "-") + " " + (root.diagData.account_type || "") + ") — Tersambung")
                                    : "Terputus / Belum Login"
                                color: root.diagData.server_connected ? Theme.up : Theme.down
                                font.pixelSize: 11
                                font.bold: true
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }
                        }

                        // 2. Saklar Algo Trading MT5
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            Text {
                                text: root.diagData.experts_trade_allowed ? "✓" : "✗"
                                color: root.diagData.experts_trade_allowed ? Theme.up : Theme.down
                                font.bold: true
                                font.pixelSize: 13
                            }
                            Text {
                                text: "Tombol Algo Trading (Ctrl+E):"
                                color: Theme.textSecondary
                                font.pixelSize: 11
                                Layout.preferredWidth: 160
                            }
                            Text {
                                text: root.diagData.experts_trade_allowed ? "Aktif di Toolbar MT5 (Ikon Hijau)" : "Nonaktif di Toolbar MT5 (Tekan Ctrl+E)"
                                color: root.diagData.experts_trade_allowed ? Theme.up : Theme.down
                                font.pixelSize: 11
                                font.bold: true
                                Layout.fillWidth: true
                            }
                        }

                        // 3. Server Internal MCP
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            Text {
                                text: root.diagData.mcp_trade_allowed ? "✓" : "✗"
                                color: root.diagData.mcp_trade_allowed ? Theme.up : Theme.down
                                font.bold: true
                                font.pixelSize: 13
                            }
                            Text {
                                text: "Server Internal MCP:"
                                color: Theme.textSecondary
                                font.pixelSize: 11
                                Layout.preferredWidth: 160
                            }
                            Text {
                                text: root.diagData.mcp_trade_allowed ? "Diizinkan (Tools > Options > MCP)" : "Dibatasi oleh Pengaturan MCP MT5"
                                color: root.diagData.mcp_trade_allowed ? Theme.up : Theme.down
                                font.pixelSize: 11
                                font.bold: true
                                Layout.fillWidth: true
                            }
                        }

                        // 4. Hak Trading Akun (Master Password)
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            Text {
                                text: root.diagData.account_trade_allowed ? "✓" : "✗"
                                color: root.diagData.account_trade_allowed ? Theme.up : Theme.down
                                font.bold: true
                                font.pixelSize: 13
                            }
                            Text {
                                text: "Hak Akses Akun Broker:"
                                color: Theme.textSecondary
                                font.pixelSize: 11
                                Layout.preferredWidth: 160
                            }
                            Text {
                                text: root.diagData.account_trade_allowed ? "Master Trading Password (Hak Penuh)" : "Terkunci / Read-Only (Investor Password)"
                                color: root.diagData.account_trade_allowed ? Theme.up : Theme.down
                                font.pixelSize: 11
                                font.bold: true
                                Layout.fillWidth: true
                            }
                        }

                        // 5. Simbol Aktif
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            Text {
                                text: root.diagData.symbol_valid ? "✓" : "!"
                                color: root.diagData.symbol_valid ? Theme.up : "#c9922e"
                                font.bold: true
                                font.pixelSize: 13
                            }
                            Text {
                                text: "Simbol Instrumen:"
                                color: Theme.textSecondary
                                font.pixelSize: 11
                                Layout.preferredWidth: 160
                            }
                            Text {
                                text: (root.diagData.symbol || "EURUSDm") + (root.diagData.symbol_valid ? " — Valid & Siap Trade" : " — Periksa Suffix Broker (m)")
                                color: root.diagData.symbol_valid ? Theme.up : "#ffb84d"
                                font.pixelSize: 11
                                font.bold: true
                                Layout.fillWidth: true
                            }
                        }
                    }
                }

                // Kotak Riwayat Penolakan (bila ada)
                Rectangle {
                    Layout.fillWidth: true
                    visible: root.diagData.trade_blocked === true
                    color: "#301515"
                    radius: 8
                    border.color: Theme.down
                    border.width: 1
                    implicitHeight: rejectCol.implicitHeight + 16

                    ColumnLayout {
                        id: rejectCol
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 4

                        Text {
                            text: "Catatan Penolakan Terakhir dari Terminal MT5:"
                            color: Theme.down
                            font.pixelSize: 11
                            font.bold: true
                        }
                        Text {
                            text: root.diagData.reject_reason || "Trading tidak diizinkan oleh terminal MT5 ('trading is not permitted')."
                            color: "#ffc2c2"
                            font.pixelSize: 10
                            wrapMode: Text.WordWrap
                            Layout.fillWidth: true
                        }
                    }
                }

                // Panduan Solusi Langkah demi Langkah (bila tidak OK)
                Rectangle {
                    Layout.fillWidth: true
                    visible: root.diagData.status !== "OK"
                    color: Theme.surfaceAlt
                    radius: 8
                    border.color: Theme.divider
                    border.width: 1
                    implicitHeight: solCol.implicitHeight + 16

                    ColumnLayout {
                        id: solCol
                        anchors.fill: parent
                        anchors.margins: 10
                        spacing: 6

                        Text {
                            text: "Langkah Perbaikan di Terminal MT5 (RDP/VPS):"
                            color: Theme.accent
                            font.pixelSize: 11
                            font.bold: true
                        }

                        Repeater {
                            model: root.diagData.solutions || []
                            delegate: RowLayout {
                                Layout.fillWidth: true
                                spacing: 6
                                Text { text: "•"; color: Theme.accent; font.bold: true }
                                Text {
                                    text: modelData
                                    color: Theme.textPrimary
                                    font.pixelSize: 10
                                    wrapMode: Text.WordWrap
                                    Layout.fillWidth: true
                                    lineHeight: 1.2
                                }
                            }
                        }
                    }
                }
            }
        }

        // ===== Footer Actions =====
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 52
            color: Theme.surfaceAlt
            radius: 12
            Rectangle {
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                height: 12
                color: Theme.surfaceAlt
            }
            Rectangle {
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                height: 1
                color: Theme.divider
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 14
                anchors.rightMargin: 14
                spacing: 8

                CButton {
                    text: "Verifikasi Ulang"
                    icon.source: "qrc:/assets/refresh.svg"
                    icon.width: 13
                    icon.height: 13
                    Layout.preferredHeight: 34
                    onClicked: root.refreshData()
                }

                CButton {
                    text: "Reset Status Tolak"
                    icon.source: "qrc:/assets/check.svg"
                    icon.width: 13
                    icon.height: 13
                    Layout.preferredHeight: 34
                    visible: root.diagData.trade_blocked === true
                    onClicked: {
                        if (bot) bot.clearTradeRejection()
                        root.refreshData()
                    }
                }

                Item { Layout.fillWidth: true }

                CButton {
                    text: "Tutup"
                    bg: Theme.surface
                    Layout.preferredHeight: 34
                    Layout.preferredWidth: 80
                    onClicked: root.close()
                }
            }
        }
    }
}
