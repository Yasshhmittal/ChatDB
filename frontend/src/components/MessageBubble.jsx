import React from 'react';
import { AlertCircle, Lightbulb, RefreshCw, CheckCircle2, Download, Trash2, PenLine, PlusCircle, Table } from 'lucide-react';
import LogoIcon from './LogoIcon';
import SqlDisplay from './SqlDisplay';
import ResultTable from './ResultTable';
import ChartDisplay from './ChartDisplay';
import { getOriginalDownloadUrl, getModifiedDownloadUrl } from '../api/client';

import { motion } from 'framer-motion';

/**
 * Map query types to human-friendly labels, icons, and colors.
 */
const QUERY_TYPE_CONFIG = {
  INSERT: { label: 'Inserted', icon: PlusCircle, color: '#34d399' },
  UPDATE: { label: 'Updated', icon: PenLine, color: '#60a5fa' },
  DELETE: { label: 'Deleted', icon: Trash2, color: '#f87171' },
  CREATE: { label: 'Created', icon: Table, color: '#a78bfa' },
  DROP:   { label: 'Dropped', icon: Trash2, color: '#fb923c' },
  ALTER:  { label: 'Altered', icon: PenLine, color: '#facc15' },
  TRUNCATE: { label: 'Truncated', icon: Trash2, color: '#fb923c' },
};

/**
 * MessageBubble — Renders a single chat message (user or assistant).
 * Shows avatar, timestamp, and content sections.
 */
export default function MessageBubble({ message, user, sessionId }) {
  const formatTime = (ts) => {
    if (!ts) return '';
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  };

  if (message.role === 'user') {
    return (
      <motion.div 
        initial={{ opacity: 0, scale: 0.9, x: 20 }}
        animate={{ opacity: 1, scale: 1, x: 0 }}
        transition={{ type: 'spring', damping: 20, stiffness: 150 }}
        className="message message-user"
      >
        <div className="message-content">{message.content}</div>
        <div className="user-avatar">{user?.avatar || 'U'}</div>
      </motion.div>
    );
  }

  // Assistant message
  const data = message.data || {};
  const { sql_query, results, columns, row_count, explanation, chart, error, retries_used, query_type, affected_rows } = data;

  const isWriteOp = query_type && query_type !== 'SELECT' && !error;
  const typeConfig = QUERY_TYPE_CONFIG[query_type] || null;

  return (
    <motion.div 
      initial={{ opacity: 0, scale: 0.9, x: -20 }}
      animate={{ opacity: 1, scale: 1, x: 0 }}
      transition={{ type: 'spring', damping: 20, stiffness: 150 }}
      className="message message-assistant"
    >
      <div className="message-assistant-header">
        <div className="assistant-avatar">
          <LogoIcon size={14} />
        </div>
        <span className="assistant-label">ChatDB</span>
        <span className="message-timestamp">{formatTime(message.timestamp)}</span>
      </div>

      {/* Error (standalone) */}
      {error && !sql_query && (
        <div className="response-section">
          <div className="error-section">
            <AlertCircle size={16} className="error-section-icon" />
            <span>{error}</span>
          </div>
        </div>
      )}

      {/* SQL Query */}
      {sql_query && (
        <SqlDisplay sql={sql_query} />
      )}

      {/* Write Operation Result */}
      {isWriteOp && typeConfig && (
        <motion.div
          initial={{ opacity: 0, y: 15 }}
          animate={{ opacity: 1, y: 0 }}
          className="response-section"
        >
          <div className="write-result-card" style={{ borderColor: typeConfig.color + '40' }}>
            <div className="write-result-header">
              <div className="write-result-icon" style={{ backgroundColor: typeConfig.color + '20', color: typeConfig.color }}>
                <CheckCircle2 size={18} />
              </div>
              <div className="write-result-info">
                <span className="write-result-label" style={{ color: typeConfig.color }}>
                  {typeConfig.label} Successfully
                </span>
                {affected_rows > 0 && (
                  <span className="write-result-count">
                    {affected_rows} row{affected_rows !== 1 ? 's' : ''} affected
                  </span>
                )}
              </div>
            </div>
            <div className="write-result-notice">
              <span>🔒 Original data preserved — changes applied to a copy</span>
            </div>
            {sessionId && (
              <div className="write-result-downloads">
                <a
                  href={getModifiedDownloadUrl(sessionId)}
                  download
                  className="download-btn download-btn-modified"
                >
                  <Download size={14} />
                  Download Modified CSV
                </a>
                <a
                  href={getOriginalDownloadUrl(sessionId)}
                  download
                  className="download-btn download-btn-original"
                >
                  <Download size={14} />
                  Download Original CSV
                </a>
              </div>
            )}
          </div>
        </motion.div>
      )}

      {/* Results Table */}
      {results && results.length > 0 && (
        <ResultTable columns={columns} rows={results} rowCount={row_count} />
      )}

      {/* Chart */}
      {chart && chart.chart_type !== 'none' && results && results.length > 0 && (
        <ChartDisplay config={chart} />
      )}

      {/* Explanation */}
      {(explanation || (error && sql_query)) && (
        <div className="response-section">
          <div className="response-section-header">
            <Lightbulb size={14} className="section-icon" />
            Explanation
          </div>
          <div className="explanation-section">
            {explanation || ''}
            {error && sql_query && (
              <div style={{ marginTop: 8, color: '#fca5a5' }}>
                <AlertCircle size={14} style={{ display: 'inline', verticalAlign: '-2px', marginRight: 4 }} />
                {error}
              </div>
            )}
            {retries_used > 0 && (
              <span className="retry-badge">
                <RefreshCw size={12} />
                {retries_used} correction{retries_used > 1 ? 's' : ''}
              </span>
            )}
          </div>
        </div>
      )}
    </motion.div>
  );
}
