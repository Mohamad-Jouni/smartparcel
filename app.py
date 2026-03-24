# -------------------------------------------------------
# SmartParcel — NET_214 Project, Spring 2026
# Author  : Mohammed Jouni
# ID      : 20220001249
# Email   : 20220001249@students.cud.ac.ae
# AWS Acc : 341907318075
# -------------------------------------------------------
import boto3
import uuid
from flask import Flask, request, jsonify

app = Flask(__name__)

# Initialize AWS clients
dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-2')
parcel_table = dynamodb.Table('smartparcel-parcels')

s3_client = boto3.client('s3', region_name='ap-southeast-2')
PHOTO_BUCKET = 'smartparcel-photos-20220001249'

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "hostname": "smartparcel-server"}), 200

@app.route('/parcel', methods=['POST'])
def create_parcel():
    data = request.json
    parcel_id = str(uuid.uuid4())[:8] 
    
    item = {
        'parcel_id': parcel_id,
        'customer_email': data.get('email'),
        'status': 'Label Created',
        'destination': data.get('destination')
    }
    
    parcel_table.put_item(Item=item)
    return jsonify({"message": "Parcel created successfully", "parcel_id": parcel_id}), 201

@app.route('/parcel/<parcel_id>', methods=['GET'])
def get_parcel(parcel_id):
    response = parcel_table.get_item(Key={'parcel_id': parcel_id})
    if 'Item' in response:
        return jsonify(response['Item']), 200
    return jsonify({"error": "Parcel not found"}), 404

@app.route('/parcel/<parcel_id>/photo', methods=['POST'])
def upload_photo(parcel_id):
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400
        
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Empty filename"}), 400
        
    try:
        # Save file to S3 inside a folder named after the parcel ID
        s3_filename = f"{parcel_id}/{uuid.uuid4().hex}_{file.filename}"
        s3_client.upload_fileobj(file, PHOTO_BUCKET, s3_filename)
        
        return jsonify({"message": "Photo uploaded successfully to S3", "path": s3_filename}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# THIS MUST BE AT THE VERY BOTTOM!
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, threaded=True)