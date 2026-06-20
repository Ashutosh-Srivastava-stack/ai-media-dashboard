from flask import Flask, render_template, request, redirect, url_for, jsonify
import boto3
import os
import time

app = Flask(__name__)

# SYSTEM INFRASTRUCTURE SINK LINKS
BUCKET_NAME = 'ai-media-uploads-ashutosh-123'
TABLE_NAME = 'ImageMetadataTable'
REGION_NAME = 'ap-southeast-2'

s3 = boto3.client('s3', region_name=REGION_NAME)
rekognition = boto3.client('rekognition', region_name=REGION_NAME)
dynamodb = boto3.resource('dynamodb', region_name=REGION_NAME)
table = dynamodb.Table(TABLE_NAME)

@app.route('/', methods=['GET'])
def index():
    active_tab = request.args.get('tab', 'object')
    filename = request.args.get('filename')
    
    # Module 1 variables
    item = None
    image_url = None
    
    # Module 2 & 3 custom results
    analysis_results = None

    if filename and active_tab == 'object':
        try:
            response = table.get_item(Key={'ImageName': filename})
            item = response.get('Item')
            image_url = f"https://{BUCKET_NAME}.s3.{REGION_NAME}.amazonaws.com/{filename}"
        except Exception as e:
            print(f"DynamoDB Query Fault: {e}")
            
    return render_template('index.html', active_tab=active_tab, item=item, image_url=image_url, filename=filename)

# --- MODULE 1: OBJECT CLASSIFIER ENTRYPOINT ---
@app.route('/upload-object', methods=['POST'])
def upload_object():
    file = request.files.get('file')
    if not file or file.filename == '':
        return "No asset selection designated", 400
        
    filename = file.filename
    try:
        s3.upload_fileobj(file, BUCKET_NAME, filename, ExtraArgs={'ACL': 'public-read'})
        time.sleep(3) # Let Lambda process data pipeline
        return redirect(url_for('index', tab='object', filename=filename))
    except Exception as e:
        return f"Pipeline Error: {str(e)}", 500

# --- MODULE 2: RESUME & TEXT ANALYZER ENGINE ---
@app.route('/analyze-resume', methods=['POST'])
def analyze_resume():
    file = request.files.get('file')
    if not file or file.filename == '':
        return redirect(url_for('index', tab='resume'))
        
    try:
        # Read file bytes directly for Rekognition Text Detection
        image_bytes = file.read()
        response = rekognition.detect_text(Image={'Bytes': image_bytes})
        
        extracted_words = [text['DetectedText'] for text in response['TextDetections'] if text['Type'] == 'WORD']
        full_text = " ".join(extracted_words).lower()
        
        # Skill keyword mapping vectors
        tech_keywords = ['python', 'java', 'javascript', 'aws', 'docker', 'flask', 'sql', 'html', 'css', 'react', 'cloud']
        found_skills = [skill.upper() for skill in tech_keywords if skill in full_text]
        missing_skills = [skill.upper() for skill in tech_keywords if skill not in full_text]
        
        results = {
            "total_words": len(extracted_words),
            "skills_found": found_skills if found_skills else ["None Detected"],
            "skills_missing": missing_skills[:4],
            "raw_text_preview": " ".join(extracted_words[:40]) + "..."
        }
        return render_template('index.html', active_tab='resume', analysis_results=results)
    except Exception as e:
        return f"Text Analyzer Fault: {str(e)}", 500

# --- MODULE 3: EMOTION & DEMOGRAPHICS ACCELERATOR ---
@app.route('/analyze-emotion', methods=['POST'])
def analyze_emotion():
    file = request.files.get('file')
    if not file or file.filename == '':
        return redirect(url_for('index', tab='emotion'))
        
    try:
        image_bytes = file.read()
        response = rekognition.detect_faces(Image={'Bytes': image_bytes}, Attributes=['ALL'])
        
        face_details = []
        for face in response.get('FaceDetails', []):
            emotions = [f"{e['Type']}: {e['Confidence']:.1f}%" for e in face['Emotions'] if e['Confidence'] > 40]
            face_details.append({
                "age_range": f"{face['AgeRange']['Low']} - {face['AgeRange']['High']} years",
                "gender": f"{face['Gender']['Value']} ({face['Gender']['Confidence']:.1f}%)",
                "emotions": emotions if emotions else ["Neutral/Calm"],
                "smile": "Yes" if face['Smile']['Value'] else "No"
            })
            
        results = {"faces": face_details, "count": len(face_details)}
        return render_template('index.html', active_tab='emotion', analysis_results=results)
    except Exception as e:
        return f"Emotion Processing Fault: {str(e)}", 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
