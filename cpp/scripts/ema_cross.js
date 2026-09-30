// EMA Crossover — Mode Programmer (JavaScript / QJSEngine).
// Konversi dari strategies/scripts/ema_cross.py.
//
// Kontrak: definisikan SETTINGS (opsional), PARAMS (opsional), dan on_bar(ctx).
// on_bar mengembalikan "BUY"/"SELL"/null, ATAU perintah dari ctx.* (objek),
// ATAU array beberapa perintah.

var SETTINGS = {
    symbol: "EURUSDm",       // Exness Standard pakai suffix 'm'
    timeframe: "M5",
    volume: 0.01,
    sl_points: 300,
    tp_points: 600,
    max_positions: 1,
};

var PARAMS = { fast: 12, slow: 26 };

function on_bar(ctx) {
    var fast = ctx.ema(ctx.close, ctx.params.fast);
    var slow = ctx.ema(ctx.close, ctx.params.slow);

    // ctx.buy()/ctx.sell() otomatis membaca volume & sl/tp dari SETTINGS.
    if (ctx.crossover(fast, slow)) return ctx.buy();
    if (ctx.crossunder(fast, slow)) return ctx.sell();
    return null;
}
