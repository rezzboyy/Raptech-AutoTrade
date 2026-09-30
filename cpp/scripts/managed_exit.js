// Managed Exit — entry RSI + exit terkelola (JavaScript / QJSEngine).
// Konversi dari strategies/scripts/managed_exit.py.

var SETTINGS = {
    symbol: "EURUSDm",
    timeframe: "M5",
    volume: 0.01,
    max_positions: 1,
};

var PARAMS = { rsi_period: 14, oversold: 30, overbought: 70, tp_profit: 5.0 };

function on_bar(ctx) {
    var r = ctx.rsi(ctx.close, ctx.params.rsi_period);
    var now = r[r.length - 1];
    var prev = r[r.length - 2];

    // Kelola posisi terbuka: ambil profit / balik arah.
    if (ctx.position) {
        // Tutup bila profit mengambang melewati target.
        if (ctx.position.profit >= ctx.params.tp_profit) return ctx.close_position();
        // Tutup BUY saat overbought, SELL saat oversold.
        if (ctx.position.type === "BUY" && now >= ctx.params.overbought) return ctx.close_position();
        if (ctx.position.type === "SELL" && now <= ctx.params.oversold) return ctx.close_position();
        return null;
    }

    // Entry: RSI keluar dari zona ekstrem.
    if (prev <= ctx.params.oversold && now > ctx.params.oversold) return ctx.buy();
    if (prev >= ctx.params.overbought && now < ctx.params.overbought) return ctx.sell();
    return null;
}
