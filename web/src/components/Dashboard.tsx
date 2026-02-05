import { useState, useEffect, useCallback } from 'react';
import type { Account, Position, Trade, Candle, StrategyStatus, WsMessage } from '../types';
import { api } from '../api/client';
import { useWebSocket } from '../hooks/useWebSocket';
import AccountInfo from './AccountInfo';
import PriceChart from './PriceChart';
import PnLPanel from './PnLPanel';
import PositionsTable from './PositionsTable';
import TradeHistory from './TradeHistory';
import StrategyControls from './StrategyControls';

const DEFAULT_ACCOUNT: Account = {
  balance: 0,
  equity: 0,
  open_positions: 0,
  total_pnl: 0,
};

const DEFAULT_STATUS: StrategyStatus = {
  running: false,
  strategy: '',
  symbol: '',
  timeframe: '',
  broker: '',
};

const POLL_INTERVAL = 5000;

export default function Dashboard() {
  const [account, setAccount] = useState<Account>(DEFAULT_ACCOUNT);
  const [positions, setPositions] = useState<Position[]>([]);
  const [trades, setTrades] = useState<Trade[]>([]);
  const [candles, setCandles] = useState<Candle[]>([]);
  const [status, setStatus] = useState<StrategyStatus>(DEFAULT_STATUS);

  const fetchAll = useCallback(async () => {
    try {
      const [acct, pos, trd, cndl, stat] = await Promise.allSettled([
        api.getAccount(),
        api.getPositions(),
        api.getTrades(),
        api.getCandles(),
        api.getStrategyStatus(),
      ]);

      if (acct.status === 'fulfilled') setAccount(acct.value);
      if (pos.status === 'fulfilled') setPositions(pos.value);
      if (trd.status === 'fulfilled') setTrades(trd.value);
      if (cndl.status === 'fulfilled') setCandles(cndl.value);
      if (stat.status === 'fulfilled') setStatus(stat.value);
    } catch {
      // silently ignore fetch errors during polling
    }
  }, []);

  // Initial load and periodic polling
  useEffect(() => {
    fetchAll();
    const interval = setInterval(fetchAll, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchAll]);

  // WebSocket handler for real-time updates
  const handleWsMessage = useCallback((msg: WsMessage) => {
    switch (msg.type) {
      case 'account_update':
        if (msg.data.account) setAccount(msg.data.account);
        if (msg.data.positions) setPositions(msg.data.positions);
        break;
      case 'tick':
        // tick events handled by periodic polling
        break;
      case 'candle_closed':
        setCandles((prev) => {
          const updated = [...prev, msg.data];
          if (updated.length > 500) updated.shift();
          return updated;
        });
        break;
      case 'order_filled':
      case 'position_closed':
        // Trigger a refresh to get updated positions/trades
        fetchAll();
        break;
      case 'engine_started':
      case 'engine_stopped':
        fetchAll();
        break;
      default:
        break;
    }
  }, [fetchAll]);

  const { connected } = useWebSocket(handleWsMessage);

  return (
    <div className="dashboard">
      <header className="dashboard-header">
        <h1>Forex Scalper</h1>
        <div className="connection-status">
          <span
            className="status-dot"
            style={{ backgroundColor: connected ? 'var(--green)' : 'var(--red)' }}
          />
          {connected ? 'Connected' : 'Disconnected'}
        </div>
      </header>

      <div className="dashboard-grid">
        <div className="grid-top-left">
          <AccountInfo account={account} />
        </div>
        <div className="grid-top-right">
          <StrategyControls status={status} onStatusChange={fetchAll} />
        </div>
        <div className="grid-middle">
          <PriceChart candles={candles} trades={trades} />
        </div>
        <div className="grid-bottom-left">
          <PositionsTable positions={positions} onPositionClosed={fetchAll} />
        </div>
        <div className="grid-bottom-center">
          <TradeHistory trades={trades} />
        </div>
        <div className="grid-bottom-right">
          <PnLPanel trades={trades} />
        </div>
      </div>
    </div>
  );
}
