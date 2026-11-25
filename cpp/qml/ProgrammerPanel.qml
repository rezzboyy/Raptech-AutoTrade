import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Dialogs
import Xaviq 1.0
import "."

// Mode Programmer: editor skrip JS (editor pro) + Bantuan API + Start/Stop.
Rectangle {
    id: root
    color: Theme.surface
    radius: 10
    border.color: Theme.border

    property var apiGroups: []
    property var settingsGroups: []
    property int errorLine: 0
    property bool simRunning: false
    property bool hasSimResult: false
    property var simResult: ({})
    readonly property bool botTrading: bot ? bot.trading : false
    readonly property bool botConnected: bot ? bot.connected : false

    Connections {
        target: bot
        function onSimulationFinished(res) {
            root.simRunning = false
            root.simResult = res || ({})
            root.hasSimResult = true
        }
    }

    Component.onCompleted: {
        apiGroups = bot ? bot.apiReference() : []
        settingsGroups = bot ? bot.settingsReference() : []
        var c = bot ? bot.currentScript() : ""
        editor.text = (c && c.length > 0) ? c : (bot ? bot.scriptTemplate() : "")
        refreshScripts()
    }

    function refreshScripts() { scriptBox.model = bot ? bot.listScripts() : [] }

    FileDialog {
        id: scriptFileDialog
        title: "Pilih file skrip strategi (.py / .js)"
        nameFilters: ["Skrip Trading (*.py *.js)", "Skrip Python (*.py)", "Skrip JavaScript (*.js)", "Semua File (*.*)"]
        onAccepted: {
            var src = bot.loadScriptFile(selectedFile.toString())
            if (src && src.length > 0) {
                editor.text = src
                var pathStr = selectedFile.toString()
                var nameOnly = pathStr.split('/').pop().replace(/\.(py|js)$/i, '')
                nameField.text = nameOnly
                root.runValidate()
            }
        }
    }

    // ===== Dialog Bantuan SETTINGS =====
    Dialog {
        id: settingsHelpDialog
        title: "Variabel SETTINGS"
        modal: true
        width: Math.min(root.width - 40, 460)
        height: Math.min(root.height - 60, 560)
        anchors.centerIn: Overlay.overlay
        standardButtons: Dialog.Close

        ColumnLayout {
            anchors.fill: parent
            spacing: 6
            CButton {
                text: "Sisipkan Template SETTINGS Lengkap"
                bg: Theme.accent; fg: "#ffffff"
                Layout.fillWidth: true; Layout.preferredHeight: 30; font.pixelSize: 11
                onClicked: { root.insertSnippet(bot.settingsTemplate() + "\n"); settingsHelpDialog.close() }
            }
            ListView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: root.settingsGroups
                spacing: 6
                ScrollBar.vertical: ThinScrollBar {}
                delegate: Column {
                    width: ListView.view.width
                    spacing: 2
                    Text { text: modelData.group; color: Theme.accent; font.pixelSize: 12; font.bold: true }
                    Repeater {
                        model: modelData.items
                        Row {
                            width: parent.width
                            spacing: 6
                            Column {
                                width: parent.width - 90
                                Text { text: modelData.signature; color: Theme.textPrimary; font.family: "Consolas, monospace"; font.pixelSize: 11; width: parent.width; elide: Text.ElideRight }
                                Text { text: modelData.desc; color: Theme.textMuted; font.pixelSize: 9; width: parent.width; wrapMode: Text.WordWrap }
                            }
                            CButton { text: "Sisipkan"; font.pixelSize: 10; implicitHeight: 26; height: 26; width: 84; onClicked: { root.insertSnippet(modelData.snippet + "\n"); settingsHelpDialog.close() } }
                        }
                    }
                }
            }
        }
    }

    function runValidate() {
        var r = bot.validateScript(editor.text)
        if (r.ok) { hl.errorLine = -1; root.errorLine = 0; setStatus("✓ Skrip valid.", true) }
        else { hl.errorLine = r.line; root.errorLine = r.line; setStatus("✗ Baris " + r.line + ": " + r.message, false) }
    }
    function setStatus(msg, ok) { statusText.text = msg; statusText.color = ok ? Theme.up : Theme.down }
    function insertSnippet(t) {
        if (!t) return
        var pos = editor.cursorPosition
        editor.insert(pos, t)
        editor.cursorPosition = pos + t.length
        editor.forceActiveFocus()
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
                spacing: 6
                Image { source: "qrc:/assets/strategy.svg"; sourceSize.width: 16; sourceSize.height: 16 }
                Text {
                    text: "Mode Programmer"
                    color: Theme.textPrimary
                    font.pixelSize: 14
                    font.bold: true
                    Layout.fillWidth: true
                    elide: Text.ElideRight
                }
                CButton { text: "Bantuan API"; icon.source: "qrc:/assets/log.svg"; icon.width: 12; icon.height: 12; Layout.preferredHeight: 28; font.pixelSize: 11; onClicked: apiHelpDialog.open() }
                CButton { text: "SETTINGS"; icon.source: "qrc:/assets/strategy.svg"; icon.width: 12; icon.height: 12; Layout.preferredHeight: 28; font.pixelSize: 11; onClicked: settingsHelpDialog.open() }
                CButton { text: "Template"; Layout.preferredHeight: 28; font.pixelSize: 11; onClicked: editor.text = bot.scriptTemplate() }
            }
            Text {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                color: Theme.textMuted; font.pixelSize: 10; lineHeight: 1.15
                text: "Tulis strategi JavaScript tersandbox: SETTINGS (opsional), PARAMS (opsional), dan on_bar(ctx) yang mengembalikan \"BUY\"/\"SELL\"/null atau perintah ctx.*."
            }

            // ===== Manajemen file skrip =====
            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                Text { text: "Skrip"; color: Theme.textMuted; font.pixelSize: 11 }
                CCombo { id: scriptBox; Layout.fillWidth: true; Layout.preferredHeight: 30 }
                CButton {
                    text: "Muat"; icon.source: "qrc:/assets/upload.svg"; icon.width: 12; icon.height: 12
                    Layout.preferredHeight: 30; font.pixelSize: 11
                    enabled: scriptBox.count > 0
                    onClicked: {
                        var src = bot.loadScript(scriptBox.currentText)
                        if (src && src.length > 0) {
                            editor.text = src
                            nameField.text = scriptBox.currentText
                            root.runValidate()
                        }
                    }
                }
                CButton {
                    text: "File..."; icon.source: "qrc:/assets/folder.svg"; icon.width: 12; icon.height: 12
                    Layout.preferredHeight: 30; font.pixelSize: 11
                    onClicked: scriptFileDialog.open()
                }
            }
            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                CField { id: nameField; Layout.fillWidth: true; Layout.preferredHeight: 30; placeholderText: "nama skrip untuk disimpan" }
                CButton {
                    text: "Simpan File"; icon.source: "qrc:/assets/save.svg"; icon.width: 12; icon.height: 12
                    Layout.preferredHeight: 30; font.pixelSize: 11
                    onClicked: {
                        if (bot.saveScript(nameField.text, editor.text)) {
                            root.refreshScripts()
                            root.setStatus("Skrip '" + nameField.text + "' tersimpan ke folder scripts.", true)
                        } else {
                            root.setStatus("Gagal menyimpan skrip (nama kosong?).", false)
                        }
                    }
                }
            }

            // Editor Pro: nomor baris + syntax highlight + validasi real-time.
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: 320
                color: Theme.bg
                radius: 8
                border.color: root.errorLine > 0 ? Theme.down : Theme.border

                FontMetrics { id: fm; font: editor.font }
                JsHighlighter { id: hl; document: editor.textDocument; errorLine: -1; isDark: Theme.isDark }

                Flickable {
                    id: flick
                    anchors.fill: parent
                    anchors.margins: 6
                    clip: true
                    contentWidth: editorRow.width
                    contentHeight: editorRow.height
                    ScrollBar.vertical: ThinScrollBar {}

                    Row {
                        id: editorRow
                        Column {
                            id: gutter
                            width: 44
                            Repeater {
                                model: editor.lineCount
                                Text {
                                    width: 44; height: fm.height
                                    text: (index + 1)
                                    color: (index + 1) === root.errorLine ? Theme.down : Theme.textMuted
                                    horizontalAlignment: Text.AlignRight; rightPadding: 8
                                    font: editor.font
                                }
                            }
                        }
                        TextArea {
                            id: editor
                            width: Math.max(flick.width - gutter.width, implicitWidth)
                            wrapMode: TextArea.NoWrap
                            font.family: "Consolas, 'Courier New', monospace"
                            font.pixelSize: 13
                            color: Theme.textPrimary
                            selectByMouse: true
                            tabStopDistance: 32
                            background: Rectangle { color: "transparent" }
                            onTextChanged: validateTimer.restart()
                        }
                    }
                }
                Timer { id: validateTimer; interval: 450; onTriggered: root.runValidate() }
            }

            Text {
                id: statusText
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                font.pixelSize: 11; color: Theme.textMuted
                text: "Ketik skrip — validasi otomatis berjalan."
            }

            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.divider }

            // ===== Aksi =====
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                CButton { text: "Validasi"; icon.source: "qrc:/assets/activity.svg"; icon.width: 13; icon.height: 13; Layout.fillWidth: true; Layout.preferredHeight: 34; onClicked: root.runValidate() }
                CButton { text: "Simpan & Terapkan Skrip"; bg: Theme.accent; fg: "#ffffff"; icon.source: "qrc:/assets/save.svg"; icon.width: 14; icon.height: 14; Layout.fillWidth: true; Layout.preferredHeight: 34; onClicked: { bot.setScript(editor.text); root.setStatus("Skrip disimpan & diterapkan (custom_script).", true) } }
            }

            // ===== Uji Simulasi Cepat (Terisolasi) =====
            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                CCombo {
                    id: simScenarioCombo
                    Layout.preferredHeight: 32
                    Layout.preferredWidth: 118
                    Layout.fillWidth: false
                    model: ["volatile", "uptrend", "downtrend", "sideways", "spread_spike"]
                }
                CCombo {
                    id: simBarsCombo
                    Layout.preferredHeight: 32
                    Layout.preferredWidth: 94
                    Layout.fillWidth: false
                    model: ["120 bar", "240 bar", "360 bar"]
                }
                CButton {
                    text: root.simRunning ? "Menguji..." : "Uji Simulasi"
                    bg: Theme.warn; fg: "#ffffff"
                    icon.source: "qrc:/assets/bolt.svg"; icon.width: 12; icon.height: 12
                    Layout.fillWidth: true; Layout.preferredHeight: 32
                    enabled: !root.simRunning && bot
                    onClicked: {
                        root.simRunning = true
                        var barCnt = parseInt(simBarsCombo.currentText) || 120
                        bot.runScriptSimulation(editor.text, simScenarioCombo.currentText, barCnt, 10000.0, 25)
                    }
                }
            }

            Rectangle {
                Layout.fillWidth: true
                visible: root.hasSimResult
                radius: 6
                color: (root.simResult.ok === true) ? Theme.bannerOkBg : Theme.bannerErrBg
                border.color: (root.simResult.ok === true) ? Theme.up : Theme.down
                border.width: 1
                implicitHeight: simSummaryCol.implicitHeight + 12

                ColumnLayout {
                    id: simSummaryCol
                    anchors.fill: parent
                    anchors.margins: 8
                    spacing: 2
                    Text {
                        Layout.fillWidth: true
                        font.pixelSize: 11; font.bold: true
                        color: (root.simResult.ok === true) ? Theme.up : Theme.down
                        text: (root.simResult.ok === true)
                              ? ("HASIL SIMULASI (" + (root.simResult.symbol || "") + " • " + (root.simResult.scenario || "") + ")")
                              : "SIMULASI GAGAL — PERIKSA SKRIP"
                    }
                    Text {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        font.pixelSize: 10
                        color: Theme.textPrimary
                        text: (root.simResult.ok === true)
                              ? ("Trades: " + (root.simResult.trades_count || 0)
                                 + " | Open: " + (root.simResult.open_positions || 0)
                                 + " | Pending: " + (root.simResult.pending_orders || 0)
                                 + " | WinRate: " + Number(root.simResult.win_rate || 0).toFixed(1) + "%"
                                 + " | Net: " + (Number(root.simResult.net_profit || 0) >= 0 ? "+$" : "-$") + Math.abs(Number(root.simResult.net_profit || 0)).toFixed(2)
                                 + " | MaxDD: " + Number(root.simResult.max_drawdown_pct || 0).toFixed(2) + "%")
                              : String(root.simResult.error || "Kesalahan tidak diketahui")
                    }
                }
            }
            Button {
                text: root.botTrading ? "Stop Trading" : "Start Trading"
                icon.source: "qrc:/assets/power.svg"; icon.width: 15; icon.height: 15
                Layout.fillWidth: true
                Layout.preferredHeight: 42
                highlighted: !root.botTrading
                Material.background: root.botTrading ? Theme.down : Theme.up
                Material.foreground: "#ffffff"
                font.bold: true
                enabled: root.botConnected
                onClicked: {
                    if (root.botTrading) { bot.setTrading(false); return }
                    bot.setScript(editor.text)
                    bot.setTrading(true)
                }
            }
            Text {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                font.pixelSize: 10
                color: root.botTrading ? Theme.up : Theme.textMuted
                text: root.botConnected
                    ? (root.botTrading ? "● Trading AKTIF memakai skrip." : "○ Terhubung. Klik Start untuk menjalankan skrip.")
                    : "○ Belum terhubung — login di tab Login dulu."
            }
        }
    }

    // ===== Dialog Bantuan API =====
    Dialog {
        id: apiHelpDialog
        title: "Bantuan API (ctx.*)"
        modal: true
        width: Math.min(root.width - 40, 460)
        height: Math.min(root.height - 60, 560)
        anchors.centerIn: Overlay.overlay
        standardButtons: Dialog.Close

        ColumnLayout {
            anchors.fill: parent
            spacing: 6
            ListView {
                Layout.fillWidth: true
                Layout.fillHeight: true
                clip: true
                model: root.apiGroups
                spacing: 6
                ScrollBar.vertical: ThinScrollBar {}
                delegate: Column {
                    width: ListView.view.width
                    spacing: 2
                    Text { text: modelData.group; color: Theme.accent; font.pixelSize: 12; font.bold: true }
                    Repeater {
                        model: modelData.items
                        Row {
                            width: parent.width
                            spacing: 6
                            Column {
                                width: parent.width - 90
                                Text { text: modelData.signature; color: Theme.textPrimary; font.family: "Consolas, monospace"; font.pixelSize: 11; width: parent.width; elide: Text.ElideRight }
                                Text { text: modelData.desc; color: Theme.textMuted; font.pixelSize: 9; width: parent.width; elide: Text.ElideRight }
                            }
                            CButton { text: "Sisipkan"; font.pixelSize: 10; implicitHeight: 26; height: 26; width: 84; onClicked: { root.insertSnippet(modelData.snippet); apiHelpDialog.close() } }
                        }
                    }
                }
            }
        }
    }
}
