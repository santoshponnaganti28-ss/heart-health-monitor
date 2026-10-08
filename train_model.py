import os
import csv
import pickle
import urllib.request
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier, VotingClassifier
from sklearn.metrics import accuracy_score, roc_auc_score, classification_report

DATASET_URL = "https://raw.githubusercontent.com/GauravPadawe/Framingham-Heart-Study/master/framingham.csv"

# Clinical default baselines (for unmeasured / optional inputs)
CLINICAL_DEFAULTS = {
    'sys_bp': 120.0,    # Normal adult baseline systolic BP (mmHg)
    'glucose': 85.0,    # Normal fasting blood glucose (mg/dL)
    'tot_chol': 200.0,  # Desirable total cholesterol (mg/dL)
    'cigs_per_day': 0.0,
    'bp_meds': 0.0,
    'diabetes': 0.0,
    'current_smoker': 0.0
}

def extract_features(age, bmi, bpm, smoker=0, cigs=0, diabetes=0, sys_bp=None, glucose=None, chol=None, bp_meds=0):
    """
    Extracts 15 clinical and physiologically engineered cardiovascular features.
    Handles optional lab metrics gracefully via standard clinical baselines.
    """
    age = float(age)
    bmi = float(bmi)
    bpm = float(bpm)
    smoker = 1.0 if (smoker or cigs > 0) else 0.0
    cigs = float(cigs) if cigs is not None else 0.0
    diabetes = float(diabetes) if diabetes is not None else 0.0
    bp_meds = float(bp_meds) if bp_meds is not None else 0.0

    # Impute optional fields if not provided
    sys_bp = float(sys_bp) if (sys_bp is not None and str(sys_bp).strip() != "") else CLINICAL_DEFAULTS['sys_bp']
    glucose = float(glucose) if (glucose is not None and str(glucose).strip() != "") else CLINICAL_DEFAULTS['glucose']
    chol = float(chol) if (chol is not None and str(chol).strip() != "") else CLINICAL_DEFAULTS['tot_chol']

    # Engineered interaction and strain features
    age_sq = (age / 50.0) ** 2
    bmi_cat = 0.0 if bmi < 18.5 else (1.0 if bmi < 25.0 else (2.0 if bmi < 30.0 else 3.0))
    hr_ratio = bpm / max(1.0, (220.0 - age))
    bp_strain = sys_bp / 120.0
    glucose_risk = 1.0 if glucose > 125.0 else (0.5 if glucose > 100.0 else 0.0)

    return [
        age,            # 1. Age (years)
        bmi,            # 2. Body Mass Index (kg/m^2)
        bpm,            # 3. Resting Heart Rate (BPM)
        smoker,         # 4. Current Smoker (0 or 1)
        cigs,           # 5. Cigarettes per day
        diabetes,       # 6. Diabetes status (0 or 1)
        sys_bp,         # 7. Systolic Blood Pressure (mmHg)
        glucose,        # 8. Fasting Blood Glucose (mg/dL)
        chol,           # 9. Total Cholesterol (mg/dL)
        bp_meds,        # 10. On BP Medication (0 or 1)
        age_sq,         # 11. Vascular Aging Acceleration
        bmi_cat,        # 12. Adiposity Category Score
        hr_ratio,       # 13. Cardiac Pulse Reserve Strain
        bp_strain,      # 14. Arterial Pressure Strain Ratio
        glucose_risk    # 15. Hyperglycemic Pre-diabetes Score
    ]

FEATURE_NAMES = [
    "Age (Years)",
    "Body Mass Index (BMI)",
    "Resting Heart Rate (BPM)",
    "Current Smoker (Yes/No)",
    "Cigarettes Per Day",
    "Diabetes Diagnosis (Yes/No)",
    "Systolic Blood Pressure (mmHg)",
    "Fasting Blood Glucose (mg/dL)",
    "Total Cholesterol (mg/dL)",
    "Blood Pressure Medication",
    "Vascular Aging Index (Age²)",
    "BMI Clinical Category Score",
    "Heart Rate Reserve Strain (BPM/MaxHR)",
    "Arterial Pressure Strain (SysBP/120)",
    "Hyperglycemic Risk Indicator"
]

def download_and_parse_dataset():
    """Downloads Framingham Heart Study CSV and parses features."""
    print(f"[INFO] Fetching Framingham dataset from: {DATASET_URL}...")
    
    try:
        response = urllib.request.urlopen(DATASET_URL, timeout=10)
        csv_data = response.read().decode('utf-8').splitlines()
    except Exception as e:
        print(f"[WARNING] Failed to download online dataset: {e}. Falling back to synthetic generator.")
        return generate_synthetic_fallback()
        
    reader = csv.DictReader(csv_data)
    parsed_rows = []
    
    for row in reader:
        try:
            target = int(row['TenYearCHD'])
            age_v = float(row['age']) if row.get('age') else None
            bmi_v = float(row['BMI']) if row.get('BMI') else None
            hr_v = float(row['heartRate']) if row.get('heartRate') else None
            cigs_v = float(row['cigsPerDay']) if row.get('cigsPerDay') else 0.0
            smoker_v = float(row['currentSmoker']) if row.get('currentSmoker') else (1.0 if cigs_v > 0 else 0.0)
            diabetes_v = float(row['diabetes']) if row.get('diabetes') else 0.0
            sys_bp_v = float(row['sysBP']) if row.get('sysBP') else None
            glucose_v = float(row['glucose']) if row.get('glucose') else None
            chol_v = float(row['totChol']) if row.get('totChol') else None
            bp_meds_v = float(row['BPMeds']) if row.get('BPMeds') else 0.0
            
            parsed_rows.append({
                'age': age_v,
                'bmi': bmi_v,
                'bpm': hr_v,
                'smoker': smoker_v,
                'cigs': cigs_v,
                'diabetes': diabetes_v,
                'sys_bp': sys_bp_v,
                'glucose': glucose_v,
                'chol': chol_v,
                'bp_meds': bp_meds_v,
                'target': target
            })
        except (ValueError, KeyError):
            continue

    # Population averages for missing clinical entries
    avg_age = np.mean([r['age'] for r in parsed_rows if r['age']]) or 49.6
    avg_bmi = np.mean([r['bmi'] for r in parsed_rows if r['bmi']]) or 25.8
    avg_hr = np.mean([r['bpm'] for r in parsed_rows if r['bpm']]) or 75.9
    avg_sys = np.mean([r['sys_bp'] for r in parsed_rows if r['sys_bp']]) or 132.4
    avg_glu = np.mean([r['glucose'] for r in parsed_rows if r['glucose']]) or 81.9
    avg_chol = np.mean([r['chol'] for r in parsed_rows if r['chol']]) or 236.9
    
    print(f"[INFO] Parsed {len(parsed_rows)} clinical records.")
    print(f"       Baselines -> sysBP: {avg_sys:.1f}, Glucose: {avg_glu:.1f}, Cholesterol: {avg_chol:.1f}")
    
    X, y = [], []
    for r in parsed_rows:
        features = extract_features(
            age=r['age'] if r['age'] is not None else avg_age,
            bmi=r['bmi'] if r['bmi'] is not None else avg_bmi,
            bpm=r['bpm'] if r['bpm'] is not None else avg_hr,
            smoker=r['smoker'],
            cigs=r['cigs'],
            diabetes=r['diabetes'],
            sys_bp=r['sys_bp'] if r['sys_bp'] is not None else avg_sys,
            glucose=r['glucose'] if r['glucose'] is not None else avg_glu,
            chol=r['chol'] if r['chol'] is not None else avg_chol,
            bp_meds=r['bp_meds']
        )
        X.append(features)
        y.append(r['target'])
        
    return np.array(X), np.array(y)

def generate_synthetic_fallback(num_samples=2500):
    """Generates synthetic epidemiological data if network request is unavailable."""
    np.random.seed(42)
    ages = np.random.randint(20, 82, size=num_samples)
    bmis = np.random.uniform(18.0, 42.0, size=num_samples)
    bpms = np.random.randint(50, 130, size=num_samples)
    smokers = np.random.binomial(1, 0.45, size=num_samples)
    cigs = [np.random.randint(5, 30) if s else 0 for s in smokers]
    diab = np.random.binomial(1, 0.08, size=num_samples)
    sys_bps = np.random.normal(130, 20, size=num_samples)
    glucoses = np.random.normal(85, 25, size=num_samples)
    chols = np.random.normal(230, 40, size=num_samples)
    bp_meds = np.random.binomial(1, 0.1, size=num_samples)
    
    X, y = [], []
    for i in range(num_samples):
        log_odds = -4.5 + 0.05 * (ages[i] - 35) + 0.06 * (bmis[i] - 22) + 0.02 * (bpms[i] - 70) + 0.4 * smokers[i] + 0.7 * diab[i] + 0.02 * (sys_bps[i] - 120)
        prob = 1.0 / (1.0 + np.exp(-log_odds))
        target = np.random.binomial(1, prob)
        
        feat = extract_features(
            age=ages[i], bmi=bmis[i], bpm=bpms[i], smoker=smokers[i],
            cigs=cigs[i], diabetes=diab[i], sys_bp=sys_bps[i],
            glucose=glucoses[i], chol=chols[i], bp_meds=bp_meds[i]
        )
        X.append(feat)
        y.append(target)
        
    return np.array(X), np.array(y)

def train_and_save_model():
    """Trains high-accuracy Ensemble Classifier on full clinical feature set."""
    X, y = download_and_parse_dataset()
    
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    
    print("[INFO] Scaling 15-dimensional clinical feature vectors...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    print("[INFO] Training Ensemble Classifier (Gradient Boosting + Random Forest)...")
    gb = GradientBoostingClassifier(
        n_estimators=140,
        learning_rate=0.05,
        max_depth=3,
        subsample=0.85,
        random_state=42
    )
    
    rf = RandomForestClassifier(
        n_estimators=200,
        max_depth=6,
        min_samples_leaf=4,
        max_features='sqrt',
        random_state=42
    )
    
    model = VotingClassifier(
        estimators=[('gb', gb), ('rf', rf)],
        voting='soft'
    )
    model.fit(X_train_scaled, y_train)
    
    predictions = model.predict(X_test_scaled)
    prob_preds = model.predict_proba(X_test_scaled)[:, 1]
    
    accuracy = accuracy_score(y_test, predictions)
    auc = roc_auc_score(y_test, prob_preds)
    
    print(f"\n[SUCCESS] Model Optimization Completed!")
    print(f"==================================================")
    print(f" Clinical Features Used: {len(FEATURE_NAMES)}")
    print(f" Test Accuracy:          {accuracy:.2%}")
    print(f" ROC-AUC Score:          {auc:.3f}")
    print(f"==================================================")
    print("\nClassification Report:")
    print(classification_report(y_test, predictions, target_names=['Low/Norm Risk', 'High Risk']))
    
    base_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(base_dir, 'heart_model.pkl')
    scaler_path = os.path.join(base_dir, 'scaler.pkl')
    
    print(f"[INFO] Saving model to {model_path}...")
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
        
    print(f"[INFO] Saving scaler to {scaler_path}...")
    with open(scaler_path, 'wb') as f:
        pickle.dump(scaler, f)
        
    print("[SUCCESS] All clinical ML artifacts saved successfully!\n")

if __name__ == '__main__':
    train_and_save_model()
