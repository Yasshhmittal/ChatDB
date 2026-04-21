import React, { useState, useCallback, useMemo } from 'react';
import { Code, Copy, Check } from 'lucide-react';

/**
 * SqlDisplay — Shows generated SQL with line numbers, syntax highlighting, and copy button.
 */

const SQL_KEYWORDS = [
  'SELECT', 'FROM', 'WHERE', 'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER',
  'ON', 'AND', 'OR', 'NOT', 'IN', 'AS', 'ORDER', 'BY', 'GROUP', 'HAVING',
  'LIMIT', 'OFFSET', 'DISTINCT', 'LIKE', 'BETWEEN', 'IS', 'NULL',
  'CASE', 'WHEN', 'THEN', 'ELSE', 'END', 'UNION', 'ALL', 'EXISTS',
  'DESC', 'ASC', 'CAST', 'COALESCE', 'INSERT', 'INTO', 'VALUES',
  'UPDATE', 'SET', 'DELETE', 'CREATE', 'TABLE', 'DROP', 'ALTER',
  'INDEX', 'VIEW', 'WITH', 'RECURSIVE', 'OVER', 'PARTITION',
  'ROW_NUMBER', 'RANK', 'DENSE_RANK', 'CROSS', 'NATURAL', 'USING',
  'EXCEPT', 'INTERSECT', 'FETCH', 'FIRST', 'NEXT', 'ROWS', 'ONLY',
];

const SQL_FUNCTIONS = [
  'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'ROUND', 'UPPER', 'LOWER',
  'LENGTH', 'SUBSTR', 'TRIM', 'REPLACE', 'IFNULL', 'NULLIF',
  'DATE', 'TIME', 'DATETIME', 'STRFTIME', 'JULIANDAY',
  'ABS', 'RANDOM', 'TYPEOF', 'TOTAL', 'GROUP_CONCAT',
  'INSTR', 'HEX', 'QUOTE', 'UNICODE', 'ZEROBLOB',
];

function highlightSQL(sql) {
  if (!sql) return '';

  let escaped = sql
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');

  // Highlight strings
  escaped = escaped.replace(/('[^']*')/g, '<span style="color:#22d3ee">$1</span>');

  // Highlight numbers
  escaped = escaped.replace(/\b(\d+\.?\d*)\b/g, '<span style="color:#fb923c">$1</span>');

  // Highlight functions
  for (const fn of SQL_FUNCTIONS) {
    const regex = new RegExp(`\\b(${fn})\\s*\\(`, 'gi');
    escaped = escaped.replace(regex, '<span style="color:#c084fc;font-weight:500">$1</span>(');
  }

  // Highlight keywords
  for (const kw of SQL_KEYWORDS) {
    const regex = new RegExp(`\\b(${kw})\\b`, 'gi');
    escaped = escaped.replace(regex, '<span style="color:#a5b4fc;font-weight:600">$1</span>');
  }

  return escaped;
}

export default function SqlDisplay({ sql }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(sql).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [sql]);

  const lineCount = useMemo(() => {
    if (!sql) return 0;
    return sql.split('\n').length;
  }, [sql]);

  if (!sql) return null;

  return (
    <div className="response-section sql-display with-line-numbers">
      <div className="response-section-header">
        <Code size={14} className="section-icon" />
        Generated SQL
      </div>
      <button className={`copy-btn ${copied ? 'copied' : ''}`} onClick={handleCopy}>
        {copied ? <Check size={12} /> : <Copy size={12} />}
        {copied ? 'Copied' : 'Copy'}
      </button>
      <div className="sql-line-numbers">
        {Array.from({ length: lineCount }, (_, i) => (
          <span key={i}>{i + 1}</span>
        ))}
      </div>
      <pre dangerouslySetInnerHTML={{ __html: highlightSQL(sql) }} />
    </div>
  );
}
