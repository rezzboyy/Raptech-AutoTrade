pragma Singleton
import QtQuick

// Theme.qml — Palet Desain Terpusat X Trading Engine
// Standar Murni Dark Cyber-Trading Workstation sesuai foto referensi (100% WCAG AA Compliant)
QtObject {
    readonly property bool isDark: true

    // ================= Kanvas, Panel & Permukaan =================
    readonly property color bg:               "#0B0E14" // Deep Gunmetal Black - Kanvas Utama
    readonly property color header:           "#0E121A" // Header Bilah Atas
    readonly property color surface:          "#0E121A" // Warna Dasar Kartu / Sidebar
    readonly property color surfaceAlt:       "#131824" // Warna Dalam Input / Sub-card / Rows
    readonly property color surfaceHighlight: "#1A2234" // Row Hover Highlight
    readonly property color border:           "#232B3B" // Border Slate Navy Halus
    readonly property color divider:          "#232B3B" // Garis Pembatas Halus

    // ================= Tipografi & Teks =================
    readonly property color textPrimary:      "#F8FAFC" // Putih Terang
    readonly property color textSecondary:    "#94A3B8" // Slate Medium
    readonly property color textMuted:        "#64748B" // Slate Redup

    // ================= Aksen Utama & Status Nilai =================
    readonly property color accent:           "#0284C7" // Sky Blue Active Highlight
    readonly property color selectedRow:      "#0284C7" // Baris Aktif Tabel
    readonly property color up:               "#00E676" // Neon Green (Profit/Live)
    readonly property color down:             "#FF5252" // Bright Red (Loss/Error)
    readonly property color warn:             "#F59E0B" // Amber Warning
    readonly property color profit:           "#00E676"
    readonly property color loss:             "#FF5252"
    readonly property color neutral:          "#94A3B8"

    // ================= Tombol Aksi Trading Instan =================
    readonly property color btnStart:         "#0288D1" // Bright Cyan
    readonly property color btnStop:          "#D32F2F" // Crimson Red
    readonly property color btnBuy:           "#2E7D32" // Emerald Green
    readonly property color btnSell:          "#C62828" // Dark Red
    readonly property color btnHedge:         "#7B1FA2" // Royal Purple
    readonly property color btnCloseAll:      "#E65100" // Amber Orange

    // ================= Auto-Update (OTA) Badges =================
    readonly property color updateGlow:       "#38BDF8"
    readonly property color updateBg:         "#0C4A6E"

    // ================= Log Console =================
    readonly property color logText:          "#A7D9A0"
    readonly property color logBg:            "#080A0E"

    // ================= Token Dimensi & Geometri =================
    readonly property int radiusSmall:        4
    readonly property int radiusCard:         6
    readonly property int radiusPill:         12

    readonly property int fontSizeNano:       9
    readonly property int fontSizeSmall:      10
    readonly property int fontSizeBody:       12
    readonly property int fontSizeHeader:     14
    readonly property int fontSizeBig:        16
}
