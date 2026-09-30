import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import ".."

// Panel Bantuan API: daftar ctx.* dikelompokkan + cari + tombol Sisipkan.
// Sinyal insertRequested(text) dipancarkan saat tombol Sisipkan diklik.
Rectangle {
    id: root
    color: Theme.surface
    radius: 10
    border.color: Theme.border

    signal insertRequested(string snippet)

    property var apiGroups: []

    function reload() {
        apiGroups = bot ? bot.apiReference() : []
        rebuild()
    }

    // Bangun model datar (header grup + item) dgn filter pencarian.
    function rebuild() {
        listModel.clear()
        var q = searchField.text.trim().toLowerCase()
        for (var g = 0; g < apiGroups.length; g++) {
            var grp = apiGroups[g]
            var items = grp.items || []
            var matched = []
            for (var i = 0; i < items.length; i++) {
                var it = items[i]
                var hay = (it.signature + " " + it.desc).toLowerCase()
                if (q.length === 0 || hay.indexOf(q) !== -1)
                    matched.push(it)
            }
            if (matched.length === 0) continue
            listModel.append({ "isHeader": true, "title": grp.group, "sig": "", "desc": "", "snippet": "" })
            for (var m = 0; m < matched.length; m++) {
                listModel.append({
                    "isHeader": false, "title": "",
                    "sig": matched[m].signature || "",
                    "desc": matched[m].desc || "",
                    "snippet": matched[m].snippet || ""
                })
            }
        }
    }

    Component.onCompleted: reload()

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            spacing: 7
            Text { text: "Bantuan API (ctx.*)"; color: Theme.textPrimary; font.pixelSize: 14; font.bold: true }
            Item { Layout.fillWidth: true }
        }

        CField {
            id: searchField
            Layout.fillWidth: true
            Layout.preferredHeight: 32
            placeholderText: "Cari fungsi/indikator... (mis. rsi, buy, ichimoku)"
            onTextChanged: root.rebuild()
        }

        ListView {
            id: apiView
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true
            spacing: 2
            model: ListModel { id: listModel }
            ScrollBar.vertical: ThinScrollBar {}

            delegate: Item {
                width: apiView.width
                height: model.isHeader ? 24 : 46

                // Judul grup.
                Text {
                    visible: model.isHeader
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    text: model.title
                    color: Theme.accent
                    font.pixelSize: 11
                    font.bold: true
                }

                // Baris item API.
                RowLayout {
                    visible: !model.isHeader
                    anchors.fill: parent
                    spacing: 8
                    ColumnLayout {
                        Layout.fillWidth: true
                        spacing: 1
                        Text {
                            text: model.sig
                            color: Theme.textPrimary
                            font.family: "Consolas, 'Courier New', monospace"
                            font.pixelSize: 12
                            elide: Text.ElideRight
                            Layout.fillWidth: true
                        }
                        Text {
                            text: model.desc
                            color: Theme.textMuted
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
                    opacity: 0.5
                }
            }
        }
    }
}
