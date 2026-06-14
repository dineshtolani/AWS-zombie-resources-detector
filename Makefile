.PHONY: all build deploy clean invoke test

STACK_NAME ?= acheron
REGION ?= us-east-1

all: build

build:
	sam build --template sam/template.yaml

deploy:
	@echo "Deploying stack: $(STACK_NAME) in $(REGION)"
	sam deploy \
		--stack-name $(STACK_NAME) \
		--s3-bucket acheron-deploy-$(shell aws sts get-caller-identity --query Account --output text)-$(REGION) \
		--region $(REGION) \
		--capabilities CAPABILITY_IAM \
		--parameter-overrides \
			FromEmail="acheron@example.com" \
			ReportRecipients="ops@example.com" \
			ContaminationRate="0.20" \
		--no-fail-on-empty-changeset

invoke:
	@echo "Manually triggering Acheron scan..."
	SM_ARN=$$(aws cloudformation describe-stacks \
		--stack-name $(STACK_NAME) \
		--query 'Stacks[0].Outputs[?OutputKey==`StateMachineArn`].OutputValue' \
		--output text) && \
	aws stepfunctions start-execution \
		--state-machine-arn $$SM_ARN \
		--input '{"trigger":"manual","week_number":1,"recipients":["ops@example.com"]}'

clean:
	rm -rf .aws-sam/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

test:
	python3 run.py --weeks 1 --reset

simulate:
	python3 run.py --weeks 6

.PHONY: layer
layer:
	@echo "Building scikit-learn Lambda layer..."
	mkdir -p layers/sklearn/python
	pip install scikit-learn joblib -t layers/sklearn/python --no-deps 2>/dev/null || \
	pip install scikit-learn joblib -t layers/sklearn/python 2>&1 | tail -3
	@echo "Layer size: $$(du -sh layers/sklearn/python | cut -f1)"
