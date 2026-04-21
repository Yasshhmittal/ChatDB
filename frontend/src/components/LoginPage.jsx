import React, { useState, useRef } from 'react';
import { AtSign, Lock, User, Eye, EyeOff, ArrowRight, Zap, BarChart3, MessageSquare, Shield, ChevronDown } from 'lucide-react';
import LogoIcon from './LogoIcon';
import ParticleBackground from './ParticleBackground';
import { signIn, signUp } from '../api/client';
import { motion, AnimatePresence, useScroll, useTransform, useMotionValue, useSpring } from 'framer-motion';

/* ── Animation Variants ── */
const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.15, delayChildren: 0.1 },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 30 },
  visible: { opacity: 1, y: 0, transition: { type: 'spring', stiffness: 80, damping: 20 } },
};

const cardVariants = {
  hidden: { opacity: 0, scale: 0.95, y: 30 },
  visible: { opacity: 1, scale: 1, y: 0, transition: { type: 'spring', damping: 25, stiffness: 120, delay: 0.3 } },
};

/* ── Floating Orb Layer ── */
function FloatingOrbs({ scrollYProgress, mouseX, mouseY }) {
  const y1 = useTransform(scrollYProgress, [0, 1], [0, -400]);
  const y2 = useTransform(scrollYProgress, [0, 1], [0, -250]);
  const y3 = useTransform(scrollYProgress, [0, 1], [0, -600]);
  const y4 = useTransform(scrollYProgress, [0, 1], [0, -350]);
  const y5 = useTransform(scrollYProgress, [0, 1], [0, -500]);
  const rotate1 = useTransform(scrollYProgress, [0, 1], [0, 180]);
  const rotate2 = useTransform(scrollYProgress, [0, 1], [0, -120]);
  const scale1 = useTransform(scrollYProgress, [0, 0.5, 1], [1, 1.3, 0.8]);
  const scale2 = useTransform(scrollYProgress, [0, 0.5, 1], [0.8, 1.2, 1]);

  // Mouse tracking transformations (different depths/speeds)
  const mx1 = useTransform(mouseX, [-1, 1], [-200, 200]);
  const my1 = useTransform(mouseY, [-1, 1], [-200, 200]);

  const mx2 = useTransform(mouseX, [-1, 1], [100, -100]);
  const my2 = useTransform(mouseY, [-1, 1], [100, -100]);

  const mx3 = useTransform(mouseX, [-1, 1], [-300, 300]);
  const my3 = useTransform(mouseY, [-1, 1], [-300, 300]);

  return (
    <div className="parallax-orbs" aria-hidden="true">
      <motion.div style={{ x: mx1, y: my1 }} className="parallax-orb-wrapper">
        <motion.div className="parallax-orb orb-1" style={{ y: y1, rotate: rotate1, scale: scale1 }} />
      </motion.div>
      <motion.div style={{ x: mx2, y: my2 }} className="parallax-orb-wrapper">
        <motion.div className="parallax-orb orb-2" style={{ y: y2, rotate: rotate2 }} />
      </motion.div>
      <motion.div style={{ x: mx3, y: my3 }} className="parallax-orb-wrapper">
        <motion.div className="parallax-orb orb-3" style={{ y: y3, scale: scale2 }} />
      </motion.div>
      <motion.div style={{ x: mx2, y: my1 }} className="parallax-orb-wrapper">
        <motion.div className="parallax-orb orb-4" style={{ y: y4 }} />
      </motion.div>
      <motion.div style={{ x: mx1, y: my2 }} className="parallax-orb-wrapper">
        <motion.div className="parallax-orb orb-5" style={{ y: y5 }} />
      </motion.div>
      <motion.div style={{ x: mx3, y: my1 }} className="parallax-orb-wrapper">
        <motion.div className="parallax-orb orb-6" style={{ y: y2, rotate: rotate1 }} />
      </motion.div>
    </div>
  );
}

/* ── Feature Card (for section 2) ── */
function FeatureCard({ icon: Icon, title, description, index }) {
  return (
    <motion.div
      className="parallax-feature-card"
      initial={{ opacity: 0, y: 50 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-80px' }}
      transition={{ type: 'spring', stiffness: 80, damping: 20, delay: index * 0.12 }}
      whileHover={{ y: -8, scale: 1.02 }}
    >
      <div className="parallax-feature-icon">
        <Icon size={24} />
      </div>
      <h3>{title}</h3>
      <p>{description}</p>
    </motion.div>
  );
}

/* ── Stat Counter ── */
function StatItem({ value, label, index }) {
  return (
    <motion.div
      className="parallax-stat"
      initial={{ opacity: 0, scale: 0.8 }}
      whileInView={{ opacity: 1, scale: 1 }}
      viewport={{ once: true, margin: '-50px' }}
      transition={{ type: 'spring', stiffness: 100, delay: index * 0.15 }}
    >
      <span className="parallax-stat-value">{value}</span>
      <span className="parallax-stat-label">{label}</span>
    </motion.div>
  );
}


/**
 * LoginPage — Full parallax landing page with glassmorphic auth card.
 */
export default function LoginPage({ onAuth }) {
  const [isSignup, setIsSignup] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [formData, setFormData] = useState({ name: '', username: '', password: '' });
  const [errors, setErrors] = useState({});

  const scrollRef = useRef(null);
  const { scrollYProgress } = useScroll({ container: scrollRef });

  // Mouse tracking
  const mouseX = useMotionValue(0);
  const mouseY = useMotionValue(0);
  const smoothMouseX = useSpring(mouseX, { stiffness: 50, damping: 20 });
  const smoothMouseY = useSpring(mouseY, { stiffness: 50, damping: 20 });

  const handleMouseMove = (e) => {
    const { clientX, clientY } = e;
    const { innerWidth, innerHeight } = window;
    // Normalize to -1 to 1
    const x = (clientX / innerWidth) * 2 - 1;
    const y = (clientY / innerHeight) * 2 - 1;
    mouseX.set(x);
    mouseY.set(y);
  };

  // Parallax transforms for hero section
  const heroY = useTransform(scrollYProgress, [0, 0.3], [0, -150]);
  const heroOpacity = useTransform(scrollYProgress, [0, 0.25], [1, 0]);
  const heroScale = useTransform(scrollYProgress, [0, 0.3], [1, 0.92]);
  const particleY = useTransform(scrollYProgress, [0, 1], [0, -100]);

  const particleMouseX = useTransform(smoothMouseX, [-1, 1], [-60, 60]);
  const particleMouseY = useTransform(smoothMouseY, [-1, 1], [-60, 60]);

  const validateForm = () => {
    const newErrors = {};
    if (isSignup && !formData.name.trim()) newErrors.name = 'Name is required';
    if (!formData.username.trim()) {
      newErrors.username = 'Username is required';
    } else if (formData.username.trim().length < 3) {
      newErrors.username = 'Username must be at least 3 characters';
    } else if (!/^[a-zA-Z0-9_]+$/.test(formData.username.trim())) {
      newErrors.username = 'Only letters, numbers, and underscores allowed';
    }
    if (!formData.password) {
      newErrors.password = 'Password is required';
    } else if (formData.password.length < 6) {
      newErrors.password = 'Password must be at least 6 characters';
    }
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!validateForm()) return;
    setIsLoading(true);
    setErrors((prev) => ({ ...prev, _general: undefined }));

    try {
      let data;
      if (isSignup) {
        data = await signUp(formData.name, formData.username, formData.password);
      } else {
        data = await signIn(formData.username, formData.password);
      }
      localStorage.setItem('chatdb_token', data.access_token);
      localStorage.setItem('chatdb_user', JSON.stringify(data.user));
      onAuth(data.user);
    } catch (err) {
      if (err.code === 'ERR_NETWORK' || err.message === 'Network Error') {
        setErrors((prev) => ({ ...prev, _general: 'Unable to connect to the server. Is the backend running?' }));
      } else if (err.response?.data?.detail) {
        setErrors((prev) => ({ ...prev, _general: err.response.data.detail }));
      } else {
        setErrors((prev) => ({ ...prev, _general: 'Authentication failed. Please check your credentials.' }));
      }
    } finally {
      setIsLoading(false);
    }
  };

  const handleChange = (field) => (e) => {
    setFormData((prev) => ({ ...prev, [field]: e.target.value }));
    if (errors[field]) setErrors((prev) => ({ ...prev, [field]: undefined }));
  };

  const switchMode = () => {
    setIsSignup(!isSignup);
    setErrors({});
  };

  const scrollToSection = (id) => {
    const el = document.getElementById(id);
    if (el) el.scrollIntoView({ behavior: 'smooth' });
  };

  return (
    <div className="login-page parallax-page" ref={scrollRef} onMouseMove={handleMouseMove}>
      {/* Fixed particle background with parallax offset */}
      <motion.div className="parallax-particle-layer" style={{ y: particleY, x: particleMouseX }}>
        <motion.div style={{ y: particleMouseY, width: '100%', height: '100%' }}>
          <ParticleBackground particleCount={100} />
        </motion.div>
      </motion.div>

      {/* Floating orbs layer */}
      <FloatingOrbs scrollYProgress={scrollYProgress} mouseX={smoothMouseX} mouseY={smoothMouseY} />

      {/* ═══════ SECTION 1 — HERO ═══════ */}
      <section className="parallax-section parallax-hero" id="hero">
        <motion.div
          className="parallax-hero-content"
          style={{ y: heroY, opacity: heroOpacity, scale: heroScale }}
        >
          <motion.div
            className="login-logo"
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: 'spring', stiffness: 100, delay: 0.2 }}
          >
            <div className="login-logo-icon">
              <LogoIcon size={28} />
            </div>
            <span className="login-logo-text">ChatDB</span>
          </motion.div>

          <motion.h1
            className="parallax-hero-title"
            initial={{ opacity: 0, y: 40 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: 'spring', stiffness: 60, damping: 18, delay: 0.4 }}
          >
            Talk to your data.
            <br />
            <span className="parallax-hero-gradient">Get instant answers.</span>
          </motion.h1>

          <motion.p
            className="parallax-hero-subtitle"
            initial={{ opacity: 0, y: 30 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ type: 'spring', stiffness: 60, damping: 18, delay: 0.6 }}
          >
            Upload any dataset and ask questions in plain English.
            ChatDB transforms natural language into SQL queries, interactive charts,
            and clear explanations — no coding required.
          </motion.p>

          <motion.div
            className="parallax-hero-actions"
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.8 }}
          >
            <button className="parallax-cta-primary" onClick={() => scrollToSection('auth')}>
              Get Started <ArrowRight size={18} />
            </button>
            <button className="parallax-cta-secondary" onClick={() => scrollToSection('features')}>
              Learn More
            </button>
          </motion.div>
        </motion.div>

        {/* Scroll indicator */}
        <motion.div
          className="parallax-scroll-indicator"
          animate={{ y: [0, 12, 0] }}
          transition={{ duration: 2, repeat: Infinity, ease: 'easeInOut' }}
          onClick={() => scrollToSection('features')}
        >
          <ChevronDown size={24} />
        </motion.div>
      </section>

      {/* ═══════ SECTION 2 — FEATURES ═══════ */}
      <section className="parallax-section parallax-features" id="features">
        <motion.div
          className="parallax-section-header"
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ type: 'spring', stiffness: 60 }}
        >
          <h2>Why <span className="parallax-hero-gradient">ChatDB</span>?</h2>
          <p>Powerful features that make data analysis feel effortless</p>
        </motion.div>

        <div className="parallax-features-grid">
          <FeatureCard
            icon={MessageSquare}
            title="Natural Language Queries"
            description="Just type what you want to know. ChatDB understands your intent and generates precise SQL queries automatically."
            index={0}
          />
          <FeatureCard
            icon={Zap}
            title="Instant SQL Generation"
            description="Watch your questions transform into optimized SQL in real-time, with automatic error correction and refinement."
            index={1}
          />
          <FeatureCard
            icon={BarChart3}
            title="Interactive Visualizations"
            description="Get beautiful charts, graphs, and tables generated on the fly. Explore your data visually with a single request."
            index={2}
          />
          <FeatureCard
            icon={Shield}
            title="Secure & Private"
            description="Your data never leaves your session. Every upload is sandboxed and automatically cleaned up when you're done."
            index={3}
          />
        </div>
      </section>

      {/* ═══════ SECTION 3 — STATS ═══════ */}
      <section className="parallax-section parallax-stats" id="stats">
        <div className="parallax-stats-row">
          <StatItem value="10x" label="Faster Insights" index={0} />
          <StatItem value="0" label="SQL Knowledge Required" index={1} />
          <StatItem value="∞" label="Questions You Can Ask" index={2} />
          <StatItem value="<1s" label="Average Response Time" index={3} />
        </div>
      </section>

      {/* ═══════ SECTION 4 — HOW IT WORKS ═══════ */}
      <section className="parallax-section parallax-steps" id="steps">
        <motion.div
          className="parallax-section-header"
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ type: 'spring', stiffness: 60 }}
        >
          <h2>How it <span className="parallax-hero-gradient">works</span></h2>
          <p>Three simple steps to unlock your data</p>
        </motion.div>

        <div className="parallax-steps-timeline">
          {[
            { step: '01', title: 'Upload your data', desc: 'Drag and drop any CSV or SQL file. ChatDB automatically detects schemas and relationships.' },
            { step: '02', title: 'Ask a question', desc: 'Type your question in plain English — "What were the top sales by region last quarter?"' },
            { step: '03', title: 'Get instant results', desc: 'Receive SQL queries, data tables, and interactive visualizations in seconds.' },
          ].map((item, i) => (
            <motion.div
              className="parallax-step-item"
              key={i}
              initial={{ opacity: 0, x: i % 2 === 0 ? -60 : 60 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, margin: '-80px' }}
              transition={{ type: 'spring', stiffness: 60, damping: 20, delay: i * 0.15 }}
            >
              <div className="parallax-step-number">{item.step}</div>
              <div className="parallax-step-content">
                <h3>{item.title}</h3>
                <p>{item.desc}</p>
              </div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* ═══════ SECTION 5 — AUTH FORM ═══════ */}
      <section className="parallax-section parallax-auth" id="auth">
        <motion.div
          className="parallax-section-header"
          initial={{ opacity: 0, y: 40 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-100px' }}
          transition={{ type: 'spring', stiffness: 60 }}
        >
          <h2>Ready to <span className="parallax-hero-gradient">start</span>?</h2>
          <p>Create an account or sign in to begin exploring your data</p>
        </motion.div>

        <motion.div
          className="login-card"
          initial={{ opacity: 0, scale: 0.92, y: 40 }}
          whileInView={{ opacity: 1, scale: 1, y: 0 }}
          viewport={{ once: true, margin: '-60px' }}
          transition={{ type: 'spring', damping: 25, stiffness: 100 }}
        >
          <div className="login-card-header">
            <h2>{isSignup ? 'Create your account' : 'Welcome back'}</h2>
            <p className="login-card-subtitle">
              {isSignup ? 'Start querying your data in minutes' : 'Sign in to continue to ChatDB'}
            </p>
          </div>

          <form className="login-form" onSubmit={handleSubmit} noValidate>
            <AnimatePresence mode="wait">
              {errors._general && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  className="login-error-banner"
                  style={{
                    background: 'rgba(239, 68, 68, 0.1)', color: '#ef4444',
                    padding: '0.75rem', borderRadius: '6px', marginBottom: '1rem',
                    fontSize: '0.875rem', border: '1px solid rgba(239, 68, 68, 0.2)',
                  }}
                >
                  {errors._general}
                </motion.div>
              )}
            </AnimatePresence>

            <AnimatePresence mode="popLayout">
              {isSignup && (
                <motion.div
                  initial={{ opacity: 0, height: 0, marginBottom: 0 }}
                  animate={{ opacity: 1, height: 'auto', marginBottom: '1.25rem' }}
                  exit={{ opacity: 0, height: 0, marginBottom: 0 }}
                  transition={{ type: 'spring', bounce: 0.2, duration: 0.4 }}
                  className={`login-field ${errors.name ? 'has-error' : ''}`}
                >
                  <label htmlFor="auth-name">Full name</label>
                  <div className="login-input-wrapper">
                    <User size={16} className="login-input-icon" />
                    <input
                      id="auth-name" type="text" placeholder="John Doe"
                      value={formData.name} onChange={handleChange('name')}
                      autoComplete="name"
                    />
                  </div>
                  {errors.name && <span className="login-error">{errors.name}</span>}
                </motion.div>
              )}
            </AnimatePresence>

            <div className={`login-field ${errors.username ? 'has-error' : ''}`}>
              <label htmlFor="auth-username">Username</label>
              <div className="login-input-wrapper">
                <AtSign size={16} className="login-input-icon" />
                <input
                  id="auth-username" type="text" placeholder="your_username"
                  value={formData.username} onChange={handleChange('username')}
                  autoComplete="username"
                />
              </div>
              {errors.username && <span className="login-error">{errors.username}</span>}
            </div>

            <div className={`login-field ${errors.password ? 'has-error' : ''}`}>
              <label htmlFor="auth-password">Password</label>
              <div className="login-input-wrapper">
                <Lock size={16} className="login-input-icon" />
                <input
                  id="auth-password"
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Minimum 6 characters"
                  value={formData.password} onChange={handleChange('password')}
                  autoComplete={isSignup ? 'new-password' : 'current-password'}
                />
                <button
                  type="button" className="login-toggle-pw"
                  onClick={() => setShowPassword(!showPassword)}
                  tabIndex={-1}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
              {errors.password && <span className="login-error">{errors.password}</span>}
            </div>

            <motion.button
              whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
              type="submit" className="login-submit-btn" disabled={isLoading}
            >
              {isLoading ? <div className="login-spinner" /> : (
                <>{isSignup ? 'Create account' : 'Sign in'} <ArrowRight size={16} /></>
              )}
            </motion.button>
          </form>

          <div className="login-divider"><span>or</span></div>

          <motion.button
            whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
            type="button" className="login-guest-btn"
            onClick={() => {
              const guest = {
                name: 'Guest User', email: 'guest@chatdb.local',
                avatar: 'G', isGuest: true, joinedAt: new Date().toISOString(),
              };
              localStorage.setItem('chatdb_user', JSON.stringify(guest));
              onAuth(guest);
            }}
          >
            Continue as guest
          </motion.button>

          <p className="login-switch">
            {isSignup ? 'Already have an account?' : "Don't have an account?"}
            <button type="button" onClick={switchMode} className="login-switch-btn">
              {isSignup ? 'Sign in' : 'Sign up'}
            </button>
          </p>
        </motion.div>
      </section>

      {/* ═══════ FOOTER ═══════ */}
      <footer className="parallax-footer">
        <div className="parallax-footer-content">
          <div className="login-logo">
            <div className="login-logo-icon"><LogoIcon size={20} /></div>
            <span className="login-logo-text">ChatDB</span>
          </div>
          <p>Query your data using natural language. Built with ❤️</p>
        </div>
      </footer>
    </div>
  );
}
