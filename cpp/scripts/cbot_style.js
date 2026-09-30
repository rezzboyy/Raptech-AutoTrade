// Gaya cBot — kontrol order penuh dari dalam skrip (JavaScript / QJSEngine).
// Konversi dari strategies/scripts/cbot_style.py.

var SETTINGS = {
    symbol: "EURUSDm",
    timeframe: "M5",
    volume: 0.01,
    max_positions: 1,
};

var PARAMS = { fast: 10, slow: 30, sl_points: 300, tp_points: 600 };

function on_bar(ctx) {
    var fast = ctx.sma(ctx.close, ctx.params.fast);
    var slow = ctx.sma(ctx.close, ctx.params.slow);

    var up = ctx.crossover(fast, slow);
    var down = ctx.crossunder(fast, slow);

    // Kelola posisi aktif: tutup saat sinyal berbalik.
    if (ctx.position) {
        if (ctx.position.type === "BUY" && down) return ctx.close_position();
        if (ctx.position.type === "SELL" && up) return ctx.close_position();
        return null; // sudah ada posisi searah, tahan
    }

    // Belum ada posisi: buka dengan SL/TP points eksplisit.
    if (up) return ctx.buy({ sl_points: ctx.params.sl_points, tp_points: ctx.params.tp_points });
    if (down) return ctx.sell({ sl_points: ctx.params.sl_points, tp_points: ctx.params.tp_points });
    return null;
}
