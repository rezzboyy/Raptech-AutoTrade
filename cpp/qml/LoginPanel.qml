import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import QtQuick.Dialogs
import "."

// Panel login: pilih backend Native (library MT5) atau MCP (server MT5).
Rectangle {
    id: root
    color: Theme.surface
    radius: 10
    border.color: Theme.border

    readonly property bool botConnected: bot ? bot.connected : false
    readonly property bool authBusy: bot ? bot.authBusy : false
    readonly property string authAction: bot ? bot.authAction : ""
    readonly property string authMessage: bot ? bot.authMessage : ""
    property var profileList: []
    property var mcpProfileList: []
    property string backendMode: bot ? bot.backend : "mcp"
    property bool hasSavedPassword: false
    readonly property int ctrlHeight: 34
    readonly property int labelWidth: 92

    Component.onCompleted: {
        refreshProfiles()
        refreshMcpProfiles()
        // Otomatis terisi dari profil tersimpan pertama bila ada
        if (profileList.length > 0 && bot) {
            root.fillFrom(bot.loadProfileFile(profileList[0].file))
        }
        if (bot) {
            var mcpCfg = bot.getMcpConfig()
            if (mcpCfg.endpoint) endpointField.text = mcpCfg.endpoint
            if (mcpCfg.hasKey) apiKeyField.placeholderText = mcpCfg.keyPlaceholder
        }
        // Pertahankan mode koneksi yang sedang aktif atau dipilih pengguna
        var currentMode = bot ? bot.backend : "mcp"
        if (!currentMode) currentMode = "mcp"
        backendMode = currentMode
        backendBox.currentIndex = (currentMode === "native") ? 1 : (currentMode === "sim" ? 2 : 0)
    }

    function refreshProfiles() {
        if (!bot) return
        profileList = bot.listProfiles()
        var names = []
        for (var i = 0; i < profileList.length; i++)
            names.push(profileList[i].name + "  (" + profileList[i].login + ")")
        profileBox.model = names
    }
    function refreshMcpProfiles() {
        if (!bot) return
        mcpProfileList = bot.listMcpProfiles()
        var names = []
        for (var i = 0; i < mcpProfileList.length; i++) names.push(mcpProfileList[i].name)
        mcpProfileBox.model = names
    }
    function fillFrom(f) {
        if (f && f.login !== undefined) {
            loginField.text = String(f.login)
            serverField.text = f.server || ""
            pathField.text = f.path || ""
            passwordField.text = ""
            root.hasSavedPassword = (f.hasPassword === true)
            if (f.name) saveNameField.text = f.name
        }
    }
    function fillMcpFrom(f) {
        if (f && f.endpoint !== undefined) { endpointField.text = f.endpoint; apiKeyField.text = "" }
    }

    ScrollView {
        id: panelScroll
        anchors.fill: parent
        anchors.margins: 16
        contentWidth: availableWidth
        clip: true
        ScrollBar.vertical: ThinScrollBar {}

        ColumnLayout {
            id: mainForm
            width: Math.min(panelScroll.availableWidth > 0 ? panelScroll.availableWidth : (root.width - 32), 620)
            spacing: 12

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Image { source: "qrc:/assets/login.svg"; sourceSize.width: 16; sourceSize.height: 16 }
                Text { text: "Login Akun MT5"; color: Theme.textPrimary; font.pixelSize: 14; font.bold: true }
            }

            // ----- Pemilih backend -----
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                Label { text: "Metode koneksi"; color: Theme.textMuted; font.pixelSize: 11 }
                CCombo {
                    id: backendBox
                    Layout.preferredHeight: root.ctrlHeight
                    enabled: !root.botConnected
                    model: [
                        "MCP (Server MT5) — Rekomendasi",
                        "Native (Peluncur Terminal MT5)",
                        "Simulasi (Paper-Trading & Uji Skrip)"
                    ]
                    onActivated: {
                        var mode = (currentIndex === 1) ? "native" : (currentIndex === 2 ? "sim" : "mcp")
                        root.backendMode = mode
                        if (bot) bot.setBackend(mode)
                    }
                }
            }
            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.divider }

            // ====== MODE NATIVE ======
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 8
                visible: root.backendMode === "native"

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    Label { text: "Profil tersimpan"; color: Theme.textMuted; font.pixelSize: 11 }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6
                        CCombo {
                            id: profileBox
                            Layout.fillWidth: true
                            Layout.preferredHeight: root.ctrlHeight
                            onActivated: {
                                var p = root.profileList[currentIndex]
                                if (p) root.fillFrom(bot.loadProfileFile(p.file))
                            }
                        }
                        CButton {
                            text: "Muat"; icon.source: "qrc:/assets/upload.svg"; icon.width: 13; icon.height: 13
                            Layout.preferredHeight: root.ctrlHeight
                            enabled: !root.botConnected && root.profileList.length > 0
                            onClicked: { var p = root.profileList[profileBox.currentIndex]; if (p) root.fillFrom(bot.loadProfileFile(p.file)) }
                        }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    CButton {
                        text: "Simpan Profil"
                        icon.source: "qrc:/assets/save.svg"; icon.width: 13; icon.height: 13
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.ctrlHeight
                        enabled: !root.botConnected
                        onClicked: {
                            var creds = {
                                "login": parseInt(loginField.text || "0"),
                                "password": passwordField.text,
                                "server": serverField.text,
                                "path": pathField.text
                            }
                            if (bot && bot.saveProfile(creds, saveNameField.text)) {
                                root.refreshProfiles()
                            }
                        }
                    }
                    CButton { text: "Pilih File..."; icon.source: "qrc:/assets/folder.svg"; icon.width: 13; icon.height: 13; Layout.preferredHeight: root.ctrlHeight; enabled: !root.botConnected; onClicked: fileDialog.open() }
                    CButton {
                        text: "Hapus"; icon.source: "qrc:/assets/trash.svg"; icon.width: 13; icon.height: 13
                        Layout.preferredHeight: root.ctrlHeight
                        enabled: !root.botConnected && root.profileList.length > 0
                        onClicked: { var p = root.profileList[profileBox.currentIndex]; if (p) bot.deleteProfile(p.file) }
                    }
                }
                GridLayout {
                    Layout.fillWidth: true
                    columns: 2; rowSpacing: 6; columnSpacing: 8
                    Label { text: "Login"; color: Theme.textSecondary; Layout.preferredWidth: root.labelWidth }
                    CField { id: loginField; Layout.preferredHeight: root.ctrlHeight; enabled: !root.botConnected; inputMethodHints: Qt.ImhDigitsOnly; placeholderText: "Nomor akun MT5 (mis. 12345678)" }
                    Label { text: "Password"; color: Theme.textSecondary; Layout.preferredWidth: root.labelWidth }
                    CField {
                        id: passwordField
                        property bool showPassword: false
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.ctrlHeight
                        enabled: !root.botConnected
                        rightPadding: 32
                        echoMode: showPassword ? TextInput.Normal : TextInput.Password
                        placeholderText: root.hasSavedPassword ? "●●●●●●●● (tersimpan di profil)" : "masukkan password MT5"

                        Item {
                            anchors.right: parent.right
                            anchors.rightMargin: 6
                            anchors.verticalCenter: parent.verticalCenter
                            width: 24
                            height: 24

                            Image {
                                anchors.centerIn: parent
                                source: passwordField.showPassword ? "qrc:/assets/eye-off.svg" : "qrc:/assets/eye.svg"
                                sourceSize: Qt.size(16, 16)
                                width: 16
                                height: 16
                                opacity: eyeMouse.containsMouse ? 1.0 : 0.65
                            }

                            MouseArea {
                                id: eyeMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: passwordField.showPassword = !passwordField.showPassword
                            }

                            ToolTip.visible: eyeMouse.containsMouse
                            ToolTip.text: passwordField.showPassword ? "Sembunyikan password" : "Buka / tampilkan password"
                        }
                    }
                    Label { text: "Server"; color: Theme.textSecondary; Layout.preferredWidth: root.labelWidth }
                    CField { id: serverField; Layout.preferredHeight: root.ctrlHeight; enabled: !root.botConnected; placeholderText: "Server broker (mis. Exness-MT5Trial10)" }
                    Label { text: "Path (opsional)"; color: Theme.textSecondary; Layout.preferredWidth: root.labelWidth }
                    CField { id: pathField; Layout.preferredHeight: root.ctrlHeight; enabled: !root.botConnected; placeholderText: "Path terminal64.exe (opsional)" }
                }
            }

            // ====== MODE MCP ======
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 8
                visible: root.backendMode === "mcp"

                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 4
                    Label { text: "Profil MCP tersimpan"; color: Theme.textMuted; font.pixelSize: 11 }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6
                        CCombo { id: mcpProfileBox; Layout.preferredHeight: root.ctrlHeight }
                        CButton {
                            text: "Muat"; icon.source: "qrc:/assets/upload.svg"; icon.width: 13; icon.height: 13
                            Layout.preferredHeight: root.ctrlHeight
                            enabled: !root.botConnected && root.mcpProfileList.length > 0
                            onClicked: { var p = root.mcpProfileList[mcpProfileBox.currentIndex]; if (p) root.fillMcpFrom(bot.loadMcpProfileFile(p.file)) }
                        }
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    CButton { text: "Pilih File..."; icon.source: "qrc:/assets/folder.svg"; icon.width: 13; icon.height: 13; Layout.fillWidth: true; Layout.preferredHeight: root.ctrlHeight; enabled: !root.botConnected; onClicked: mcpFileDialog.open() }
                    CButton {
                        text: "Hapus"; icon.source: "qrc:/assets/trash.svg"; icon.width: 13; icon.height: 13
                        Layout.preferredHeight: root.ctrlHeight
                        enabled: !root.botConnected && root.mcpProfileList.length > 0
                        onClicked: { var p = root.mcpProfileList[mcpProfileBox.currentIndex]; if (p) bot.deleteMcpProfile(p.file) }
                    }
                }
                GridLayout {
                    Layout.fillWidth: true
                    columns: 2; rowSpacing: 6; columnSpacing: 8
                    Label { text: "Endpoint"; color: Theme.textSecondary; Layout.preferredWidth: root.labelWidth }
                    CField { id: endpointField; Layout.preferredHeight: root.ctrlHeight; enabled: !root.botConnected; text: "http://127.0.0.1:22346/mcp" }
                    Label { text: "API Key"; color: Theme.textSecondary; Layout.preferredWidth: root.labelWidth }
                    CField {
                        id: apiKeyField
                        property bool showKey: false
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.ctrlHeight
                        enabled: !root.botConnected
                        rightPadding: 32
                        echoMode: showKey ? TextInput.Normal : TextInput.Password
                        placeholderText: "kosongkan jika pakai profil"

                        Item {
                            anchors.right: parent.right
                            anchors.rightMargin: 6
                            anchors.verticalCenter: parent.verticalCenter
                            width: 24
                            height: 24

                            Image {
                                anchors.centerIn: parent
                                source: apiKeyField.showKey ? "qrc:/assets/eye-off.svg" : "qrc:/assets/eye.svg"
                                sourceSize: Qt.size(16, 16)
                                width: 16
                                height: 16
                                opacity: apiEyeMouse.containsMouse ? 1.0 : 0.65
                            }

                            MouseArea {
                                id: apiEyeMouse
                                anchors.fill: parent
                                hoverEnabled: true
                                cursorShape: Qt.PointingHandCursor
                                onClicked: apiKeyField.showKey = !apiKeyField.showKey
                            }

                            ToolTip.visible: apiEyeMouse.containsMouse
                            ToolTip.text: apiKeyField.showKey ? "Sembunyikan API key" : "Buka / tampilkan API key"
                        }
                    }
                }
                Text {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    color: (bot && bot.getMcpConfig().hasKey) ? Theme.accent : Theme.textMuted
                    font.pixelSize: 10; lineHeight: 1.15
                    text: (bot && bot.getMcpConfig().hasKey)
                        ? "✓ Kunci API MT5 aktif terdeteksi dari mcp_secret.json. Anda bisa langsung klik Login & Connect."
                        : "API Key dari MT5: Tools → Options → tab MCP (aktifkan 'Enable internal server')."
                }
            }

            // ====== MODE SIMULASI ======
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 8
                visible: root.backendMode === "sim"

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Label { text: "Simbol Uji"; color: Theme.textSecondary; Layout.preferredWidth: root.labelWidth }
                    CField {
                        id: simSymbolField
                        Layout.preferredHeight: root.ctrlHeight
                        enabled: !root.botConnected
                        text: (bot && bot.chartSymbol) ? bot.chartSymbol : "XAUUSDm"
                        placeholderText: "contoh: XAUUSDm, EURUSDm"
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Label { text: "Saldo Virtual"; color: Theme.textSecondary; Layout.preferredWidth: root.labelWidth }
                    CField {
                        id: simBalanceField
                        Layout.preferredHeight: root.ctrlHeight
                        enabled: !root.botConnected
                        text: "10000"
                        validator: DoubleValidator { bottom: 100 }
                        placeholderText: "USD (min 100)"
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Label { text: "Skenario"; color: Theme.textSecondary; Layout.preferredWidth: root.labelWidth }
                    CCombo {
                        id: simScenarioBox
                        Layout.preferredHeight: root.ctrlHeight
                        enabled: !root.botConnected
                        model: ["volatile", "uptrend", "downtrend", "sideways", "spread_spike"]
                    }
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Label { text: "Spread (pts)"; color: Theme.textSecondary; Layout.preferredWidth: root.labelWidth }
                    CField {
                        id: simSpreadField
                        Layout.preferredHeight: root.ctrlHeight
                        enabled: !root.botConnected
                        text: "25"
                        validator: IntValidator { bottom: 1; top: 5000 }
                    }
                }
                Text {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    color: Theme.accent
                    font.pixelSize: 10; lineHeight: 1.2
                    text: "Mode Simulasi berjalan 100% terisolasi dari akun MT5 Demo/Real. Ideal untuk menguji validitas skrip, pending order, SL/TP, serta trailing/recovery sebelum live."
                }
            }

            // ----- Simpan sbg (hanya MT5 Native / MCP) -----
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                visible: root.backendMode !== "sim"
                Label { text: "Simpan sbg"; color: Theme.textSecondary; Layout.preferredWidth: root.labelWidth }
                CField { id: saveNameField; Layout.preferredHeight: root.ctrlHeight; enabled: !root.botConnected; placeholderText: "nama profil (opsional)" }
            }

            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.divider; Layout.topMargin: 4 }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                CButton {
                    text: {
                        if (root.authBusy && root.authAction === "login") return "Menghubungkan..."
                        if (root.botConnected) return "Terhubung"
                        return (root.backendMode === "sim" ? "Mulai Simulasi" : "Login & Connect")
                    }
                    icon.source: "qrc:/assets/power.svg"; icon.width: 15; icon.height: 15
                    bg: (root.botConnected || root.authBusy) ? Theme.surfaceAlt : Theme.accent
                    fg: (root.botConnected || root.authBusy) ? Theme.textSecondary : "#ffffff"
                    enabled: !root.botConnected && !root.authBusy
                    Layout.fillWidth: true
                    Layout.preferredHeight: 40
                    font.bold: true
                    onClicked: {
                        if (root.backendMode === "sim") {
                            bot.connectSim({
                                "symbol": simSymbolField.text.trim() || "XAUUSDm",
                                "balance": parseFloat(simBalanceField.text || "10000"),
                                "scenario": simScenarioBox.currentText,
                                "spread_points": parseInt(simSpreadField.text || "25")
                            })
                        } else if (root.backendMode === "mcp") {
                            bot.connectMcp({ "endpoint": endpointField.text, "api_key": apiKeyField.text }, saveNameField.text)
                        } else {
                            bot.loginAndConnect({
                                "login": parseInt(loginField.text || "0"),
                                "password": passwordField.text,
                                "server": serverField.text,
                                "path": pathField.text
                            }, saveNameField.text)
                        }
                    }
                }
                CButton {
                    text: (root.authBusy && root.authAction === "logout") ? "Logout..." : "Logout"
                    icon.source: "qrc:/assets/link-off.svg"; icon.width: 14; icon.height: 14
                    bg: Theme.down; fg: "#ffffff"
                    visible: root.botConnected || (root.authBusy && root.authAction === "logout")
                    enabled: root.botConnected && !root.authBusy
                    Layout.preferredHeight: 40
                    Layout.preferredWidth: 120
                    onClicked: bot.logoutAccount()
                }
            }

            // ===== Banner Loading & Keterangan Login / Logout =====
            Rectangle {
                Layout.fillWidth: true
                visible: root.authBusy || root.authMessage.length > 0
                radius: 8
                implicitHeight: authBannerRow.implicitHeight + 14
                color: root.authBusy
                       ? Theme.bannerWarnBg
                       : (root.botConnected ? Theme.bannerOkBg : Theme.surfaceAlt)
                border.color: root.authBusy
                              ? Theme.badgeWarnBorder
                              : (root.botConnected ? Theme.up : Theme.border)
                border.width: 1

                RowLayout {
                    id: authBannerRow
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 8

                    BusyIndicator {
                        running: root.authBusy
                        visible: root.authBusy
                        Layout.preferredWidth: 20
                        Layout.preferredHeight: 20
                    }

                    Image {
                        visible: !root.authBusy
                        source: root.botConnected ? "qrc:/assets/check.svg" : "qrc:/assets/activity.svg"
                        sourceSize: Qt.size(16, 16)
                        Layout.preferredWidth: 16
                        Layout.preferredHeight: 16
                    }

                    Text {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        font.pixelSize: 11
                        font.bold: root.authBusy
                        color: root.authBusy ? Theme.badgeWarnText : (root.botConnected ? Theme.up : Theme.textSecondary)
                        text: root.authMessage
                    }
                }
            }
        }
    }

    FileDialog {
        id: fileDialog
        title: "Pilih file profil (.json)"
        nameFilters: ["Profil JSON (*.json)"]
        onAccepted: root.fillFrom(bot.loadProfileFile(selectedFile.toString()))
    }
    FileDialog {
        id: mcpFileDialog
        title: "Pilih file profil MCP (.json)"
        nameFilters: ["Profil MCP JSON (*.json)"]
        onAccepted: root.fillMcpFrom(bot.loadMcpProfileFile(selectedFile.toString()))
    }

    Connections {
        target: bot
        function onProfilesChanged(list) { root.refreshProfiles() }
        function onMcpProfilesChanged(list) { root.refreshMcpProfiles() }
        function onBackendChanged(name) {
            root.backendMode = name
            backendBox.currentIndex = (name === "native") ? 1 : 0
        }
    }
}
