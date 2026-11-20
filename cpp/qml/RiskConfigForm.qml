import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "."

// Form pengaturan EKSEKUSI & RISIKO/PROTEKSI (dipakai tab Manual & Programmer).
//   load()    -> isi field dari bot.getConfig()
//   collect() -> kembalikan objek field risiko/eksekusi
ColumnLayout {
    id: form
    spacing: 8

    readonly property int ctrlHeight: 34
    readonly property int labelWidth: 150

    function load() {
        if (!bot) return
        var c = bot.getConfig()
        symbolField.text = c.symbol || "EURUSDm"
        var curTf = c.timeframe_str || (bot ? bot.timeframe : "M5")
        timeframeBox.currentIndex = Math.max(0, timeframeBox.model.indexOf(curTf))
        riskField.text = String(c.risk_per_trade !== undefined ? c.risk_per_trade : 0.01)
        maxPosField.text = String(c.max_open_positions || 1)
        magicField.text = String(c.magic_number || 100200)
        intervalField.text = String(c.loop_interval || 15)

        sltpModeBox.currentIndex = (c.sl_tp_mode === "percent") ? 1 : 0
        slField.text = String(c.sl_points !== undefined ? c.sl_points : 300)
        tpField.text = String(c.tp_points !== undefined ? c.tp_points : 600)
        slPercentField.text = String(c.sl_percent !== undefined ? c.sl_percent : 0.5)
        tpPercentField.text = String(c.tp_percent !== undefined ? c.tp_percent : 1.0)
        virtualSwitch.checked = Boolean(c.virtual_sltp_enabled)

        trailingSwitch.checked = Boolean(c.trailing_stop_enabled)
        trailingPtsField.text = String(c.trailing_stop_points !== undefined ? c.trailing_stop_points : 200)
        trailingStepField.text = String(c.trailing_step_points !== undefined ? c.trailing_step_points : 50)

        beSwitch.checked = Boolean(c.break_even_enabled)
        beTriggerField.text = String(c.break_even_trigger_points !== undefined ? c.break_even_trigger_points : 150)
        beOffsetField.text = String(c.break_even_offset_points !== undefined ? c.break_even_offset_points : 10)

        drawdownField.text = String((c.daily_drawdown_limit !== undefined ? c.daily_drawdown_limit : 0.05) * 100)
        maxTradesField.text = String(c.max_daily_trades !== undefined ? c.max_daily_trades : 10)

        spreadField.text = String(c.max_spread_points !== undefined ? c.max_spread_points : 0)
        exposureField.text = String(c.max_exposure_lots !== undefined ? c.max_exposure_lots : 0)
        equityStopField.text = String((c.equity_stop_loss !== undefined ? c.equity_stop_loss : 0) * 100)
        lossStreakField.text = String(c.max_consecutive_losses !== undefined ? c.max_consecutive_losses : 0)
    }

    Connections {
        target: bot
        function onTimeframeChanged(tf) {
            var idx = timeframeBox.model.indexOf(tf)
            if (idx >= 0) timeframeBox.currentIndex = idx
        }
    }

    function collect() {
        return {
            "symbol": symbolField.text,
            "timeframe_str": timeframeBox.currentText,
            "risk_per_trade": parseFloat(riskField.text || "0.01"),
            "max_open_positions": parseInt(maxPosField.text || "1"),
            "magic_number": parseInt(magicField.text || "100200"),
            "loop_interval": parseInt(intervalField.text || "15"),
            "sl_tp_mode": sltpModeBox.currentIndex === 1 ? "percent" : "points",
            "sl_points": parseInt(slField.text || "300"),
            "tp_points": parseInt(tpField.text || "600"),
            "sl_percent": parseFloat(slPercentField.text || "0.5"),
            "tp_percent": parseFloat(tpPercentField.text || "1.0"),
            "virtual_sltp_enabled": virtualSwitch.checked,
            "trailing_stop_enabled": trailingSwitch.checked,
            "trailing_stop_points": parseInt(trailingPtsField.text || "200"),
            "trailing_step_points": parseInt(trailingStepField.text || "50"),
            "break_even_enabled": beSwitch.checked,
            "break_even_trigger_points": parseInt(beTriggerField.text || "150"),
            "break_even_offset_points": parseInt(beOffsetField.text || "10"),
            "daily_drawdown_limit": parseFloat(drawdownField.text || "0") / 100.0,
            "max_daily_trades": parseInt(maxTradesField.text || "10"),
            "max_spread_points": parseInt(spreadField.text || "0"),
            "max_exposure_lots": parseFloat(exposureField.text || "0"),
            "equity_stop_loss": parseFloat(equityStopField.text || "0") / 100.0,
            "max_consecutive_losses": parseInt(lossStreakField.text || "0")
        }
    }

    // ===== Pengaturan Dasar =====
    GridLayout {
        Layout.fillWidth: true
        columns: 2; rowSpacing: 6; columnSpacing: 8
        Label { text: "Simbol (Multi)"; color: Theme.textSecondary; Layout.preferredWidth: form.labelWidth }
        CField { id: symbolField; Layout.preferredHeight: form.ctrlHeight; placeholderText: "EURUSDm atau EURUSDm, GBPUSDm" }
        Label { text: "Timeframe"; color: Theme.textSecondary; Layout.preferredWidth: form.labelWidth }
        CCombo { id: timeframeBox; Layout.preferredHeight: form.ctrlHeight; model: ["M1","M5","M15","M30","H1","H4","D1"] }
        Label { text: "Risiko/trade"; color: Theme.textSecondary; Layout.preferredWidth: form.labelWidth }
        CField { id: riskField; Layout.preferredHeight: form.ctrlHeight; placeholderText: "0.01 = 1%" }
        Label { text: "Maks Posisi"; color: Theme.textSecondary; Layout.preferredWidth: form.labelWidth }
        CField { id: maxPosField; Layout.preferredHeight: form.ctrlHeight }
        Label { text: "Magic Number"; color: Theme.textSecondary; Layout.preferredWidth: form.labelWidth }
        CField { id: magicField; Layout.preferredHeight: form.ctrlHeight }
        Label { text: "Interval (dtk)"; color: Theme.textSecondary; Layout.preferredWidth: form.labelWidth }
        CField { id: intervalField; Layout.preferredHeight: form.ctrlHeight }
    }

    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.divider }

    // ===== SL / TP =====
    RowLayout {
        Layout.fillWidth: true
        Text { text: "Order SL & TP"; color: Theme.textMuted; font.pixelSize: 11; font.bold: true; Layout.fillWidth: true }
        CCombo { id: sltpModeBox; model: ["Points", "Percent"]; Layout.preferredWidth: 120; Layout.preferredHeight: form.ctrlHeight }
    }
    GridLayout {
        Layout.fillWidth: true
        columns: 2; rowSpacing: 6; columnSpacing: 8
        visible: sltpModeBox.currentIndex === 0
        Label { text: "Stop Loss (pts)"; color: Theme.textSecondary; Layout.preferredWidth: form.labelWidth }
        CField { id: slField; Layout.preferredHeight: form.ctrlHeight; placeholderText: "300" }
        Label { text: "Take Profit (pts)"; color: Theme.textSecondary; Layout.preferredWidth: form.labelWidth }
        CField { id: tpField; Layout.preferredHeight: form.ctrlHeight; placeholderText: "600" }
    }
    GridLayout {
        Layout.fillWidth: true
        columns: 2; rowSpacing: 6; columnSpacing: 8
        visible: sltpModeBox.currentIndex === 1
        Label { text: "Stop Loss (%)"; color: Theme.textSecondary; Layout.preferredWidth: form.labelWidth }
        CField { id: slPercentField; Layout.preferredHeight: form.ctrlHeight; placeholderText: "0.5" }
        Label { text: "Take Profit (%)"; color: Theme.textSecondary; Layout.preferredWidth: form.labelWidth }
        CField { id: tpPercentField; Layout.preferredHeight: form.ctrlHeight; placeholderText: "1.0" }
    }
    RowLayout {
        Layout.fillWidth: true
        Text { text: "Virtual / Hidden SL/TP"; color: Theme.textMuted; font.pixelSize: 11; font.bold: true; Layout.fillWidth: true }
        Switch { id: virtualSwitch; text: virtualSwitch.checked ? "Aktif" : "Nonaktif" }
    }

    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.divider }

    // ===== Trailing Stop =====
    RowLayout {
        Layout.fillWidth: true
        Text { text: "Trailing Stop Loss"; color: Theme.textMuted; font.pixelSize: 11; font.bold: true; Layout.fillWidth: true }
        Switch { id: trailingSwitch; text: trailingSwitch.checked ? "Aktif" : "Nonaktif" }
    }
    GridLayout {
        Layout.fillWidth: true
        columns: 2; rowSpacing: 6; columnSpacing: 8
        visible: trailingSwitch.checked
        Label { text: "Jarak Trailing (pts)"; color: Theme.textSecondary; Layout.preferredWidth: form.labelWidth }
        CField { id: trailingPtsField; Layout.preferredHeight: form.ctrlHeight; placeholderText: "200" }
        Label { text: "Step Geser (pts)"; color: Theme.textSecondary; Layout.preferredWidth: form.labelWidth }
        CField { id: trailingStepField; Layout.preferredHeight: form.ctrlHeight; placeholderText: "50" }
    }

    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.divider }

    // ===== Break-Even =====
    RowLayout {
        Layout.fillWidth: true
        Text { text: "Break-Even Stop"; color: Theme.textMuted; font.pixelSize: 11; font.bold: true; Layout.fillWidth: true }
        Switch { id: beSwitch; text: beSwitch.checked ? "Aktif" : "Nonaktif" }
    }
    GridLayout {
        Layout.fillWidth: true
        columns: 2; rowSpacing: 6; columnSpacing: 8
        visible: beSwitch.checked
        Label { text: "Pemicu Profit (pts)"; color: Theme.textSecondary; Layout.preferredWidth: form.labelWidth }
        CField { id: beTriggerField; Layout.preferredHeight: form.ctrlHeight; placeholderText: "150" }
        Label { text: "Offset SL (pts)"; color: Theme.textSecondary; Layout.preferredWidth: form.labelWidth }
        CField { id: beOffsetField; Layout.preferredHeight: form.ctrlHeight; placeholderText: "10" }
    }

    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.divider }

    // ===== Proteksi Harian =====
    Text { text: "Batas Proteksi Harian"; color: Theme.textMuted; font.pixelSize: 11; font.bold: true }
    GridLayout {
        Layout.fillWidth: true
        columns: 2; rowSpacing: 6; columnSpacing: 8
        Label { text: "Batas Max Drawdown (%)"; color: Theme.textSecondary; Layout.preferredWidth: form.labelWidth }
        CField { id: drawdownField; Layout.preferredHeight: form.ctrlHeight; placeholderText: "5 (0 = nonaktif)" }
        Label { text: "Batas Trade Harian"; color: Theme.textSecondary; Layout.preferredWidth: form.labelWidth }
        CField { id: maxTradesField; Layout.preferredHeight: form.ctrlHeight; placeholderText: "10 (0 = tanpa batas)" }
    }

    Rectangle { Layout.fillWidth: true; Layout.preferredHeight: 1; color: Theme.divider }

    // ===== Proteksi Lanjutan =====
    Text { text: "Proteksi Lanjutan"; color: Theme.textMuted; font.pixelSize: 11; font.bold: true }
    GridLayout {
        Layout.fillWidth: true
        columns: 2; rowSpacing: 6; columnSpacing: 8
        Label { text: "Max Spread (pts)"; color: Theme.textSecondary; Layout.preferredWidth: form.labelWidth }
        CField { id: spreadField; Layout.preferredHeight: form.ctrlHeight; placeholderText: "0 = nonaktif" }
        Label { text: "Max Eksposur (lot)"; color: Theme.textSecondary; Layout.preferredWidth: form.labelWidth }
        CField { id: exposureField; Layout.preferredHeight: form.ctrlHeight; placeholderText: "0 = tanpa batas" }
        Label { text: "Equity Cut-Loss (%)"; color: Theme.textSecondary; Layout.preferredWidth: form.labelWidth }
        CField { id: equityStopField; Layout.preferredHeight: form.ctrlHeight; placeholderText: "0 = nonaktif" }
        Label { text: "Max Loss Beruntun"; color: Theme.textSecondary; Layout.preferredWidth: form.labelWidth }
        CField { id: lossStreakField; Layout.preferredHeight: form.ctrlHeight; placeholderText: "0 = nonaktif" }
    }
}
