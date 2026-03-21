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

# Initialize AWS clients (the IAM role on EC2 will handle credentials automatically!)
dynamodb = boto3.resource('dynamodb', region_name='ap-southeast-2')
parcel_table = dynamodb.Table('smartparcel-parcels')

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy", "hostname": "smartparcel-server"}), 200

@app.route('/parcel', methods=['POST'])
def create_parcel():
    data = request.json
    # Generate a random 8-character parcel ID
    parcel_id = str(uuid.uuid4())[:8] 
    
    item = {
        'parcel_id': parcel_id,
        'customer_email': data.get('email'),
        'status': 'Label Created',
        'destination': data.get('destination')
    }
    
    # Save to DynamoDB
    parcel_table.put_item(Item=item)
    return jsonify({"message": "Parcel created successfully", "parcel_id": parcel_id}), 201

@app.route('/parcel/<parcel_id>', methods=['GET'])
def get_parcel(parcel_id):
    # Retrieve from DynamoDB
    response = parcel_table.get_item(Key={'parcel_id': parcel_id})
    if 'Item' in response:
        return jsonify(response['Item']), 200
    return jsonify({"error": "Parcel not found"}), 404

# THIS MUST BE AT THE VERY BOTTOM!
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, threaded=True)