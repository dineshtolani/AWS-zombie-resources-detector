#!/usr/bin/env bash
set -euo pipefail

# Project Acheron — SAM Deploy Script
# Prerequisites:
#   - AWS CLI configured
#   - AWS SAM CLI installed
#   - SES email identity verified

STACK_NAME="${1:-acheron}"
REGION="${2:-us-east-1}"
CONFIRM="${3:-}"
S3_BUCKET="acheron-deploy-$(aws sts get-caller-identity --query Account --output text)-${REGION}"

echo "==> Creating deployment S3 bucket (if needed)..."
aws s3 mb "s3://${S3_BUCKET}" --region "${REGION}" 2>/dev/null || true

echo "==> Building SAM application..."
sam build --template sam/template.yaml

echo "==> Deploying stack: ${STACK_NAME}"
sam deploy \
    --stack-name "${STACK_NAME}" \
    --s3-bucket "${S3_BUCKET}" \
    --region "${REGION}" \
    --capabilities CAPABILITY_IAM \
    --parameter-overrides \
        FromEmail="acheron@example.com" \
        ReportRecipients="ops@example.com" \
        ContaminationRate="0.20" \
        LogGroups="/aws/lambda/*,/aws/eks/*" \
        EksClusterNames="eks-prod,eks-staging" \
    --no-fail-on-empty-changeset

echo "==> Stack outputs:"
aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --query "Stacks[0].Outputs[].[OutputKey,OutputValue]" \
    --output table

echo "==> Done. Invoke a manual test:"
echo "    aws stepfunctions start-execution \\"
echo "      --state-machine-arn \$(aws cloudformation describe-stacks \\"
echo "        --stack-name ${STACK_NAME} \\"
echo "        --query 'Stacks[0].Outputs[?OutputKey==\"StateMachineArn\"].OutputValue' \\"
echo "        --output text) \\"
echo "      --input '{\"trigger\":\"manual\",\"week_number\":1,\"recipients\":[\"ops@example.com\"]}'"
