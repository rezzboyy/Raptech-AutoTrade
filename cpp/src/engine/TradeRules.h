#pragma once
#include <QString>

#include "backend/Models.h"

class TradingBackend;
struct Settings;

// Aturan trading backend-agnostik (padanan src/trade_rules.py).
namespace TradeRules {

// Petakan sinyal -> sisi order ("buy"/"sell"). QString() bila bukan sinyal.
QString mapSignalToSide(const QString &signal);

// Hitung lot dari spesifikasi simbol + risiko. 0 bila data tak memadai.
double calcLotFromSpec(const SymbolSpec &spec, double balance, double riskPercent,
                       double slPrice, double entryPrice);

int countOpenPositions(TradingBackend &backend, const QString &symbol, long long magic);
bool canOpenNewPosition(TradingBackend &backend, const QString &symbol, long long magic,
                        int maxPositions);

// Break-even & trailing (kirim modify SL ke broker). True bila SL dimodifikasi.
bool applyBreakEven(TradingBackend &backend, const Position &pos, const SymbolSpec &spec,
                    int triggerPoints, int offsetPoints);
bool applyTrailingStop(TradingBackend &backend, const Position &pos, const SymbolSpec &spec,
                       int trailingPoints, int stepPoints);

// SL/TP virtual tercapai? Kembalikan "SL"/"TP"/QString().
QString virtualExitHit(const QString &posType, double sl, double tp, double bid, double ask);

// SL/TP berbasis persen harga. Mengisi outSl/outTp.
void computePercentSlTp(const QString &side, double entry, double slPercent,
                        double tpPercent, int digits, double &outSl, double &outTp);

double currentExposure(TradingBackend &backend, long long magic);
int consecutiveLosses(TradingBackend &backend, long long magic);
int dailyTradeCount(TradingBackend &backend, long long magic);
// Drawdown harian terlampaui? isBreached + fraksi drawdown via out param.
bool dailyDrawdownBreached(TradingBackend &backend, double maxDrawdown, long long magic,
                           double &outDd);

// Evaluasi seluruh gerbang risiko. True + reason kosong bila boleh.
bool passesRiskGates(TradingBackend &backend, const Settings &s, const QString &symbol,
                     QString &reason);

// Buka order hanya bila gerbang risiko + eksposur lolos.
OrderResult openOrderIfAllowed(TradingBackend &backend, const Settings &s, const QString &symbol,
                               const QString &side, double volume, double sl, double tp,
                               const QString &comment);

} // namespace TradeRules
