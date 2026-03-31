# -------------------------------------------------------
# SmartParcel — NET_214 Project, Spring 2026
# Author  : Mohammed Jouni
# ID      : 20220001249
# -------------------------------------------------------
import boto3
import uuid
import json
import logging
import socket
from datetime import datetime
from flask import Flask, request, jsonify, g

app = Flask(__name__)

# --- CONFIGURATION & AWS CLIENTS ---
REGION = 'ap-southeast-2'
PHOTO_BUCKET = 'smartparcel-photos-20220001249'
QUEUE_URL = 'https://sqs.ap-southeast-2.amazonaws.com/341907318075/smartparcel-notifications-20220001249'

dynamodb = boto3.resource('dynamodb', region_name=REGION)
parcel_table = dynamodb.Table('smartparcel-parcels')
s3_client = boto3.client('s3', region_name=REGION)
sqs_client = boto3.client('sqs', region_name=REGION)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- SECURITY: MOCK DATABASE FOR API KEYS ---
VALID_KEYS = {
    "key-admin-001": {"role": "admin", "name": "Admin User"},
    "key-driver-001": {"role": "driver", "name": "Khalid"},
    "key-customer-001": {"role": "customer", "name": "Mohammed"}
}

# --- SECURITY MIDDLEWARE ---
@app.before_request
def security_check():
    # 1. Skip auth for health check
    if request.path == '/health':
        return

    # 2. Check Payload Size (Prevent DoS)
    if request.content_length and request.content_length > 10000:  # 10KB limit for JSON
        if not request.path.endswith('/photo'): # allow photos to be larger
            return jsonify({"error": "Payload too large"}), 400

    # 3. SQL Injection / Input Validation
    if request.is_json and request.json:
        payload_str = request.get_data(as_text=True).upper()
        if any(bad_string in payload_str for bad_string in ["'", "DROP TABLE", "SELECT *"]):
            return jsonify({"error": "Invalid characters detected. SQL Injection attempt blocked."}), 400

    # 4. API Key Authentication
    api_key = request.headers.get('X-API-Key')
    if not api_key or api_key not in VALID_KEYS:
        return jsonify({"error": "Unauthorized. Missing or invalid X-API-Key."}), 401
    
    # Store user info for this request
    g.user = VALID_KEYS[api_key]

@app.after_request
def log_request(response):
    logging.info(f"Method: {request.method} Path: {request.path} Status: {response.status_code}")
    return response

# --- ENDPOINTS ---

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "hostname": socket.gethostname()}), 200

@app.route('/api/parcels', methods=['POST'])
def create_parcel():
    if g.user['role'] not in ['admin', 'driver']:
        return jsonify({"error": "Forbidden. Only drivers or admins can create parcels."}), 403
    
    data = request.json
    if not data or 'sender' not in data or 'receiver' not in data or 'address' not in data:
        return jsonify({"error": "Missing required fields: sender, receiver, address"}), 400

    parcel_id = f"PKG-2026-{str(uuid.uuid4().hex)[:6]}"
    
    item = {
        'parcel_id': parcel_id,
        'customer_email': data.get('receiver_email', 'default@example.com'),
        'sender': data['sender'],
        'receiver': data['receiver'],
        'address': data['address'],
        'status': 'label_created',
        'created_at': datetime.utcnow().isoformat() + "Z"
    }
    
    parcel_table.put_item(Item=item)
    return jsonify({"message": "Parcel created successfully", "parcel_id": parcel_id}), 201

@app.route('/api/parcels/<parcel_id>', methods=['GET'])
def get_parcel(parcel_id):
    # Any authenticated user can view (checked by middleware)
    response = parcel_table.get_item(Key={'parcel_id': parcel_id})
    if 'Item' in response:
        return jsonify(response['Item']), 200
    return jsonify({"error": "Parcel not found"}), 404

@app.route('/api/parcels/<parcel_id>/status', methods=['PUT'])
def update_status(parcel_id):
    if g.user['role'] != 'driver':
        return jsonify({"error": "Forbidden. Only drivers can update status."}), 403

    data = request.json
    new_status = data.get('status')
    valid_statuses = ['picked_up', 'in_transit', 'delivered']
    
    if new_status not in valid_statuses:
        return jsonify({"error": f"Invalid status. Must be one of {valid_statuses}"}), 400
        
    response = parcel_table.get_item(Key={'parcel_id': parcel_id})
    if 'Item' not in response:
        return jsonify({"error": "Parcel not found"}), 404
        
    parcel = response['Item']
    
    parcel_table.update_item(
        Key={'parcel_id': parcel_id},
        UpdateExpression="set #st = :s",
        ExpressionAttributeNames={'#st': 'status'},
        ExpressionAttributeValues={':s': new_status}
    )
    
    # SQS Payload formatted exactly as rubric requested
    message_body = {
        "parcel_id": parcel_id,
        "new_status": new_status,
        "customer_email": parcel.get('customer_email', 'test@example.com'),
        "driver_name": g.user['name'],
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "photo_url": parcel.get('photo_url', '')
    }
    
    sqs_client.send_message(QueueUrl=QUEUE_URL, MessageBody=json.dumps(message_body))
    return jsonify({"message": "Status updated and notification triggered"}), 200

@app.route('/api/parcels', methods=['GET'])
def list_parcels():
    if g.user['role'] != 'admin':
        return jsonify({"error": "Forbidden. Only admins can list all parcels."}), 403
        
    # Simple scan for demo purposes
    response = parcel_table.scan()
    return jsonify({"parcels": response.get('Items', [])}), 200

@app.route('/api/parcels/<parcel_id>', methods=['DELETE'])
def delete_parcel(parcel_id):
    if g.user['role'] != 'admin':
        return jsonify({"error": "Forbidden. Only admins can delete parcels."}), 403
        
    response = parcel_table.get_item(Key={'parcel_id': parcel_id})
    if 'Item' not in response:
        return jsonify({"error": "Parcel not found"}), 404
        
    if response['Item'].get('status') != 'label_created':
        return jsonify({"error": "Cannot cancel a parcel that has already been picked up."}), 400
        
    parcel_table.delete_item(Key={'parcel_id': parcel_id})
    return jsonify({"message": "Parcel deleted successfully"}), 200

@app.route('/api/parcels/<parcel_id>/photo', methods=['POST'])
def upload_photo(parcel_id):
    if g.user['role'] != 'driver':
        return jsonify({"error": "Forbidden. Only drivers can upload photos."}), 403

    if 'photo' not in request.files:
        return jsonify({"error": "No file uploaded. Key must be 'photo'."}), 400
        
    file = request.files['photo']
    if file.filename == '':
        return jsonify({"error": "Empty filename"}), 400
        
    try:
        s3_filename = f"{parcel_id}/proof.jpg"
        s3_client.upload_fileobj(file, PHOTO_BUCKET, s3_filename)
        photo_url = f"s3://{PHOTO_BUCKET}/{s3_filename}"
        
        # Update DynamoDB with photo URL
        parcel_table.update_item(
            Key={'parcel_id': parcel_id},
            UpdateExpression="set photo_url = :p",
            ExpressionAttributeValues={':p': photo_url}
        )
        
        return jsonify({"parcel_id": parcel_id, "photo_url": photo_url}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, threaded=True)