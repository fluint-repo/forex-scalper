import { useEffect, useRef } from 'react';
import { createChart, LineSeries, type IChartApi, type LineData, type Time } from 'lightweight-charts';
import type { Trade } from '../types';

interface Props {
  trades: Trade[];
}

export default function PnLPanel({ trades }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const seriesRef = useRef<any>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      width: containerRef.current.clientWidth,
      height: 250,
      layout: {
        background: { color: '#16213e' },
        textColor: '#e0e0e0',
      },
      grid: {
        vertLines: { color: '#1a1a2e' },
        horzLines: { color: '#1a1a2e' },
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

    const series = chart.addSeries(LineSeries, {
      color: '#4fc3f7',
      lineWidth: 2,
      crosshairMarkerVisible: true,
      crosshairMarkerRadius: 4,
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
    if (!seriesRef.current) return;

    if (trades.length === 0) {
      seriesRef.current.setData([]);
      return;
    }

    // Build cumulative P&L from closed trades sorted by exit_time
    const sorted = [...trades].sort(
      (a, b) => new Date(a.exit_time).getTime() - new Date(b.exit_time).getTime()
    );

    let cumPnl = 0;
    const data: LineData<Time>[] = sorted.map((t) => {
      cumPnl += t.pnl;
      return {
        time: (Math.floor(new Date(t.exit_time).getTime() / 1000)) as Time,
        value: cumPnl,
      };
    });

    seriesRef.current.setData(data);

    // Color the line based on final P&L
    const finalColor = cumPnl >= 0 ? '#00c853' : '#ff1744';
    seriesRef.current.applyOptions({ color: finalColor });

    chartRef.current?.timeScale().fitContent();
  }, [trades]);

  return (
    <div className="card pnl-panel">
      <h2 className="card-title">Equity Curve</h2>
      <div ref={containerRef} className="chart-container" />
    </div>
  );
}
