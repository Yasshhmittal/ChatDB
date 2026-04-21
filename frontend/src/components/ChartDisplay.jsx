import React, { useState, useRef, useCallback } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  RadialLinearScale,
  Title,
  Tooltip,
  Legend,
  Filler,
} from 'chart.js';
import { Bar, Line, Pie, Scatter, Doughnut, PolarArea } from 'react-chartjs-2';
import {
  BarChart3, LineChart, PieChart, ScatterChart,
  CircleDot, Target,
  Maximize2, Minimize2, Download, TrendingUp
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  RadialLinearScale,
  Title,
  Tooltip,
  Legend,
  Filler
);

const CHART_TYPES = [
  { key: 'bar', label: 'Bar', Icon: BarChart3 },
  { key: 'line', label: 'Line', Icon: LineChart },
  { key: 'scatter', label: 'Scatter', Icon: ScatterChart },
  { key: 'pie', label: 'Pie', Icon: PieChart },
  { key: 'doughnut', label: 'Donut', Icon: CircleDot },
  { key: 'polarArea', label: 'Polar', Icon: Target },
];

/**
 * ChartDisplay — Auto-renders charts with pill type selector, fullscreen, and download.
 */
export default function ChartDisplay({ config }) {
  const [chartTypeOverride, setChartTypeOverride] = useState(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const chartRef = useRef(null);

  if (!config || !config.datasets || config.datasets.length === 0) return null;

  const activeChartType = chartTypeOverride || config.chart_type;
  const isMultiColor = ['pie', 'doughnut', 'polarArea'].includes(activeChartType);

  const generateColor = (index, total) => {
    const hue = (index * (360 / Math.max(total, 1))) % 360;
    const sat = 72 + (index % 2) * 12;
    const lit = 58 + (index % 3) * 5;
    return `hsla(${hue}, ${sat}%, ${lit}%, 0.85)`;
  };

  const processedDatasets = config.datasets.map((ds, i) => {
    let mappedData = ds.data;

    if (activeChartType === 'scatter' && mappedData.length > 0) {
      if (typeof mappedData[0] === 'object' && !('x' in mappedData[0])) {
        mappedData = mappedData.map((obj, idx) => ({ x: idx, y: obj.value || 0 }));
      } else if (typeof mappedData[0] !== 'object') {
        mappedData = mappedData.map((val, idx) => ({ x: idx, y: Number(val) || 0 }));
      }
    } else if (!['scatter'].includes(activeChartType) && mappedData.length > 0) {
      if (typeof mappedData[0] === 'object' && 'value' in mappedData[0]) {
        mappedData = mappedData.map((d) => Number(d.value) || 0);
      }
    }

    if (isMultiColor) {
      const len = mappedData.length;
      return {
        ...ds,
        data: mappedData,
        backgroundColor: mappedData.map((_, j) => generateColor(j, len)),
        borderColor: '#0a0e1a',
        borderWidth: 2,
        hoverOffset: 6,
      };
    }

    const hue = (i * 55 + 240) % 360;
    const baseColor = `hsla(${hue}, 75%, 62%, 0.8)`;
    const baseBorderColor = `hsla(${hue}, 75%, 62%, 1)`;
    return {
      ...ds,
      data: mappedData,
      backgroundColor: baseColor,
      borderColor: baseBorderColor,
      borderWidth: 2,
      pointBackgroundColor: baseBorderColor,
      pointRadius: 3.5,
      tension: 0.3,
    };
  });

  const chartData = {
    labels: config.labels || [],
    datasets: processedDatasets,
  };

  const commonOptions = {
    responsive: true,
    maintainAspectRatio: false,
    cutout: activeChartType === 'doughnut' ? '65%' : undefined,
    plugins: {
      legend: {
        position: isMultiColor ? 'right' : 'top',
        labels: {
          color: '#e2e8f0',
          font: { family: 'Inter', size: 11, weight: '500' },
          usePointStyle: true,
          padding: 16,
          boxWidth: 8,
        },
      },
      tooltip: {
        backgroundColor: 'rgba(15, 23, 42, 0.95)',
        titleFont: { family: 'Inter', size: 13 },
        bodyFont: { family: 'Inter', size: 12 },
        borderColor: 'rgba(99, 102, 241, 0.2)',
        borderWidth: 1,
        padding: 10,
        cornerRadius: 8,
      },
    },
    scales: ['pie', 'doughnut', 'polarArea'].includes(activeChartType) ? undefined : {
      x: {
        ticks: { color: '#64748b', font: { family: 'Inter', size: 11 } },
        grid: { color: 'rgba(148, 163, 184, 0.05)' },
        title: {
          display: !!config.x_label,
          text: config.x_label,
          color: '#94a3b8',
          font: { family: 'Inter', size: 12 },
        },
      },
      y: {
        ticks: { color: '#64748b', font: { family: 'Inter', size: 11 } },
        grid: { color: 'rgba(148, 163, 184, 0.05)' },
        title: {
          display: !!config.y_label,
          text: config.y_label,
          color: '#94a3b8',
          font: { family: 'Inter', size: 12 },
        },
      },
    },
    animation: {
      duration: 600,
      easing: 'easeOutQuart',
    },
  };

  const ChartComponent = {
    bar: Bar,
    line: Line,
    pie: Pie,
    scatter: Scatter,
    doughnut: Doughnut,
    polarArea: PolarArea,
  }[activeChartType] || Bar;

  const downloadChart = useCallback(() => {
    const chart = chartRef.current;
    if (!chart) return;
    const url = chart.toBase64Image();
    const a = document.createElement('a');
    a.href = url;
    a.download = 'chart.png';
    a.click();
  }, []);

  const chartElement = (
    <ChartComponent
      ref={chartRef}
      data={chartData}
      options={commonOptions}
    />
  );

  return (
    <>
      <AnimatePresence>
        {isFullscreen && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="chart-fullscreen-overlay"
          >
            <div className="chart-fullscreen-header">
              <motion.button
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                className="chart-action-btn exit-btn"
                onClick={() => setIsFullscreen(false)}
              >
                <Minimize2 size={16} />
                <span>Exit Fullscreen</span>
              </motion.button>
            </div>
            <motion.div 
              initial={{ scale: 0.9, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0.9, opacity: 0 }}
              transition={{ type: 'spring', damping: 25, stiffness: 200 }}
              className="chart-fullscreen-body"
            >
              {chartElement}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      <motion.div 
        initial={{ opacity: 0, scale: 0.98 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4 }}
        className="response-section"
      >
        <div className="response-section-header">
          <div className="chart-controls">
            <div className="chart-type-pills">
              {CHART_TYPES.map(({ key, label, Icon }) => (
                <motion.button
                  whileHover={{ y: -2 }}
                  whileTap={{ y: 0 }}
                  key={key}
                  className={`chart-pill ${activeChartType === key ? 'active' : ''}`}
                  onClick={() => setChartTypeOverride(key)}
                >
                  <Icon size={12} />
                  {label}
                </motion.button>
              ))}
            </div>
            <div className="chart-actions">
              <button className="chart-action-btn" onClick={() => setIsFullscreen(true)} title="Fullscreen">
                <Maximize2 size={13} />
              </button>
              <button className="chart-action-btn" onClick={downloadChart} title="Download as PNG">
                <Download size={13} />
              </button>
            </div>
          </div>
        </div>
        <div className="chart-container" style={{ minHeight: '340px' }}>
          <AnimatePresence mode="wait">
            <motion.div
              key={activeChartType}
              initial={{ opacity: 0, scale: 0.98 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 1.02 }}
              transition={{ duration: 0.2 }}
              className="chart-animation-wrapper"
              style={{ width: '100%', height: '100%' }}
            >
              {chartElement}
            </motion.div>
          </AnimatePresence>
        </div>
      </motion.div>
    </>
  );
}
