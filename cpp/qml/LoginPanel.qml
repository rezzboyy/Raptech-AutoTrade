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
    property var profileList: []
    property var mcpProfileList: []
    property string backendMode: bot ? bot.backend : "mcp"
    readonly property int ctrlHeight: 34
    readonly property int labelWidth: 92

    Component.onCompleted: {
        refreshProfiles()
        refreshMcpProfiles()
        if (bot) {
            var mcpCfg = bot.getMcpConfig()
            if (mcpCfg.endpoint) endpointField.text = mcpCfg.endpoint
            if (mcpCfg.hasKey) apiKeyField.placeholderText = mcpCfg.keyPlaceholder
        }
        // Default ke MCP (metode yang berfungsi di versi C++), Native tetap bisa dipilih.
        if (!root.botConnected && backendMode !== "mcp") {
            backendMode = "mcp"
            if (bot) bot.setBackend("mcp")
        }
        backendBox.currentIndex = (backendMode === "mcp") ? 1 : 0
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
            serverField.text = f.server
            pathField.text = f.path
            passwordField.text = ""
        }
    }
    function fillMcpFrom(f) {
        if (f && f.endpoint !== undefined) { endpointField.text = f.endpoint; apiKeyField.text = "" }
    }

    ScrollView {
        id: panelScroll
        anchors.fill: parent
        anchors.margins: 12
        clip: true
        ScrollBar.vertical: ThinScrollBar {}
        ScrollBar.horizontal: ThinScrollBar {}

        ColumnLayout {
            width: panelScroll.availableWidth > 0 ? panelScroll.availableWidth : (root.width - 24)
            spacing: 10

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
                    model: ["Native (Library MetaTrader5)", "MCP (Server MT5)"]
                    onActivated: {
                        var mode = (currentIndex === 1) ? "mcp" : "native"
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
                        CCombo { id: profileBox; Layout.preferredHeight: root.ctrlHeight }
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
                    CButton { text: "Pilih File..."; icon.source: "qrc:/assets/folder.svg"; icon.width: 13; icon.height: 13; Layout.fillWidth: true; Layout.preferredHeight: root.ctrlHeight; enabled: !root.botConnected; onClicked: fileDialog.open() }
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
                    CField { id: loginField; Layout.preferredHeight: root.ctrlHeight; enabled: !root.botConnected; inputMethodHints: Qt.ImhDigitsOnly }
                    Label { text: "Password"; color: Theme.textSecondary; Layout.preferredWidth: root.labelWidth }
                    CField { id: passwordField; Layout.preferredHeight: root.ctrlHeight; enabled: !root.botConnected; echoMode: TextInput.Password; placeholderText: "kosongkan jika pakai profil" }
                    Label { text: "Server"; color: Theme.textSecondary; Layout.preferredWidth: root.labelWidth }
                    CField { id: serverField; Layout.preferredHeight: root.ctrlHeight; enabled: !root.botConnected }
                    Label { text: "Path (opsional)"; color: Theme.textSecondary; Layout.preferredWidth: root.labelWidth }
                    CField { id: pathField; Layout.preferredHeight: root.ctrlHeight; enabled: !root.botConnected }
                }
                Text {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap; color: Theme.warn; font.pixelSize: 10; lineHeight: 1.15
                    text: "Catatan: backend Native belum tersedia di versi C++ ini. Profil bisa disimpan, tetapi untuk connect gunakan metode MCP."
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
                    CField { id: apiKeyField; Layout.preferredHeight: root.ctrlHeight; enabled: !root.botConnected; echoMode: TextInput.Password; placeholderText: "kosongkan jika pakai profil" }
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

            // ----- Simpan sbg (kedua mode) -----
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Label { text: "Simpan sbg"; color: Theme.textSecondary; Layout.preferredWidth: root.labelWidth }
                CField { id: saveNameField; Layout.preferredHeight: root.ctrlHeight; enabled: !root.botConnected; placeholderText: "nama profil (opsional)" }
            }

            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.divider; Layout.topMargin: 4 }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                CButton {
                    text: root.botConnected ? "Terhubung" : "Login & Connect"
                    icon.source: "qrc:/assets/power.svg"; icon.width: 15; icon.height: 15
                    bg: root.botConnected ? Theme.surfaceAlt : Theme.accent
                    fg: "#ffffff"
                    enabled: !root.botConnected
                    Layout.fillWidth: true
                    Layout.preferredHeight: 40
                    font.bold: true
                    onClicked: {
                        if (root.backendMode === "mcp") {
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
                    text: "Logout"
                    icon.source: "qrc:/assets/link-off.svg"; icon.width: 14; icon.height: 14
                    bg: Theme.down; fg: "#ffffff"
                    visible: root.botConnected
                    enabled: root.botConnected
                    Layout.preferredHeight: 40
                    Layout.preferredWidth: 110
                    onClicked: bot.logoutAccount()
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
            backendBox.currentIndex = (name === "mcp") ? 1 : 0
        }
    }
}
