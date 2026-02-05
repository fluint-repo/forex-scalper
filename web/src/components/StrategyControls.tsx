import { useState, useEffect } from 'react';
import type { StrategyStatus } from '../types';
import { api } from '../api/client';

interface Props {
  status: StrategyStatus;
  onStatusChange: () => void;
}

const STRATEGIES = ['ema_crossover', 'bb_reversion'];
const SYMBOLS = ['EURUSD=X', 'GBPUSD=X', 'USDJPY=X'];
const TIMEFRAMES = ['1m', '5m', '15m', '1h', '4h', '1d'];
const BROKERS = ['paper', 'oanda'];

export default function StrategyControls({ status, onStatusChange }: Props) {
  const [strategy, setStrategy] = useState(STRATEGIES[0]);
  const [symbol, setSymbol] = useState(SYMBOLS[0]);
  const [timeframe, setTimeframe] = useState(TIMEFRAMES[1]);
  const [broker, setBroker] = useState(BROKERS[0]);
  const [capital, setCapital] = useState('10000');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (status.running) {
      setStrategy(status.strategy || STRATEGIES[0]);
      setSymbol(status.symbol || SYMBOLS[0]);
      setTimeframe(status.timeframe || TIMEFRAMES[1]);
      setBroker(status.broker || BROKERS[0]);
    }
  }, [status]);

  const handleStart = async () => {
    setLoading(true);
    setError(null);
    try {
      await api.startStrategy({
        strategy,
        symbol,
        timeframe,
        broker,
        capital: parseFloat(capital),
      });
      onStatusChange();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start strategy');
    } finally {
      setLoading(false);
    }
  };

  const handleStop = async () => {
    setLoading(true);
    setError(null);
    try {
      await api.stopStrategy();
      onStatusChange();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to stop strategy');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card strategy-controls">
      <h2 className="card-title">Strategy Controls</h2>

      <div className="controls-grid">
        <div className="control-group">
          <label htmlFor="strategy-select">Strategy</label>
          <select
            id="strategy-select"
            value={strategy}
            onChange={(e) => setStrategy(e.target.value)}
            disabled={status.running}
          >
            {STRATEGIES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        <div className="control-group">
          <label htmlFor="symbol-select">Symbol</label>
          <select
            id="symbol-select"
            value={symbol}
            onChange={(e) => setSymbol(e.target.value)}
            disabled={status.running}
          >
            {SYMBOLS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </div>

        <div className="control-group">
          <label htmlFor="timeframe-select">Timeframe</label>
          <select
            id="timeframe-select"
            value={timeframe}
            onChange={(e) => setTimeframe(e.target.value)}
            disabled={status.running}
          >
            {TIMEFRAMES.map((tf) => (
              <option key={tf} value={tf}>
                {tf}
              </option>
            ))}
          </select>
        </div>

        <div className="control-group">
          <label htmlFor="broker-select">Broker</label>
          <select
            id="broker-select"
            value={broker}
            onChange={(e) => setBroker(e.target.value)}
            disabled={status.running}
          >
            {BROKERS.map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </select>
        </div>

        <div className="control-group">
          <label htmlFor="capital-input">Capital ($)</label>
          <input
            id="capital-input"
            type="number"
            value={capital}
            onChange={(e) => setCapital(e.target.value)}
            disabled={status.running}
            min="100"
            step="100"
          />
        </div>

        <div className="control-group control-action">
          {status.running ? (
            <button
              className="btn btn-danger btn-lg"
              onClick={handleStop}
              disabled={loading}
            >
              {loading ? 'Stopping...' : 'Stop Strategy'}
            </button>
          ) : (
            <button
              className="btn btn-primary btn-lg"
              onClick={handleStart}
              disabled={loading}
            >
              {loading ? 'Starting...' : 'Start Strategy'}
            </button>
          )}
        </div>
      </div>

      {status.running && (
        <div className="status-bar">
          Running: <strong>{status.strategy}</strong> on <strong>{status.symbol}</strong> ({status.timeframe}) via{' '}
          <strong>{status.broker}</strong>
        </div>
      )}

      {error && <div className="error-bar">{error}</div>}
    </div>
  );
}
