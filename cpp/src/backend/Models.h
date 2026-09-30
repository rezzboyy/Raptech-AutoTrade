#pragma once
#include <QString>

// Model data ternormalisasi (padanan dict di backends/base.py).
// Dipakai lintas backend agar engine/risk/order tidak bergantung bentuk respons MCP.

struct Account {
    long long login = 0;
    double balance = 0.0;
    double equity = 0.0;
    double margin = 0.0;
    double freeMargin = 0.0;
    double profit = 0.0;
    QString currency;
    QString server;
    QString accountType;          // "DEMO" | "REAL" | "CONTEST" | "?"
    bool tradeAllowed = false;    // mcp_trade_allowed && experts_trade_allowed
    bool expertsTradeAllowed = true;
    bool serverConnected = false;
    bool valid = false;
};

struct SymbolSpec {
    QString symbol;
    int digits = 5;
    double point = 0.0;
    double volumeMin = 0.01;
    double volumeMax = 0.0;
    double volumeStep = 0.01;
    double tickValue = 0.0;
    double tickSize = 0.0;
    int stopLevel = 0;
    bool valid = false;
};

struct Tick {
    double bid = 0.0;
    double ask = 0.0;
    long long time = 0;           // epoch detik
    bool valid = false;
};

struct Position {
    long long ticket = 0;
    QString symbol;
    QString type;                 // "BUY" | "SELL"
    double volume = 0.0;
    double priceOpen = 0.0;
    double priceCurrent = 0.0;
    double sl = 0.0;
    double tp = 0.0;
    double profit = 0.0;
    long long magic = 0;
    long long time = 0;           // epoch detik (waktu buka posisi)
};

struct Order {
    long long ticket = 0;
    QString symbol;
    QString type;                 // buy_limit | sell_limit | buy_stop | sell_stop
    double volume = 0.0;
    double price = 0.0;
    double sl = 0.0;
    double tp = 0.0;
    long long magic = 0;
};

struct Candle {
    long long t = 0;              // epoch detik
    double o = 0.0;
    double h = 0.0;
    double l = 0.0;
    double c = 0.0;
    double tickVolume = 0.0;
    double spread = 0.0;
};

struct Deal {
    long long ticket = 0;
    long long time = 0;           // epoch detik
    QString symbol;
    long long magic = 0;
    double netProfit = 0.0;
    double profit = 0.0;
};

struct OrderResult {
    bool ok = false;
    long long ticket = 0;
    bool hasTicket = false;
    QString message;
};
