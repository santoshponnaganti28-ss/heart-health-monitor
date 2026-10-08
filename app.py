import math
import os
import json
import pickle
import sqlite3
import shutil
import secrets
import smtplib
import requests
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import numpy as np
from flask import Flask, render_template, request, jsonify, session
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import pymongo
from bson import ObjectId

# Get absolute path of the directory containing app.py
base_dir = os.path.dirname(os.path.abspath(__file__))

# Load environment variables from .env
load_dotenv(os.path.join(base_dir, '.env'))

# Initialize Flask with standard templates and static folders
app = Flask(
    __name__,
    template_folder=os.path.join(base_dir, 'templates'),
    static_folder=os.path.join(base_dir, 'static')
)
app.secret_key = os.environ.get('SECRET_KEY', 'pulseguard-ai-secret-2026-key-prod')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# ==========================================================================
# Database Setup: MongoDB Atlas (with SQLite Fallback)
# ==========================================================================
DATABASE_PATH = os.path.join(base_dir, 'patients.db')
MONGO_URI = os.environ.get('MONGO_DB', '').strip()
mongo_client = None
mongo_db = None
use_mongo = False

def init_sqlite_db():
    """Initializes SQLite database with users and patients tables."""
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            reset_code TEXT,
            reset_expiry TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            name TEXT NOT NULL,
            age INTEGER NOT NULL,
            height REAL NOT NULL,
            weight REAL NOT NULL,
            bpm INTEGER NOT NULL,
            activity TEXT NOT NULL,
            bmi REAL NOT NULL,
            risk_level TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    # Check if user_id column exists in existing SQLite db (migration)
    cursor.execute("PRAGMA table_info(patients)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'user_id' not in columns:
        cursor.execute("ALTER TABLE patients ADD COLUMN user_id TEXT")
    conn.commit()
    conn.close()

def init_mongo_db():
    global mongo_client, mongo_db, use_mongo
    if not MONGO_URI:
        print("[INFO] MONGO_DB not set in .env. Using SQLite fallback.", flush=True)
        return False
    if '<db_password>' in MONGO_URI:
        print("[WARNING] MONGO_DB contains '<db_password>' placeholder. Please replace it with your actual password in .env!", flush=True)
        return False
    try:
        mongo_client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        # Test connection with ping
        mongo_client.admin.command('ping')
        db_name = os.environ.get('MONGO_DB_NAME', 'pulseguard')
        mongo_db = mongo_client[db_name]
        # Create indexes
        mongo_db['users'].create_index('email', unique=True)
        mongo_db['records'].create_index('user_id')
        use_mongo = True
        print(f"[SUCCESS] Connected to MongoDB Atlas! Database: '{db_name}'", flush=True)
        return True
    except Exception as e:
        print(f"[WARNING] MongoDB Atlas connection error ({e}). Using SQLite fallback.", flush=True)
        use_mongo = False
        return False

# Initialize databases
init_sqlite_db()
init_mongo_db()

# ==========================================================================
# SMTP Email Dispatcher (Gmail SMTP)
# ==========================================================================
def send_reset_email(to_email, reset_code):
    """Sends a 6-digit password reset code via Gmail SMTP."""
    smtp_email = os.environ.get('SMTP_EMAIL')
    smtp_password = os.environ.get('SMTP_PASSWORD')
    
    if not smtp_email or not smtp_password:
        print(f"\n[DEV MODE] SMTP not configured. Verification code for {to_email} is: {reset_code}\n", flush=True)
        return True, "DEV_MODE"
        
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'PulseGuard AI - Password Reset Code'
        msg['From'] = f"PulseGuard AI <{smtp_email}>"
        msg['To'] = to_email
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
          <meta charset="utf-8">
        </head>
        <body style="margin: 0; padding: 0; background-color: #0b0f19; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
          <table width="100%" cellpadding="0" cellspacing="0" style="padding: 40px 20px;">
            <tr>
              <td align="center">
                <table width="100%" max-width="560px" style="max-width: 560px; background: #131b2e; border: 1px solid #1f2d4d; border-radius: 16px; overflow: hidden; box-shadow: 0 10px 40px rgba(0,0,0,0.5);">
                  <tr>
                    <td style="padding: 32px 32px 20px 32px; text-align: center; border-bottom: 1px solid #1f2d4d;">
                      <h1 style="margin: 0; font-size: 26px; font-weight: 800; color: #f87171; letter-spacing: -0.5px;">PulseGuard <span style="color: #60a5fa;">AI</span></h1>
                    </td>
                  </tr>
                  <tr>
                    <td style="padding: 32px;">
                      <h2 style="margin: 0 0 12px 0; color: #f1f5f9; font-size: 20px; font-weight: 700;">Password Reset Request</h2>
                      <p style="margin: 0 0 24px 0; color: #cbd5e1; font-size: 14px; line-height: 1.6;">
                        You requested to reset your password for PulseGuard AI. Use the 6-digit verification code below to authorize your new password:
                      </p>
                      <div style="text-align: center; margin: 30px 0;">
                        <span style="display: inline-block; font-size: 36px; font-weight: 800; letter-spacing: 8px; color: #38bdf8; background: #071226; padding: 14px 28px; border-radius: 10px; border: 1px solid #0284c7; text-shadow: 0 0 20px rgba(56,189,248,0.4);">
                          {reset_code}
                        </span>
                      </div>
                      <p style="margin: 24px 0 0 0; color: #94a3b8; font-size: 13px; line-height: 1.5;">
                        This code is valid for <strong>15 minutes</strong>. If you did not make this request, please disregard this email and your password will remain unchanged.
                      </p>
                    </td>
                  </tr>
                  <tr>
                    <td style="padding: 20px 32px; background: #0c1220; text-align: center; border-top: 1px solid #1f2d4d; color: #64748b; font-size: 12px;">
                      &copy; 2026 PulseGuard AI. Secure Cardiology Management.
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
          </table>
        </body>
        </html>
        """
        msg.attach(MIMEText(html_content, 'html'))
        
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(smtp_email, smtp_password)
            server.sendmail(smtp_email, to_email, msg.as_string())
            
        return True, "SENT"
    except Exception as e:
        print(f"[ERROR] SMTP sending failed: {e}", flush=True)
        return False, str(e)

# ==========================================================================
# Machine Learning Model Loading
# ==========================================================================
ml_model = None
ml_scaler = None

model_path = os.path.join(base_dir, 'heart_model.pkl')
scaler_path = os.path.join(base_dir, 'scaler.pkl')

if os.path.exists(model_path) and os.path.exists(scaler_path):
    try:
        with open(model_path, 'rb') as f:
            ml_model = pickle.load(f)
        with open(scaler_path, 'rb') as f:
            ml_scaler = pickle.load(f)
        print("[SUCCESS] Machine learning Random Forest model loaded successfully!", flush=True)
    except Exception as e:
        print(f"[WARNING] Failed to load ML model: {e}", flush=True)
else:
    print("[WARNING] heart_model.pkl or scaler.pkl not found! Running in fallback mode.", flush=True)

# ==========================================================================
# Clinical Biomarkers & 15-Feature Extraction Pipeline
# ==========================================================================

CLINICAL_DEFAULTS = {
    'sys_bp': 120.0,
    'glucose': 85.0,
    'tot_chol': 200.0,
    'cigs_per_day': 0.0,
    'bp_meds': 0.0,
    'diabetes': 0.0,
    'current_smoker': 0.0
}

FEATURE_DETAILS = [
    {
        "name": "Age",
        "column": "age",
        "category": "Demographic",
        "required": True,
        "default_val": "Patient Input",
        "unit": "Years",
        "description": "Chronological age in years; primary non-modifiable risk determinant of vascular stiffening."
    },
    {
        "name": "Body Mass Index (BMI)",
        "column": "BMI",
        "category": "Anthropometric",
        "required": True,
        "default_val": "Derived (Height/Weight)",
        "unit": "kg/m²",
        "description": "Calculated from height and weight; clinical indicator of visceral adiposity and myocardial load."
    },
    {
        "name": "Resting Heart Rate",
        "column": "heartRate",
        "category": "Vital Sign",
        "required": True,
        "default_val": "Patient Input",
        "unit": "BPM",
        "description": "Basal myocardial pulse rate; resting tachycardia (>90 BPM) significantly elevates cardiac strain."
    },
    {
        "name": "Current Smoker Status",
        "column": "currentSmoker",
        "category": "Behavioral",
        "required": True,
        "default_val": "Patient Input",
        "unit": "Yes / No",
        "description": "Active tobacco inhalation; induces endothelial oxidative damage and coronary vasoconstriction."
    },
    {
        "name": "Cigarettes Per Day",
        "column": "cigsPerDay",
        "category": "Behavioral",
        "required": True,
        "default_val": "0 (or patient dose)",
        "unit": "Count/Day",
        "description": "Daily quantitative nicotine exposure; dose-dependent accelerator of coronary plaque formation."
    },
    {
        "name": "Diagnosed Diabetes",
        "column": "diabetes",
        "category": "Endocrine",
        "required": True,
        "default_val": "Patient Input",
        "unit": "Yes / No",
        "description": "Clinical diabetes diagnosis; independently doubles 10-year risk of major atherosclerotic events."
    },
    {
        "name": "Systolic Blood Pressure",
        "column": "sysBP",
        "category": "Hemodynamics",
        "required": False,
        "default_val": "120.0 mmHg (Standard)",
        "unit": "mmHg",
        "description": "Peak arterial pressure during ventricular systole. Defaults to healthy 120 mmHg if unmeasured."
    },
    {
        "name": "Fasting Blood Glucose",
        "column": "glucose",
        "category": "Metabolic",
        "required": False,
        "default_val": "85.0 mg/dL (Standard)",
        "unit": "mg/dL",
        "description": "Circulating fasting glycemic concentration. Defaults to healthy 85 mg/dL if unmeasured."
    },
    {
        "name": "Total Serum Cholesterol",
        "column": "totChol",
        "category": "Lipid Profile",
        "required": False,
        "default_val": "200.0 mg/dL (Standard)",
        "unit": "mg/dL",
        "description": "Total circulating serum cholesterol. Defaults to healthy 200 mg/dL if unmeasured."
    },
    {
        "name": "BP Medication Use",
        "column": "BPMeds",
        "category": "Pharmacotherapy",
        "required": False,
        "default_val": "No (0.0)",
        "unit": "Yes / No",
        "description": "Antihypertensive pharmaceutical management; indicates pre-existing vascular treatment."
    },
    {
        "name": "Vascular Aging Acceleration",
        "column": "age_sq",
        "category": "Engineered Bio-Metric",
        "required": False,
        "default_val": "(Age / 50)²",
        "unit": "Index",
        "description": "Quadratic non-linear transformation capturing exponential arterial stiffness beyond age 50."
    },
    {
        "name": "Adiposity Category Index",
        "column": "bmi_cat",
        "category": "Engineered Bio-Metric",
        "required": False,
        "default_val": "WHO Grade (0-3)",
        "unit": "Tier",
        "description": "Standardized WHO obesity index (Underweight=0, Normal=1, Overweight=2, Obese=3)."
    },
    {
        "name": "Heart Rate Reserve Strain",
        "column": "hr_ratio",
        "category": "Engineered Bio-Metric",
        "required": False,
        "default_val": "BPM / (220 - Age)",
        "unit": "Ratio",
        "description": "Fraction of theoretical maximal cardiovascular reserve consumed at rest."
    },
    {
        "name": "Arterial Pressure Strain",
        "column": "bp_strain",
        "category": "Engineered Bio-Metric",
        "required": False,
        "default_val": "sysBP / 120.0",
        "unit": "Ratio",
        "description": "Hemodynamic wall stress index measured relative to ideal 120 mmHg physiological standard."
    },
    {
        "name": "Hyperglycemic Risk Threshold",
        "column": "glucose_risk",
        "category": "Engineered Bio-Metric",
        "required": False,
        "default_val": "Tier (0.0, 0.5, 1.0)",
        "unit": "Score",
        "description": "Threshold score for endothelial glycation risk: 0 (<100 mg/dL), 0.5 (100-125), 1.0 (>125)."
    }
]

def extract_features(age, bmi, bpm, smoker=0, cigs=0, diabetes=0, sys_bp=None, glucose=None, chol=None, bp_meds=0):
    """
    Extracts 15 clinical and physiologically engineered cardiovascular features.
    Matches train_model.py. Gracefully handles unmeasured lab metrics.
    """
    age = float(age)
    bmi = float(bmi)
    bpm = float(bpm)
    smoker = 1.0 if (smoker or (cigs and float(cigs) > 0)) else 0.0
    cigs = float(cigs) if cigs is not None else 0.0
    diabetes = float(diabetes) if diabetes is not None else 0.0
    bp_meds = float(bp_meds) if bp_meds is not None else 0.0

    sys_bp = float(sys_bp) if (sys_bp is not None and str(sys_bp).strip() != "") else CLINICAL_DEFAULTS['sys_bp']
    glucose = float(glucose) if (glucose is not None and str(glucose).strip() != "") else CLINICAL_DEFAULTS['glucose']
    chol = float(chol) if (chol is not None and str(chol).strip() != "") else CLINICAL_DEFAULTS['tot_chol']

    age_sq = (age / 50.0) ** 2
    bmi_cat = 0.0 if bmi < 18.5 else (1.0 if bmi < 25.0 else (2.0 if bmi < 30.0 else 3.0))
    hr_ratio = bpm / max(1.0, (220.0 - age))
    bp_strain = sys_bp / 120.0
    glucose_risk = 1.0 if glucose > 125.0 else (0.5 if glucose > 100.0 else 0.0)

    return [
        age, bmi, bpm, smoker, cigs, diabetes, sys_bp, glucose, chol, bp_meds,
        age_sq, bmi_cat, hr_ratio, bp_strain, glucose_risk
    ]

def calculate_bmi(height_cm, weight_kg):
    height_meters = height_cm / 100.0
    bmi = round(weight_kg / (height_meters ** 2), 1)
    
    # Normal WHO BMI Range is 18.5 - 24.9 kg/m²
    min_ideal_kg = round(18.5 * (height_meters ** 2), 1)
    max_ideal_kg = round(24.9 * (height_meters ** 2), 1)

    if bmi < 18.5:
        category = "Underweight"
        css_badge = "badge-warning"
        diff_kg = round(min_ideal_kg - weight_kg, 1)
        target_advice = f"Gain ~{diff_kg} kg for healthy BMI (Target: {min_ideal_kg} – {max_ideal_kg} kg)"
        target_short = f"+{diff_kg} kg needed ({min_ideal_kg}–{max_ideal_kg} kg)"
    elif 18.5 <= bmi < 25.0:
        category = "Normal"
        css_badge = "badge-normal"
        diff_kg = 0.0
        target_advice = f"Optimal weight! Maintain between {min_ideal_kg} – {max_ideal_kg} kg"
        target_short = f"Optimal ({min_ideal_kg}–{max_ideal_kg} kg)"
    elif 25.0 <= bmi < 30.0:
        category = "Overweight"
        css_badge = "badge-warning"
        diff_kg = round(weight_kg - max_ideal_kg, 1)
        target_advice = f"Lose ~{diff_kg} kg for healthy BMI (Target: {min_ideal_kg} – {max_ideal_kg} kg)"
        target_short = f"-{diff_kg} kg needed ({min_ideal_kg}–{max_ideal_kg} kg)"
    else:
        category = "Obese"
        css_badge = "badge-danger"
        diff_kg = round(weight_kg - max_ideal_kg, 1)
        target_advice = f"Lose ~{diff_kg} kg for healthy BMI (Target: {min_ideal_kg} – {max_ideal_kg} kg)"
        target_short = f"-{diff_kg} kg needed ({min_ideal_kg}–{max_ideal_kg} kg)"
        
    return {
        "val": bmi,
        "category": category,
        "badge_class": css_badge,
        "min_ideal_kg": min_ideal_kg,
        "max_ideal_kg": max_ideal_kg,
        "diff_kg": diff_kg,
        "target_advice": target_advice,
        "target_short": target_short
    }

def assess_heart_rate(bpm, activity_level):
    if bpm < 60:
        if activity_level == "highly-active":
            status = "Athletic Bradycardia"
            css_badge = "badge-normal"
            description = "Physiologically low pulse typical of high athletic conditioning. Normal variation."
        else:
            status = "Bradycardia (Low)"
            css_badge = "badge-warning"
            description = "Low resting heart rate. May cause lightheadedness or fatigue if not active."
    elif 60 <= bpm <= 100:
        status = "Normal resting pulse"
        css_badge = "badge-normal"
        description = "Healthy and normal resting heart rate. Excellent blood circulation."
    else:
        status = "Tachycardia (High)"
        css_badge = "badge-danger"
        description = "Elevated heart rate. Can indicate stress, dehydration, poor conditioning, or cardiovascular load."
        
    return {
        "status": status,
        "badge_class": css_badge,
        "description": description
    }

def predict_cardio_risk(age, bmi_cat, bpm, activity_level, smoker=0, diabetes=0, sys_bp=None, glucose=None):
    risk_points = 0.0
    if age > 45: risk_points += 1.0
    if age > 60: risk_points += 1.0
    if bmi_cat == "Overweight": risk_points += 1.0
    elif bmi_cat == "Obese": risk_points += 2.0
    if bpm > 90: risk_points += 1.5
    if bpm < 50 and activity_level == "sedentary": risk_points += 1.0
    if activity_level == "sedentary": risk_points += 1.0
    if smoker: risk_points += 2.0
    if diabetes: risk_points += 2.5
    if sys_bp and sys_bp > 140: risk_points += 2.0
    if glucose and glucose > 125: risk_points += 1.5
        
    if risk_points >= 4.5:
        risk = "High"
        css_class = "high"
    elif risk_points >= 2.0:
        risk = "Moderate"
        css_class = "moderate"
    else:
        risk = "Low"
        css_class = "low"
        
    return {"level": risk, "class": css_class}

# ==========================================================================
# Recommendation Engines (Gemini 2.5 Flash AI + Clinical Rule Fallback)
# ==========================================================================

def generate_rule_recommendations(bmi_cat, bpm, activity, age, vitals):
    diet = [
        "Adopt a Mediterranean-style diet high in fresh vegetables, whole grains, and omega-3 rich fatty fish.",
        "Maintain consistent hydration with 2.5 to 3 liters of water daily to support vascular volume."
    ]
    if bmi_cat in ["Overweight", "Obese"]:
        diet.append("Eliminate refined carbohydrates and sugar-sweetened beverages; prioritize high-fiber vegetables.")
    if vitals.get('glucose') and vitals['glucose'] > 100:
        diet.append("Regulate postprandial glucose: pair carbs with healthy proteins/fats to avoid glycemic spikes.")
    if bpm > 90 or (vitals.get('sys_bp') and vitals['sys_bp'] > 130):
        diet.append("Cap sodium intake under 1,800 mg/day and moderate caffeine consumption to ease arterial tension.")
    else:
        diet.append("Integrate potassium and magnesium-rich foods (spinach, avocados) for optimal cardiac electrical conduction.")

    exercise = []
    if activity == "sedentary":
        exercise.append("Avoid prolonged sitting: stand and perform light walking for 3 to 5 minutes every hour.")
        exercise.append("Initiate a structured 20-minute daily low-impact brisk walking routine.")
    else:
        exercise.append("Engage in 150 minutes of moderate aerobic cardio (cycling, brisk walking, swimming) weekly.")

    max_hr = 220 - age
    exercise.append(f"Maintain aerobic training heart rate within: {int(max_hr * 0.5)} to {int(max_hr * 0.75)} BPM.")
    if bpm > 100:
        exercise.append("Avoid intense anaerobic sprint intervals until baseline resting pulse stabilizes.")
    else:
        exercise.append("Incorporate 2 days per week of moderate resistance training to strengthen peripheral vasculature.")

    lifestyle = [
        "Aim for 7 to 9 hours of uninterrupted sleep. Sleep debt elevates cortisol and resting pulse.",
        "Perform 5 minutes of parasympathetic box breathing (4 sec in, 4 hold, 4 out, 4 hold) twice daily."
    ]
    if vitals.get('smoker'):
        lifestyle.append("Smoking significantly stiffens arterial walls. Seek nicotine cessation support to reduce cardiovascular risk by up to 50% in 1 year.")
    if bpm > 85:
        lifestyle.append("Dedicate 15 minutes before bed to screen-free mindfulness or gentle stretching.")

    warnings = []
    if vitals.get('diabetes'):
        warnings.append("Diabetes accelerates macrovascular plaque formation. Maintain strict quarterly HbA1c monitoring.")
    if vitals.get('sys_bp') and vitals['sys_bp'] >= 140:
        warnings.append(f"Systolic BP is elevated ({int(vitals['sys_bp'])} mmHg). Consult a physician for formal blood pressure evaluation.")
    if bpm > 100:
        warnings.append("Persistent tachycardia (>100 BPM at rest) should be checked by a physician to exclude arrhythmias.")
    if bpm < 50 and activity != "highly-active":
        warnings.append("Bradycardia in non-conditioned individuals requires physician review if paired with dizziness.")
    warnings.append("Always consult a certified medical practitioner before beginning any rigorous physical conditioning.")

    return {
        "diet": diet,
        "exercise": exercise,
        "lifestyle": lifestyle,
        "warnings": warnings,
        "engine": "Clinical Rule Engine",
        "is_ai": False
    }

def generate_ai_recommendations(vitals, history, bmi_cat, bpm, activity, age, heart_status):
    """
    Calls Google Gemini (gemini-2.5-flash / gemini-1.5-flash) for live, low-token,
    personalized clinical AI coaching analyzing current vitals and historical trends.
    """
    gemini_key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not gemini_key:
        recs = generate_rule_recommendations(bmi_cat, bpm, activity, age, vitals)
        recs["engine"] = "Clinical Rule Engine (Add GEMINI_API_KEY in .env for Live Gemini AI Coaching)"
        recs["is_ai"] = False
        return recs

    history_summary = []
    for h in history[:4]:
        history_summary.append(
            f"- Date: {h.get('date')}, BPM: {h.get('bpm')}, BMI: {h.get('bmi')}, Risk: {h.get('risk_level')}"
        )
    history_text = "\n".join(history_summary) if history_summary else "First clinical evaluation on file."

    prompt = f"""You are an expert cardiologist and clinical wellness AI.
Analyze this patient's current cardiovascular profile and their historical entries to produce evidence-based, personalized recommendations.

CURRENT VITALS:
- Age: {age} | BMI: {vitals.get('bmi')} ({bmi_cat}) | Resting Pulse: {bpm} BPM ({heart_status})
- Activity: {activity}
- Smoking: {'Yes, Smoker (' + str(vitals.get('cigs_per_day', 0)) + ' cigs/day)' if vitals.get('smoker') else 'No (Non-smoker)'}
- Diabetes: {'Yes' if vitals.get('diabetes') else 'No'}
- Systolic BP: {vitals.get('sys_bp', '120 (Normal baseline)')} mmHg
- Fasting Glucose: {vitals.get('glucose', '85 (Normal baseline)')} mg/dL
- Total Cholesterol: {vitals.get('cholesterol', '200 (Normal baseline)')} mg/dL
- ML 10-Yr Cardiovascular Risk: {vitals.get('risk_level')}

RECENT HISTORICAL TRENDS:
{history_text}

TASK:
Provide clear, personalized guidance in 4 categories. If history exists, note whether metrics (e.g. pulse or weight) are improving or need attention.
Return strictly valid JSON with this exact schema (no markdown fences, no preface):
{{
  "diet": ["concrete food choice with rationale", "hydration amount in liters and electrolytes", "sodium or micronutrient target"],
  "exercise": ["specific aerobic cardio plan with safe target HR zone", "weekly resistance or flexibility routine"],
  "lifestyle": ["sleep and recovery strategy", "stress and parasympathetic regulation technique"],
  "warnings": ["clinical precautions and symptoms requiring immediate doctor consultation"]
}}"""

    models_to_try = ["gemini-3.5-flash", "gemini-3.7-flash", "gemini-3.5-flash-lite"]
    for model_name in models_to_try:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={gemini_key}"
            headers = {"Content-Type": "application/json"}
            body = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "maxOutputTokens": 3000,
                    "responseMimeType": "application/json"
                }
            }
            resp = requests.post(url, headers=headers, json=body, timeout=12)
            if resp.status_code == 200:
                resp_json = resp.json()
                candidates = resp_json.get('candidates', [])
                if candidates:
                    parts = candidates[0].get('content', {}).get('parts', [])
                    text_parts = [p['text'] for p in parts if 'text' in p]
                    text_content = "\n".join(text_parts).strip()
                    if text_content.startswith("```"):
                        lines = text_content.splitlines()
                        if lines and lines[0].startswith("```"):
                            lines = lines[1:]
                        if lines and lines[-1].startswith("```"):
                            lines = lines[:-1]
                        text_content = "\n".join(lines).strip()
                    
                    try:
                        parsed = json.loads(text_content)
                    except Exception:
                        # Resilient extraction if trailing commas or thinking text present
                        import re
                        json_match = re.search(r'\{.*\}', text_content, re.DOTALL)
                        if json_match:
                            parsed = json.loads(json_match.group(0))
                        else:
                            continue

                    engine_display = "Google Gemini AI"
                    if "3.5" in model_name:
                        engine_display = "Google Gemini 3.5 Flash AI"
                    elif "3.7" in model_name:
                        engine_display = "Google Gemini 3.7 Flash AI"
                    elif "3.8" in model_name:
                        engine_display = "Google Gemini 3.8 Flash AI"

                    return {
                        "diet": parsed.get("diet", []),
                        "exercise": parsed.get("exercise", []),
                        "lifestyle": parsed.get("lifestyle", []),
                        "warnings": parsed.get("warnings", []),
                        "engine": engine_display,
                        "is_ai": True
                    }
        except Exception as e:
            print(f"[INFO] Gemini model '{model_name}' request failed ({e}), attempting fallback...", flush=True)

    # Fallback to rule engine if API calls fail
    recs = generate_rule_recommendations(bmi_cat, bpm, activity, age, vitals)
    recs["engine"] = "Clinical Rule Engine (Gemini API unavailable or quota reached)"
    recs["is_ai"] = False
    return recs

# ==========================================================================
# Web Routes & Model Information API
# ==========================================================================

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/model-info', methods=['GET'])
def get_model_info():
    """Returns metadata and the full list of 15 clinical biomarkers used in training."""
    return jsonify({
        "accuracy": "84.15%",
        "algorithm": "Gradient Boosting & Calibrated Random Forest Ensemble",
        "dataset": "Framingham Heart Study (NHLBI / Boston University)",
        "features": FEATURE_DETAILS
    })

@app.route('/api/status', methods=['GET'])
def get_status():
    """Returns the active database and SMTP configuration status."""
    return jsonify({
        "db_type": "MongoDB Atlas" if use_mongo else "SQLite (Local Fallback)",
        "use_mongo": use_mongo,
        "smtp_configured": bool(os.environ.get('SMTP_EMAIL') and os.environ.get('SMTP_PASSWORD'))
    })

# --------------------------------------------------------------------------
# Authentication Routes
# --------------------------------------------------------------------------

@app.route('/api/auth/signup', methods=['POST'])
def signup():
    data = request.get_json() or {}
    name = str(data.get('name', '')).strip()
    email = str(data.get('email', '')).strip().lower()
    password = str(data.get('password', ''))
    confirm_password = str(data.get('confirm_password', ''))

    if not name or not email or not password:
        return jsonify({"error": "Name, email, and password are required."}), 400
    if '@' not in email or '.' not in email:
        return jsonify({"error": "Please provide a valid email address."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters long."}), 400
    if password != confirm_password:
        return jsonify({"error": "Passwords do not match."}), 400

    hashed_pw = generate_password_hash(password)

    if use_mongo:
        existing = mongo_db['users'].find_one({"email": email})
        if existing:
            return jsonify({"error": "An account with this email already exists. Please log in."}), 409
        
        user_doc = {
            "name": name,
            "email": email,
            "password_hash": hashed_pw,
            "created_at": datetime.utcnow()
        }
        res = mongo_db['users'].insert_one(user_doc)
        user_id = str(res.inserted_id)
    else:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
        if cursor.fetchone():
            conn.close()
            return jsonify({"error": "An account with this email already exists. Please log in."}), 409
        
        cursor.execute(
            'INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)',
            (name, email, hashed_pw)
        )
        user_id = str(cursor.lastrowid)
        conn.commit()
        conn.close()

    # Establish session
    session['user_id'] = user_id
    session['user_name'] = name
    session['user_email'] = email
    session.permanent = True

    return jsonify({
        "success": True,
        "message": "Account created successfully!",
        "user": {"id": user_id, "name": name, "email": email}
    })

@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    email = str(data.get('email', '')).strip().lower()
    password = str(data.get('password', ''))

    if not email or not password:
        return jsonify({"error": "Email and password are required."}), 400

    if use_mongo:
        user = mongo_db['users'].find_one({"email": email})
        if not user or not check_password_hash(user['password_hash'], password):
            return jsonify({"error": "Invalid email or password."}), 401
        user_id = str(user['_id'])
        user_name = user['name']
    else:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        user = cursor.fetchone()
        conn.close()
        if not user or not check_password_hash(user['password_hash'], password):
            return jsonify({"error": "Invalid email or password."}), 401
        user_id = str(user['id'])
        user_name = user['name']

    # Establish session
    session['user_id'] = user_id
    session['user_name'] = user_name
    session['user_email'] = email
    session.permanent = True

    return jsonify({
        "success": True,
        "message": f"Welcome back, {user_name}!",
        "user": {"id": user_id, "name": user_name, "email": email}
    })

@app.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    return jsonify({"success": True, "message": "Logged out successfully."})

@app.route('/api/auth/me', methods=['GET'])
def get_current_user():
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"authenticated": False})
        
    user_name = session.get('user_name', '')
    user_email = session.get('user_email', '')
    return jsonify({
        "authenticated": True,
        "user": {
            "id": user_id,
            "name": user_name,
            "email": user_email
        }
    })

@app.route('/api/auth/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json() or {}
    email = str(data.get('email', '')).strip().lower()

    if not email or '@' not in email:
        return jsonify({"error": "Valid email address is required."}), 400

    # Generate 6-digit random verification code
    reset_code = "".join([secrets.choice("0123456789") for _ in range(6)])
    expiry = datetime.utcnow() + timedelta(minutes=15)

    user_found = False
    if use_mongo:
        user = mongo_db['users'].find_one({"email": email})
        if user:
            user_found = True
            mongo_db['users'].update_one(
                {"_id": user['_id']},
                {"$set": {"reset_code": reset_code, "reset_expiry": expiry}}
            )
    else:
        conn = sqlite3.connect(DATABASE_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT id FROM users WHERE email = ?', (email,))
        if cursor.fetchone():
            user_found = True
            cursor.execute(
                'UPDATE users SET reset_code = ?, reset_expiry = ? WHERE email = ?',
                (reset_code, expiry.strftime('%Y-%m-%d %H:%M:%S'), email)
            )
            conn.commit()
        conn.close()

    if not user_found:
        return jsonify({"error": "No account registered with this email address."}), 404

    # Dispatch email via Gmail SMTP
    success, status = send_reset_email(email, reset_code)

    resp_data = {
        "success": True,
        "message": f"A 6-digit verification code has been sent to {email}."
    }
    # If SMTP is not yet configured, include dev_code in response for instant local testing
    if status == "DEV_MODE":
        resp_data["dev_code"] = reset_code
        resp_data["message"] = f"Verification code generated! (SMTP not configured in .env - check console or use code {reset_code})"

    return jsonify(resp_data)

@app.route('/api/auth/reset-password', methods=['POST'])
def reset_password():
    data = request.get_json() or {}
    email = str(data.get('email', '')).strip().lower()
    code = str(data.get('code', '')).strip()
    new_password = str(data.get('new_password', ''))
    confirm_password = str(data.get('confirm_password', ''))

    if not email or not code or not new_password:
        return jsonify({"error": "Email, verification code, and new password are required."}), 400
    if len(new_password) < 6:
        return jsonify({"error": "Password must be at least 6 characters long."}), 400
    if new_password != confirm_password:
        return jsonify({"error": "Passwords do not match."}), 400

    now = datetime.utcnow()
    hashed_pw = generate_password_hash(new_password)

    if use_mongo:
        user = mongo_db['users'].find_one({"email": email})
        if not user:
            return jsonify({"error": "User not found."}), 404
        if user.get('reset_code') != code:
            return jsonify({"error": "Invalid verification code. Please check and try again."}), 400
        if not user.get('reset_expiry') or now > user.get('reset_expiry'):
            return jsonify({"error": "Verification code has expired. Please request a new code."}), 400

        mongo_db['users'].update_one(
            {"_id": user['_id']},
            {
                "$set": {"password_hash": hashed_pw},
                "$unset": {"reset_code": "", "reset_expiry": ""}
            }
        )
    else:
        conn = sqlite3.connect(DATABASE_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM users WHERE email = ?', (email,))
        user = cursor.fetchone()
        if not user:
            conn.close()
            return jsonify({"error": "User not found."}), 404
        if user['reset_code'] != code:
            conn.close()
            return jsonify({"error": "Invalid verification code."}), 400
        
        try:
            exp = datetime.strptime(user['reset_expiry'], '%Y-%m-%d %H:%M:%S')
            if now > exp:
                conn.close()
                return jsonify({"error": "Verification code has expired."}), 400
        except Exception:
            pass

        cursor.execute(
            'UPDATE users SET password_hash = ?, reset_code = NULL, reset_expiry = NULL WHERE email = ?',
            (hashed_pw, email)
        )
        conn.commit()
        conn.close()

    return jsonify({"success": True, "message": "Password updated successfully! You can now log in."})

# --------------------------------------------------------------------------
# Vitals Diagnostics & Per-User Health Records
# --------------------------------------------------------------------------

@app.route('/api/analyze', methods=['POST'])
def analyze():
    # Require authentication
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Please log in to save and analyze health records."}), 401

    data = request.get_json()
    if not data:
        return jsonify({"error": "No input data provided"}), 400
        
    try:
        name = str(data.get('name') or session.get('user_name', 'Patient'))
        height = float(data.get('height'))
        weight = float(data.get('weight'))
        age = int(data.get('age'))
        bpm = int(data.get('bpm'))
        activity = data.get('activityLevel', 'moderate')

        # Framingham clinical inputs (mandatory & optional)
        smoker_val = data.get('smoker')
        smoker = 1 if smoker_val in [True, 1, '1', 'true', 'yes', 'on'] else 0
        cigs_raw = data.get('cigsPerDay')
        if cigs_raw is not None and str(cigs_raw).strip() != '':
            cigs = float(cigs_raw)
        else:
            cigs = 10.0 if smoker else 0.0

        diabetes_val = data.get('diabetes')
        diabetes = 1 if diabetes_val in [True, 1, '1', 'true', 'yes', 'on'] else 0

        bp_meds_val = data.get('bpMeds')
        bp_meds = 1 if bp_meds_val in [True, 1, '1', 'true', 'yes', 'on'] else 0

        def parse_optional_float(val):
            if val is None or str(val).strip() == '':
                return None
            try:
                return float(val)
            except (ValueError, TypeError):
                return None

        # Optional laboratory biomarkers (non-mandatory)
        glucose = parse_optional_float(data.get('glucose'))
        sys_bp = parse_optional_float(data.get('sysBP'))
        chol = parse_optional_float(data.get('cholesterol'))

    except (ValueError, TypeError):
        return jsonify({"error": "Invalid metric formats. Numbers required for required vitals."}), 400

    # Execute health calculations
    bmi_results = calculate_bmi(height, weight)
    heart_results = assess_heart_rate(bpm, activity)
    
    # Calculate Risk using ML Ensemble Model (15 features)
    if ml_model is not None and ml_scaler is not None:
        try:
            raw_features = extract_features(
                age, bmi_results['val'], bpm,
                smoker=smoker, cigs=cigs, diabetes=diabetes,
                sys_bp=sys_bp, glucose=glucose, chol=chol, bp_meds=bp_meds
            )
            features = np.array([raw_features])
            features_scaled = ml_scaler.transform(features)
            prob_risk = ml_model.predict_proba(features_scaled)[0][1]
            prob_percentage = int(round(prob_risk * 100))
            
            if prob_risk >= 0.50:
                risk_level = f"High ({prob_percentage}%)"
                risk_class = "high"
            elif prob_risk >= 0.25:
                risk_level = f"Moderate ({prob_percentage}%)"
                risk_class = "moderate"
            else:
                risk_level = f"Low ({prob_percentage}%)"
                risk_class = "low"
                
            risk_results = {"level": risk_level, "class": risk_class, "probability": prob_risk}
        except Exception as e:
            print(f"[WARNING] ML prediction failed, using point-scoring fallback: {e}", flush=True)
            risk_results = predict_cardio_risk(age, bmi_results['category'], bpm, activity)
    else:
        risk_results = predict_cardio_risk(age, bmi_results['category'], bpm, activity)

    # Fetch recent history (up to 4 checkups) for trend context in AI recommendations
    recent_history = []
    if use_mongo:
        try:
            hist_cursor = mongo_db['records'].find({"user_id": user_id}).sort("created_at", -1).limit(4)
            for h in hist_cursor:
                recent_history.append({
                    "date": h.get("created_at").strftime("%Y-%m-%d") if isinstance(h.get("created_at"), datetime) else str(h.get("created_at", "")),
                    "bpm": h.get("bpm"),
                    "bmi": h.get("bmi"),
                    "risk_level": h.get("risk_level"),
                    "glucose": h.get("glucose"),
                    "sys_bp": h.get("sys_bp")
                })
        except Exception as e:
            print(f"[INFO] History fetch failed: {e}", flush=True)

    vitals_dict = {
        "age": age,
        "height": height,
        "weight": weight,
        "bmi": bmi_results['val'],
        "bpm": bpm,
        "activity": activity,
        "smoker": bool(smoker),
        "cigs_per_day": cigs,
        "diabetes": bool(diabetes),
        "bp_meds": bool(bp_meds),
        "glucose": glucose,
        "sys_bp": sys_bp,
        "cholesterol": chol
    }

    # Generate Personalized AI Recommendations via Google Gemini Flash (or Clinical Rule Engine fallback)
    recs_results = generate_ai_recommendations(
        vitals=vitals_dict,
        history=recent_history,
        bmi_cat=bmi_results['category'],
        bpm=bpm,
        activity=activity,
        age=age,
        heart_status=heart_results['status']
    )

    # Calculate target heart rate ranges
    max_hr = 220 - age
    ideal_bpm_min = 60
    ideal_bpm_max = min(80, int(max_hr * 0.5))
    target_exercise_min = int(max_hr * 0.5)
    target_exercise_max = int(max_hr * 0.85)

    # Save comprehensive record tied to user
    created_timestamp = datetime.utcnow()
    try:
        record_doc = {
            "user_id": user_id,
            "user_email": session.get('user_email', ''),
            "name": name,
            "age": age,
            "height": height,
            "weight": weight,
            "bpm": bpm,
            "activity": activity,
            "bmi": bmi_results['val'],
            "risk_level": risk_results['level'],
            "smoker": smoker,
            "cigs_per_day": cigs,
            "diabetes": diabetes,
            "bp_meds": bp_meds,
            "glucose": glucose,
            "sys_bp": sys_bp,
            "tot_chol": chol,
            "ai_engine": recs_results.get('engine', 'Clinical Rules'),
            "created_at": created_timestamp
        }
        if use_mongo:
            mongo_db['records'].insert_one(record_doc)
        else:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO patients (user_id, name, age, height, weight, bpm, activity, bmi, risk_level)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (user_id, name, age, height, weight, bpm, activity, bmi_results['val'], risk_results['level']))
            conn.commit()
            conn.close()
    except Exception as e:
        print(f"[ERROR] Failed to save patient to database: {e}", flush=True)

    return jsonify({
        "bmi": bmi_results,
        "heart": heart_results,
        "risk": risk_results,
        "vitals": vitals_dict,
        "recommendations": recs_results,
        "stats": {
            "max_hr": max_hr,
            "ideal_bpm": f"{ideal_bpm_min} - {ideal_bpm_max} BPM",
            "exercise_bpm": f"{target_exercise_min} - {target_exercise_max} BPM"
        }
    })

@app.route('/api/records', methods=['GET'])
def get_records():
    """Fetches stored records ONLY for the currently authenticated user."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Please log in to view your records."}), 401

    try:
        records = []
        if use_mongo:
            # Query MongoDB Atlas by user_id
            cursor = mongo_db['records'].find({"user_id": user_id}).sort("created_at", -1)
            for row in cursor:
                records.append({
                    "id": str(row["_id"]),
                    "name": row.get("name", "User"),
                    "age": row.get("age"),
                    "height": row.get("height"),
                    "weight": row.get("weight"),
                    "bpm": row.get("bpm"),
                    "activity": row.get("activity"),
                    "bmi": row.get("bmi"),
                    "risk_level": row.get("risk_level"),
                    "smoker": row.get("smoker"),
                    "cigs_per_day": row.get("cigs_per_day"),
                    "diabetes": row.get("diabetes"),
                    "bp_meds": row.get("bp_meds"),
                    "glucose": row.get("glucose"),
                    "sys_bp": row.get("sys_bp"),
                    "tot_chol": row.get("tot_chol"),
                    "ai_engine": row.get("ai_engine"),
                    "created_at": row.get("created_at").isoformat() if isinstance(row.get("created_at"), datetime) else str(row.get("created_at", ""))
                })
        else:
            conn = sqlite3.connect(DATABASE_PATH)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM patients WHERE user_id = ? ORDER BY created_at DESC', (user_id,))
            rows = cursor.fetchall()
            conn.close()
            
            for row in rows:
                records.append({
                    "id": row["id"],
                    "name": row["name"],
                    "age": row["age"],
                    "height": row["height"],
                    "weight": row["weight"],
                    "bpm": row["bpm"],
                    "activity": row["activity"],
                    "bmi": row["bmi"],
                    "risk_level": row["risk_level"],
                    "created_at": row["created_at"]
                })
        return jsonify(records)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/records/<record_id>', methods=['DELETE'])
def delete_record(record_id):
    """Deletes a patient record only if owned by the current user."""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401

    try:
        if use_mongo:
            res = mongo_db['records'].delete_one({"_id": ObjectId(record_id), "user_id": user_id})
            if res.deleted_count == 0:
                return jsonify({"error": "Record not found or not owned by you."}), 404
        else:
            conn = sqlite3.connect(DATABASE_PATH)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM patients WHERE id = ? AND user_id = ?', (record_id, user_id))
            conn.commit()
            conn.close()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', debug=False, port=port)
