export interface Account {
  balance: number;
  equity: number;
  open_positions: number;
  total_pnl: number;
  margin_used?: number;
  margin_available?: number;
}

export interface Position {
  order_id: string;
  symbol: string;
  side: string;
  entry_price: number;
  volume: number;
  sl: number;
  tp: number;
  entry_time: string;
  unrealized_pnl: number;
}

export interface Trade {
  strategy_name: string;
  symbol: string;
  timeframe: string;
  side: string;
  entry_time: string;
  exit_time: string;
  entry_price: number;
  exit_price: number;
  volume: number;
  pnl: number;
  sl: number;
  tp: number;
  exit_reason: string;
}

export interface Candle {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface StrategyStatus {
  running: boolean;
  strategy: string;
  symbol: string;
  timeframe: string;
  broker: string;
}

export interface WsMessage {
  type: string;
  data: any;
}
