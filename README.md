# SmartParcel API
Backend API for the SmartParcel delivery tracking system.

## Features
- Create new parcels (DynamoDB)
- Upload delivery proof photos (S3)
- Trigger email notifications on status changes (SQS -> Lambda -> SNS)