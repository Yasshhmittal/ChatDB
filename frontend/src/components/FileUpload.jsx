import React, { useState, useRef, useCallback } from 'react';
import { Upload, FileText, CheckCircle, AlertCircle, Loader } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { uploadFile } from '../api/client';

/**
 * FileUpload — Drag-and-drop file upload zone with progress indicator.
 */
export default function FileUpload({ onUploadSuccess }) {
  const [isDragOver, setIsDragOver] = useState(false);
  const [status, setStatus] = useState(null);
  const [uploadedFile, setUploadedFile] = useState(null);
  const fileInputRef = useRef(null);

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const handleFile = useCallback(async (file) => {
    if (!file) return;

    const ext = file.name.split('.').pop().toLowerCase();
    if (!['csv', 'sql', 'xlsx', 'xls', 'json'].includes(ext)) {
      setStatus({ type: 'error', message: 'Only .csv, .sql, .xlsx, .xls, and .json files are supported.' });
      return;
    }

    if (file.size > 50 * 1024 * 1024) {
      setStatus({ type: 'error', message: 'File too large. Maximum size is 50MB.' });
      return;
    }

    setStatus({ type: 'loading', message: `Uploading ${file.name}...` });

    try {
      const data = await uploadFile(file);
      setStatus({ type: 'success', message: data.message });
      setUploadedFile({ name: file.name, size: file.size });
      onUploadSuccess(data);
    } catch (err) {
      const msg = err.response?.data?.detail || err.message || 'Upload failed.';
      setStatus({ type: 'error', message: msg });
    }
  }, [onUploadSuccess]);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    setIsDragOver(false);
    handleFile(e.dataTransfer.files?.[0]);
  }, [handleFile]);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => {
    setIsDragOver(false);
  }, []);

  const handleClick = useCallback(() => {
    if (fileInputRef.current) {
      fileInputRef.current.value = null;
      fileInputRef.current.click();
    }
  }, []);

  const handleInputChange = useCallback((e) => {
    handleFile(e.target.files?.[0]);
  }, [handleFile]);

  return (
    <div>
      <motion.div
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        className={`upload-zone ${isDragOver ? 'drag-over' : ''}`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onClick={handleClick}
        id="upload-zone"
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <motion.div 
          className="upload-icon"
          animate={isDragOver ? { y: -5, color: '#8b5cf6' } : { y: 0 }}
        >
          <Upload size={28} />
        </motion.div>
        <div className="upload-text">
          <strong>Drop your file here</strong>
          <br />
          or click to browse
        </div>
        <div className="file-types">Supports .csv, .sql, .xlsx, and .json files</div>
        <AnimatePresence>
          {status?.type === 'loading' && (
            <motion.div 
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="upload-progress-bar"
            >
              <div className="upload-progress-fill" />
            </motion.div>
          )}
        </AnimatePresence>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv,.sql,.xlsx,.xls,.json"
          onChange={handleInputChange}
          onClick={(e) => e.stopPropagation()}
          id="file-input"
        />
      </motion.div>

      {/* Uploaded file chip */}
      <AnimatePresence>
        {uploadedFile && (
          <motion.div 
            initial={{ opacity: 0, scale: 0.9, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9 }}
            className="uploaded-file-chip"
          >
            <FileText size={14} className="file-chip-icon" />
            <span className="file-chip-name">{uploadedFile.name}</span>
            <span className="file-chip-size">{formatFileSize(uploadedFile.size)}</span>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Status message */}
      <AnimatePresence mode="wait">
        {status && (
          <motion.div 
            key={status.message}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 10 }}
            className={`upload-status ${status.type}`} 
            id="upload-status"
          >
            {status.type === 'loading' && <Loader size={14} className="spin" />}
            {status.type === 'success' && <CheckCircle size={14} />}
            {status.type === 'error' && <AlertCircle size={14} />}
            {status.message}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
