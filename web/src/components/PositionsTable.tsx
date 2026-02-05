import { useState } from 'react';
import type { Position } from '../types';
import { api } from '../api/client';

interface Props {
  positions: Position[];
  onPositionClosed: () => void;
}

export default function PositionsTable({ positions, onPositionClosed }: Props) {
  const [closingId, setClosingId] = useState<string | null>(null);

  const handleClose = async (orderId: string) => {
    setClosingId(orderId);
    try {
      await api.closePosition(orderId);
      onPositionClosed();
    } catch (err) {
      console.error('Failed to close position:', err);
    } finally {
      setClosingId(null);
    }
  };

  return (
    <div className="card positions-table">
      <h2 className="card-title">Open Positions</h2>
      <div className="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Order ID</th>
              <th>Symbol</th>
              <th>Side</th>
              <th>Entry Price</th>
              <th>Volume</th>
              <th>SL</th>
              <th>TP</th>
              <th>Unrealized P&L</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {positions.length === 0 ? (
              <tr>
                <td colSpan={9} className="empty-row">
                  No open positions
                </td>
              </tr>
            ) : (
              positions.map((pos) => (
                <tr key={pos.order_id}>
                  <td className="mono">{pos.order_id.slice(0, 8)}</td>
                  <td>{pos.symbol}</td>
                  <td className={pos.side === 'buy' ? 'text-green' : 'text-red'}>
                    {pos.side.toUpperCase()}
                  </td>
                  <td className="mono">{pos.entry_price.toFixed(5)}</td>
                  <td className="mono">{pos.volume.toFixed(2)}</td>
                  <td className="mono">{pos.sl.toFixed(5)}</td>
                  <td className="mono">{pos.tp.toFixed(5)}</td>
                  <td
                    className="mono"
                    style={{
                      color: pos.unrealized_pnl >= 0 ? 'var(--green)' : 'var(--red)',
                    }}
                  >
                    {pos.unrealized_pnl >= 0 ? '+' : ''}
                    {pos.unrealized_pnl.toFixed(2)}
                  </td>
                  <td>
                    <button
                      className="btn btn-danger btn-sm"
                      onClick={() => handleClose(pos.order_id)}
                      disabled={closingId === pos.order_id}
                    >
                      {closingId === pos.order_id ? 'Closing...' : 'Close'}
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
