"""Test alur kerja Mode Programmer: Bantuan API, Syntax Highlighter, Validasi, Jurnal, dan Ekspor CSV.

Memastikan seluruh fitur Tahap 1 s/d Tahap 4 teruji secara komprehensif dan fail-safe.
"""

import os
import sys
from pathlib import Path
import pytest

from PySide6.QtCore import QCoreApplication
from PySide6.QtGui import QGuiApplication, QTextDocument

from src.controller import BotController
from src.qml_highlighter import PythonHighlighter
from strategies.script_runtime import DEFAULT_TEMPLATE, validate_detail


@pytest.fixture(scope="session")
def qapp():
    """Fixture QGuiApplication untuk pengujian komponen Qt."""
    app = QGuiApplication.instance()
    if app is None:
        app = QGuiApplication(sys.argv)
    return app


@pytest.fixture
def controller(qapp):
    """Fixture BotController baru untuk tiap test."""
    ctrl = BotController()
    yield ctrl
    try:
        ctrl.disconnectBot()
    except Exception:
        pass


def test_api_reference_structure(controller):
    """apiReference harus mengembalikan daftar kategori dan item dengan signature, desc, snippet."""
    cats = controller.apiReference()
    assert isinstance(cats, list)
    assert len(cats) >= 5, f"Kategori API terlalu sedikit: {len(cats)}"

    total_items = 0
    cat_names = set()
    for cat in cats:
        assert "group" in cat
        assert "items" in cat
        cat_names.add(cat["group"])
        for item in cat["items"]:
            total_items += 1
            assert "signature" in item and len(item["signature"]) > 0
            assert "desc" in item and len(item["desc"]) > 0
            assert "snippet" in item and len(item["snippet"]) > 0

    assert total_items >= 35, f"Total snippet API terlalu sedikit: {total_items}"
    # Verifikasi kategori penting ada
    expected_categories = {"Data Harga", "Harga Live & Simbol", "Akun & Posisi", "Waktu / Sesi", "Indikator", "Perintah Order", "Lain-lain"}
    for exp in expected_categories:
        assert exp in cat_names, f"Kategori '{exp}' tidak ditemukan di apiReference"


def test_python_highlighter_non_mutating(qapp):
    """PythonHighlighter harus mewarnai sintaks tanpa memodifikasi isi teks dokumen."""
    sample_code = (
        "# Skrip Uji Mode Programmer\n"
        "PARAMS = [{'key': 'period', 'default': 14}]\n\n"
        "def on_bar(ctx):\n"
        "    sma_val = ctx.sma(ctx.close, 14)\n"
        "    if ctx.close[-1] > sma_val[-1]:\n"
        "        return ctx.buy(0.01, sl_points=50, comment='test_hl')\n"
        "    return None\n"
    )
    doc = QTextDocument(sample_code)
    assert doc.toPlainText() == sample_code

    # Pasang highlighter
    hl = PythonHighlighter(doc)
    assert hl is not None

    # Teks dokumen harus persis sama sebelum dan sesudah dipasang highlighter
    assert doc.toPlainText() == sample_code


def test_validate_script_detail_controller(controller):
    """validateScriptDetail pada controller harus mengembalikan status ok, line, dan message."""
    # 1. Template default harus valid
    res_ok = controller.validateScriptDetail(DEFAULT_TEMPLATE)
    assert res_ok["ok"] is True
    assert res_ok["line"] == 0

    # 2. Syntax error pada baris tertentu
    bad_code = "PARAMS = []\nbaris_error_sintaks :: 123\ndef on_bar(ctx):\n    pass\n"
    res_bad = controller.validateScriptDetail(bad_code)
    assert res_bad["ok"] is False
    assert res_bad["line"] == 2
    assert "Sintaks error" in res_bad["message"]

    # 3. Penggunaan library terlarang (sandbox AST)
    sandbox_violation = "import os\ndef on_bar(ctx):\n    return None\n"
    res_sandbox = controller.validateScriptDetail(sandbox_violation)
    assert res_sandbox["ok"] is False
    assert "dilarang" in res_sandbox["message"].lower() or "import" in res_sandbox["message"].lower()


def test_export_journal_and_clear(controller, tmp_path):
    """Jurnal harus merekam entri, dapat diekspor ke CSV valid, dan dapat dibersihkan."""
    # 1. Bersihkan jurnal awal
    controller.clearJournal()
    assert controller.journal == []

    # 2. Masukkan beberapa entri simulasi via _on_journal
    controller._on_journal({
        "action": "BUY",
        "symbol": "EURUSDm",
        "detail": 'Lot 0.01 SL 1.1000 TP 1.1100 "cBot style"',
        "ok": True,
    })
    controller._on_journal({
        "action": "MODIFY",
        "symbol": "EURUSDm",
        "detail": "Geser SL ke breakeven",
        "ok": True,
    })
    controller._on_journal({
        "action": "CLOSE",
        "symbol": "EURUSDm",
        "detail": "Trailing stop hit",
        "ok": True,
    })
    controller._on_journal({
        "action": "BUY",
        "symbol": "XAUUSDm",
        "detail": "Gagal: balance tidak cukup",
        "ok": False,
    })

    assert len(controller.journal) == 4
    assert controller.journal[0]["action"] == "BUY"
    assert controller.journal[0]["ok"] is True
    assert controller.journal[3]["ok"] is False

    # 3. Ekspor ke file CSV
    out_csv = str(tmp_path / "journal_test.csv")
    res_path = controller.exportJournal(out_csv)
    assert res_path == out_csv
    assert os.path.exists(res_path)

    # 4. Verifikasi isi CSV
    with open(res_path, "r", encoding="utf-8") as f:
        lines = f.readlines()

    assert len(lines) == 5  # 1 header + 4 baris data
    assert lines[0].strip() == "Waktu,Aksi,Simbol,Detail,Status"

    # Verifikasi baris 1 (BUY, escape quote pada detail, status OK)
    assert '"BUY"' in lines[1]
    assert '"EURUSDm"' in lines[1]
    assert '""cBot style""' in lines[1]  # Double-quotes ter-escape
    assert '"OK"' in lines[1]

    # Verifikasi baris 4 (GAGAL)
    assert '"XAUUSDm"' in lines[4]
    assert '"GAGAL"' in lines[4]

    # 5. Bersihkan jurnal
    controller.clearJournal()
    assert len(controller.journal) == 0


def test_journal_capacity_limit(controller):
    """Jurnal harus dibatasi maksimal 2000 entri (ring-buffer) agar memori aman."""
    controller.clearJournal()
    for i in range(2050):
        controller._on_journal({
            "action": "LOG",
            "symbol": "EURUSDm",
            "detail": f"Aksi nomor {i}",
            "ok": True,
        })

    assert len(controller.journal) == 2000
    # Entri pertama harus bergeser (indeks 50), bukan 0
    assert "Aksi nomor 50" in controller.journal[0]["detail"]
    assert "Aksi nomor 2049" in controller.journal[-1]["detail"]


def test_end_to_end_programmer_flow_simulation(controller, tmp_path, monkeypatch):
    """Simulasi alur pengguna lengkap di tab Mode Programmer:
    Buka Programmer -> Sisip Snippet API -> Validasi -> Eksekusi Simulasi -> Jurnal terisi -> Ekspor CSV.
    """
    from src import config_store
    monkeypatch.setattr(config_store, "CONFIG_FILE", str(tmp_path / "config.json"))
    # 1. Ambil snippet API dari bantuan
    refs = controller.apiReference()
    order_cat = next(c for c in refs if c["group"] == "Perintah Order")
    buy_item = next(it for it in order_cat["items"] if "buy(" in it["signature"])
    snippet = buy_item["snippet"]
    assert "ctx.buy" in snippet

    # 2. Bangun skrip kustom menggunakan snippet
    custom_script = (
        "PARAMS = [{'key': 'vol', 'label': 'Volume', 'type': 'float', 'default': 0.02}]\n\n"
        "def on_bar(ctx):\n"
        f"    {snippet.strip()}\n"
    )

    # 3. Validasi skrip
    v = controller.validateScriptDetail(custom_script)
    assert v["ok"] is True, f"Skrip tidak valid: {v['message']}"

    # 4. Terapkan skrip
    apply_ok = controller.applyScript(custom_script, "e2e_simulasi", {"vol": 0.02})
    assert apply_ok is True

    # 5. Simulasi engine memancarkan sinyal/jurnal aksi saat trading
    controller.clearJournal()
    controller._on_journal({
        "action": "BUY",
        "symbol": "EURUSDm",
        "detail": "Volume 0.02 sl_points=100 tp_points=200",
        "ok": True,
    })
    controller._on_journal({
        "action": "CLOSE",
        "symbol": "EURUSDm",
        "detail": "Target profit tercapai",
        "ok": True,
    })

    assert len(controller.journal) == 2

    # 6. Ekspor jurnal aksi ke CSV
    export_file = str(tmp_path / "e2e_journal_export.csv")
    res = controller.exportJournal(export_file)
    assert res == export_file
    assert os.path.exists(export_file)

    with open(export_file, "r", encoding="utf-8") as f:
        content = f.read()
    assert "Volume 0.02" in content
    assert "Target profit tercapai" in content


def test_load_script_file_flow(controller, tmp_path):
    """loadScriptFile harus memuat file skrip sembarang, mengembalikan nama, path, dan source."""
    script_content = (
        "SETTINGS = {'symbol': 'BTCUSDm', 'tp_points': 3000}\n"
        "PARAMS = [{'key': 'lot', 'default': 0.05}]\n"
        "def on_bar(ctx):\n"
        "    return ctx.buy()\n"
    )
    test_file = tmp_path / "custom_scalper_btc.py"
    test_file.write_text(script_content, encoding="utf-8")

    # 1. Uji pemuatan lewat path biasa
    res1 = controller.loadScriptFile(str(test_file))
    assert res1["ok"] is True
    assert res1["name"] == "custom_scalper_btc"
    assert res1["source"] == script_content
    assert res1["path"] == str(test_file.resolve())

    # 2. Uji pemuatan lewat URL file://
    url = f"file:///{str(test_file).replace(os.sep, '/')}"
    res2 = controller.loadScriptFile(url)
    assert res2["ok"] is True
    assert res2["name"] == "custom_scalper_btc"
    assert res2["source"] == script_content

    # 3. Uji file tidak ada (fail-safe)
    res_err = controller.loadScriptFile(str(tmp_path / "non_existent.py"))
    assert res_err["ok"] is False
    assert "tidak ditemukan" in res_err["error"].lower()

