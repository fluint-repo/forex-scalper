import type { Account } from '../types';

interface Props {
  account: Account;
}

export default function AccountInfo({ account }: Props) {
  const pnlColor = account.total_pnl >= 0 ? 'var(--green)' : 'var(--red)';

  return (
    <div className="card account-info">
      <h2 className="card-title">Account</h2>
      <div className="stats-grid">
        <div className="stat-card">
          <span className="stat-label">Balance</span>
          <span className="stat-value mono">
            ${account.balance.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Equity</span>
          <span className="stat-value mono">
            ${account.equity.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Total P&L</span>
          <span className="stat-value mono" style={{ color: pnlColor }}>
            {account.total_pnl >= 0 ? '+' : ''}
            ${account.total_pnl.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </span>
        </div>
        <div className="stat-card">
          <span className="stat-label">Open Positions</span>
          <span className="stat-value mono">{account.open_positions}</span>
        </div>
      </div>
    </div>
  );
}
