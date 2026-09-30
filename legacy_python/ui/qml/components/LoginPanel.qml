import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import QtQuick.Dialogs
import ".."

// Panel login adaptif: mendukung backend Native (library) & MCP (server MT5).
Rectangle {
    id: root
    objectName: "loginPanel"
    color: Theme.surface
    radius: 10
    border.color: Theme.border

    readonly property bool botConnected: bot ? bot.connected : false
    property var profileList: []
    property var mcpProfileList: []
    // "native" | "mcp"
    property string backendMode: bot ? bot.backend : "native"

    // Metrik layout seragam.
    readonly property int ctrlHeight: 34
    readonly property int labelWidth: 92

    Component.onCompleted: {
        refreshProfiles()
        refreshMcpProfiles()
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
        for (var i = 0; i < mcpProfileList.length; i++)
            names.push(mcpProfileList[i].name)
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
        if (f && f.endpoint !== undefined) {
            endpointField.text = f.endpoint
            apiKeyField.text = ""  // pakai key dari settings (profil sudah dimuat)
        }
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

            // ================= Header =================
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Image { source: "../../assets/login.svg"; sourceSize.width: 16; sourceSize.height: 16 }
                Text { text: "Login Akun MT5"; color: Theme.textPrimary; font.pixelSize: 14; font.bold: true }
            }

            // ----- Pemilih backend -----
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4
                Label { text: "Metode koneksi"; color: Theme.textMuted; font.pixelSize: 11 }
                CCombo {
                    id: backendBox
                    Layout.fillWidth: true
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
                        CCombo {
                            id: profileBox
                            Layout.fillWidth: true
                            Layout.preferredHeight: root.ctrlHeight
                        }
                        Button {
                            text: "Muat"
                            Layout.preferredHeight: root.ctrlHeight
                            icon.source: "../../assets/upload.svg"; icon.width: 14; icon.height: 14
                            enabled: !root.botConnected && root.profileList.length > 0
                            onClicked: {
                                var p = root.profileList[profileBox.currentIndex]
                                if (p) root.fillFrom(bot.loadProfileFile(p.file))
                            }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    Button {
                        text: "Pilih File..."
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.ctrlHeight
                        icon.source: "../../assets/folder.svg"; icon.width: 14; icon.height: 14
                        enabled: !root.botConnected
                        onClicked: fileDialog.open()
                    }
                    Button {
                        text: "Hapus"
                        Layout.preferredHeight: root.ctrlHeight
                        icon.source: "../../assets/trash.svg"; icon.width: 14; icon.height: 14
                        enabled: !root.botConnected && root.profileList.length > 0
                        onClicked: {
                            var p = root.profileList[profileBox.currentIndex]
                            if (p) bot.deleteProfile(p.file)
                        }
                    }
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    rowSpacing: 6
                    columnSpacing: 8
                    Label { text: "Login"; color: Theme.textSecondary; Layout.preferredWidth: root.labelWidth }
                    CField { id: loginField; Layout.fillWidth: true; Layout.preferredHeight: root.ctrlHeight; enabled: !root.botConnected; inputMethodHints: Qt.ImhDigitsOnly }
                    Label { text: "Password"; color: Theme.textSecondary; Layout.preferredWidth: root.labelWidth }
                    CField { id: passwordField; Layout.fillWidth: true; Layout.preferredHeight: root.ctrlHeight; enabled: !root.botConnected; echoMode: TextInput.Password; placeholderText: "kosongkan jika pakai profil" }
                    Label { text: "Server"; color: Theme.textSecondary; Layout.preferredWidth: root.labelWidth }
                    CField { id: serverField; Layout.fillWidth: true; Layout.preferredHeight: root.ctrlHeight; enabled: !root.botConnected }
                    Label { text: "Path (opsional)"; color: Theme.textSecondary; Layout.preferredWidth: root.labelWidth }
                    CField { id: pathField; Layout.fillWidth: true; Layout.preferredHeight: root.ctrlHeight; enabled: !root.botConnected }
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
                        CCombo {
                            id: mcpProfileBox
                            Layout.fillWidth: true
                            Layout.preferredHeight: root.ctrlHeight
                        }
                        Button {
                            text: "Muat"
                            Layout.preferredHeight: root.ctrlHeight
                            icon.source: "../../assets/upload.svg"; icon.width: 14; icon.height: 14
                            enabled: !root.botConnected && root.mcpProfileList.length > 0
                            onClicked: {
                                var p = root.mcpProfileList[mcpProfileBox.currentIndex]
                                if (p) root.fillMcpFrom(bot.loadMcpProfileFile(p.file))
                            }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    Button {
                        text: "Pilih File..."
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.ctrlHeight
                        icon.source: "../../assets/folder.svg"; icon.width: 14; icon.height: 14
                        enabled: !root.botConnected
                        onClicked: mcpFileDialog.open()
                    }
                    Button {
                        text: "Hapus"
                        Layout.preferredHeight: root.ctrlHeight
                        icon.source: "../../assets/trash.svg"; icon.width: 14; icon.height: 14
                        enabled: !root.botConnected && root.mcpProfileList.length > 0
                        onClicked: {
                            var p = root.mcpProfileList[mcpProfileBox.currentIndex]
                            if (p) bot.deleteMcpProfile(p.file)
                        }
                    }
                }

                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    rowSpacing: 6
                    columnSpacing: 8
                    Label { text: "Endpoint"; color: Theme.textSecondary; Layout.preferredWidth: root.labelWidth }
                    CField { id: endpointField; Layout.fillWidth: true; Layout.preferredHeight: root.ctrlHeight; enabled: !root.botConnected; text: "http://127.0.0.1:22346/mcp" }
                    Label { text: "API Key"; color: Theme.textSecondary; Layout.preferredWidth: root.labelWidth }
                    CField { id: apiKeyField; Layout.fillWidth: true; Layout.preferredHeight: root.ctrlHeight; enabled: !root.botConnected; echoMode: TextInput.Password; placeholderText: "kosongkan jika pakai profil" }
                }
                Text {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    color: Theme.textMuted
                    font.pixelSize: 10
                    lineHeight: 1.15
                    text: "API Key dari MT5: Tools -> Options -> tab MCP (aktifkan 'Enable internal server')."
                }
            }

            // ----- Simpan sbg (dipakai kedua mode) -----
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Label { text: "Simpan sbg"; color: Theme.textSecondary; Layout.preferredWidth: root.labelWidth }
                CField {
                    id: saveNameField
                    Layout.fillWidth: true
                    Layout.preferredHeight: root.ctrlHeight
                    enabled: !root.botConnected
                    placeholderText: "nama profil (opsional, auto jika kosong)"
                }
            }

            // Spacer: dorong tombol aksi ke bawah agar ruang kosong terpakai rapi.
            Item { Layout.fillHeight: true; Layout.minimumHeight: 8 }

            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.divider }

            // ----- Tombol aksi (pinned bawah) -----
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Button {
                    text: root.botConnected ? "Terhubung" : "Login && Connect"
                    icon.source: "../../assets/power.svg"; icon.width: 15; icon.height: 15
                    enabled: !root.botConnected
                    Layout.fillWidth: true
                    Layout.preferredHeight: 40
                    highlighted: !root.botConnected
                    Material.background: root.botConnected ? Theme.surfaceAlt : Theme.accent
                    Material.foreground: "#ffffff"
                    font.bold: true
                    onClicked: {
                        if (root.backendMode === "mcp") {
                            var mcpCfg = {
                                "endpoint": endpointField.text,
                                "api_key": apiKeyField.text
                            }
                            bot.connectMcp(mcpCfg, saveNameField.text)
                        } else {
                            var creds = {
                                "login": parseInt(loginField.text || "0"),
                                "password": passwordField.text,
                                "server": serverField.text,
                                "path": pathField.text
                            }
                            bot.loginAndConnect(creds, saveNameField.text)
                        }
                    }
                }
                Button {
                    text: "Logout"
                    icon.source: "../../assets/link-off.svg"; icon.width: 15; icon.height: 15
                    enabled: root.botConnected
                    Layout.preferredHeight: 40
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
