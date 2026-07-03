/* ==========================================================================
   PulseGuard AI - Frontend Controller (Flask Interface)
   ========================================================================== */

// App State
const state = {
  userName: '',
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
const welcomeScreen = document.getElementById('welcome-screen');
const dashboardScreen = document.getElementById('dashboard-screen');
const welcomeForm = document.getElementById('welcome-form');
const vitalsForm = document.getElementById('vitals-form');
const displayName = document.getElementById('display-name');
const avatarInitials = document.getElementById('avatar-initials');

// Canvas Setup for ECG Simulator
const canvas = document.getElementById('ecg-canvas');
const ctx = canvas.getContext('2d');
let animationFrameId = null;

// Initialization on Load
window.addEventListener('DOMContentLoaded', () => {
  resizeCanvas();
  window.addEventListener('resize', resizeCanvas);

  const savedName = localStorage.getItem('pg_python_user_name');
  const savedMetrics = localStorage.getItem('pg_python_user_metrics');

  if (savedName) {
    state.userName = savedName;
    if (savedMetrics) {
      state.metrics = JSON.parse(savedMetrics);
      populateForm();
    }
    showScreen('dashboard');
    if (state.metrics.bpm) {
      analyzeHealth();
    } else {
      startECG('normal');
    }
  }
});

function resizeCanvas() {
  const dpr = window.devicePixelRatio || 1;
  const rect = canvas.getBoundingClientRect();
  canvas.width = rect.width * dpr;
  canvas.height = rect.height * dpr;
  ctx.scale(dpr, dpr);
}

function showScreen(screenId) {
  if (screenId === 'welcome') {
    welcomeScreen.classList.add('active');
    dashboardScreen.classList.remove('remove'); // safety reset
    welcomeScreen.style.display = 'block';
    dashboardScreen.style.display = 'none';
  } else if (screenId === 'dashboard') {
    welcomeScreen.style.display = 'none';
    dashboardScreen.style.display = 'block';
    setTimeout(() => {
      dashboardScreen.classList.add('active');
    }, 50);
    
    displayName.textContent = state.userName;
    avatarInitials.textContent = state.userName.substring(0, 2).toUpperCase();
  }
}

function proceedToDashboard() {
  const nameInput = document.getElementById('user-name');
  if (nameInput.value.trim() === '') return;

  state.userName = nameInput.value.trim();
  localStorage.setItem('pg_python_user_name', state.userName);
  
  showScreen('dashboard');
  startECG('normal');
}

function resetApp() {
  localStorage.removeItem('pg_python_user_name');
  localStorage.removeItem('pg_python_user_metrics');
  
  state.userName = '';
  state.metrics = {
    height: null,
    weight: null,
    age: null,
    bpm: null,
    activityLevel: 'moderate'
  };
  
  document.getElementById('user-name').value = '';
  vitalsForm.reset();
  
  document.getElementById('results-container').style.display = 'none';
  document.getElementById('results-placeholder').style.display = 'flex';

  showScreen('welcome');
  stopECG();
}

function populateForm() {
  document.getElementById('height').value = state.metrics.height;
  document.getElementById('weight').value = state.metrics.weight;
  document.getElementById('age').value = state.metrics.age;
  document.getElementById('bpm').value = state.metrics.bpm;
  document.getElementById('activity-level').value = state.metrics.activityLevel;
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

// REST Client: Sends metrics to Flask Backend
function analyzeHealth() {
  const height = parseFloat(document.getElementById('height').value);
  const weight = parseFloat(document.getElementById('weight').value);
  const age = parseInt(document.getElementById('age').value);
  const bpm = parseInt(document.getElementById('bpm').value);
  const activityLevel = document.getElementById('activity-level').value;

  if (isNaN(height) || isNaN(weight) || isNaN(age) || isNaN(bpm)) {
    alert('Please enter all health metric details.');
    return;
  }

  // Update State
  state.metrics = { height, weight, age, bpm, activityLevel };
  localStorage.setItem('pg_python_user_metrics', JSON.stringify(state.metrics));

  // Trigger POST request to Python backend
  fetch('/api/analyze', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(state.metrics)
  })
  .then(response => {
    if (!response.ok) throw new Error('API request failed');
    return response.json();
  })
  .then(data => {
    renderAnalysisResults(data);
    
    // Sync ECG simulation state to match the returned heart diagnosis
    let currentPreset = 'normal';
    if (bpm > 100) currentPreset = 'tachy';
    else if (bpm < 60) currentPreset = 'brady';
    
    startECG(currentPreset, bpm);
  })
  .catch(error => {
    console.error('Error analyzing health:', error);
    alert('Failed to connect to the Python health analysis service.');
  });
}

// Renders calculations received from the Python backend
function renderAnalysisResults(data) {
  // Sync basic index cards
  document.getElementById('res-bmi-val').textContent = data.bmi.val;
  
  const bmiTag = document.getElementById('res-bmi-tag');
  bmiTag.textContent = data.bmi.category;
  bmiTag.className = `block-tag ${data.bmi.badge_class}`;

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

  // Sync diagnostic values
  document.getElementById('res-diagnostic-summary').textContent = 
    `Diagnostic Insight: Age ${state.metrics.age} physical profile shows a BMI of ${data.bmi.val} (${data.bmi.category}). ${data.heart.description}`;

  document.getElementById('comp-bpm-ideal').textContent = data.stats.ideal_bpm;
  document.getElementById('comp-bpm-exercise').textContent = data.stats.exercise_bpm;
  document.getElementById('comp-bpm-max').textContent = `${data.stats.max_hr} BPM`;

  // Render list guidelines
  renderList('rec-diet-list', data.recommendations.diet);
  renderList('rec-exercise-list', data.recommendations.exercise);
  renderList('rec-lifestyle-list', data.recommendations.lifestyle);
  renderList('rec-warning-list', data.recommendations.warnings);

  // Sync warnings style
  const warningSection = document.getElementById('warning-section');
  if (data.recommendations.has_warnings) {
    warningSection.style.borderColor = 'var(--color-danger)';
    warningSection.style.background = 'rgba(239, 68, 68, 0.04)';
  } else {
    warningSection.style.borderColor = 'rgba(255, 255, 255, 0.04)';
    warningSection.style.background = 'rgba(255, 255, 255, 0.02)';
  }

  // Show Results layout
  document.getElementById('results-placeholder').style.display = 'none';
  document.getElementById('results-container').style.display = 'block';

  if (window.innerWidth <= 1100) {
    document.getElementById('results-container').scrollIntoView({ behavior: 'smooth' });
  }
}

function renderList(elementId, items) {
  const container = document.getElementById(elementId);
  container.innerHTML = '';
  items.forEach(item => {
    container.innerHTML += `<li>${item}</li>`;
  });
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
