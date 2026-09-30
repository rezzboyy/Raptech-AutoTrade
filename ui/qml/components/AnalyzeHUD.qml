import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Material
import QtQuick.Layouts
import ".."

// AnalyzeHUD: Komponen animasi HUD "Analyze" saat trading aktif di Mode Programmer.
// Menampilkan scanner radar cyber, gelombang spektrum frekuensi pasar real-time,
// siklus tahap analisis strategi, dan status telemetri keamanan.
Rectangle {
    id: hud

    property bool active: false
    property bool previewMode: false
    readonly property bool isAnalyzing: active || previewMode

    property string symbol: ""
    property string timeframe: ""
    property string strategyName: ""

    property int currentPhase: 0
    readonly property var phases: [
        "Memindai formasi bar candle terbaru & pergerakan tick pasar...",
        "Menghitung konfluensi indikator strategi (Trend, Momentum, Pullback)...",
        "Memvalidasi batas spread broker & filter keamanan risiko akun...",
        "Siaga mengeksekusi order instan begitu sinyal terkonfirmasi..."
    ]

    visible: opacity > 0.001
    opacity: isAnalyzing ? 1.0 : 0.0
    implicitHeight: isAnalyzing ? contentCol.implicitHeight + 20 : 0
    clip: true

    Behavior on opacity { NumberAnimation { duration: 280 } }
    Behavior on implicitHeight { NumberAnimation { duration: 320; easing.type: Easing.OutCubic } }

    color: Theme.surfaceAlt
    radius: 8
    border.color: isAnalyzing ? Theme.accent : Theme.border
    border.width: 1

    // Timer untuk memutar tahapan analisis setiap 2.8 detik
    Timer {
        id: phaseTimer
        interval: 2800
        repeat: true
        running: hud.isAnalyzing
        onTriggered: {
            phaseFadeAnim.restart()
            hud.currentPhase = (hud.currentPhase + 1) % hud.phases.length
        }
    }

    ColumnLayout {
        id: contentCol
        anchors.fill: parent
        anchors.margins: 10
        spacing: 8

        // ================= Header HUD =================
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            // Indikator radar pulsing beacon
            Item {
                width: 16
                height: 16

                // Lingkaran ripple luar yang berdenyut membesar & memudar
                Rectangle {
                    id: ripple
                    anchors.centerIn: parent
                    width: 14
                    height: 14
                    radius: 7
                    color: "transparent"
                    border.color: Theme.up
                    border.width: 1.5

                    SequentialAnimation on scale {
                        running: hud.isAnalyzing
                        loops: Animation.Infinite
                        NumberAnimation { from: 0.8; to: 1.7; duration: 1100; easing.type: Easing.OutQuad }
                        NumberAnimation { from: 1.7; to: 0.8; duration: 100 }
                    }
                    SequentialAnimation on opacity {
                        running: hud.isAnalyzing
                        loops: Animation.Infinite
                        NumberAnimation { from: 0.9; to: 0.0; duration: 1100; easing.type: Easing.OutQuad }
                        NumberAnimation { from: 0.0; to: 0.9; duration: 100 }
                    }
                }

                // Titik inti neon bersinar
                Rectangle {
                    anchors.centerIn: parent
                    width: 7
                    height: 7
                    radius: 3.5
                    color: Theme.up

                    SequentialAnimation on opacity {
                        running: hud.isAnalyzing
                        loops: Animation.Infinite
                        NumberAnimation { from: 0.5; to: 1.0; duration: 600 }
                        NumberAnimation { from: 1.0; to: 0.5; duration: 600 }
                    }
                }
            }

            Text {
                text: "ANALYZER MODE PROGRAMMER"
                font.pixelSize: 11
                font.bold: true
                color: Theme.textPrimary
            }

            Rectangle {
                Layout.preferredHeight: 14
                Layout.preferredWidth: hud.previewMode && !hud.active ? 68 : 62
                radius: 3
                color: Theme.bg
                border.color: Theme.accent
                border.width: 1

                RowLayout {
                    anchors.centerIn: parent
                    spacing: 3
                    Rectangle {
                        width: 5; height: 5; radius: 2.5; color: Theme.up
                    }
                    Text {
                        text: hud.previewMode && !hud.active ? "PREVIEW" : "SCANNING"
                        font.pixelSize: 8
                        font.bold: true
                        color: Theme.up
                    }
                }
            }

            Item { Layout.fillWidth: true }

            // Badge instrumen target
            Text {
                text: (hud.symbol ? hud.symbol : "EURUSDm") + (hud.timeframe ? " [" + hud.timeframe + "]" : " [M5]")
                font.pixelSize: 10
                font.bold: true
                color: Theme.textSecondary
            }
        }

        // Garis pemisah halus
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 1
            color: Theme.divider
        }

        // ================= Visual Scanning Centerpiece =================
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            // Visual 1: Reticle Radar Cyber Mini
            Item {
                Layout.preferredWidth: 46
                Layout.preferredHeight: 46

                // Lingkaran luar radar
                Rectangle {
                    anchors.centerIn: parent
                    width: 44; height: 44; radius: 22
                    color: Theme.bg
                    border.color: Theme.border
                    border.width: 1

                    // Lingkaran dalam radar
                    Rectangle {
                        anchors.centerIn: parent
                        width: 24; height: 24; radius: 12
                        color: "transparent"
                        border.color: Theme.border
                        border.width: 1
                    }

                    // Garis sumbu silang
                    Rectangle {
                        anchors.centerIn: parent
                        width: 40; height: 1
                        color: Theme.divider
                    }
                    Rectangle {
                        anchors.centerIn: parent
                        width: 1; height: 40
                        color: Theme.divider
                    }

                    // Jarum sapuan pemindai (Radar Sweep Needle)
                    Item {
                        id: radarNeedle
                        anchors.fill: parent

                        Rectangle {
                            anchors.horizontalCenter: parent.horizontalCenter
                            y: 2
                            width: 1.5
                            height: 20
                            color: Theme.up
                            opacity: 0.85
                        }

                        RotationAnimation on rotation {
                            from: 0; to: 360
                            duration: 2200
                            loops: Animation.Infinite
                            running: hud.isAnalyzing
                        }
                    }

                    // Titik pusat radar
                    Rectangle {
                        anchors.centerIn: parent
                        width: 4; height: 4; radius: 2
                        color: Theme.up
                    }
                }
            }

            // Visual 2: Equalizer / Spektrum Frekuensi Pasar (Market Waveform Analyzer)
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 4

                RowLayout {
                    Layout.fillWidth: true
                    spacing: 4

                    Text {
                        text: "Market Tick & Signal Spectrum"
                        font.pixelSize: 9
                        color: Theme.textMuted
                    }

                    Item { Layout.fillWidth: true }

                    Text {
                        text: "Loop: 1.0s Scan"
                        font.pixelSize: 9
                        color: Theme.accent
                    }
                }

                // Bar spectrum dinamis
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 28
                    color: Theme.bg
                    radius: 4
                    border.color: Theme.border

                    Row {
                        anchors.centerIn: parent
                        spacing: 4

                        Repeater {
                            model: [
                                { minH: 6, maxH: 22, dur: 480 },
                                { minH: 8, maxH: 26, dur: 360 },
                                { minH: 4, maxH: 18, dur: 620 },
                                { minH: 10, maxH: 24, dur: 410 },
                                { minH: 5, maxH: 20, dur: 530 },
                                { minH: 9, maxH: 26, dur: 390 },
                                { minH: 4, maxH: 22, dur: 570 },
                                { minH: 8, maxH: 24, dur: 450 },
                                { minH: 6, maxH: 20, dur: 510 },
                                { minH: 10, maxH: 26, dur: 380 },
                                { minH: 5, maxH: 19, dur: 600 },
                                { minH: 7, maxH: 23, dur: 440 }
                            ]

                            delegate: Item {
                                width: 5
                                height: 26

                                Rectangle {
                                    id: bar
                                    anchors.bottom: parent.bottom
                                    anchors.bottomMargin: 1
                                    anchors.horizontalCenter: parent.horizontalCenter
                                    width: 4
                                    height: modelData.minH
                                    radius: 1.5
                                    color: (index % 2 === 0) ? Theme.up : Theme.accent

                                    SequentialAnimation on height {
                                        running: hud.isAnalyzing
                                        loops: Animation.Infinite
                                        NumberAnimation {
                                            from: modelData.minH
                                            to: modelData.maxH
                                            duration: modelData.dur
                                            easing.type: Easing.InOutQuad
                                        }
                                        NumberAnimation {
                                            from: modelData.maxH
                                            to: modelData.minH
                                            duration: modelData.dur
                                            easing.type: Easing.InOutQuad
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        // ================= Status Ticker Tahap Analisis =================
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 22
            color: Theme.bg
            radius: 4
            border.color: Theme.border

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 8
                anchors.rightMargin: 8
                spacing: 6

                Text {
                    text: "●"
                    font.pixelSize: 8
                    color: Theme.up
                }

                Text {
                    id: phaseText
                    Layout.fillWidth: true
                    text: hud.phases[hud.currentPhase]
                    font.pixelSize: 10
                    color: Theme.textSecondary
                    elide: Text.ElideRight

                    SequentialAnimation on opacity {
                        id: phaseFadeAnim
                        NumberAnimation { from: 1.0; to: 0.2; duration: 180 }
                        NumberAnimation { from: 0.2; to: 1.0; duration: 250 }
                    }
                }

                Text {
                    text: "Tahap " + (hud.currentPhase + 1) + "/4"
                    font.pixelSize: 9
                    color: Theme.textMuted
                }
            }
        }
    }
}
