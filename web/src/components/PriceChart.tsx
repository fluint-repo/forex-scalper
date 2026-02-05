import { useEffect, useRef } from 'react';
import { createChart, CandlestickSeries, type IChartApi, type CandlestickData, type Time } from 'lightweight-charts';
import type { Candle, Trade } from '../types';

interface Props {
  candles: Candle[];
  trades?: Trade[];
}

function toUnixTime(ts: string): Time {
  return Math.floor(new Date(ts).getTime() / 1000) as Time;
}

export default function PriceChart({ candles, trades }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const seriesRef = useRef<any>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 400,
      layout: {
        background: { color: '#16213e' },
        textColor: '#e0e0e0',
      },
      grid: {
        vertLines: { color: '#1a1a2e' },
        horzLines: { color: '#1a1a2e' },
      },
      crosshair: {
        mode: 0,
      },
      timeScale: {
        borderColor: '#0f3460',
        timeVisible: true,
        secondsVisible: false,
      },
      rightPriceScale: {
        borderColor: '#0f3460',
      },
    });

    const series = chart.addSeries(CandlestickSeries, {
      upColor: '#00c853',
      downColor: '#ff1744',
      borderDownColor: '#ff1744',
      borderUpColor: '#00c853',
      wickDownColor: '#ff1744',
      wickUpColor: '#00c853',
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener('resize', handleResize);

    return () => {
      window.removeEventListener('resize', handleResize);
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!seriesRef.current || candles.length === 0) return;

    const data: CandlestickData<Time>[] = candles.map((c) => ({
      time: toUnixTime(c.timestamp),
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));

    seriesRef.current.setData(data);

    if (trades && trades.length > 0) {
      const markers = trades.map((t) => ({
        time: toUnixTime(t.entry_time),
        position: t.side.toUpperCase() === 'BUY' ? ('belowBar' as const) : ('aboveBar' as const),
        color: t.pnl >= 0 ? '#00c853' : '#ff1744',
        shape: t.side.toUpperCase() === 'BUY' ? ('arrowUp' as const) : ('arrowDown' as const),
        text: `${t.side.toUpperCase()} ${t.pnl >= 0 ? '+' : ''}${t.pnl.toFixed(2)}`,
      }));

      markers.sort((a, b) => (a.time as number) - (b.time as number));
      seriesRef.current.setMarkers(markers);
    }

    chartRef.current?.timeScale().fitContent();
  }, [candles, trades]);

  return (
    <div className="card price-chart">
      <h2 className="card-title">Price Chart</h2>
      <div ref={containerRef} className="chart-container" />
    </div>
  );
}
