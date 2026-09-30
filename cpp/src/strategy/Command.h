#pragma once
#include <QString>
#include <QVector>

#include "backend/Models.h"

// Satu perintah trading dari strategi/skrip (padanan dict cmd di bot_engine.py).
struct Command {
    QString action;              // BUY | SELL | CLOSE | CLOSE_ALL | MODIFY
    bool hasVolume = false;      double volume = 0.0;
    bool hasSl = false;          double sl = 0.0;    // harga absolut
    bool hasTp = false;          double tp = 0.0;
    bool hasSlPoints = false;    int slPoints = 0;
    bool hasTpPoints = false;    int tpPoints = 0;
    bool hasRisk = false;        double risk = 0.0;
    long long ticket = 0;
    QString comment;
    QString barTime;
};

// Konteks runtime yang diberikan engine ke strategi/skrip tiap bar.
struct RuntimeContext {
    QString symbol;
    QVector<Position> positions;
    Account account;
    Tick tick;
    SymbolSpec spec;
};
