#!/bin/bash
set -euo pipefail

# ============================================================
# AWS Ops Agent — One-Click Deploy to ECS Fargate
# ============================================================
# Usage:
#   ./deploy/deploy.sh --vpc vpc-xxx --subnets subnet-aaa,subnet-bbb
#   ./deploy/deploy.sh --vpc vpc-xxx --subnets subnet-aaa,subnet-bbb --profile my-profile
#   ./deploy/deploy.sh --vpc vpc-xxx --subnets subnet-aaa,subnet-bbb --region us-west-2
#   ./deploy/deploy.sh --destroy   (tear down the stack)
# ============================================================

STACK_NAME="ops-agent-dashboard"
ECR_REPO_NAME="ops-agent"
IMAGE_TAG="latest"
REGION="${AWS_DEFAULT_REGION:-us-east-1}"
PROFILE=""
VPC_ID=""
SUBNET_IDS=""
API_KEY=""
DESTROY=false

# Parse arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --vpc) VPC_ID="$2"; shift 2 ;;
    --subnets) SUBNET_IDS="$2"; shift 2 ;;
    --profile) PROFILE="$2"; shift 2 ;;
    --region) REGION="$2"; shift 2 ;;
    --api-key) API_KEY="$2"; shift 2 ;;
    --stack-name) STACK_NAME="$2"; shift 2 ;;
    --destroy) DESTROY=true; shift ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

AWS_CMD="aws"
if [ -n "$PROFILE" ]; then
  AWS_CMD="aws --profile $PROFILE"
fi
AWS_CMD="$AWS_CMD --region $REGION"

# --- Destroy mode ---
if [ "$DESTROY" = true ]; then
  echo "🗑  Destroying stack: $STACK_NAME"
  $AWS_CMD cloudformation delete-stack --stack-name "$STACK_NAME"
  echo "⏳ Waiting for stack deletion..."
  $AWS_CMD cloudformation wait stack-delete-complete --stack-name "$STACK_NAME"
  echo "✅ Stack deleted."
  # Clean up ECR
  ACCOUNT_ID=$($AWS_CMD sts get-caller-identity --query Account --output text)
  ECR_URI="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO_NAME"
  echo "🗑  Deleting ECR repository: $ECR_REPO_NAME"
  $AWS_CMD ecr delete-repository --repository-name "$ECR_REPO_NAME" --force 2>/dev/null || true
  echo "✅ Cleanup complete."
  exit 0
fi

# --- Validate inputs ---
if [ -z "$VPC_ID" ] || [ -z "$SUBNET_IDS" ]; then
  echo "❌ Required: --vpc and --subnets"
  echo ""
  echo "Usage:"
  echo "  ./deploy/deploy.sh --vpc vpc-xxx --subnets subnet-aaa,subnet-bbb"
  echo ""
  echo "Find your VPC and subnets:"
  echo "  aws ec2 describe-vpcs --query 'Vpcs[].{Id:VpcId,Name:Tags[?Key==\`Name\`].Value|[0]}' --output table"
  echo "  aws ec2 describe-subnets --filters Name=vpc-id,Values=YOUR_VPC_ID --query 'Subnets[?MapPublicIpOnLaunch].{Id:SubnetId,AZ:AvailabilityZone}' --output table"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "============================================================"
echo "⚡🔧 AWS Ops Agent — Deploying to ECS Fargate"
echo "============================================================"
echo "Region:    $REGION"
echo "VPC:       $VPC_ID"
echo "Subnets:   $SUBNET_IDS"
echo "Stack:     $STACK_NAME"
echo "============================================================"

# Step 1: Get account ID
ACCOUNT_ID=$($AWS_CMD sts get-caller-identity --query Account --output text)
ECR_URI="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO_NAME"
echo ""
echo "📦 Step 1/4: Setting up ECR repository..."

# Create ECR repo if it doesn't exist
$AWS_CMD ecr describe-repositories --repository-names "$ECR_REPO_NAME" 2>/dev/null || \
  $AWS_CMD ecr create-repository --repository-name "$ECR_REPO_NAME" --image-scanning-configuration scanOnPush=true

# Step 2: Build and push Docker image
echo ""
echo "🐳 Step 2/4: Building and pushing Docker image..."
$AWS_CMD ecr get-login-password | docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"
docker build -t "$ECR_REPO_NAME:$IMAGE_TAG" "$PROJECT_DIR"
docker tag "$ECR_REPO_NAME:$IMAGE_TAG" "$ECR_URI:$IMAGE_TAG"
docker push "$ECR_URI:$IMAGE_TAG"
echo "✅ Image pushed: $ECR_URI:$IMAGE_TAG"

# Step 3: Generate API key if not provided
if [ -z "$API_KEY" ]; then
  API_KEY=$(python3 -c "import secrets; print(f'ops-{secrets.token_urlsafe(32)}')")
  echo ""
  echo "🔑 Generated API key: $API_KEY"
  echo "   Save this — you'll need it for API access."
fi

# Step 4: Deploy CloudFormation stack
echo ""
echo "☁️  Step 3/4: Deploying CloudFormation stack..."
$AWS_CMD cloudformation deploy \
  --template-file "$SCRIPT_DIR/cloudformation.yaml" \
  --stack-name "$STACK_NAME" \
  --parameter-overrides \
    ImageUri="$ECR_URI:$IMAGE_TAG" \
    VpcId="$VPC_ID" \
    SubnetIds="$SUBNET_IDS" \
    ApiKey="$API_KEY" \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset

# Step 5: Get outputs
echo ""
echo "🔍 Step 4/4: Getting dashboard URL..."
DASHBOARD_URL=$($AWS_CMD cloudformation describe-stacks \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs[?OutputKey==`DashboardURL`].OutputValue' \
  --output text)

echo ""
echo "============================================================"
echo "✅ AWS Ops Agent deployed successfully!"
echo "============================================================"
echo ""
echo "🌐 Dashboard:  $DASHBOARD_URL"
echo "🔑 API Key:    $API_KEY"
echo ""
echo "The ALB may take 1-2 minutes to become healthy."
echo ""
echo "To tear down:"
echo "  ./deploy/deploy.sh --destroy${PROFILE:+ --profile $PROFILE} --region $REGION"
echo "============================================================"
