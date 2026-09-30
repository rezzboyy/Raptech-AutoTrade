import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import QtQuick.Dialogs
import ".."

// Mode Programmer: editor skrip strategi kustom (mirip kolom script cBot,
// namun versi trading). Pengguna menulis Python tersandbox: PARAMS + on_bar(ctx).
Rectangle {
    id: root
    color: Theme.surface
    radius: 10
    border.color: Theme.border

    property string currentName: ""
    property string currentFilePath: ""
    property int errorLine: 0   // baris error terakhir (0 = tak ada)
    property var detectedSettings: ({})
    readonly property bool hasScriptSettings: detectedSettings && Object.keys(detectedSettings).length > 0
    readonly property bool botConnected: bot ? bot.connected : false
    readonly property bool botTrading: bot ? bot.trading : false

    // Metrik layout seragam.
    readonly property int ctrlHeight: 34
    readonly property int labelWidth: 96

    // Terapkan skrip di editor sebagai strategi aktif (+ parameter). true bila sukses.
    function applyCurrent() {
        var nm = nameField.text.trim()
        if (nm.length === 0 && root.detectedSettings && root.detectedSettings.name) {
            nm = root.detectedSettings.name
            nameField.text = nm
        }
        var ok = bot.applyScript(editor.text, nm, root.collectParams())
        if (ok && riskForm) {
            riskForm.load()
        }
        return ok
    }

    // Tangani hasil muat file skrip dari dialog pemilihan file.
    function loadFileResult(res) {
        if (!res || !res.ok) {
            setStatus("Gagal memuat file: " + (res && res.error ? res.error : "File tidak ditemukan"), false)
            return false
        }
        root.currentFilePath = res.path
        if (filePathField) filePathField.text = res.path
        editor.text = res.source
        nameField.text = res.name
        root.currentName = res.name
        refreshParams()
        refreshSettings()
        applyCurrent()
        setStatus("Skrip '" + res.name + "' berhasil dimuat dan disinkronkan.", true)
        return true
    }

    function refreshList() {
        // No-op kompatibilitas
    }

    // Perbarui deteksi pengaturan skrip (SETTINGS / konstanta level-atas).
    function refreshSettings() {
        if (bot && bot.scriptSettings) {
            root.detectedSettings = bot.scriptSettings(editor.text) || {}
            if (root.detectedSettings.name && nameField.text.trim().length === 0)
                nameField.text = root.detectedSettings.name
        } else {
            root.detectedSettings = {}
        }
    }

    // Bangun ulang form parameter dari skema PARAMS skrip aktif di editor.
    function refreshParams() {
        var schema = bot.scriptParams(editor.text)
        paramModel.clear()
        for (var i = 0; i < schema.length; i++) {
            var p = schema[i]
            paramModel.append({
                "key": p.key || "",
                "label": p.label || p.key || "",
                "ptype": p.type || "float",
                "value": (p.default !== undefined ? String(p.default) : "")
            })
        }
    }

    // Kumpulkan nilai parameter dari form menjadi objek {key: value}.
    function collectParams() {
        var out = {}
        for (var i = 0; i < paramModel.count; i++) {
            var it = paramModel.get(i)
            if (!it.key) continue
            if (it.ptype === "int")
                out[it.key] = parseInt(it.value)
            else if (it.ptype === "float")
                out[it.key] = parseFloat(it.value)
            else
                out[it.key] = it.value
        }
        return out
    }

    function setStatus(msg, ok) {
        statusText.text = msg
        statusText.color = ok ? Theme.up : Theme.down
    }

    // Sisipkan snippet API ke editor di posisi kursor.
    function insertSnippet(text) {
        if (!text) return
        var pos = editor.cursorPosition
        editor.insert(pos, text)
        editor.cursorPosition = pos + text.length
        editor.forceActiveFocus()
    }

    Component.onCompleted: {
        var c = bot ? bot.getConfig() : null
        if (c && c.script_source && c.script_source.trim().length > 0) {
            editor.text = c.script_source
            if (c.script_name) {
                nameField.text = c.script_name
                root.currentName = c.script_name
            }
        } else if (editor.text.trim().length === 0 && bot) {
            editor.text = bot.scriptTemplate()
        }
        refreshParams()
        refreshSettings()
        if (riskForm) riskForm.load()
        // Pasang syntax highlighter Python ke dokumen editor.
        if (bot && bot.attachHighlighter)
            bot.attachHighlighter(editor.textDocument)
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
            spacing: 14

            // ================= Header =================
            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Image { source: "../../assets/bolt.svg"; sourceSize.width: 16; sourceSize.height: 16 }
                Text { text: "Mode Programmer"; color: Theme.textPrimary; font.pixelSize: 14; font.bold: true }
            }

            Text {
                Layout.fillWidth: true
                Layout.topMargin: -8
                wrapMode: Text.WordWrap
                color: Theme.textMuted
                font.pixelSize: 10
                lineHeight: 1.15
                text: "Tulis strategi Python tersandbox: definisikan PARAMS (opsional) dan on_bar(ctx) yang mengembalikan \"BUY\", \"SELL\", atau None."
            }

            // ================= Pilih File Skrip =================
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 6

                Text {
                    text: "Pilih File Skrip Strategi (.py)"
                    color: Theme.textSecondary; font.pixelSize: 11; font.bold: true
                }
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    CField {
                        id: filePathField
                        Layout.fillWidth: true
                        Layout.minimumWidth: 80
                        Layout.preferredHeight: root.ctrlHeight
                        placeholderText: "Pilih file skrip strategi (*.py)..."
                        readOnly: true
                        text: root.currentFilePath
                    }
                    Button {
                        text: "Pilih File"
                        Layout.preferredHeight: root.ctrlHeight
                        Layout.preferredWidth: 105
                        icon.source: "../../assets/folder.svg"; icon.width: 14; icon.height: 14
                        highlighted: true
                        onClicked: scriptFileDialog.open()
                    }
                }
            }

            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.divider }

            // ================= Editor Skrip =================
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6
                    Text {
                        text: "Kode Skrip Python"
                        color: Theme.textSecondary; font.pixelSize: 11; font.bold: true
                    }
                    Item { Layout.fillWidth: true }
                    Button {
                        text: "Template"
                        Layout.preferredHeight: 26
                        font.pixelSize: 11
                        onClicked: {
                            editor.text = bot.scriptTemplate()
                            root.currentFilePath = ""
                            if (filePathField) filePathField.text = ""
                            nameField.text = "template_strategi"
                            refreshParams()
                            refreshSettings()
                            setStatus("Template skrip dimuat.", true)
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 6

                    Button {
                        text: "Bantuan API"
                        Layout.fillWidth: true
                        Layout.preferredHeight: 28
                        font.pixelSize: 11
                        icon.source: "../../assets/log.svg"; icon.width: 12; icon.height: 12
                        onClicked: apiHelpDialog.open()
                    }
                    Button {
                        text: "Variabel SETTINGS"
                        Layout.fillWidth: true
                        Layout.preferredHeight: 28
                        font.pixelSize: 11
                        icon.source: "../../assets/refresh.svg"; icon.width: 12; icon.height: 12
                        onClicked: settingsHelpDialog.open()
                    }
                }

                // Nama skrip.
                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Label {
                        text: "Nama"
                        color: Theme.textSecondary
                        Layout.preferredWidth: root.labelWidth
                    }
                    CField {
                        id: nameField
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.ctrlHeight
                        placeholderText: "nama_skrip"
                    }
                }

                // Editor kode PRO: nomor baris + syntax highlight + error real-time.
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 300
                    color: Theme.bg
                    radius: 8
                    border.color: root.errorLine > 0 ? Theme.down : Theme.border

                    Flickable {
                        id: editorFlick
                        anchors.fill: parent
                        anchors.margins: 8
                        clip: true
                        contentWidth: gutter.width + editor.width
                        contentHeight: Math.max(editor.contentHeight, height)
                        ScrollBar.vertical: ThinScrollBar {}
                        ScrollBar.horizontal: ThinScrollBar {}

                        Row {
                            id: editorRow
                            // Nomor baris (gutter).
                            Column {
                                id: gutter
                                width: 40
                                Repeater {
                                    model: Math.max(editor.lineCount, 1)
                                    delegate: Text {
                                        width: gutter.width - 8
                                        height: editor.contentHeight / Math.max(editor.lineCount, 1)
                                        text: (index + 1)
                                        color: (index + 1) === root.errorLine ? Theme.down : Theme.textMuted
                                        font.family: "Consolas, 'Courier New', monospace"
                                        font.pixelSize: 12
                                        horizontalAlignment: Text.AlignRight
                                        verticalAlignment: Text.AlignTop
                                    }
                                }
                            }
                            TextArea {
                                id: editor
                                width: Math.max(editorFlick.width - gutter.width, implicitWidth)
                                height: Math.max(editorFlick.height, contentHeight)
                                wrapMode: TextArea.NoWrap
                                color: Theme.textPrimary
                                font.family: "Consolas, 'Courier New', monospace"
                                font.pixelSize: 12
                                selectByMouse: true
                                tabStopDistance: 32
                                leftPadding: 4
                                background: Rectangle { color: "transparent" }
                                onTextChanged: validateTimer.restart()
                            }
                        }
                    }

                    // Debounce validasi real-time (± 500ms setelah berhenti mengetik).
                    Timer {
                        id: validateTimer
                        interval: 500
                        onTriggered: {
                            var d = bot.validateScriptDetail(editor.text)
                            if (d.ok) {
                                root.errorLine = 0
                                refreshSettings()
                            } else {
                                root.errorLine = d.line || 0
                                if (d.message && d.message.length > 0)
                                    setStatus((d.line > 0 ? "Baris " + d.line + ": " : "") + d.message, false)
                            }
                        }
                    }
                }
            }

            // ================= Mode Full Script Settings (Banner Info) =================
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: scriptSettingsCol.implicitHeight + 18
                visible: root.hasScriptSettings
                color: Theme.surfaceAlt
                radius: 8
                border.color: Theme.accent
                border.width: 1

                ColumnLayout {
                    id: scriptSettingsCol
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 6

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6
                        Image {
                            source: "../../assets/bolt.svg"
                            sourceSize.width: 13; sourceSize.height: 13
                        }
                        Text {
                            text: "Full Script Settings Aktif"
                            color: Theme.accent
                            font.pixelSize: 11
                            font.bold: true
                        }
                        Item { Layout.fillWidth: true }
                        Text {
                            text: "Otomatis dari Skrip"
                            color: Theme.up
                            font.pixelSize: 10
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        color: Theme.textSecondary
                        font.pixelSize: 10
                        text: {
                            var s = root.detectedSettings || {}
                            var parts = []
                            if (s.symbol) parts.push("Simbol: " + s.symbol)
                            if (s.timeframe_str) parts.push("TF: " + s.timeframe_str)
                            if (s.volume !== undefined) parts.push("Lot: " + s.volume)
                            if (s.sl_points !== undefined) parts.push("SL: " + s.sl_points + " pts")
                            if (s.tp_points !== undefined) parts.push("TP: " + s.tp_points + " pts")
                            if (s.trailing_stop_points) parts.push("Trailing: " + s.trailing_stop_points + " pts")
                            if (s.break_even_points || s.break_even_trigger_points) parts.push("BE: " + (s.break_even_points || s.break_even_trigger_points) + " pts")
                            if (s.max_spread_points) parts.push("Max Spread: " + s.max_spread_points + " pts")
                            if (s.max_open_positions) parts.push("Maks Posisi: " + s.max_open_positions)
                            return parts.length > 0 ? parts.join("  •  ") : "Pengaturan trading terdeteksi di dalam kode skrip."
                        }
                    }

                    Text {
                        Layout.fillWidth: true
                        wrapMode: Text.WordWrap
                        color: Theme.textMuted
                        font.pixelSize: 9
                        text: "Seluruh konfigurasi diselaraskan otomatis dari kode skrip tanpa harus input formulir manual."
                    }
                }
            }

            // ================= Form parameter dinamis =================
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: paramCol.implicitHeight + 20
                visible: paramModel.count > 0
                color: Theme.bg
                radius: 8
                border.color: Theme.border

                ColumnLayout {
                    id: paramCol
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 8

                    Text { text: "Parameter"; color: Theme.textSecondary; font.pixelSize: 11; font.bold: true }

                    Repeater {
                        model: ListModel { id: paramModel }
                        delegate: RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            Label {
                                text: model.label
                                color: Theme.textSecondary
                                Layout.preferredWidth: root.labelWidth
                                elide: Text.ElideRight
                            }
                            CField {
                                Layout.fillWidth: true
                                Layout.preferredHeight: root.ctrlHeight
                                text: model.value
                                inputMethodHints: (model.ptype === "int" || model.ptype === "float")
                                    ? Qt.ImhFormattedNumbersOnly : Qt.ImhNone
                                onTextChanged: paramModel.setProperty(index, "value", text)
                            }
                        }
                    }
                }
            }

            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.divider }

            // ================= Risiko & Proteksi (bersama tab Manual) =================
            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                Text {
                    text: "Risiko & Proteksi"
                    color: Theme.textSecondary; font.pixelSize: 11; font.bold: true
                    Layout.fillWidth: true
                }
                Button {
                    text: riskBox.visible ? "Sembunyikan" : "Atur"
                    Layout.preferredHeight: 28
                    font.pixelSize: 11
                    onClicked: riskBox.visible = !riskBox.visible
                }
            }
            Text {
                Layout.fillWidth: true
                Layout.topMargin: -4
                wrapMode: Text.WordWrap
                color: Theme.textMuted
                font.pixelSize: 10
                text: "Simbol, timeframe, risiko/lot, SL/TP, dan proteksi dipakai skrip ini. Sama dengan pengaturan di tab Manual (tersimpan bersama)."
            }
            ColumnLayout {
                id: riskBox
                Layout.fillWidth: true
                visible: false
                spacing: 8

                RiskConfigForm { id: riskForm; Layout.fillWidth: true }

                Button {
                    text: "Simpan Pengaturan Risiko"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 32
                    icon.source: "../../assets/save.svg"; icon.width: 13; icon.height: 13
                    onClicked: {
                        if (bot.saveConfig(riskForm.collect()))
                            setStatus("Pengaturan risiko disimpan.", true)
                        else
                            setStatus("Gagal menyimpan pengaturan risiko (cek nilai).", false)
                    }
                }
            }

            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.divider }

            // ================= Aksi =================
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 8

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Button {
                        text: "Validasi"
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.ctrlHeight
                        onClicked: {
                            var err = bot.validateScript(editor.text)
                            if (err.length === 0) {
                                refreshParams()
                                refreshSettings()
                                setStatus("Skrip valid.", true)
                            } else {
                                setStatus("Error: " + err, false)
                            }
                        }
                    }
                    Button {
                        text: "Simpan"
                        Layout.fillWidth: true
                        Layout.preferredHeight: root.ctrlHeight
                        icon.source: "../../assets/save.svg"; icon.width: 13; icon.height: 13
                        onClicked: {
                            var nm = nameField.text.trim()
                            if (nm.length === 0) {
                                setStatus("Beri nama skrip dulu.", false)
                                return
                            }
                            if (bot.saveScript(nm, editor.text)) {
                                setStatus("Skrip '" + nm + "' disimpan.", true)
                                root.currentName = nm
                                refreshList()
                            } else {
                                setStatus("Gagal menyimpan skrip.", false)
                            }
                        }
                    }
                }

                Button {
                    text: "Terapkan sebagai Strategi"
                    Layout.fillWidth: true
                    Layout.preferredHeight: root.ctrlHeight
                    icon.source: "../../assets/strategy.svg"; icon.width: 14; icon.height: 14
                    onClicked: {
                        if (root.applyCurrent())
                            setStatus("Diterapkan sebagai strategi aktif (custom_script).", true)
                        else
                            setStatus("Gagal menerapkan skrip (lihat pesan error).", false)
                    }
                }

                Button {
                    text: root.botTrading ? "Stop Trading (Menganalisis...)" : "Start Trading"
                    Layout.fillWidth: true
                    Layout.preferredHeight: 40
                    highlighted: !root.botTrading
                    Material.background: root.botTrading ? Theme.down : Theme.up
                    icon.source: "../../assets/power.svg"; icon.width: 15; icon.height: 15
                    font.bold: true
                    onClicked: {
                        if (root.botTrading) {
                            bot.setTrading(false)
                            setStatus("Trading dihentikan.", true)
                            return
                        }
                        if (!root.botConnected) {
                            setStatus("Hubungkan ke MT5 dulu di tab Login sebelum Start.", false)
                            return
                        }
                        if (!root.applyCurrent()) {
                            setStatus("Skrip tidak valid; perbaiki dulu sebelum Start.", false)
                            return
                        }
                        // Sinkronkan form risiko agar menampilkan nilai dari skrip yang baru diterapkan
                        riskForm.load()
                        bot.setTrading(true)
                        setStatus("Trading dimulai memakai skrip + animasi analize aktif.", true)
                    }
                }
            }

            // ================= HUD Animasi Analyze Market (Mode Programmer) =================
            AnalyzeHUD {
                id: analyzeHUD
                Layout.fillWidth: true
                active: root.botTrading
                symbol: root.detectedSettings && root.detectedSettings.symbol ? root.detectedSettings.symbol : (bot ? bot.chartSymbol : "")
                timeframe: root.detectedSettings && root.detectedSettings.timeframe_str ? root.detectedSettings.timeframe_str : "M5"
                strategyName: root.currentName ? root.currentName : "Strategi Kustom"
            }

            // ================= Status =================
            Text {
                id: statusText
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                color: Theme.textMuted
                font.pixelSize: 11
                text: "Siap. Klik Validasi untuk memeriksa skrip."
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8

                Text {
                    Layout.fillWidth: true
                    wrapMode: Text.WordWrap
                    font.pixelSize: 10
                    color: root.botTrading ? Theme.up : Theme.textMuted
                    text: root.botConnected
                        ? (root.botTrading ? "● Trading & Analize AKTIF memakai strategi skrip."
                                           : "○ Terhubung. Klik Start untuk menjalankan skrip.")
                        : "○ Belum terhubung — login di tab Login dulu."
                }

                Button {
                    visible: !root.botTrading
                    text: analyzeHUD.previewMode ? "Tutup Preview" : "Pratinjau Animasi"
                    Layout.preferredHeight: 22
                    font.pixelSize: 9
                    flat: true
                    onClicked: analyzeHUD.previewMode = !analyzeHUD.previewMode
                }
            }

            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.divider }

            // ================= Jurnal Aksi Skrip =================
            RowLayout {
                Layout.fillWidth: true
                spacing: 6
                Text {
                    text: "Jurnal Aksi"
                    color: Theme.textSecondary; font.pixelSize: 11; font.bold: true
                }
                Text { text: journalModel.count + " entri"; color: Theme.textMuted; font.pixelSize: 10 }
                Item { Layout.fillWidth: true }
                Button {
                    text: journalBox.visible ? "Sembunyikan" : "Tampilkan"
                    Layout.preferredHeight: 26
                    font.pixelSize: 11
                    onClicked: journalBox.visible = !journalBox.visible
                }
            }
            ColumnLayout {
                id: journalBox
                Layout.fillWidth: true
                visible: false
                spacing: 6

                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 150
                    color: Theme.bg
                    radius: 8
                    border.color: Theme.border

                    ListView {
                        id: journalView
                        anchors.fill: parent
                        anchors.margins: 6
                        clip: true
                        spacing: 1
                        model: ListModel { id: journalModel }
                        ScrollBar.vertical: ThinScrollBar {}
                        delegate: RowLayout {
                            width: journalView.width
                            spacing: 6
                            Text { text: model.time; color: Theme.textMuted; font.pixelSize: 10; Layout.preferredWidth: 56 }
                            Text {
                                text: model.action
                                color: model.ok ? Theme.up : Theme.down
                                font.pixelSize: 10; font.bold: true; Layout.preferredWidth: 62
                            }
                            Text { text: model.symbol; color: Theme.textPrimary; font.pixelSize: 10; Layout.preferredWidth: 68 }
                            Text {
                                text: model.detail; color: Theme.textSecondary; font.pixelSize: 10
                                elide: Text.ElideRight; Layout.fillWidth: true
                            }
                        }
                    }
                }

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 8
                    Button {
                        text: "Ekspor CSV"
                        Layout.fillWidth: true
                        Layout.preferredHeight: 28
                        font.pixelSize: 11
                        icon.source: "../../assets/download.svg"; icon.width: 12; icon.height: 12
                        enabled: journalModel.count > 0
                        onClicked: {
                            var p = bot.exportJournal("")
                            if (p.length > 0) setStatus("Jurnal diekspor: " + p, true)
                        }
                    }
                    Button {
                        text: "Bersihkan"
                        Layout.preferredHeight: 28
                        font.pixelSize: 11
                        icon.source: "../../assets/trash.svg"; icon.width: 12; icon.height: 12
                        enabled: journalModel.count > 0
                        onClicked: bot.clearJournal()
                    }
                }
            }

            Item { Layout.preferredHeight: 2 }
        }
    }

    // Sinkronkan model jurnal dari controller.
    function refreshJournal() {
        var j = bot ? bot.journal : []
        journalModel.clear()
        for (var i = 0; i < j.length; i++)
            journalModel.append(j[i])
        if (journalModel.count > 0)
            journalView.positionViewAtEnd()
    }

    Connections {
        target: bot
        function onJournalChanged() { root.refreshJournal() }
    }

    // ================= Dialog Bantuan API =================
    Dialog {
        id: apiHelpDialog
        modal: true
        title: "Bantuan API — klik Sisipkan untuk menaruh ke editor"
        anchors.centerIn: Overlay.overlay
        width: Math.min(root.width * 1.6, 560)
        height: Math.min(root.height * 0.9, 620)
        standardButtons: Dialog.Close

        ApiHelpPanel {
            anchors.fill: parent
            onInsertRequested: function(snippet) {
                root.insertSnippet(snippet)
                root.setStatus("Snippet disisipkan ke editor.", true)
            }
        }
    }

    // ================= Dialog Variabel SETTINGS =================
    Dialog {
        id: settingsHelpDialog
        modal: true
        title: "Daftar Variabel SETTINGS — klik Sisipkan untuk menaruh ke editor"
        anchors.centerIn: Overlay.overlay
        width: Math.min(root.width * 1.7, 620)
        height: Math.min(root.height * 0.9, 640)
        standardButtons: Dialog.Close

        SettingsHelpPanel {
            anchors.fill: parent
            onInsertRequested: function(snippet) {
                root.insertSnippet(snippet)
                root.setStatus("Variabel SETTINGS disisipkan ke editor.", true)
            }
        }
    }

    // ================= Dialog Pemilihan File Skrip =================
    FileDialog {
        id: scriptFileDialog
        title: "Pilih File Skrip Python (.py)"
        nameFilters: ["Skrip Python (*.py)", "Semua File (*.*)"]
        onAccepted: {
            var url = selectedFile.toString()
            var res = null
            if (bot && bot.loadScriptFile) {
                res = bot.loadScriptFile(url)
            } else if (bot && bot.loadScript) {
                var cleanPath = url
                if (cleanPath.indexOf("file:///") === 0)
                    cleanPath = cleanPath.substring(8)
                else if (cleanPath.indexOf("file://") === 0)
                    cleanPath = cleanPath.substring(7)
                var src = bot.loadScript(cleanPath)
                if (src && src.length > 0) {
                    var parts = cleanPath.split(/[/\\]/)
                    var filename = parts[parts.length - 1]
                    var stem = filename.replace(/\.py$/i, "")
                    res = { "name": stem, "path": cleanPath, "source": src, "ok": true }
                }
            }
            root.loadFileResult(res)
        }
    }
}
