pragma Singleton
import QtQuick

// Theme.qml — Palet Desain Terpusat X Trading Engine
// Mendukung Dark Cyber-Trading & Soft Warm-Slate Light Mode (Nyaman di mata, tidak silau)
QtObject {
    readonly property bool isDark: (typeof bot !== "undefined" && bot) ? (bot.theme !== "light") : true

    // ================= Kanvas, Panel & Permukaan =================
    readonly property color bg:               isDark ? "#0B0E14" : "#E9EEF5" // Kanvas Utama (Slate Lembut saat Light)
    readonly property color header:           isDark ? "#0E121A" : "#F3F6FA" // Header Bilah Atas
    readonly property color surface:          isDark ? "#0E121A" : "#F4F7FB" // Warna Dasar Kartu / Sidebar
    readonly property color surfaceAlt:       isDark ? "#131824" : "#E2E9F2" // Warna Dalam Input / Sub-card / Rows
    readonly property color surfaceHighlight: isDark ? "#1A2234" : "#D4DFEE" // Row Hover Highlight
    readonly property color border:           isDark ? "#232B3B" : "#C4D0DF" // Border Slate Halus
    readonly property color divider:          isDark ? "#232B3B" : "#CBD5E1" // Garis Pembatas Halus

    // ================= Tabel & Semantik Status =================
    readonly property color tableHeader:      isDark ? "#101622" : "#DFE7F2"
    readonly property color rowEven:          isDark ? "#0B0E14" : "#F4F7FB"
    readonly property color rowOdd:           isDark ? "#0E121A" : "#EBF0F7"
    readonly property color hoverSurface:     isDark ? "#1E293B" : "#DCE5F1"
    readonly property color dangerHover:      isDark ? "#331616" : "#FEE2E2"
    readonly property color dangerTint:       isDark ? "#301515" : "#FEF2F2"
    readonly property color dangerText:       isDark ? "#ffc2c2" : "#991B1B"
    readonly property color bannerOkBg:       isDark ? "#163828" : "#DCFCE7"
    readonly property color bannerErrBg:      isDark ? "#3d1818" : "#FEE2E2"
    readonly property color bannerWarnBg:     isDark ? "#3d2e12" : "#FEF3C7"
    readonly property color badgeWarnBorder:  isDark ? "#c9922e" : "#D97706"
    readonly property color badgeWarnText:    isDark ? "#ffb84d" : "#B45309"

    // ================= Tipografi =================
    readonly property color textPrimary:      isDark ? "#F8FAFC" : "#0F172A"
    readonly property color textSecondary:    isDark ? "#94A3B8" : "#475569"
    readonly property color textMuted:        isDark ? "#64748B" : "#64748B"

    // ================= Aksen & Indikator =================
    readonly property color accent:           isDark ? "#0284C7" : "#0369A1" // Sky Blue Active Highlight
    readonly property color selectedRow:      isDark ? "#0284C7" : "#0284C7" // Baris Aktif Tabel
    readonly property color up:               isDark ? "#00E676" : "#15803D" // Green (Profit/Live)
    readonly property color down:             isDark ? "#FF5252" : "#DC2626" // Red (Loss/Error)
    readonly property color warn:             isDark ? "#F59E0B" : "#B45309" // Amber Warning
    readonly property color profit:           isDark ? "#00E676" : "#15803D"
    readonly property color loss:             isDark ? "#FF5252" : "#DC2626"
    readonly property color neutral:          isDark ? "#94A3B8" : "#475569"

    // ================= Warna Tombol Aksi =================
    readonly property color btnStart:         isDark ? "#0288D1" : "#0284C7" // Cyan/Blue
    readonly property color btnStop:          isDark ? "#D32F2F" : "#DC2626" // Crimson Red
    readonly property color btnBuy:           isDark ? "#2E7D32" : "#15803D" // Emerald Green
    readonly property color btnSell:          isDark ? "#C62828" : "#B91C1C" // Dark Red
    readonly property color btnHedge:         isDark ? "#7B1FA2" : "#6D28D9" // Royal Purple
    readonly property color btnCloseAll:      isDark ? "#E65100" : "#C2410C" // Amber Orange

    // ================= Banner Update =================
    readonly property color updateGlow:       isDark ? "#38BDF8" : "#0284C7"
    readonly property color updateBg:         isDark ? "#0C4A6E" : "#DBEAFE"

    // ================= Log Console =================
    readonly property color logText:          isDark ? "#A7D9A0" : "#1E293B"
    readonly property color logBg:            isDark ? "#080A0E" : "#ECF1F7"

    // ================= Metrik Tata Letak & Tipografi =================
    readonly property int radiusSmall:        4
    readonly property int radiusMedium:       6
    readonly property int radiusLarge:        8
    readonly property int fontSizeTiny:       10
    readonly property int fontSizeSmall:      11
    readonly property int fontSizeNormal:     12
    readonly property int fontSizeMedium:     13
    readonly property int fontSizeLarge:      14
    readonly property int fontSizeTitle:      18
}
