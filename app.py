import math
import os
import pickle
import numpy as np
from flask import Flask, render_template, request, jsonify

import shutil

# Self-healing folder structure setup:
# If files were uploaded directly to the root of the repository, copy them to standard templates/static folders dynamically at startup.
base_dir = os.path.dirname(os.path.abspath(__file__))

print("DEBUG: base_dir is", base_dir, flush=True)
try:
    print("DEBUG: files in base_dir are", os.listdir(base_dir), flush=True)
except Exception as e:
    print("DEBUG: failed to list files:", e, flush=True)

# 1. Handle HTML template
root_html = os.path.join(base_dir, 'index.html')
target_html_dir = os.path.join(base_dir, 'templates')
if os.path.exists(root_html):
    os.makedirs(target_html_dir, exist_ok=True)
    shutil.copy(root_html, os.path.join(target_html_dir, 'index.html'))

# 2. Handle CSS stylesheet
root_css = os.path.join(base_dir, 'index.css')
target_static_dir = os.path.join(base_dir, 'static')
if os.path.exists(root_css):
    os.makedirs(target_static_dir, exist_ok=True)
    shutil.copy(root_css, os.path.join(target_static_dir, 'index.css'))

# 3. Handle JavaScript file
root_js = os.path.join(base_dir, 'app.js')
if os.path.exists(root_js):
    os.makedirs(target_static_dir, exist_ok=True)
    shutil.copy(root_js, os.path.join(target_static_dir, 'app.js'))

print("DEBUG: index.html in root exists?", os.path.exists(root_html), flush=True)
print("DEBUG: templates/index.html copy exists?", os.path.exists(os.path.join(target_html_dir, 'index.html')), flush=True)

# Initialize Flask normally
app = Flask(__name__)

# Load Machine Learning Model and Scaler at Startup
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
    print("[WARNING] heart_model.pkl or scaler.pkl not found! Running in point-scoring fallback mode.", flush=True)

# ==========================================================================
# Core Health Assessment Engines (Python Backend)
# ==========================================================================

def calculate_bmi(height_cm, weight_kg):
    """Calculates BMI and returns value and clinical category."""
    height_meters = height_cm / 100.0
    bmi = round(weight_kg / (height_meters ** 2), 1)
    
    if bmi < 18.5:
        category = "Underweight"
        css_badge = "badge-warning"
    elif 18.5 <= bmi < 25.0:
        category = "Normal"
        css_badge = "badge-normal"
    elif 25.0 <= bmi < 30.0:
        category = "Overweight"
        css_badge = "badge-warning"
    else:
        category = "Obese"
        css_badge = "badge-danger"
        
    return {"val": bmi, "category": category, "badge_class": css_badge}

def assess_heart_rate(bpm, activity_level):
    """Evaluates resting heart rate status based on activity level."""
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

def predict_cardio_risk(age, bmi_cat, bpm, activity_level):
    """Determines overall cardiovascular risk index based on indices."""
    risk_points = 0.0
    
    if age > 45:
        risk_points += 1.0
    if age > 60:
        risk_points += 1.0
    if bmi_cat == "Overweight":
        risk_points += 1.0
    elif bmi_cat == "Obese":
        risk_points += 2.5
    if bpm > 90:
        risk_points += 1.5
    if bpm < 50 and activity_level == "sedentary":
        risk_points += 1.0
    if activity_level == "sedentary":
        risk_points += 1.0
        
    if risk_points >= 3.5:
        risk = "High"
        css_class = "high"
    elif risk_points >= 1.5:
        risk = "Moderate"
        css_class = "moderate"
    else:
        risk = "Low"
        css_class = "low"
        
    return {"level": risk, "class": css_class}

def generate_recommendations(bmi_cat, bpm, activity, age, heart_status):
    """Generates structured advice across nutrition, exercise, sleep, and clinical warnings."""
    # Nutrition Recommendations
    diet = [
        "Adopt a Mediterranean-style diet high in fruits, fresh vegetables, whole grains, and healthy fats (olive oil, avocados).",
        "Stay hydrated with 2.5 to 3 liters of water daily to maintain electrolyte balance."
    ]
    if bmi_cat in ["Overweight", "Obese"]:
        diet.append("Reduce refined carbohydrates, sugar-sweetened beverages, and practice portion control to lower body fat.")
    if bpm > 90:
        diet.append("Reduce sodium intake (under 2,000 mg/day) and caffeine consumption to lower cardiovascular workload.")
    else:
        diet.append("Integrate potassium-rich foods (bananas, sweet potatoes, spinach) to support optimal myocardial conduction.")

    # Exercise Recommendations
    exercise = []
    if activity == "sedentary":
        exercise.append("Avoid long periods of sitting; stand and stretch for 5 minutes every hour.")
        exercise.append("Begin with daily 15-minute low-impact walks, working up to 30 minutes.")
    else:
        exercise.append("Engage in 150 minutes of moderate aerobic workouts (brisk walking, swimming) or 75 minutes of high-intensity training weekly.")
    
    if bpm > 105:
        exercise.append("Avoid extreme peak heavy lifting or sudden anaerobic sprints until resting BPM drops; focus on steady-state recovery cardio.")
    else:
        exercise.append("Incorporate twice-weekly strength resistance training to improve capillary networks and oxygen utilization.")
    
    # Calculate target heart rate range
    max_hr = 220 - age
    target_min = int(max_hr * 0.5)
    target_max = int(max_hr * 0.75)
    exercise.append(f"Aim to keep exercise heart rates in your target zone: {target_min} to {target_max} BPM.")

    # Lifestyle / Habits
    lifestyle = [
        "Aim for 7 to 9 hours of quality, regular sleep each night. Sleep deprivation elevates stress hormones like cortisol.",
        "Perform deep breathing exercises (e.g., 4-7-8 box breathing) twice daily for 5 minutes to tone your parasympathetic nervous system."
    ]
    if bpm > 85:
        lifestyle.append("Identify stressors and dedicate 15 minutes to active decompression or mindfulness practices.")

    # Warnings
    warnings = []
    if bmi_cat == "Obese":
        warnings.append("Monitor weight trends weekly; high abdominal fat raises pressure inside arteries.")
    if bpm > 100:
        warnings.append("Persistent high resting pulse (Tachycardia) should be evaluated by a physician to rule out arrhythmias, thyroid dysfunction, or anemia.")
    if bpm < 50 and activity != "highly-active":
        warnings.append("Low resting pulse (Bradycardia) in non-athletes requires monitoring. Seek medical review if you experience dizziness, fainting, or chest discomfort.")
    
    # Standard warning
    warnings.append("Always consult with a physician before starting any new, intensive physical fitness programs or making major dietary changes.")

    return {
        "diet": diet,
        "exercise": exercise,
        "lifestyle": lifestyle,
        "warnings": warnings,
        "has_warnings": len(warnings) > 1 or (len(warnings) == 1 and "consult" not in warnings[0])
    }

# ==========================================================================
# Web Routes
# ==========================================================================

@app.route('/')
def index():
    """Serves the main frontend Single Page Application."""
    return render_template('index.html')

@app.route('/api/analyze', methods=['POST'])
def analyze():
    """API Endpoint to compute heart health recommendations from user vitals."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "No input data provided"}), 400
        
    try:
        height = float(data.get('height'))
        weight = float(data.get('weight'))
        age = int(data.get('age'))
        bpm = int(data.get('bpm'))
        activity = data.get('activityLevel', 'moderate')
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid metric formats. Numbers required."}), 400

    # Execute health calculations
    bmi_results = calculate_bmi(height, weight)
    heart_results = assess_heart_rate(bpm, activity)
    
    # Calculate Risk using ML Model if loaded, else fall back to point scoring
    if ml_model is not None and ml_scaler is not None:
        try:
            # Prepare inputs: [age, bmi, bpm] (matches real Framingham features)
            features = np.array([[age, bmi_results['val'], bpm]])
            
            # Scale features
            features_scaled = ml_scaler.transform(features)
            
            # Predict probability of heart disease risk (class 1)
            prob_risk = ml_model.predict_proba(features_scaled)[0][1]
            prob_percentage = int(round(prob_risk * 100))
            
            # Categorize risk based on ML probability thresholds
            if prob_risk >= 0.70:
                risk_level = f"High ({prob_percentage}%)"
                risk_class = "high"
            elif prob_risk >= 0.35:
                risk_level = f"Moderate ({prob_percentage}%)"
                risk_class = "moderate"
            else:
                risk_level = f"Low ({prob_percentage}%)"
                risk_class = "low"
                
            risk_results = {"level": risk_level, "class": risk_class}
        except Exception as e:
            print(f"[WARNING] ML prediction failed, using point-scoring fallback: {e}", flush=True)
            risk_results = predict_cardio_risk(age, bmi_results['category'], bpm, activity)
    else:
        risk_results = predict_cardio_risk(age, bmi_results['category'], bpm, activity)

    recs_results = generate_recommendations(
        bmi_results['category'], bpm, activity, age, heart_results['status']
    )

    # Calculate ranges
    max_hr = 220 - age
    ideal_bpm_min = 60
    ideal_bpm_max = min(80, int(max_hr * 0.5))
    target_exercise_min = int(max_hr * 0.5)
    target_exercise_max = int(max_hr * 0.85)

    return jsonify({
        "bmi": bmi_results,
        "heart": heart_results,
        "risk": risk_results,
        "recommendations": recs_results,
        "stats": {
            "max_hr": max_hr,
            "ideal_bpm": f"{ideal_bpm_min} - {ideal_bpm_max} BPM",
            "exercise_bpm": f"{target_exercise_min} - {target_exercise_max} BPM"
        }
    })

if __name__ == '__main__':
    # Start local Flask development server, listening on all interfaces
    # Render binds the app to the PORT environment variable, defaulting to 5000 locally
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', debug=True, port=port)
