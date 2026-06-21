from flask import Flask, render_template, request, redirect, url_for
import boto3
import time
import base64

app = Flask(__name__)

# SYSTEM INFRASTRUCTURE SINK LINKS
BUCKET_NAME = 'ai-media-uploads-ashutosh-123'
TABLE_NAME = 'ImageMetadataTable'
REGION_NAME = 'ap-southeast-2'

s3 = boto3.client('s3', region_name=REGION_NAME)
rekognition = boto3.client('rekognition', region_name=REGION_NAME)
dynamodb = boto3.resource('dynamodb', region_name=REGION_NAME)
table = dynamodb.Table(TABLE_NAME)

@app.route('/', methods=['GET', 'POST'])
def index():
    active_tab = request.args.get('tab', 'object')
    filename = request.args.get('filename')
    
    item = None
    image_url = None
    analysis_results = None

    if request.method == 'POST':
        form_type = request.form.get('form_type')
        file = request.files.get('file')
        
        if file and file.filename != '':
            image_bytes = file.read()
            # Convert to Base64 so we can show the image immediately without S3 lag
            encoded_image = base64.b64encode(image_bytes).decode('utf-8')
            image_url = f"data:image/jpeg;base64,{encoded_image}"

            # --- MODULE 1: OBJECT CLASSIFIER ---
            if form_type == 'object':
                filename = file.filename
                try:
                    s3.put_object(Bucket=BUCKET_NAME, Key=filename, Body=image_bytes, ACL='public-read', ContentType='image/jpeg')
                    time.sleep(3) 
                    return redirect(url_for('index', tab='object', filename=filename))
                except Exception as e:
                    return f"S3 Error: {str(e)}", 500
            
            # --- MODULE 2: RESUME & TEXT ANALYZER ---
            elif form_type == 'resume':
                active_tab = 'resume'
                try:
                    response = rekognition.detect_text(Image={'Bytes': image_bytes})
                    extracted_words = [text['DetectedText'] for text in response['TextDetections'] if text['Type'] == 'WORD']
                    full_text = " ".join(extracted_words).lower()
                    tech_keywords = ['python', 'java', 'javascript', 'aws', 'docker', 'flask', 'sql', 'html', 'css', 'react', 'cloud']
                    found_skills = [skill.upper() for skill in tech_keywords if skill in full_text]
                    missing_skills = [skill.upper() for skill in tech_keywords if skill not in full_text]
                    analysis_results = {
                        "total_words": len(extracted_words),
                        "skills_found": found_skills if found_skills else ["None Detected"],
                        "skills_missing": missing_skills[:4],
                        "raw_text_preview": " ".join(extracted_words[:40]) + "..."
                    }
                except Exception as e:
                    return f"Text Analyzer Fault: {str(e)}", 500

            # --- MODULE 3: EMOTION SENTIMENT ENGINE ---
            elif form_type == 'emotion':
                active_tab = 'emotion'
                try:
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
                    analysis_results = {"faces": face_details, "count": len(face_details)}
                except Exception as e:
                    return f"Emotion Processing Fault: {str(e)}", 500

    # Handle GET for Object Recognition Persistence
    if filename and active_tab == 'object':
        try:
            response = table.get_item(Key={'ImageName': filename})
            item = response.get('Item')
            image_url = f"https://{BUCKET_NAME}.s3.{REGION_NAME}.amazonaws.com/{filename}"
        except: pass
            
    return render_template('index.html', active_tab=active_tab, item=item, image_url=image_url, filename=filename, analysis_results=analysis_results)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)
