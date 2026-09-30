import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import "."

// Tab Manual: pilih strategi bawaan + parameter + eksekusi/risiko (RiskConfigForm).
Rectangle {
    id: root
    color: Theme.surface
    radius: 10
    border.color: Theme.border

    property var strategies: []

    Component.onCompleted: { loadStrategies(); loadConfig() }

    function loadStrategies() {
        if (!bot) return
        strategies = bot.getStrategies()
        var names = []
        for (var i = 0; i < strategies.length; i++) names.push(strategies[i].display_name)
        strategyBox.model = names
    }
    function findStrategy(name) {
        for (var i = 0; i < strategies.length; i++)
            if (strategies[i].name === name) return strategies[i]
        return strategies.length > 0 ? strategies[0] : null
    }
    function currentStrategyName() {
        return (strategies.length > 0 && strategyBox.currentIndex >= 0)
            ? strategies[strategyBox.currentIndex].name : ""
    }
    function populateParams(name, saved) {
        paramModel.clear()
        var s = findStrategy(name)
        if (!s) return
        for (var i = 0; i < s.params.length; i++) {
            var p = s.params[i]
            var val = (saved && saved[p.key] !== undefined) ? saved[p.key] : p.default
            paramModel.append({ "pkey": p.key, "plabel": p.label, "pvalue": String(val) })
        }
    }
    function loadConfig() {
        if (!bot) return
        var c = bot.getConfig()
        riskForm.load()
        var idx = 0
        for (var i = 0; i < strategies.length; i++)
            if (strategies[i].name === c.strategy_name) { idx = i; break }
        strategyBox.currentIndex = idx
        populateParams(strategies[idx] ? strategies[idx].name : c.strategy_name, c.strategy_params)
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
                Image { source: "qrc:/assets/strategy.svg"; sourceSize.width: 16; sourceSize.height: 16 }
                Text { text: "Mode Manual (Strategi Bawaan)"; color: Theme.textPrimary; font.pixelSize: 14; font.bold: true }
            }
            Text {
                Layout.fillWidth: true
                wrapMode: Text.WordWrap
                color: Theme.textMuted; font.pixelSize: 10; lineHeight: 1.15
                text: "Pilih strategi bawaan tanpa koding. Pengaturan risiko/SL-TP/proteksi di bawah bersifat GLOBAL — dipakai juga saat menjalankan skrip di tab Programmer."
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Label { text: "Strategi"; color: Theme.textSecondary; Layout.preferredWidth: 150 }
                CCombo {
                    id: strategyBox
                    Layout.preferredHeight: 34
                    onActivated: root.populateParams(root.currentStrategyName(), {})
                }
            }

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
                    spacing: 6
                    Text { text: "Parameter Strategi (" + root.currentStrategyName() + ")"; color: Theme.textSecondary; font.pixelSize: 11; font.bold: true }
                    Repeater {
                        model: ListModel { id: paramModel }
                        delegate: RowLayout {
                            Layout.fillWidth: true
                            spacing: 8
                            Label { text: model.plabel; color: Theme.textSecondary; Layout.preferredWidth: 150 }
                            CField {
                                Layout.preferredHeight: 34
                                text: model.pvalue
                                onTextChanged: paramModel.setProperty(index, "pvalue", text)
                            }
                        }
                    }
                }
            }

            Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.divider }

            RiskConfigForm { id: riskForm; Layout.fillWidth: true }

            RowLayout {
                Layout.fillWidth: true
                spacing: 8
                Button {
                    text: "Simpan Konfigurasi"
                    icon.source: "qrc:/assets/save.svg"; icon.width: 15; icon.height: 15
                    Layout.fillWidth: true
                    Layout.preferredHeight: 38
                    highlighted: true
                    Material.background: Theme.accent
                    Material.foreground: "#ffffff"
                    font.bold: true
                    onClicked: {
                        var params = {}
                        for (var i = 0; i < paramModel.count; i++) {
                            var row = paramModel.get(i)
                            params[row.pkey] = parseFloat(row.pvalue)
                        }
                        var cfg = riskForm.collect()
                        cfg.strategy_name = root.currentStrategyName()
                        cfg.strategy_params = params
                        bot.saveConfig(cfg)
                    }
                }
                CButton {
                    text: "Reset"
                    icon.source: "qrc:/assets/refresh.svg"; icon.width: 14; icon.height: 14
                    Layout.preferredHeight: 38
                    onClicked: root.loadConfig()
                }
            }
            Item { Layout.preferredHeight: 6 }
        }
    }
}
