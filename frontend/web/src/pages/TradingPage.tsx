import { useEffect, useMemo, useState } from "react";
import { Pie, PieChart, ResponsiveContainer, Cell, Tooltip } from "recharts";
import { BrainCog, Plus, Trash2 } from "lucide-react";

import { api } from "../services/api";
import { PortfolioSummary, Trade } from "../types/api";

const PIE_COLORS = ["#3B82F6", "#10B981", "#F59E0B", "#F43F5E", "#6366F1"];

export default function TradingPage() {
  const [watchlist, setWatchlist] = useState<Array<Record<string, unknown>>>([]);
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [analysis, setAnalysis] = useState<Record<string, unknown> | null>(null);
  const [symbol, setSymbol] = useState("");
  const [exchange, setExchange] = useState("NSE");

  const load = async () => {
    const [watchlistRows, portfolioSummary, tradeRows] = await Promise.all([
      api.trading.watchlist(),
      api.trading.portfolio(),
      api.trading.trades({ limit: 100, offset: 0 }),
    ]);
    setWatchlist(watchlistRows);
    setPortfolio(portfolioSummary);
    setTrades(tradeRows);
  };

  useEffect(() => {
    void load();
  }, []);

  const holdingsData = useMemo(() => {
    const gainers = (portfolio?.top_gainers || []) as Array<Record<string, unknown>>;
    if (gainers.length > 0) {
      return gainers.map((item) => ({
        name: String(item.symbol || "Unknown"),
        value: Number(item.current_value || 0),
      }));
    }

    const grouped = trades.reduce<Record<string, number>>((acc, trade) => {
      acc[trade.symbol] = (acc[trade.symbol] || 0) + Number(trade.total_value || 0);
      return acc;
    }, {});

    return Object.entries(grouped).map(([name, value]) => ({ name, value }));
  }, [portfolio, trades]);

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
      <header>
        <h1 className="text-2xl font-bold">Trading Dashboard</h1>
        <p className="text-sm text-[rgb(var(--text-dim))]">Watchlist, portfolio analytics, and trade intelligence.</p>
      </header>

      <section className="grid gap-4 lg:grid-cols-3">
        <article className="card p-4 lg:col-span-2">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-lg font-semibold">Watchlist</h2>
            <div className="flex items-center gap-2">
              <input
                value={symbol}
                onChange={(event) => setSymbol(event.target.value.toUpperCase())}
                placeholder="INFY"
                className="w-28 rounded-lg border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-2 py-1 text-sm"
              />
              <input
                value={exchange}
                onChange={(event) => setExchange(event.target.value.toUpperCase())}
                className="w-20 rounded-lg border border-[rgb(var(--border))] bg-[rgb(var(--bg-muted))] px-2 py-1 text-sm"
              />
              <button
                type="button"
                onClick={() => void onAddWatchlist()}
                className="inline-flex items-center gap-1 rounded-lg bg-[rgb(var(--primary))] px-2 py-1 text-xs font-semibold text-white"
              >
                <Plus className="h-3.5 w-3.5" /> Add
              </button>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[540px] text-left text-sm">
              <thead>
                <tr className="text-xs uppercase text-[rgb(var(--text-dim))]">
                  <th className="pb-2">Symbol</th>
                  <th className="pb-2">Exchange</th>
                  <th className="pb-2">Above</th>
                  <th className="pb-2">Below</th>
                  <th className="pb-2">Actions</th>
                </tr>
              </thead>
              <tbody>
                {watchlist.map((row) => (
                  <tr key={String(row.id)} className="border-t border-[rgb(var(--border))]">
                    <td className="py-2 data-font">{String(row.symbol)}</td>
                    <td className="py-2">{String(row.exchange)}</td>
                    <td className="py-2">{String(row.alert_price_above ?? "-")}</td>
                    <td className="py-2">{String(row.alert_price_below ?? "-")}</td>
                    <td className="py-2">
                      <button
                        type="button"
                        onClick={() => void api.trading.removeWatchlist(String(row.id)).then(load)}
                        className="rounded-lg border border-[rgb(var(--danger))]/40 p-1.5 text-[rgb(var(--danger))]"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </article>

        <article className="card p-4">
          <h2 className="text-lg font-semibold">Portfolio</h2>
          <p className="mt-2 data-font text-2xl font-bold">₹{(portfolio?.current_value ?? 0).toLocaleString()}</p>
          <p className={`text-sm ${(portfolio?.daily_pnl ?? 0) >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
            Daily P&L: ₹{(portfolio?.daily_pnl ?? 0).toLocaleString()}
          </p>

          <div className="mt-4 h-52">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={holdingsData} dataKey="value" nameKey="name" innerRadius={45} outerRadius={80}>
                  {holdingsData.map((entry, index) => (
                    <Cell key={entry.name} fill={PIE_COLORS[index % PIE_COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </article>
      </section>

      <section className="card p-4">
        <h2 className="mb-3 text-lg font-semibold">Trade log</h2>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[680px] text-left text-sm">
            <thead>
              <tr className="text-xs uppercase text-[rgb(var(--text-dim))]">
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
                <tr key={trade.id} className="border-t border-[rgb(var(--border))]">
                  <td className="py-2">{trade.trade_date}</td>
                  <td className="py-2 data-font">{trade.symbol}</td>
                  <td className="py-2">{trade.action}</td>
                  <td className="py-2">{trade.quantity}</td>
                  <td className="py-2">{trade.price}</td>
                  <td className="py-2">{trade.total_value}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="card p-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold">AI analysis</h2>
          <button
            type="button"
            onClick={() => void onAnalyze()}
            className="inline-flex items-center gap-2 rounded-xl bg-[rgb(var(--primary))] px-3 py-2 text-sm font-semibold text-white"
          >
            <BrainCog className="h-4 w-4" /> Generate
          </button>
        </div>
        <pre className="mt-3 overflow-x-auto rounded-xl bg-[rgb(var(--bg-muted))] p-3 text-xs text-[rgb(var(--text-dim))]">
          {analysis ? JSON.stringify(analysis, null, 2) : "No analysis yet."}
        </pre>
      </section>
    </div>
  );
}
