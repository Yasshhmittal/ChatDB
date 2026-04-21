/**
 * API Client — Centralized HTTP calls to the FastAPI backend.
 * All endpoints go through Vite's proxy (/api → localhost:8000).
 */

import axios from 'axios';

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/api',
  timeout: 120000, // 2 min timeout (LLM calls can be slow)
  headers: {
    'Accept': 'application/json',
  },
});

// Add a request interceptor to attach the JWT token if available
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('chatdb_token');
    if (token) {
      config.headers['Authorization'] = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

/**
 * Upload a CSV or SQL file.
 * @returns {Promise<{session_id, tables, message}>}
 */
export async function uploadFile(file) {
  const formData = new FormData();
  formData.append('file', file);

  const response = await api.post('/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
}

/**
 * Upload multiple CSV/SQL files into a single session.
 * All files share one database for cross-file queries.
 * @returns {Promise<{session_id, tables, message}>}
 */
export async function uploadMultipleFiles(files) {
  const formData = new FormData();
  files.forEach((file) => {
    formData.append('files', file);
  });

  const response = await api.post('/upload-multiple', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return response.data;
}

/**
 * Send a chat question about the uploaded database.
 * @returns {Promise<{question, sql_query, results, columns, row_count, explanation, chart, error, retries_used}>}
 */
export async function sendQuestion(sessionId, question, chatHistory = []) {
  const response = await api.post('/chat', {
    session_id: sessionId,
    question,
    chat_history: chatHistory,
  });
  return response.data;
}

/**
 * Get database schema for a session.
 * @returns {Promise<{session_id, tables}>}
 */
export async function getSchema(sessionId) {
  const response = await api.get(`/schema/${sessionId}`);
  return response.data;
}

/**
 * Get sample data for a specific table.
 * @returns {Promise<{table, columns, rows}>}
 */
export async function getSampleData(sessionId, tableName) {
  const response = await api.get(`/schema/${sessionId}/sample/${tableName}`);
  return response.data;
}

/**
 * Health check.
 */
export async function healthCheck() {
  const response = await api.get('/health');
  return response.data;
}

/**
 * Authentication APIs
 */
export async function signUp(name, username, password) {
  const response = await api.post('/auth/signup', { name, username, password });
  return response.data;
}

export async function signIn(username, password) {
  const response = await api.post('/auth/signin', { username, password });
  return response.data;
}

/**
 * Download Database APIs
 */

/**
 * Check whether original and/or modified databases are available.
 * @returns {Promise<{session_id, original_available, modified_available}>}
 */
export async function getDownloadStatus(sessionId) {
  const response = await api.get(`/download/${sessionId}/status`);
  return response.data;
}

/**
 * Download the original (unmodified) database as CSV(s).
 */
export function getOriginalDownloadUrl(sessionId) {
  const base = api.defaults.baseURL === '/api' ? '/api' : api.defaults.baseURL;
  return `${base}/download/${sessionId}/csv/original`;
}

/**
 * Download the modified database as CSV(s).
 */
export function getModifiedDownloadUrl(sessionId) {
  const base = api.defaults.baseURL === '/api' ? '/api' : api.defaults.baseURL;
  return `${base}/download/${sessionId}/csv/modified`;
}

export default api;
