pragma Singleton
import QtQuick

// Palet warna terpusat — mendukung mode Gelap (Dark) dan Terang (Light).
QtObject {
    property bool isDark: true

    // Latar & permukaan
    readonly property color bg:          isDark ? "#181b24" : "#f1f4f8"
    readonly property color header:      isDark ? "#1f2430" : "#ffffff"
    readonly property color surface:     isDark ? "#222834" : "#ffffff"
    readonly property color surfaceAlt:  isDark ? "#2a3140" : "#e9edf4"
    readonly property color border:      isDark ? "#333b4d" : "#d2d8e4"
    readonly property color divider:     isDark ? "#2c333f" : "#e2e7ef"

    // Teks
    readonly property color textPrimary:   isDark ? "#dce1ea" : "#1e293b"
    readonly property color textSecondary: isDark ? "#a9b2c4" : "#475569"
    readonly property color textMuted:     isDark ? "#79839a" : "#8c96a8"

    // Aksen & status
    readonly property color accent:  isDark ? "#5bb98c" : "#16a34a"
    readonly property color up:      isDark ? "#5bc48e" : "#16a34a"
    readonly property color down:    isDark ? "#e2707a" : "#dc2626"
    readonly property color warn:    isDark ? "#e0a15c" : "#d97706"
    readonly property color logText: isDark ? "#a7d9a0" : "#1b4d24"
    readonly property color logBg:   isDark ? "#151820" : "#f8fafc"
}
