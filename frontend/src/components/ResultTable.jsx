import React, { useState, useMemo } from 'react';
import {
  Table2, Search, Download, ArrowUpDown, ArrowUp, ArrowDown
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

/**
 * ResultTable — Data table with sorting, search, CSV export, and row count footer.
 */
export default function ResultTable({ columns, rows, rowCount }) {
  const [sortCol, setSortCol] = useState(null);
  const [sortDir, setSortDir] = useState('asc');
  const [search, setSearch] = useState('');

  if (!columns || !rows || rows.length === 0) return null;

  const handleSort = (col) => {
    if (sortCol === col) {
      setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortCol(col);
      setSortDir('asc');
    }
  };

  // Filter rows
  const filteredRows = useMemo(() => {
    if (!search.trim()) return rows;
    const q = search.toLowerCase();
    return rows.filter((row) =>
      columns.some((col) => String(row[col] ?? '').toLowerCase().includes(q))
    );
  }, [rows, columns, search]);

  // Sort rows
  const sortedRows = useMemo(() => {
    if (!sortCol) return filteredRows;
    return [...filteredRows].sort((a, b) => {
      const va = a[sortCol];
      const vb = b[sortCol];
      if (va == null && vb == null) return 0;
      if (va == null) return 1;
      if (vb == null) return -1;
      if (typeof va === 'number' && typeof vb === 'number') {
        return sortDir === 'asc' ? va - vb : vb - va;
      }
      const sa = String(va).toLowerCase();
      const sb = String(vb).toLowerCase();
      if (sa < sb) return sortDir === 'asc' ? -1 : 1;
      if (sa > sb) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });
  }, [filteredRows, sortCol, sortDir]);

  const exportCSV = () => {
    const header = columns.join(',');
    const body = sortedRows.map((row) =>
      columns.map((col) => {
        const v = row[col];
        if (v == null) return '';
        const s = String(v);
        return s.includes(',') || s.includes('"') || s.includes('\n')
          ? `"${s.replace(/"/g, '""')}"`
          : s;
      }).join(',')
    ).join('\n');
    const csv = `${header}\n${body}`;
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'query_results.csv';
    a.click();
    URL.revokeObjectURL(url);
  };

  const showPercent = Math.min(100, Math.round((rows.length / Math.max(rowCount, 1)) * 100));

  return (
    <motion.div 
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      className="response-section"
    >
      <div className="response-section-header">
        <Table2 size={14} className="section-icon" />
        Results
      </div>

      {/* Toolbar */}
      <div className="result-table-toolbar">
        <motion.div 
          initial={{ opacity: 0, x: -10 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ delay: 0.1 }}
          className="table-search-wrapper"
        >
          <Search size={12} className="search-icon" />
          <input
            className="table-search-input"
            type="text"
            placeholder="Filter results..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </motion.div>
        <motion.button 
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          className="table-action-btn" 
          onClick={exportCSV} 
          title="Export as CSV"
        >
          <Download size={12} />
          Export
        </motion.button>
      </div>

      {/* Table */}
      <div className="result-table-wrapper">
        <table className="result-table" id="result-table">
          <thead>
            <tr>
              {columns.map((col) => (
                <th key={col} onClick={() => handleSort(col)}>
                  <div className="th-content">
                    {col}
                    {sortCol === col ? (
                      sortDir === 'asc'
                        ? <ArrowUp size={12} className="sort-icon active" />
                        : <ArrowDown size={12} className="sort-icon active" />
                    ) : (
                      <ArrowUpDown size={12} className="sort-icon" />
                    )}
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <AnimatePresence mode="popLayout">
              {sortedRows.map((row, idx) => (
                <motion.tr 
                  layout
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  key={idx}
                >
                  {columns.map((col) => (
                    <td key={col} title={String(row[col] ?? '')} className={getCellClass(row[col])}>
                      {formatValue(row[col])}
                    </td>
                  ))}
                </motion.tr>
              ))}
            </AnimatePresence>
          </tbody>
        </table>
      </div>

      {/* Footer */}
      <div className="table-footer">
        <div className="table-row-count">
          Showing {sortedRows.length} of {rowCount.toLocaleString()} row{rowCount !== 1 ? 's' : ''}
          <div className="row-count-bar">
            <motion.div 
              initial={{ width: 0 }}
              animate={{ width: `${showPercent}%` }}
              transition={{ duration: 1, ease: "easeOut" }}
              className="row-count-bar-fill" 
            />
          </div>
        </div>
      </div>
    </motion.div>
  );
}

function getCellClass(val) {
  if (val === null || val === undefined) return 'cell-null';
  if (typeof val === 'number') return 'cell-number';
  return '';
}

function formatValue(val) {
  if (val === null || val === undefined) return 'null';
  if (typeof val === 'number') {
    if (Number.isInteger(val)) return val.toLocaleString();
    return val.toLocaleString(undefined, { maximumFractionDigits: 4 });
  }
  const str = String(val);
  if (str.length > 80) return str.substring(0, 77) + '...';
  return str;
}
