import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// Panel Daftar Variabel SETTINGS: menampilkan kamus variabel strategi lengkap
// dengan tipe data, default, penjelasan, pencarian, dan tombol sisipkan.
Rectangle {
    id: root
    color: Theme.surface
    radius: 10
    border.color: Theme.border

    signal insertRequested(string snippet)

    property var groups: []

    function reload() {
        groups = bot ? bot.settingsReference() : []
        rebuild()
    }

    function rebuild() {
        listModel.clear()
        var q = searchField.text.trim().toLowerCase()
        for (var g = 0; g < groups.length; g++) {
            var grp = groups[g]
            var items = grp.items || []
            var matched = []
            for (var i = 0; i < items.length; i++) {
                var it = items[i]
                var hay = (it.name + " " + it.type + " " + it.desc + " " + it.default).toLowerCase()
                if (q.length === 0 || hay.indexOf(q) !== -1)
                    matched.push(it)
            }
            if (matched.length === 0) continue

            listModel.append({
                "isHeader": true,
                "title": grp.group,
                "name": "",
                "type": "",
                "defaultVal": "",
                "desc": "",
                "snippet": ""
            })
            for (var m = 0; m < matched.length; m++) {
                listModel.append({
                    "isHeader": false,
                    "title": "",
                    "name": matched[m].name || "",
                    "type": matched[m].type || "",
                    "defaultVal": matched[m].default !== undefined ? String(matched[m].default) : "",
                    "desc": matched[m].desc || "",
                    "snippet": matched[m].snippet || ""
                })
            }
        }
    }

    // Snippet template SETTINGS lengkap siap pakai
    function insertFullTemplate() {
        var tmpl =
            'SETTINGS = {\n' +
            '    # === Pasar & Simbol ===\n' +
            '    "symbol": "EURUSDm",          # Simbol Exness (suffix "m")\n' +
            '    "timeframe": "M5",            # M1, M5, M15, M30, H1, H4, D1\n' +
            '    "volume": 0.01,               # Ukuran lot per trade\n' +
            '    "max_positions": 1,           # Maksimal posisi aktif\n' +
            '\n' +
            '    # === Stop Loss & Take Profit ===\n' +
            '    "sl_points": 300,             # Stop Loss (points)\n' +
            '    "tp_points": 600,             # Take Profit (points)\n' +
            '    "risk_reward_ratio": 2.0,     # Hitung TP = SL * 2.0 (opsional)\n' +
            '    "atr_sl_mult": 1.5,           # SL dinamis = 1.5 * ATR (opsional)\n' +
            '    "atr_tp_mult": 3.0,           # TP dinamis = 3.0 * ATR (opsional)\n' +
            '\n' +
            '    # === Trailing & Proteksi Posisi ===\n' +
            '    "trailing_stop_points": 200,  # Trailing stop aktif di 200 pts (0 = off)\n' +
            '    "trailing_step_points": 50,   # Step trailing\n' +
            '    "break_even_points": 150,     # Geser SL ke entry saat profit 150 pts\n' +
            '    "break_even_offset_points": 10,# Lock profit 10 pts di atas entry\n' +
            '\n' +
            '    # === Waktu & Sesi Pasar ===\n' +
            '    "trade_start_time": "13:00",  # Jam buka trading (UTC)\n' +
            '    "trade_end_time": "21:00",    # Jam tutup trading (UTC)\n' +
            '    "close_friday_hour": 20,      # Tutup posisi hari Jumat jam 20 UTC\n' +
            '    "active_days": [0, 1, 2, 3, 4], # Hari trading aktif (Senin-Jumat)\n' +
            '\n' +
            '    # === Kontrol Entry & Anti-Spam ===\n' +
            '    "close_on_reversal": True,    # Tutup posisi berlawanan saat sinyal baru\n' +
            '    "one_trade_per_bar": True,    # 1 trade per candle bar\n' +
            '    "cooldown_bars": 2,           # Jeda 2 bar sebelum order baru\n' +
            '    "min_margin_level": 200.0,    # Minimal margin level % untuk buka order\n' +
            '    "max_holding_bars": 24,       # Auto exit jika posisi terbuka > 24 bar\n' +
            '    "max_spread_points": 35,      # Filter spread maksimal\n' +
            '}\n'
        root.insertRequested(tmpl)
    }

    Component.onCompleted: reload()

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 12
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            ColumnLayout {
                spacing: 2
                Text {
                    text: "Variabel Konfigurasi SETTINGS"
                    color: Theme.textPrimary
                    font.pixelSize: 14
                    font.bold: true
                }
                Text {
                    text: "Daftar variabel yang dapat dikonfigurasi langsung dari skrip Python tanpa setting manual."
                    color: Theme.textMuted
                    font.pixelSize: 10
                }
            }
            Item { Layout.fillWidth: true }
            Button {
                text: "Sisipkan Template SETTINGS Lengkap"
                font.pixelSize: 11
                Layout.preferredHeight: 30
                icon.source: "../../assets/save.svg"
                icon.width: 12; icon.height: 12
                onClicked: root.insertFullTemplate()
            }
        }

        CField {
            id: searchField
            Layout.fillWidth: true
            Layout.preferredHeight: 32
            placeholderText: "Cari variabel... (mis. symbol, time, atr, trailing, margin, spread)"
            onTextChanged: root.rebuild()
        }

        ListView {
            id: settingsView
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 4
            model: ListModel { id: listModel }
            ScrollBar.vertical: ThinScrollBar {}

            delegate: Item {
                width: settingsView.width
                height: model.isHeader ? 28 : 52

                // Header Grup Kategori
                Rectangle {
                    visible: model.isHeader
                    anchors.fill: parent
                    color: Theme.surfaceAlt
                    radius: 4
                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 8
                        Text {
                            text: model.title
                            color: Theme.accent
                            font.pixelSize: 11
                            font.bold: true
                        }
                    }
                }

                // Baris Item Variabel
                RowLayout {
                    visible: !model.isHeader
                    anchors.fill: parent
                    anchors.leftMargin: 6
                    anchors.rightMargin: 6
                    spacing: 8

                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 2

                        RowLayout {
                            spacing: 6
                            Text {
                                text: model.name
                                color: Theme.textPrimary
                                font.family: "Consolas, 'Courier New', monospace"
                                font.pixelSize: 12
                                font.bold: true
                            }

                            // Badge Tipe Data
                            Rectangle {
                                color: Theme.surfaceAlt
                                radius: 3
                                border.color: Theme.border
                                implicitWidth: typeText.implicitWidth + 8
                                implicitHeight: 18
                                Text {
                                    id: typeText
                                    anchors.centerIn: parent
                                    text: model.type
                                    color: Theme.accent
                                    font.pixelSize: 9
                                    font.bold: true
                                }
                            }

                            // Teks default value
                            Text {
                                text: "default: " + model.defaultVal
                                color: Theme.textMuted
                                font.family: "Consolas, 'Courier New', monospace"
                                font.pixelSize: 10
                            }
                        }

                        Text {
                            text: model.desc
                            color: Theme.textSecondary
                            font.pixelSize: 10
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                    }

                    Button {
                        text: "Sisipkan"
                        font.pixelSize: 11
                        Layout.preferredHeight: 28
                        onClicked: root.insertRequested(model.snippet)
                    }
                }

                Rectangle {
                    visible: !model.isHeader
                    anchors.bottom: parent.bottom
                    width: parent.width; height: 1
                    color: Theme.divider
                    opacity: 0.4
                }
            }
        }
    }
}
