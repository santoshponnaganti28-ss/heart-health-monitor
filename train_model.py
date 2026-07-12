import os
import csv
import pickle
import urllib.request
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

# URL to the real Framingham Heart Study Dataset on GitHub
DATASET_URL = "https://raw.githubusercontent.com/GauravPadawe/Framingham-Heart-Study/master/framingham.csv"

def download_and_parse_dataset():
    """Downloads the real Framingham Heart Study CSV and parses features."""
    print(f"[INFO] Downloading real Framingham dataset from: {DATASET_URL}...")
    
    try:
        response = urllib.request.urlopen(DATASET_URL)
        csv_data = response.read().decode('utf-8').splitlines()
    except Exception as e:
        print(f"[ERROR] Failed to download dataset: {e}")
        raise e
        
    reader = csv.DictReader(csv_data)
    
    X_raw = []
    y_raw = []
    
    # Track column values to calculate averages for missing data imputation
    age_sum, bmi_sum, hr_sum = 0.0, 0.0, 0.0
    age_count, bmi_count, hr_count = 0, 0, 0
    
    parsed_rows = []
    
    for row in reader:
        try:
            # Extract target
            target = int(row['TenYearCHD'])
            
            # Extract features (allow None temporarily for imputation)
            age_val = float(row['age']) if row['age'] else None
            bmi_val = float(row['BMI']) if row['BMI'] else None
            hr_val = float(row['heartRate']) if row['heartRate'] else None
            
            if age_val is not None:
                age_sum += age_val
                age_count += 1
            if bmi_val is not None:
                bmi_sum += bmi_val
                bmi_count += 1
            if hr_val is not None:
                hr_sum += hr_val
                hr_count += 1
                
            parsed_rows.append({
                'age': age_val,
                'bmi': bmi_val,
                'heartRate': hr_val,
                'target': target
            })
        except ValueError:
            # Skip corrupted rows
            continue
            
    # Calculate column averages for missing values imputation
    avg_age = age_sum / age_count if age_count > 0 else 49.0
    avg_bmi = bmi_sum / bmi_count if bmi_count > 0 else 25.8
    avg_hr = hr_sum / hr_count if hr_count > 0 else 75.0
    
    print(f"[INFO] Parsed {len(parsed_rows)} rows. Imputing missing values with averages...")
    print(f"       Avg Age: {avg_age:.1f}, Avg BMI: {avg_bmi:.1f}, Avg HeartRate: {avg_hr:.1f}")
    
    for r in parsed_rows:
        age_final = r['age'] if r['age'] is not None else avg_age
        bmi_final = r['bmi'] if r['bmi'] is not None else avg_bmi
        hr_final = r['heartRate'] if r['heartRate'] is not None else avg_hr
        
        X_raw.append([age_final, bmi_final, hr_final])
        y_raw.append(r['target'])
        
    return np.array(X_raw), np.array(y_raw)

def train_and_save_model():
    """Trains a Random Forest classifier on the real dataset and serializes it."""
    try:
        X, y = download_and_parse_dataset()
    except Exception:
        print("[WARNING] Could not train on real dataset. Falling back to synthetic training script.")
        # Fallback to simple synthetic generation if GitHub raw download fails
        X, y = generate_synthetic_fallback()
        
    # Split dataset into train and test sets
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
    # Scale features
    print("[INFO] Scaling patient metrics...")
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train Random Forest Classifier
    print("[INFO] Training Random Forest model on Framingham dataset...")
    # Using balanced class weight since heart risk is imbalanced (~15% risk in Framingham)
    model = RandomForestClassifier(n_estimators=150, max_depth=8, class_weight='balanced', random_state=42)
    model.fit(X_train_scaled, y_train)
    
    predictions = model.predict(X_test_scaled)
    accuracy = accuracy_score(y_test, predictions)
    print(f"[SUCCESS] Model trained successfully! Test Accuracy: {accuracy:.2%}")
    print("\nClassification Report:")
    print(classification_report(y_test, predictions))
    
    # Save the artifacts
    base_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(base_dir, 'heart_model.pkl')
    scaler_path = os.path.join(base_dir, 'scaler.pkl')
    
    print(f"[INFO] Saving model to {model_path}...")
    with open(model_path, 'wb') as f:
        pickle.dump(model, f)
        
    print(f"[INFO] Saving scaler to {scaler_path}...")
    with open(scaler_path, 'wb') as f:
        pickle.dump(scaler, f)
        
    print("[SUCCESS] All machine learning artifacts saved successfully!")

def generate_synthetic_fallback(num_samples=1000):
    """Generates synthetic data in case raw network requests fail."""
    np.random.seed(42)
    age = np.random.randint(18, 85, size=num_samples)
    bmi = np.random.uniform(16.0, 42.0, size=num_samples)
    bpm = np.random.randint(45, 140, size=num_samples)
    
    log_odds = -4.5 + 0.04 * (age - 35) + 0.1 * (bmi - 22) + 0.03 * (bpm - 72)
    probability = 1.0 / (1.0 + np.exp(-log_odds))
    heart_disease = np.random.binomial(1, probability)
    
    X = np.column_stack((age, bmi, bpm))
    return X, heart_disease

if __name__ == '__main__':
    train_and_save_model()
