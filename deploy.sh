set -euo pipefail

# 1) Create/Update S3 stack
aws cloudformation deploy \
  --template-file templates/s3-buckets.yaml \
  --stack-name photoalbum-s3

# 2) Create/Update IAM roles
aws cloudformation deploy \
  --template-file templates/iam-roles.yaml \
  --stack-name photoalbum-iam \
  --capabilities CAPABILITY_IAM

# 3) Create/Update Lambda functions
aws cloudformation deploy \
  --template-file templates/lambda-functions.yaml \
  --stack-name photoalbum-lambda \
  --capabilities CAPABILITY_IAM

# 4) Create/Update API Gateway
aws cloudformation deploy \
  --template-file templates/api-gateway.yaml \
  --stack-name photoalbum-api \
  --capabilities CAPABILITY_IAM

echo "Deployment complete."
echo "Frontend website URL:"
aws cloudformation describe-stacks \
  --stack-name photoalbum-s3 \
  --query 'Stacks[0].Outputs[?OutputKey==`FrontendWebsiteURL`].OutputValue' \
  --output text

echo "API URL:"
aws cloudformation describe-stacks \
  --stack-name photoalbum-api \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' \
  --output text
