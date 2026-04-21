import React, { useState, useMemo } from 'react';
import {
  ChevronRight, Database as DatabaseIcon,
  Table2, Columns, Hash, Search
} from 'lucide-react';

import { motion, AnimatePresence } from 'framer-motion';

/**
 * SchemaViewer — Collapsible tree view with stats, search, and column type coloring.
 */
export default function SchemaViewer({ tables, sessionId }) {
  const [expanded, setExpanded] = useState({});
  const [searchQuery, setSearchQuery] = useState('');

  const toggleTable = (tableName) => {
    setExpanded((prev) => ({ ...prev, [tableName]: !prev[tableName] }));
  };

  // Compute stats
  const stats = useMemo(() => {
    if (!tables) return null;
    const totalCols = tables.reduce((s, t) => s + (t.columns?.length || 0), 0);
    const totalRows = tables.reduce((s, t) => s + (t.row_count || 0), 0);
    return { tables: tables.length, columns: totalCols, rows: totalRows };
  }, [tables]);

  // Filter tables by search
  const filteredTables = useMemo(() => {
    if (!tables) return [];
    if (!searchQuery.trim()) return tables;
    const q = searchQuery.toLowerCase();
    return tables.filter((t) =>
      t.name.toLowerCase().includes(q) ||
      t.columns?.some((c) => c.name.toLowerCase().includes(q))
    );
  }, [tables, searchQuery]);

  // Map dtype to color class
  const getTypeClass = (dtype) => {
    const d = (dtype || '').toLowerCase();
    if (d.includes('int') || d.includes('integer')) return 'type-integer';
    if (d.includes('real') || d.includes('float') || d.includes('double') || d.includes('numeric') || d.includes('decimal')) return 'type-real';
    if (d.includes('date') || d.includes('time') || d.includes('timestamp')) return 'type-date';
    if (d.includes('text') || d.includes('varchar') || d.includes('char') || d.includes('string')) return 'type-text';
    return 'type-other';
  };

  if (!tables || tables.length === 0) return null;

  const containerVariants = {
    hidden: { opacity: 0 },
    visible: { 
      opacity: 1, 
      transition: { staggerChildren: 0.05 } 
    }
  };

  const itemVariants = {
    hidden: { opacity: 0, x: -10 },
    visible: { opacity: 1, x: 0 }
  };

  return (
    <div className="schema-section" id="schema-viewer">
      <div className="schema-section-label">Database Schema</div>

      {/* Stats */}
      {stats && (
        <motion.div 
          className="schema-stats"
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ type: 'spring', damping: 20 }}
        >
          <div className="schema-stat">
            <div className="schema-stat-value">{stats.tables}</div>
            <div className="schema-stat-label">Tables</div>
          </div>
          <div className="schema-stat">
            <div className="schema-stat-value">{stats.columns}</div>
            <div className="schema-stat-label">Columns</div>
          </div>
          <div className="schema-stat">
            <div className="schema-stat-value">{stats.rows.toLocaleString()}</div>
            <div className="schema-stat-label">Rows</div>
          </div>
        </motion.div>
      )}

      {/* Search */}
      {tables.length > 1 && (
        <motion.div 
          className="schema-search-wrapper"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          delay={0.2}
        >
          <Search size={12} className="search-icon" />
          <input
            className="schema-search"
            type="text"
            placeholder="Search tables or columns..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </motion.div>
      )}

      {/* Tables */}
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="visible"
      >
        {filteredTables.map((table) => (
          <motion.div className="schema-table" key={table.name} variants={itemVariants}>
            <div
              className="schema-table-header"
              onClick={() => toggleTable(table.name)}
            >
              <span className="table-name">
                <ChevronRight
                  size={14}
                  className={`expand-icon ${expanded[table.name] ? 'expanded' : ''}`}
                />
                <Table2 size={13} className="table-icon" />
                {table.name}
              </span>
              <span className="row-count">{table.row_count.toLocaleString()} rows</span>
            </div>
            <AnimatePresence>
              {expanded[table.name] && (
                <motion.div 
                  initial={{ height: 0, opacity: 0 }}
                  animate={{ height: 'auto', opacity: 1 }}
                  exit={{ height: 0, opacity: 0 }}
                  transition={{ duration: 0.2 }}
                  style={{ overflow: 'hidden' }}
                  className="schema-table-columns"
                >
                  {table.columns.map((col) => (
                    <div className="schema-column" key={col.name}>
                      <span className="col-name">{col.name}</span>
                      <span className={`col-type ${getTypeClass(col.dtype)}`}>{col.dtype}</span>
                    </div>
                  ))}
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        ))}
      </motion.div>
    </div>
  );
}
