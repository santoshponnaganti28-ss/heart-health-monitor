/* ==========================================================================
   PulseGuard AI - Frontend Controller (Flask + MongoDB Atlas / SQLite)
   ========================================================================== */

// App State
const state = {
  user: null, // { id, name, email }
  metrics: {
    height: null,
    weight: null,
    age: null,
    bpm: null,
    activityLevel: 'moderate'
  },
  currentECGPreset: 'normal',
  ecgActive: false
};

// DOM Elements
const authScreen = document.getElementById('auth-screen');
const dashboardScreen = document.getElementById('dashboard-screen');
const loginForm = document.getElementById('login-form');
const signupForm = document.getElementById('signup-form');
const forgotModal = document.getElementById('forgot-modal');
const vitalsForm = document.getElementById('vitals-form');
const displayName = document.getElementById('display-name');
const displayEmail = document.getElementById('display-email');
const avatarInitials = document.getElementById('avatar-initials');

// Canvas Setup for ECG Simulator
const canvas = document.getElementById('ecg-canvas');
const ctx = canvas.getContext('2d');
let animationFrameId = null;

// Database State
let cachedRecords = [];

// Initialization on Load
window.addEventListener('DOMContentLoaded', () => {
  resizeCanvas();
  window.addEventListener('resize', resizeCanvas);

  // Check user session
  checkAuthStatus();
});

function checkAuthStatus() {
  fetch('/api/auth/me')
    .then(r => r.json())
    .then(data => {
      if (data.authenticated && data.user) {
        state.user = data.user;
        updateUserUI();
        showScreen('dashboard');
        loadRecords();
        startECG('normal');
      } else {
        state.user = null;
        showScreen('auth');
      }
    })
    .catch(err => {
      console.warn('Auth check error:', err);
      showScreen('auth');
    });
}

function updateUserUI() {
  if (!state.user) return;
  if (displayName) displayName.textContent = state.user.name;
  if (displayEmail) displayEmail.textContent = state.user.email;
  if (avatarInitials) {
    const initials = state.user.name
      .split(' ')
      .map(n => n[0])
      .join('')
      .substring(0, 2)
      .toUpperCase();
    avatarInitials.textContent = initials || 'U';
  }
}

function resizeCanvas() {
  if (!canvas) return;
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.scale(dpr, dpr);
}

function showScreen(screenId) {
  if (screenId === 'auth') {
    if (authScreen) authScreen.style.display = 'block';
    if (dashboardScreen) dashboardScreen.style.display = 'none';
    if (authScreen) authScreen.classList.add('active');
    if (dashboardScreen) dashboardScreen.classList.remove('active');
  } else if (screenId === 'dashboard') {
    if (authScreen) authScreen.style.display = 'none';
    if (dashboardScreen) dashboardScreen.style.display = 'block';
    setTimeout(() => {
      if (dashboardScreen) dashboardScreen.classList.add('active');
    }, 50);
  }
}

// --------------------------------------------------------------------------
// Auth Navigation & Form Handlers
// --------------------------------------------------------------------------

function switchAuthMode(mode) {
  const loginTab = document.getElementById('auth-tab-login');
  const signupTab = document.getElementById('auth-tab-signup');
  const loginF = document.getElementById('login-form');
  const signupF = document.getElementById('signup-form');

  if (mode === 'login') {
    loginTab.classList.add('active');
    signupTab.classList.remove('active');
    loginF.style.display = 'block';
    signupF.style.display = 'none';
  } else {
    signupTab.classList.add('active');
    loginTab.classList.remove('active');
    signupF.style.display = 'block';
    loginF.style.display = 'none';
  }
}

function togglePasswordVisibility(inputId) {
  const input = document.getElementById(inputId);
  if (!input) return;
  input.type = input.type === 'password' ? 'text' : 'password';
}

function handleLogin() {
  const email = document.getElementById('login-email').value.trim();
  const password = document.getElementById('login-password').value;
  const submitBtn = document.getElementById('login-submit-btn');

  if (!email || !password) {
    showToast('Please enter both email and password.', 'warning');
    return;
  }

  submitBtn.disabled = true;
  submitBtn.querySelector('span').textContent = 'Signing in...';

  fetch('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password })
  })
    .then(res => res.json().then(data => ({ status: res.status, ok: res.ok, data })))
    .then(({ ok, data }) => {
      submitBtn.disabled = false;
      submitBtn.querySelector('span').textContent = 'Sign In to Dashboard';

      if (!ok) {
        showToast(data.error || 'Failed to log in.', 'danger');
        return;
      }

      state.user = data.user;
      updateUserUI();
      showScreen('dashboard');
      showToast(data.message || `Welcome back, ${data.user.name}!`, 'success');
      loadRecords();
      startECG('normal');
    })
    .catch(err => {
      submitBtn.disabled = false;
      submitBtn.querySelector('span').textContent = 'Sign In to Dashboard';
      console.error('Login error:', err);
      showToast('Network error while connecting to server.', 'danger');
    });
}

function handleSignup() {
  const name = document.getElementById('signup-name').value.trim();
  const email = document.getElementById('signup-email').value.trim();
  const password = document.getElementById('signup-password').value;
  const confirmPassword = document.getElementById('signup-confirm-password').value;
  const submitBtn = document.getElementById('signup-submit-btn');

  if (!name || !email || !password) {
    showToast('Please fill in all required fields.', 'warning');
    return;
  }

  if (password.length < 6) {
    showToast('Password must be at least 6 characters long.', 'warning');
    return;
  }

  if (password !== confirmPassword) {
    showToast('Passwords do not match.', 'danger');
    return;
  }

  submitBtn.disabled = true;
  submitBtn.querySelector('span').textContent = 'Creating account...';

  fetch('/api/auth/signup', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name,
      email,
      password,
      confirm_password: confirmPassword
    })
  })
    .then(res => res.json().then(data => ({ status: res.status, ok: res.ok, data })))
    .then(({ ok, data }) => {
      submitBtn.disabled = false;
      submitBtn.querySelector('span').textContent = 'Create Account';

      if (!ok) {
        showToast(data.error || 'Registration failed.', 'danger');
        return;
      }

      state.user = data.user;
      updateUserUI();
      showScreen('dashboard');
      showToast(`Account created! Welcome to PulseGuard, ${data.user.name}.`, 'success');
      loadRecords();
      startECG('normal');
    })
    .catch(err => {
      submitBtn.disabled = false;
      submitBtn.querySelector('span').textContent = 'Create Account';
      console.error('Signup error:', err);
      showToast('Network error while creating account.', 'danger');
    });
}

function handleLogout() {
  fetch('/api/auth/logout', { method: 'POST' })
    .finally(() => {
      state.user = null;
      stopECG();
      showScreen('auth');
      showToast('You have been logged out.', 'info');
      // Reset views
      switchTab('dashboard');
    });
}

// --------------------------------------------------------------------------
// Forgot Password Flow
// --------------------------------------------------------------------------

function openForgotModal() {
  const modal = document.getElementById('forgot-modal');
  modal.style.display = 'flex';
  document.getElementById('forgot-step-1').style.display = 'block';
  document.getElementById('forgot-step-2').style.display = 'none';
  document.getElementById('dev-code-banner').style.display = 'none';

  // Pre-fill email from login form if entered
  const loginEmail = document.getElementById('login-email').value.trim();
  if (loginEmail) {
    document.getElementById('forgot-email').value = loginEmail;
  }
}

function closeForgotModal() {
  document.getElementById('forgot-modal').style.display = 'none';
}

function backToStep1() {
  document.getElementById('forgot-step-1').style.display = 'block';
  document.getElementById('forgot-step-2').style.display = 'none';
}

function requestResetCode() {
  const email = document.getElementById('forgot-email').value.trim();
  const sendBtn = document.getElementById('forgot-send-btn');

  if (!email) {
    showToast('Please enter your email address.', 'warning');
    return;
  }

  sendBtn.disabled = true;
  sendBtn.textContent = 'Sending...';

  fetch('/api/auth/forgot-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email })
  })
    .then(res => res.json().then(data => ({ ok: res.ok, data })))
    .then(({ ok, data }) => {
      sendBtn.disabled = false;
      sendBtn.textContent = 'Send Reset Code';

      if (!ok) {
        showToast(data.error || 'Failed to send reset code.', 'danger');
        return;
      }

      showToast(data.message, 'info');

      // If dev_code was provided (automatic fallback)
      if (data.dev_code) {
        const banner = document.getElementById('dev-code-banner');
        banner.style.display = 'block';
        banner.innerHTML = `<strong>Verification Code:</strong> <code>${data.dev_code}</code><br><small>(Auto-filled verification code)</small>`;
        document.getElementById('forgot-code').value = data.dev_code;
      }

      document.getElementById('forgot-step-1').style.display = 'none';
      document.getElementById('forgot-step-2').style.display = 'block';
    })
    .catch(err => {
      sendBtn.disabled = false;
      sendBtn.textContent = 'Send Reset Code';
      console.error('Forgot password error:', err);
      showToast('Network error while requesting reset code.', 'danger');
    });
}

function submitPasswordReset() {
  const email = document.getElementById('forgot-email').value.trim();
  const code = document.getElementById('forgot-code').value.trim();
  const newPassword = document.getElementById('forgot-new-pw').value;
  const confirmPassword = document.getElementById('forgot-confirm-pw').value;
  const resetBtn = document.getElementById('forgot-reset-btn');

  if (!code || !newPassword) {
    showToast('Please fill in the code and new password.', 'warning');
    return;
  }

  if (newPassword.length < 6) {
    showToast('Password must be at least 6 characters long.', 'warning');
    return;
  }

  if (newPassword !== confirmPassword) {
    showToast('Passwords do not match.', 'danger');
    return;
  }

  resetBtn.disabled = true;
  resetBtn.textContent = 'Updating...';

  fetch('/api/auth/reset-password', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      email,
      code,
      new_password: newPassword,
      confirm_password: confirmPassword
    })
  })
    .then(res => res.json().then(data => ({ ok: res.ok, data })))
    .then(({ ok, data }) => {
      resetBtn.disabled = false;
      resetBtn.textContent = 'Update Password';

      if (!ok) {
        showToast(data.error || 'Failed to reset password.', 'danger');
        return;
      }

      showToast('Password reset successfully! Please sign in.', 'success');
      closeForgotModal();
      switchAuthMode('login');
      document.getElementById('login-email').value = email;
      document.getElementById('login-password').value = '';
    })
    .catch(err => {
      resetBtn.disabled = false;
      resetBtn.textContent = 'Update Password';
      console.error('Reset password error:', err);
      showToast('Network error while resetting password.', 'danger');
    });
}

function populateForm() {
  document.getElementById('height').value = state.metrics.height;
  document.getElementById('weight').value = state.metrics.weight;
  document.getElementById('age').value = state.metrics.age;
  document.getElementById('bpm').value = state.metrics.bpm;
  document.getElementById('activity-level').value = state.metrics.activityLevel;
}

// Navigation Tab Switcher
function switchTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
  document.querySelectorAll('.tab-view').forEach(view => view.classList.remove('active'));

  if (tabId === 'dashboard') {
    document.getElementById('tab-dashboard').classList.add('active');
    document.getElementById('view-dashboard').classList.add('active');
  } else if (tabId === 'database') {
    document.getElementById('tab-database').classList.add('active');
    document.getElementById('view-database').classList.add('active');
    loadRecords();
  }
}

function setECGPreset(presetType) {
  state.currentECGPreset = presetType;
  
  const buttons = document.querySelectorAll('.preset-buttons .btn');
  buttons.forEach(btn => btn.classList.remove('active'));

  const presetIndex = { 'normal': 0, 'tachy': 1, 'brady': 2, 'arrhythmia': 3 };
  if (buttons[presetIndex[presetType]]) {
    buttons[presetIndex[presetType]].classList.add('active');
  }

  let simulatedBPM = 72;
  if (presetType === 'tachy') simulatedBPM = 115;
  else if (presetType === 'brady') simulatedBPM = 45;
  else if (presetType === 'arrhythmia') simulatedBPM = 82;

  document.getElementById('bpm').value = simulatedBPM;
  state.metrics.bpm = simulatedBPM;

  startECG(presetType, simulatedBPM);

  if (document.getElementById('results-container').style.display === 'block') {
    analyzeHealth();
  }
}

function toggleSmokingInput() {
  const isSmoker = document.getElementById('smoker-select').value === '1';
  const cigsGroup = document.getElementById('cigs-input-group');
  if (cigsGroup) {
    cigsGroup.style.display = isSmoker ? 'flex' : 'none';
    if (isSmoker) {
      document.getElementById('cigs-per-day').focus();
    }
  }
}

let loadingTimer = null;
let currentProgress = 0;

function startDiagnosticLoading() {
  const placeholder = document.getElementById('results-placeholder');
  const resultsContainer = document.getElementById('results-container');
  const loadingCard = document.getElementById('results-loading');
  const progressBar = document.getElementById('analysis-progress-bar');
  const pctText = document.getElementById('loading-pct-text');
  const stageText = document.getElementById('loading-stage-text');

  if (placeholder) placeholder.style.display = 'none';
  if (resultsContainer) resultsContainer.style.display = 'none';
  if (loadingCard) loadingCard.style.display = 'block';

  currentProgress = 12;
  if (progressBar) progressBar.style.width = '12%';
  if (pctText) pctText.textContent = '12% Completed';

  const stages = [
    { pct: 30, stage: "Extracting 15 Framingham Clinical Biomarkers...", chip: 1 },
    { pct: 55, stage: "Evaluating Gradient Boosting & Calibrated RF Risk...", chip: 2 },
    { pct: 78, stage: "Consulting Google Gemini AI for Personalized Coaching...", chip: 3 },
    { pct: 92, stage: "Synthesizing Historical Health Trends & Vitals...", chip: 4 }
  ];

  let stageIdx = 0;
  if (loadingTimer) clearInterval(loadingTimer);

  loadingTimer = setInterval(() => {
    if (stageIdx < stages.length) {
      const s = stages[stageIdx];
      currentProgress = s.pct;
      if (progressBar) progressBar.style.width = `${s.pct}%`;
      if (pctText) pctText.textContent = `${s.pct}% Completed`;
      if (stageText) stageText.textContent = s.stage;

      for (let i = 1; i <= 4; i++) {
        const chip = document.getElementById(`step-chip-${i}`);
        if (chip) {
          if (i <= s.chip) chip.classList.add('active');
          else chip.classList.remove('active');
        }
      }
      stageIdx++;
    }
  }, 2200);
}

function stopDiagnosticLoading() {
  if (loadingTimer) {
    clearInterval(loadingTimer);
    loadingTimer = null;
  }
  const progressBar = document.getElementById('analysis-progress-bar');
  const pctText = document.getElementById('loading-pct-text');
  if (progressBar) progressBar.style.width = '100%';
  if (pctText) pctText.textContent = '100% Completed';
}

// REST Client: Sends metrics to Flask Backend and saves to Database
function analyzeHealth() {
  const height = parseFloat(document.getElementById('height').value);
  const weight = parseFloat(document.getElementById('weight').value);
  const age = parseInt(document.getElementById('age').value);
  const bpm = parseInt(document.getElementById('bpm').value);
  const activityLevel = document.getElementById('activity-level').value;

  if (isNaN(height) || isNaN(weight) || isNaN(age) || isNaN(bpm)) {
    showToast('Please enter all mandatory health metrics marked with *', 'warning');
    return;
  }

  const smoker = document.getElementById('smoker-select').value === '1';
  const cigsPerDayVal = document.getElementById('cigs-per-day').value.trim();
  const cigsPerDay = cigsPerDayVal !== '' ? parseFloat(cigsPerDayVal) : (smoker ? 10 : 0);
  const diabetes = document.getElementById('diabetes-select').value === '1';

  // Optional lab metrics
  const glucoseVal = document.getElementById('glucose').value.trim();
  const sysBPVal = document.getElementById('sys-bp').value.trim();
  const cholVal = document.getElementById('cholesterol').value.trim();
  const bpMeds = document.getElementById('bp-meds').value === '1';

  const glucose = glucoseVal !== '' ? parseFloat(glucoseVal) : null;
  const sysBP = sysBPVal !== '' ? parseFloat(sysBPVal) : null;
  const cholesterol = cholVal !== '' ? parseFloat(cholVal) : null;

  // Update State
  state.metrics = { 
    height, weight, age, bpm, activityLevel,
    smoker, cigsPerDay, diabetes, glucose, sysBP, cholesterol, bpMeds
  };
  localStorage.setItem('pg_database_user_metrics', JSON.stringify(state.metrics));

  // Package payload (with patient name for database storage)
  const payload = {
    name: state.user ? state.user.name : 'Patient',
    ...state.metrics
  };

  const submitBtn = document.querySelector('#vitals-form button[type="submit"]');
  const originalBtnHTML = submitBtn ? submitBtn.innerHTML : '';
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.innerHTML = `
      <span class="btn-spinner"></span>
      <span>Analyzing with Gemini AI...</span>
    `;
  }

  startDiagnosticLoading();

  // Trigger POST request to Python backend
  fetch('/api/analyze', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(payload)
  })
  .then(response => {
    if (!response.ok) throw new Error('API request failed');
    return response.json();
  })
  .then(data => {
    stopDiagnosticLoading();

    setTimeout(() => {
      const loadingCard = document.getElementById('results-loading');
      if (loadingCard) loadingCard.style.display = 'none';

      renderAnalysisResults(data);
      showToast(`Diagnostics saved to your personal history!`, 'success');
      
      // Refresh history records table
      loadRecords();

      // Sync ECG simulation state to match the returned heart diagnosis
      let currentPreset = 'normal';
      if (bpm > 100) currentPreset = 'tachy';
      else if (bpm < 60) currentPreset = 'brady';
      startECG(currentPreset, bpm);

      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalBtnHTML;
      }
    }, 350);
  })
  .catch(error => {
    stopDiagnosticLoading();
    const loadingCard = document.getElementById('results-loading');
    const placeholder = document.getElementById('results-placeholder');
    if (loadingCard) loadingCard.style.display = 'none';
    if (placeholder) placeholder.style.display = 'block';

    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = originalBtnHTML;
    }
    console.error('Error analyzing health:', error);
    showToast('Failed to connect to health assessment services.', 'danger');
  });
}

// Renders calculations received from the Python backend
function renderAnalysisResults(data) {
  document.getElementById('res-bmi-val').textContent = data.bmi.val;
  
  const bmiTag = document.getElementById('res-bmi-tag');
  bmiTag.textContent = data.bmi.category;
  bmiTag.className = `block-tag ${data.bmi.badge_class}`;

  // Target Healthy Weight Guidance
  const targetWrap = document.getElementById('res-bmi-target-wrap');
  const targetVal = document.getElementById('res-bmi-target-val');
  const targetPill = document.getElementById('res-bmi-target-pill');
  if (targetWrap && data.bmi.min_ideal_kg && data.bmi.max_ideal_kg) {
    targetWrap.style.display = 'flex';
    targetVal.textContent = `${data.bmi.min_ideal_kg} – ${data.bmi.max_ideal_kg} kg`;
    
    if (data.bmi.category === 'Normal') {
      targetPill.textContent = '✓ Optimal weight';
      targetPill.className = 'target-weight-pill pill-success';
    } else if (data.bmi.category === 'Underweight') {
      targetPill.textContent = `+${data.bmi.diff_kg} kg needed`;
      targetPill.className = 'target-weight-pill pill-warning';
    } else {
      targetPill.textContent = `-${data.bmi.diff_kg} kg needed`;
      targetPill.className = 'target-weight-pill pill-danger';
    }
  }

  const heartVal = document.getElementById('res-heart-val');
  heartVal.textContent = data.heart.status;
  heartVal.className = `block-val text-${data.heart.badge_class.split('-')[1]}`;
  
  const heartTag = document.getElementById('res-heart-tag');
  const healthyKeywords = ['Normal', 'Athletic'];
  const isHealthy = healthyKeywords.some(k => data.heart.status.includes(k));
  heartTag.textContent = isHealthy ? 'Healthy resting' : 'Review Vitals';
  heartTag.className = `block-tag ${data.heart.badge_class}`;

  document.getElementById('res-risk-val').textContent = data.risk.level;
  const riskBar = document.getElementById('res-risk-bar');
  riskBar.className = `risk-bar ${data.risk.class}`;

  const weightAdvice = data.bmi.target_advice ? ` ${data.bmi.target_advice}.` : '';
  document.getElementById('res-diagnostic-summary').textContent = 
    `Diagnostic Insight: Patient profile shows a BMI of ${data.bmi.val} (${data.bmi.category}).${weightAdvice} ${data.heart.description}`;

  document.getElementById('comp-bpm-ideal').textContent = data.stats.ideal_bpm;
  document.getElementById('comp-bpm-exercise').textContent = data.stats.exercise_bpm;
  document.getElementById('comp-bpm-max').textContent = `${data.stats.max_hr} BPM`;

  // Render Engine Badge
  const engineBadge = document.getElementById('rec-engine-badge');
  const engineText = document.getElementById('rec-engine-text');
  if (data.recommendations && data.recommendations.engine) {
    engineText.textContent = data.recommendations.engine;
    if (data.recommendations.is_ai) {
      engineBadge.className = 'engine-badge badge-ai';
      engineBadge.title = 'Generated dynamically via Google Gemini Flash AI';
    } else {
      engineBadge.className = 'engine-badge badge-rules';
      engineBadge.title = 'Generated via Clinical Rule Engine';
    }
  }

  renderList('rec-diet-list', data.recommendations.diet);
  renderList('rec-exercise-list', data.recommendations.exercise);
  renderList('rec-lifestyle-list', data.recommendations.lifestyle);
  renderList('rec-warning-list', data.recommendations.warnings);

  const warningSection = document.getElementById('warning-section');
  if (data.recommendations.warnings && data.recommendations.warnings.length > 0) {
    warningSection.style.borderColor = 'var(--color-danger)';
    warningSection.style.background = 'rgba(239, 68, 68, 0.04)';
  } else {
    warningSection.style.borderColor = 'rgba(255, 255, 255, 0.04)';
    warningSection.style.background = 'rgba(255, 255, 255, 0.02)';
  }

  document.getElementById('results-placeholder').style.display = 'none';
  document.getElementById('results-container').style.display = 'block';

  if (window.innerWidth <= 1100) {
    document.getElementById('results-container').scrollIntoView({ behavior: 'smooth' });
  }
}

function renderList(elementId, items) {
  const container = document.getElementById(elementId);
  container.innerHTML = '';
  (items || []).forEach(item => {
    container.innerHTML += `<li>${item}</li>`;
  });
}

// ==========================================================================
// Model Biomarkers Info Modal
// ==========================================================================

function openModelInfoModal() {
  const modal = document.getElementById('model-info-modal');
  modal.style.display = 'flex';
  fetchModelInfo();
}

function closeModelInfoModal() {
  document.getElementById('model-info-modal').style.display = 'none';
}

let cachedModelInfo = null;
function fetchModelInfo() {
  if (cachedModelInfo) {
    renderModelInfo(cachedModelInfo);
    return;
  }
  const tbody = document.getElementById('modal-features-tbody');
  if (tbody) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted" style="padding: 24px;">Loading 15 trained biomarker specifications...</td></tr>`;
  }

  fetch('/api/model-info')
    .then(res => {
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      return res.json();
    })
    .then(data => {
      cachedModelInfo = data;
      renderModelInfo(data);
    })
    .catch(err => {
      console.error('Failed to load model info:', err);
      if (tbody) {
        tbody.innerHTML = `<tr><td colspan="6" class="text-center text-danger" style="padding: 24px;">Failed to fetch model biomarkers. Error: ${escapeHtml(err.message)}</td></tr>`;
      }
    });
}

function renderModelInfo(data) {
  const accuracy = (data && data.accuracy) ? data.accuracy : '84.15%';
  const features = (data && data.features) ? data.features : [];

  const accEl = document.getElementById('modal-model-acc');
  const countEl = document.getElementById('modal-feature-count');
  if (accEl) accEl.textContent = accuracy;
  if (countEl) countEl.textContent = `${features.length} Features`;

  const tbody = document.getElementById('modal-features-tbody');
  if (!tbody) return;
  tbody.innerHTML = '';
  
  if (features.length === 0) {
    tbody.innerHTML = `<tr><td colspan="6" class="text-center text-muted" style="padding: 24px;">No biomarker specifications available.</td></tr>`;
    return;
  }

  features.forEach((feat, idx) => {
    const isReq = Boolean(feat.required);
    const reqBadge = isReq ? 
      `<span class="badge-req">Mandatory *</span>` : 
      `<span class="badge-opt">Optional</span>`;

    const name = escapeHtml(feat.name || 'Biomarker');
    const colName = feat.column ? `<br><small class="text-muted" style="font-family: monospace;">(${escapeHtml(feat.column)})</small>` : '';
    const cat = escapeHtml(feat.category || feat.type || 'Clinical');
    const defaultVal = escapeHtml(feat.default_val || feat.unit || '--');
    const desc = escapeHtml(feat.description || feat.desc || '');

    tbody.innerHTML += `
      <tr>
        <td><span class="feat-num">${idx + 1}</span></td>
        <td><strong>${name}</strong>${colName}</td>
        <td><span class="feat-cat">${cat}</span></td>
        <td>${reqBadge}</td>
        <td><code class="feat-code">${defaultVal}</code></td>
        <td class="feat-desc">${desc}</td>
      </tr>
    `;
  });
}

// ==========================================================================
// Database API Calls
// ==========================================================================

function loadRecords() {
  const tbody = document.getElementById('db-table-body');
  tbody.innerHTML = `<tr><td colspan="10" class="text-center text-muted">Retrieving patient database records...</td></tr>`;

  fetch('/api/records')
  .then(response => {
    if (!response.ok) throw new Error('Failed to fetch records');
    return response.json();
  })
  .then(data => {
    cachedRecords = data;
    renderRecordsTable(data);
  })
  .catch(error => {
    console.error('Error loading records:', error);
    showToast('Failed to load database records', 'danger');
  });
}

function renderRecordsTable(records) {
  const tbody = document.getElementById('db-table-body');
  
  if (!records || records.length === 0) {
    tbody.innerHTML = `<tr><td colspan="10" class="text-center text-muted">No records found. Run a vital diagnostic on the left to add a patient.</td></tr>`;
    return;
  }

  tbody.innerHTML = '';
  records.forEach(row => {
    const dateStr = new Date(row.created_at).toLocaleDateString([], { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
    const riskClass = (row.risk_level || '').toLowerCase().includes('high') ? 'badge-danger' : 
                      (row.risk_level || '').toLowerCase().includes('mod') ? 'badge-warning' : 'badge-normal';

    const smokerBadge = row.smoker ? 
      `<span class="badge-tag badge-warning">Smoker (${row.cigs_per_day || 0}/d)</span>` : 
      `<span class="badge-tag badge-subtle">No</span>`;

    const diabetesBadge = row.diabetes ? 
      `<span class="badge-tag badge-danger">Yes</span>` : 
      `<span class="badge-tag badge-subtle">No</span>`;

    const glucoseStr = (row.glucose !== null && row.glucose !== undefined) ? 
      `<strong>${row.glucose}</strong> <small class="text-muted">mg/dL</small>` : `<span class="text-muted">--</span>`;

    const sysBPStr = (row.sys_bp !== null && row.sys_bp !== undefined) ? 
      `<strong>${row.sys_bp}</strong> <small class="text-muted">mmHg</small>` : `<span class="text-muted">--</span>`;

    tbody.innerHTML += `
      <tr>
        <td><small class="text-muted">${dateStr}</small></td>
        <td><strong>${escapeHtml(row.name)}</strong></td>
        <td>${row.age}y &bull; <small class="text-muted">BMI</small> ${row.bmi}</td>
        <td><strong>${row.bpm}</strong> <small class="text-muted">BPM</small></td>
        <td>${smokerBadge}</td>
        <td>${diabetesBadge}</td>
        <td>${glucoseStr}</td>
        <td>${sysBPStr}</td>
        <td><span class="block-tag ${riskClass}" style="margin-top:0">${row.risk_level}</span></td>
        <td>
          <button class="btn-danger-xs" onclick="deleteRecord('${row.id}')">Delete</button>
        </td>
      </tr>
    `;
  });
}

function deleteRecord(id) {
  if (!confirm('Are you sure you want to permanently delete this health assessment record?')) return;

  fetch(`/api/records/${id}`, {
    method: 'DELETE'
  })
  .then(response => {
    if (!response.ok) throw new Error('Delete failed');
    return response.json();
  })
  .then(data => {
    if (data.success) {
      showToast('Health assessment deleted successfully!', 'success');
      loadRecords();
    } else {
      showToast(data.error || 'Failed to delete record', 'danger');
    }
  })
  .catch(error => {
    console.error('Error deleting record:', error);
    showToast('Failed to delete health record', 'danger');
  });
}

function filterRecords() {
  const query = document.getElementById('search-input').value.toLowerCase();
  const filtered = cachedRecords.filter(r => 
    (r.name && r.name.toLowerCase().includes(query)) ||
    (r.risk_level && r.risk_level.toLowerCase().includes(query)) ||
    (r.created_at && r.created_at.toLowerCase().includes(query))
  );
  renderRecordsTable(filtered);
}

function exportDatabaseCSV() {
  if (cachedRecords.length === 0) {
    showToast('No records available to export', 'danger');
    return;
  }

  let csvContent = "data:text/csv;charset=utf-8,";
  csvContent += "ID,Date Created,Patient Name,Age,Height (cm),Weight (kg),BPM,Activity,BMI,Smoker,Cigs/Day,Diabetes,Glucose,Sys BP,ML Risk Level\n";

  cachedRecords.forEach(row => {
    const line = [
      row.id,
      row.created_at,
      `"${(row.name || '').replace(/"/g, '""')}"`,
      row.age,
      row.height,
      row.weight,
      row.bpm,
      row.activity,
      row.bmi,
      row.smoker ? 'Yes' : 'No',
      row.cigs_per_day || 0,
      row.diabetes ? 'Yes' : 'No',
      row.glucose || '',
      row.sys_bp || '',
      `"${(row.risk_level || '').replace(/"/g, '""')}"`
    ].join(",");
    csvContent += line + "\n";
  });

  const encodedUri = encodeURI(csvContent);
  const link = document.createElement("a");
  link.setAttribute("href", encodedUri);
  link.setAttribute("download", `PulseGuard_Health_Records_${new Date().toISOString().slice(0, 10)}.csv`);
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  showToast('Database records exported as CSV successfully!', 'success');
}

// Helper Utilities
function escapeHtml(str) {
  return str.replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
}

function showToast(message, type = 'success') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  
  setTimeout(() => {
    toast.remove();
  }, 3000);
}

// ==========================================================================
// ECG Wave Rendering Math & Simulation Loop
// ==========================================================================
let ecgX = 0;
const ecgPoints = [];
let lastBeatTime = 0;
let beatInterval = 1000;
let isBeating = false;
let beatProgress = 0;

function startECG(preset, bpmInput = 72) {
  stopECG();
  
  state.ecgActive = true;
  ecgX = 0;
  beatInterval = (60 / bpmInput) * 1000;
  
  const stateText = document.getElementById('ecg-state-text');
  const bpmText = document.getElementById('ecg-bpm-text');
  
  bpmText.textContent = `${bpmInput} BPM`;
  
  if (preset === 'normal') {
    stateText.textContent = 'NORMAL SINUS';
    stateText.className = 'val text-normal';
  } else if (preset === 'tachy') {
    stateText.textContent = 'TACHYCARDIA';
    stateText.className = 'val text-danger';
  } else if (preset === 'brady') {
    stateText.textContent = 'BRADYCARDIA';
    stateText.className = 'val text-warning';
  } else if (preset === 'arrhythmia') {
    stateText.textContent = 'ARRHYTHMIA';
    stateText.className = 'val text-danger';
  }

  ecgPoints.length = 0;
  lastBeatTime = performance.now();
  renderECG();
}

function stopECG() {
  state.ecgActive = false;
  if (animationFrameId) {
    cancelAnimationFrame(animationFrameId);
    animationFrameId = null;
  }
}

function getQRSAmplitude(progress) {
  if (progress < 0.15) {
    const t = progress / 0.15;
    return Math.sin(t * Math.PI) * 4;
  } 
  else if (progress < 0.22) {
    return 0;
  } 
  else if (progress < 0.26) {
    const t = (progress - 0.22) / 0.04;
    return -t * 6;
  } 
  else if (progress < 0.32) {
    const t = (progress - 0.26) / 0.06;
    if (t < 0.5) {
      return -6 + (t * 2) * 56;
    } else {
      return 50 - ((t - 0.5) * 2) * 65;
    }
  } 
  else if (progress < 0.37) {
    const t = (progress - 0.32) / 0.05;
    return -15 + t * 15;
  } 
  else if (progress < 0.43) {
    return 0;
  } 
  else if (progress < 0.65) {
    const t = (progress - 0.43) / 0.22;
    return Math.sin(t * Math.PI) * 10;
  } 
  return 0;
}

function renderECG() {
  if (!state.ecgActive) return;

  const w = canvas.width / (window.devicePixelRatio || 1);
  const h = canvas.height / (window.devicePixelRatio || 1);
  const centerY = h / 2;

  ctx.fillStyle = '#030712';
  ctx.fillRect(0, 0, w, h);

  ctx.strokeStyle = 'rgba(0, 242, 254, 0.04)';
  ctx.lineWidth = 1;
  const gridSize = 15;
  
  for (let x = 0; x < w; x += gridSize) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();
  }
  for (let y = 0; y < h; y += gridSize) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }

  const currentTime = performance.now();
  let timeSinceLastBeat = currentTime - lastBeatTime;

  if (state.currentECGPreset === 'arrhythmia' && timeSinceLastBeat >= beatInterval) {
    const variation = (Math.random() - 0.5) * 600;
    const baseBpm = state.metrics.bpm || 80;
    const targetInterval = (60 / baseBpm) * 1000;
    beatInterval = Math.max(450, targetInterval + variation);
  }

  if (timeSinceLastBeat >= beatInterval) {
    isBeating = true;
    lastBeatTime = currentTime;
    timeSinceLastBeat = 0;
  }

  let amplitude = 0;
  if (isBeating) {
    const beatDuration = 450;
    beatProgress = timeSinceLastBeat / beatDuration;
    
    if (beatProgress >= 1.0) {
      isBeating = false;
      amplitude = 0;
    } else {
      amplitude = getQRSAmplitude(beatProgress);
    }
  }

  const noise = (Math.random() - 0.5) * 0.5;
  const targetY = centerY - (amplitude * 1.6) + noise;

  ecgX += 2.0;
  if (ecgX > w) {
    ecgX = 0;
  }

  ecgPoints[Math.floor(ecgX)] = targetY;

  ctx.lineWidth = 2;
  ctx.strokeStyle = state.currentECGPreset === 'arrhythmia' || state.currentECGPreset === 'tachy' 
    ? 'hsl(351, 89%, 60%)' 
    : 'hsl(184, 100%, 50%)';
  ctx.shadowBlur = 8;
  ctx.shadowColor = ctx.strokeStyle;
  
  ctx.beginPath();
  let first = true;
  
  for (let i = 0; i < w; i++) {
    if (Math.abs(i - ecgX) < 22 && i > ecgX) {
      continue;
    }
    
    const yVal = ecgPoints[i];
    if (yVal !== undefined) {
      if (first) {
        ctx.moveTo(i, yVal);
        first = false;
      } else {
        ctx.lineTo(i, yVal);
      }
    }
  }
  ctx.stroke();
  
  ctx.shadowBlur = 12;
  ctx.fillStyle = '#ffffff';
  ctx.beginPath();
  ctx.arc(ecgX, targetY, 3, 0, Math.PI * 2);
  ctx.fill();

  ctx.shadowBlur = 0;
  animationFrameId = requestAnimationFrame(renderECG);
}

// ==========================================================================
// Safe HTML Escaping Utility
// ==========================================================================
function escapeHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
