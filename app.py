from flask import Flask, render_template, request, redirect, url_for
import boto3
import os
import time

app = Flask(__name__)

# CONFIGURATION - Set these to match your architecture layout exactly
BUCKET_NAME = 'ai-media-uploads-ashutosh-123'
TABLE_NAME = 'ImageMetadataTable'
REGION_NAME = 'ap-southeast-2'

# Initializing AWS SDK clients
s3 = boto3.client('s3', region_name=REGION_NAME)
dynamodb = boto3.resource('dynamodb', region_name=REGION_NAME)
table = dynamodb.Table(TABLE_NAME)

@app.route('/', methods=['GET'])
def index():
    # Identify if a specific image tracking event just completed
    filename = request.args.get('filename')
    item = None
    image_url = None
    
    if filename:
        try:
            # Query only the individual file record from the database registry
            response = table.get_item(Key={'ImageName': filename})
            item = response.get('Item')
            
            # Formulate the public CDN access link for the UI preview engine
            image_url = f"https://{BUCKET_NAME}.s3.{REGION_NAME}.amazonaws.com/{filename}"
        except Exception as e:
            print(f"Error querying DynamoDB registry: {e}")
            
    return render_template('index.html', item=item, image_url=image_url, filename=filename)

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "No asset packet delivered", 400
        
    file = request.files['file']
    if file.filename == '':
        return "No asset selection designated", 400

    if file:
        filename = file.filename
        try:
            # Uploading directly with public visibility parameters assigned
            s3.upload_fileobj(
                file, 
                BUCKET_NAME, 
                filename,
                ExtraArgs={'ACL': 'public-read'}
            )
            
            # Giving the AWS Lambda event thread 3 seconds to finalize processing
            time.sleep(3)
            
            # Returning the dashboard context back to the file tracking system
            return redirect(url_for('index', filename=filename))
        except Exception as e:
            return f"Storage transmission fault: {str(e)}", 500

if __name__ == '__main__':
    # Running on port 80 so it matches the exposed configuration for Docker/EC2
    app.run(host='0.0.0.0', port=80)
