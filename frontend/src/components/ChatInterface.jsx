import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  MessageSquare, Send, Menu, ChevronDown,
  Database, BarChart3, Table2, Search
} from 'lucide-react';
import { sendQuestion } from '../api/client';
import MessageBubble from './MessageBubble';
import LogoIcon from './LogoIcon';

import { motion, AnimatePresence } from 'framer-motion';

/**
 * ChatInterface — Main chat area with message list, typing indicator, and input bar.
 */
export default function ChatInterface({ sessionId, messages, onNewMessage, onMenuClick, user }) {
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showScrollBtn, setShowScrollBtn] = useState(false);
  const messagesEndRef = useRef(null);
  const containerRef = useRef(null);

  // Auto scroll to bottom
  useEffect(() => {
    const container = containerRef.current;
    if (container) {
      container.scrollTop = container.scrollHeight;
    }
  }, [messages, isLoading]);

  // Show/hide scroll-to-bottom button
  const handleScroll = useCallback(() => {
    const c = containerRef.current;
    if (!c) return;
    const distFromBottom = c.scrollHeight - c.scrollTop - c.clientHeight;
    setShowScrollBtn(distFromBottom > 120);
  }, []);

  const scrollToBottom = () => {
    const c = containerRef.current;
    if (c) c.scrollTo({ top: c.scrollHeight, behavior: 'smooth' });
  };

  const handleSubmit = useCallback(async (question) => {
    if (!question.trim() || !sessionId || isLoading) return;

    const q = question.trim();
    setInput('');
    setIsLoading(true);

    const chatHistory = messages.map((m) => ({
      role: m.role,
      content: m.role === 'user' ? m.content : (m.data?.explanation || m.content || ''),
    }));

    const userMessage = { role: 'user', content: q, timestamp: new Date() };

    try {
      const response = await sendQuestion(sessionId, q, chatHistory);
      const assistantMessage = { role: 'assistant', data: response, timestamp: new Date() };
      onNewMessage(userMessage, assistantMessage);
    } catch (err) {
      const errorMsg = err.response?.data?.detail || err.message || 'Something went wrong.';
      const assistantMessage = {
        role: 'assistant',
        data: { error: errorMsg, question: q },
        timestamp: new Date(),
      };
      onNewMessage(userMessage, assistantMessage);
    } finally {
      setIsLoading(false);
    }
  }, [sessionId, isLoading, messages, onNewMessage]);

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(input);
    }
  };

  const handleTipClick = (question) => {
    if (sessionId) handleSubmit(question);
  };

  const suggestions = sessionId && messages.length > 0 ? [
    'Count total rows',
    'Show top 10 records',
    'Find missing/null values',
    'Group by category',
  ] : [];

  return (
    <>
      {/* Header */}
      <motion.div 
        className="chat-header"
        initial={{ y: -20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.3 }}
      >
        <div className="chat-header-title">
          <button className="mobile-menu-btn" onClick={onMenuClick} aria-label="Toggle menu">
            <Menu size={20} />
          </button>
          <MessageSquare size={18} className="chat-header-icon" />
          <h2>Chat</h2>
        </div>
        <div className="header-right">
          {sessionId && (
            <motion.div 
              className="header-badges"
              initial={{ scale: 0.8, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              transition={{ type: 'spring', stiffness: 200, damping: 15 }}
            >
              <div className="connection-indicator">
                <div className="connection-dot" />
                Active
              </div>
              <span className="session-badge">{sessionId.slice(0, 8)}</span>
            </motion.div>
          )}
        </div>
      </motion.div>

      {/* Messages */}
      <div
        className="messages-container"
        id="messages-container"
        ref={containerRef}
        onScroll={handleScroll}
      >
        <AnimatePresence mode="wait">
          {messages.length === 0 && !isLoading ? (
            <motion.div 
              key="welcome"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="welcome-screen"
            >
              <motion.div 
                className="welcome-icon-wrapper"
                animate={{ y: [0, -8, 0] }}
                transition={{ repeat: Infinity, duration: 4, ease: "easeInOut" }}
              >
                <LogoIcon size={32} />
              </motion.div>
              <h2>Ask anything about your data</h2>
              <p>
                Upload a CSV or SQL file, then ask questions in plain English.
                SQL is generated automatically and results are displayed
                with tables and charts.
              </p>
              {sessionId && (
                <motion.div 
                  className="welcome-tips"
                  initial="hidden"
                  animate="visible"
                  variants={{
                    hidden: { opacity: 0 },
                    visible: {
                      opacity: 1,
                      transition: { staggerChildren: 0.1 }
                    }
                  }}
                >
                  <motion.div variants={{hidden: { opacity: 0, x: -10 }, visible: { opacity: 1, x: 0 }}} className="welcome-tip" onClick={() => handleTipClick('Show me all tables and their row counts')}>
                    <Table2 size={16} className="tip-icon" />
                    <span className="tip-text">Show all tables and row counts</span>
                  </motion.div>
                  <motion.div variants={{hidden: { opacity: 0, x: -10 }, visible: { opacity: 1, x: 0 }}} className="welcome-tip" onClick={() => handleTipClick('What are the top 10 records?')}>
                    <BarChart3 size={16} className="tip-icon" />
                    <span className="tip-text">Show top 10 records</span>
                  </motion.div>
                  <motion.div variants={{hidden: { opacity: 0, x: -10 }, visible: { opacity: 1, x: 0 }}} className="welcome-tip" onClick={() => handleTipClick('Give me a summary of the data')}>
                    <Database size={16} className="tip-icon" />
                    <span className="tip-text">Summarize the data</span>
                  </motion.div>
                  <motion.div variants={{hidden: { opacity: 0, x: -10 }, visible: { opacity: 1, x: 0 }}} className="welcome-tip" onClick={() => handleTipClick('What columns are available?')}>
                    <Search size={16} className="tip-icon" />
                    <span className="tip-text">Show available columns</span>
                  </motion.div>
                </motion.div>
              )}
            </motion.div>
          ) : (
            <motion.div key="chat-content" initial={{ opacity: 0 }} animate={{ opacity: 1 }}>
              {messages.map((msg, idx) => (
                <MessageBubble key={idx} message={msg} user={user} sessionId={sessionId} />
              ))}
              <AnimatePresence>
                {isLoading && (
                  <motion.div 
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 10 }}
                    className="message message-assistant"
                  >
                    <div className="message-assistant-header">
                      <div className="assistant-avatar">
                        <LogoIcon size={14} />
                      </div>
                      <span className="assistant-label">ChatDB</span>
                    </div>
                    <div className="response-section">
                      <div className="typing-indicator">
                        <div className="typing-dots">
                          <span />
                          <span />
                          <span />
                        </div>
                        <span className="typing-text">Analyzing your query...</span>
                      </div>
                    </div>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          )}
        </AnimatePresence>
        <div ref={messagesEndRef} />
      </div>

      {/* Scroll to bottom */}
      <AnimatePresence>
        {showScrollBtn && (
          <motion.button 
            initial={{ opacity: 0, scale: 0.8, y: 10 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.8, y: 10 }}
            className="scroll-bottom-btn" 
            onClick={scrollToBottom} 
            aria-label="Scroll to bottom"
          >
            <ChevronDown size={18} />
          </motion.button>
        )}
      </AnimatePresence>

      {/* Input bar */}
      <motion.div 
        className="chat-input-container"
        initial={{ y: 20, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.3 }}
      >
        <AnimatePresence>
          {suggestions.length > 0 && (
            <motion.div 
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="input-suggestions"
            >
              {suggestions.map((s) => (
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  key={s}
                  className="input-suggestion"
                  onClick={() => handleSubmit(s)}
                >
                  {s}
                </motion.button>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
        <div className="chat-input-wrapper">
          <input
            className="chat-input"
            type="text"
            placeholder={
              sessionId
                ? 'Ask a question about your data...'
                : 'Upload a file first to start chatting...'
            }
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={!sessionId || isLoading}
            id="chat-input"
          />
          <motion.button
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            className="send-btn"
            onClick={() => handleSubmit(input)}
            disabled={!sessionId || isLoading || !input.trim()}
            id="send-button"
            aria-label="Send message"
          >
            <Send size={18} />
          </motion.button>
        </div>
        <div className="input-hint">Press Enter to send</div>
      </motion.div>
    </>
  );
}
