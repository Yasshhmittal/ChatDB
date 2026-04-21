import React, { useState, useCallback, useEffect } from 'react';
import { LogOut, X } from 'lucide-react';
import LogoIcon from './components/LogoIcon';
import { motion, AnimatePresence } from 'framer-motion';
import LoginPage from './components/LoginPage';
import FileUpload from './components/FileUpload';
import SchemaViewer from './components/SchemaViewer';
import ChatInterface from './components/ChatInterface';
import ParticleBackground from './components/ParticleBackground';
import ToastContainer from './components/ToastNotification';

/**
 * App — Main layout with auth gate, sidebar (upload + schema), and chat area.
 */
export default function App() {
  const [user, setUser] = useState(() => {
    const stored = localStorage.getItem('chatdb_user');
    return stored ? JSON.parse(stored) : null;
  });

  const [sessionId, setSessionId] = useState(null);
  const [schema, setSchema] = useState(null);
  const [messages, setMessages] = useState([]);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback((type, message, title = '') => {
    const id = Date.now() + Math.random();
    setToasts((prev) => [...prev, { id, type, message, title, duration: 4000 }]);
  }, []);

  const dismissToast = useCallback((id) => {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }, []);

  const handleAuth = useCallback((userData) => {
    setUser(userData);
    addToast('success', `Signed in as ${userData.name}`, 'Welcome');
  }, [addToast]);

  const handleLogout = useCallback(() => {
    localStorage.removeItem('chatdb_user');
    localStorage.removeItem('chatdb_token');
    setUser(null);
    setSessionId(null);
    setSchema(null);
    setMessages([]);
  }, []);

  const handleUploadSuccess = useCallback((data) => {
    setSessionId(data.session_id);
    setSchema(data.tables);
    setMessages([]);
    setIsMobileMenuOpen(false);
    addToast('success', data.message || 'File uploaded successfully');
  }, [addToast]);

  const handleNewMessage = useCallback((userMsg, assistantMsg) => {
    setMessages((prev) => [...prev, userMsg, assistantMsg]);
  }, []);

  // If not authenticated, show login
  if (!user) {
    return (
      <>
        <LoginPage onAuth={handleAuth} />
        <ToastContainer toasts={toasts} onDismiss={dismissToast} />
      </>
    );
  }

  return (
    <motion.div 
      className="app-container"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ duration: 0.5 }}
    >
      <ParticleBackground particleCount={40} />

      {/* Mobile overlay */}
      <AnimatePresence>
        {isMobileMenuOpen && (
          <motion.div 
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="sidebar-overlay" 
            onClick={() => setIsMobileMenuOpen(false)} 
          />
        )}
      </AnimatePresence>

      {/* Sidebar */}
      <aside className={`sidebar ${isMobileMenuOpen ? 'open' : ''}`}>
        <div className="sidebar-header">
          <div className="sidebar-logo">
            <div className="logo-icon">
              <LogoIcon size={18} />
            </div>
            <div>
              <h1>ChatDB</h1>
              <div className="subtitle">Database Assistant</div>
            </div>
          </div>
          <button
            className="mobile-close-btn"
            onClick={() => setIsMobileMenuOpen(false)}
            aria-label="Close menu"
          >
            <X size={18} />
          </button>
        </div>

        <div className="sidebar-content">
          <FileUpload onUploadSuccess={handleUploadSuccess} />
          {schema && (
            <SchemaViewer tables={schema} sessionId={sessionId} />
          )}
        </div>

        <div className="sidebar-user">
          <div className="sidebar-user-info">
            <div className="sidebar-user-avatar">{user.avatar}</div>
            <span className="sidebar-user-name">{user.name}</span>
          </div>
          <button
            className="sidebar-logout-btn"
            onClick={handleLogout}
            title="Sign out"
            aria-label="Sign out"
          >
            <LogOut size={16} />
          </button>
        </div>
      </aside>

      {/* Main Chat Area */}
      <main className="main-content">
        <ChatInterface
          sessionId={sessionId}
          messages={messages}
          onNewMessage={handleNewMessage}
          onMenuClick={() => setIsMobileMenuOpen(true)}
          user={user}
        />
      </main>

      <ToastContainer toasts={toasts} onDismiss={dismissToast} />
    </motion.div>
  );
}
