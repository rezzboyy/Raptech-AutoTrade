import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// Grafik kurva ekuitas & balance dari waktu ke waktu berbasis Canvas.
Rectangle {
    id: root
    color: Theme.surface
    radius: 10
    border.color: Theme.border

    property var equityPoints: (bot && bot.equityCurve) ? bot.equityCurve : []

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 6

        RowLayout {
            Layout.fillWidth: true
            spacing: 8
            Image { source: "../../assets/activity.svg"; sourceSize.width: 16; sourceSize.height: 16 }
            Text { text: "Equity Curve"; color: Theme.textPrimary; font.pixelSize: 14; font.bold: true }

            // Legend
            RowLayout {
                spacing: 12
                Layout.leftMargin: 10
                Row {
                    spacing: 4
                    Rectangle { width: 14; height: 3; color: Theme.accent; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: "Balance"; color: Theme.textSecondary; font.pixelSize: 11 }
                }
                Row {
                    spacing: 4
                    Rectangle { width: 14; height: 3; color: Theme.up; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: "Equity"; color: Theme.textSecondary; font.pixelSize: 11 }
                }
            }

            Item { Layout.fillWidth: true }

            Text {
                text: bot ? ("Eq: " + bot.equity.toFixed(2) + " " + bot.currency) : "—"
                color: Theme.textPrimary
                font.pixelSize: 14
                font.bold: true
            }
        }

        Canvas {
            id: canvas
            Layout.fillWidth: true
            Layout.fillHeight: true

            onWidthChanged: requestPaint()
            onHeightChanged: requestPaint()

            Connections {
                target: bot
                function onEquityChanged() {
                    root.equityPoints = bot.equityCurve
                    canvas.requestPaint()
                }
            }
            Connections {
                target: Theme
                function onIsDarkChanged() { canvas.requestPaint() }
            }

            onPaint: {
                var ctx = getContext("2d")
                ctx.reset()
                ctx.clearRect(0, 0, width, height)

                var cGrid = String(Theme.divider)
                var cText = String(Theme.textMuted)
                var cBal = String(Theme.accent)
                var cEq = String(Theme.up)

                var data = root.equityPoints
                if (!data || data.length < 2) {
                    ctx.fillStyle = cText
                    ctx.font = "13px sans-serif"
                    ctx.fillText(bot && bot.connected ? "Menunggu transaksi atau perubahan saldo..." : "Hubungkan MT5 untuk melihat riwayat kurva ekuitas", 16, height / 2)
                    return
                }

                var mL = 8, mR = 75, mT = 10, mB = 22
                var plotW = width - mL - mR
                var plotH = height - mT - mB
                var n = data.length

                var minVal = Number.MAX_VALUE
                var maxVal = -Number.MAX_VALUE

                for (var i = 0; i < n; i++) {
                    var b = data[i].balance || 0
                    var e = data[i].equity || b
                    if (b < minVal) minVal = b
                    if (e < minVal) minVal = e
                    if (b > maxVal) maxVal = b
                    if (e > maxVal) maxVal = e
                }

                if (maxVal <= minVal) {
                    maxVal = minVal + 10
                    minVal = Math.max(0, minVal - 10)
                }

                // Tambahkan padding 5% atas dan bawah
                var padding = (maxVal - minVal) * 0.05
                maxVal += padding
                minVal -= padding
                var range = maxVal - minVal

                function yOf(val) { return mT + (maxVal - val) / range * plotH }
                function xOf(idx) { return mL + (idx / (n - 1)) * plotW }

                // Gambar grid garis horizontal
                ctx.strokeStyle = cGrid
                ctx.fillStyle = cText
                ctx.font = "10px sans-serif"
                ctx.lineWidth = 1
                var gridLines = 4
                for (var g = 0; g <= gridLines; g++) {
                    var val = minVal + (range * g / gridLines)
                    var yy = yOf(val)
                    ctx.beginPath()
                    ctx.moveTo(mL, yy)
                    ctx.lineTo(mL + plotW, yy)
                    ctx.stroke()
                    ctx.fillText(val.toFixed(2), mL + plotW + 5, yy + 3)
                }

                // Gambar fill area di bawah kurva Balance
                ctx.save()
                var grad = ctx.createLinearGradient(0, mT, 0, mT + plotH)
                grad.addColorStop(0, "rgba(91, 185, 140, 0.25)")
                grad.addColorStop(1, "rgba(91, 185, 140, 0.02)")
                ctx.fillStyle = grad
                ctx.beginPath()
                ctx.moveTo(xOf(0), yOf(minVal))
                for (var j = 0; j < n; j++) {
                    ctx.lineTo(xOf(j), yOf(data[j].balance || data[j].equity))
                }
                ctx.lineTo(xOf(n - 1), yOf(minVal))
                ctx.closePath()
                ctx.fill()
                ctx.restore()

                // Gambar garis Balance
                ctx.strokeStyle = cBal
                ctx.lineWidth = 2
                ctx.beginPath()
                for (var k = 0; k < n; k++) {
                    var xk = xOf(k)
                    var yk = yOf(data[k].balance)
                    if (k === 0) ctx.moveTo(xk, yk)
                    else ctx.lineTo(xk, yk)
                }
                ctx.stroke()

                // Gambar garis Equity (bila berbeda dari balance)
                var hasDiff = false
                for (var d = 0; d < n; d++) {
                    if (data[d].equity !== data[d].balance) { hasDiff = true; break }
                }
                if (hasDiff) {
                    ctx.strokeStyle = cEq
                    ctx.lineWidth = 1.8
                    ctx.setLineDash([4, 3])
                    ctx.beginPath()
                    for (var m = 0; m < n; m++) {
                        var xm = xOf(m)
                        var ym = yOf(data[m].equity)
                        if (m === 0) ctx.moveTo(xm, ym)
                        else ctx.lineTo(xm, ym)
                    }
                    ctx.stroke()
                    ctx.setLineDash([])
                }

                // Label waktu di sumbu X (awal, tengah, akhir)
                function fmtTime(t) {
                    if (!t) return ""
                    var dt = new Date(t * 1000)
                    function pad(num) { return (num < 10 ? "0" : "") + num }
                    return pad(dt.getDate()) + "/" + pad(dt.getMonth() + 1) + " " + pad(dt.getHours()) + ":" + pad(dt.getMinutes())
                }

                ctx.fillStyle = cText
                ctx.fillText(fmtTime(data[0].t), mL, height - 6)
                if (n > 2) {
                    var midIdx = Math.floor(n / 2)
                    ctx.fillText(fmtTime(data[midIdx].t), xOf(midIdx) - 25, height - 6)
                }
                ctx.fillText(fmtTime(data[n - 1].t), mL + plotW - 40, height - 6)
            }
        }
    }
}
