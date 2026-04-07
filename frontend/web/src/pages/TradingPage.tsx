import { motion, useReducedMotion } from "framer-motion";
import { BrainCog, Plus, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";

import { fadeInUp, reduceMotion, staggerContainer } from "../lib/animations";
import { api } from "../services/api";
import { PortfolioSummary, Trade } from "../types/api";
import { AppCard, EmptyState, SectionHeader, SkeletonLoader } from "../components/ui";

function num(v: unknown) {
  if (typeof v === "number") return v;
  if (typeof v === "string") return Number(v) || 0;
  return 0;
}

export default function TradingPage() {
  const [watchlist, setWatchlist] = useState<Array<Record<string, unknown>>>([]);
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [analysis, setAnalysis] = useState<Record<string, unknown> | null>(null);
  const [symbol, setSymbol] = useState("");
  const [exchange, setExchange] = useState("NSE");
  const [loading, setLoading] = useState(true);

  const shouldReduceMotion = useReducedMotion();
  const fadeMotion = reduceMotion(shouldReduceMotion, fadeInUp);

  const load = async () => {
    setLoading(true);
    const [watchlistRows, portfolioSummary, tradeRows] = await Promise.all([
      api.trading.watchlist(),
      api.trading.portfolio(),
      api.trading.trades({ limit: 100, offset: 0 }),
    ]);
    setWatchlist(watchlistRows);
    setPortfolio(portfolioSummary);
    setTrades(tradeRows);
    setLoading(false);
  };

  useEffect(() => {
    void load();
  }, []);

  const onAddWatchlist = async () => {
    await api.trading.addWatchlist({ symbol, exchange, asset_type: "equity" });
    setSymbol("");
    await load();
  };

  const onAnalyze = async () => {
    const result = await api.trading.analyze(90);
    setAnalysis(result);
  };

  return (
    <div className="space-y-6">
      <SectionHeader
        title="Trading"
        subtitle="Sharper execution view for watchlist, portfolio movement, and journaled trades."
      />

      <AppCard>
        <div className="flex items-start justify-between gap-4">
          <div>
            <p className="section-label">Portfolio Value</p>
            <p className="mt-2 text-4xl font-semibold tracking-tight text-text-primary">
              INR {(portfolio?.current_value ?? 0).toLocaleString()}
            </p>
            <p className={`mt-1 text-sm ${num(portfolio?.daily_pnl) >= 0 ? "text-success" : "text-danger"}`}>
              Day change: {num(portfolio?.daily_pnl) >= 0 ? "+" : ""}
              {num(portfolio?.daily_pnl).toLocaleString()}
            </p>
          </div>
          <button
            type="button"
            onClick={() => void onAnalyze()}
            className="inline-flex items-center gap-2 rounded-button bg-accent px-4 py-2 text-sm font-semibold text-white"
          >
            <BrainCog className="h-4 w-4" /> Run Analysis
          </button>
        </div>
      </AppCard>

      {loading ? (
        <SkeletonLoader variant="card" />
      ) : watchlist.length === 0 && trades.length === 0 ? (
        <EmptyState
          icon={<BrainCog className="h-6 w-6" />}
          title="No trading data yet"
          description="Add symbols to your watchlist or log a trade to start this module."
          action={
            <button
              type="button"
              onClick={() => void api.trading.addWatchlist({ symbol: symbol || "NIFTY50", exchange, asset_type: "equity" }).then(load)}
              className="rounded-button bg-accent px-4 py-2 text-sm font-semibold text-white"
            >
              Add First Symbol
            </button>
          }
        />
      ) : (
        <motion.section variants={staggerContainer} initial="initial" animate="animate" className="space-y-4">
          <motion.div variants={fadeMotion}>
            <AppCard>
              <div className="mb-3 flex items-center justify-between gap-2">
                <p className="section-label">Watchlist</p>
                <div className="flex items-center gap-2">
                  <input
                    value={symbol}
                    onChange={(event) => setSymbol(event.target.value.toUpperCase())}
                    placeholder="INFY"
                    className="w-28 rounded-input border border-border bg-surface-raised px-2 py-1.5 text-xs"
                  />
                  <input
                    value={exchange}
                    onChange={(event) => setExchange(event.target.value.toUpperCase())}
                    className="w-20 rounded-input border border-border bg-surface-raised px-2 py-1.5 text-xs"
                  />
                  <button
                    type="button"
                    onClick={() => void onAddWatchlist()}
                    className="inline-flex items-center gap-1 rounded-button bg-accent px-2 py-1.5 text-xs font-semibold text-white"
                  >
                    <Plus className="h-3.5 w-3.5" /> Add
                  </button>
                </div>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full min-w-[720px] text-left text-sm">
                  <thead>
                    <tr className="text-xs uppercase tracking-widest text-text-muted">
                      <th className="pb-2">Symbol</th>
                      <th className="pb-2">Price</th>
                      <th className="pb-2">Change %</th>
                      <th className="pb-2">Alert</th>
                      <th className="pb-2">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {watchlist.map((row) => {
                      const change = num(row.change_pct || row.change_percent || row.pnl_pct);
                      return (
                        <tr key={String(row.id)} className="border-t border-border">
                          <td className="py-2 font-medium text-text-primary">{String(row.symbol || "-")}</td>
                          <td className="py-2 text-text-secondary">{String(row.last_price ?? row.price ?? "-")}</td>
                          <td className={`py-2 ${change >= 0 ? "text-success" : "text-danger"}`}>{change.toFixed(2)}%</td>
                          <td className="py-2 text-text-secondary">
                            {String(row.alert_price_above ?? "-")} / {String(row.alert_price_below ?? "-")}
                          </td>
                          <td className="py-2">
                            <button
                              type="button"
                              onClick={() => void api.trading.removeWatchlist(String(row.id)).then(load)}
                              className="rounded-button border border-danger/40 p-1.5 text-danger"
                            >
                              <Trash2 className="h-3.5 w-3.5" />
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </AppCard>
          </motion.div>

          <motion.div variants={fadeMotion}>
            <AppCard>
              <p className="section-label">Trade Log</p>
              <div className="mt-3 overflow-x-auto">
                <table className="w-full min-w-[760px] text-left text-sm">
                  <thead>
                    <tr className="text-xs uppercase tracking-widest text-text-muted">
                      <th className="pb-2">Date</th>
                      <th className="pb-2">Symbol</th>
                      <th className="pb-2">Action</th>
                      <th className="pb-2">Qty</th>
                      <th className="pb-2">Price</th>
                      <th className="pb-2">Value</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trades.map((trade) => (
                      <tr key={trade.id} className="border-t border-border">
                        <td className="py-2 text-text-secondary">{trade.trade_date}</td>
                        <td className="py-2 font-medium text-text-primary">{trade.symbol}</td>
                        <td className="py-2 text-text-secondary uppercase">{trade.action}</td>
                        <td className="py-2 text-text-secondary">{trade.quantity}</td>
                        <td className="py-2 text-text-secondary">{trade.price}</td>
                        <td className="py-2 text-text-secondary">{trade.total_value}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </AppCard>
          </motion.div>

          <motion.div variants={fadeMotion}>
            <AppCard>
              <p className="section-label">Analysis Output</p>
              <pre className="mt-3 overflow-x-auto rounded-lg bg-surface-raised p-3 text-xs text-text-secondary">
                {analysis ? JSON.stringify(analysis, null, 2) : "Run analysis to generate insights."}
              </pre>
            </AppCard>
          </motion.div>
        </motion.section>
      )}
    </div>
  );
}
