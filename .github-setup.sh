#!/bin/bash
# This script would create the GitHub Actions workflow structure
# Run: bash .github-setup.sh

mkdir -p .github/workflows
cat > .github/workflows/ci.yml << 'EOF'
name: MCP SOC CI/CD Pipeline

on:
  push:
    branches:
      - main
      - develop
  pull_request:
    branches:
      - main
      - develop

env:
  PYTHON_VERSION: '3.12'
  REDIS_HOST: localhost
  REDIS_PORT: 6379
  MONGODB_HOST: localhost
  MONGODB_PORT: 27017

jobs:
  lint:
    name: Lint Code
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install ruff bandit

      - name: Lint with Ruff
        run: ruff check . --exit-zero
        continue-on-error: true

      - name: Security scan with Bandit
        run: bandit -r . -ll --skip B101,B601
        continue-on-error: true

  test:
    name: Run Tests
    runs-on: ubuntu-latest
    services:
      redis:
        image: redis:7-alpine
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 6379:6379

      mongodb:
        image: mongo:7
        options: >-
          --health-cmd "mongosh --eval 'db.adminCommand(\"ping\")'
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 27017:27017
        env:
          MONGO_INITDB_ROOT_USERNAME: root
          MONGO_INITDB_ROOT_PASSWORD: password

    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ env.PYTHON_VERSION }}

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          if [ -f requirements.txt ]; then pip install -r requirements.txt; fi
          pip install pytest pytest-cov pytest-asyncio

      - name: Run tests with coverage
        env:
          REDIS_HOST: ${{ env.REDIS_HOST }}
          REDIS_PORT: ${{ env.REDIS_PORT }}
          MONGODB_HOST: ${{ env.MONGODB_HOST }}
          MONGODB_PORT: ${{ env.MONGODB_PORT }}
          MONGODB_USER: root
          MONGODB_PASSWORD: password
          PYTHONPATH: ${{ github.workspace }}
        run: |
          pytest \
            --cov=. \
            --cov-report=xml \
            --cov-report=html \
            --cov-report=term-missing \
            --junitxml=junit.xml \
            -v

      - name: Upload coverage reports to Codecov
        uses: codecov/codecov-action@v3
        with:
          file: ./coverage.xml
          flags: unittests
          name: codecov-umbrella
          fail_ci_if_error: false
        continue-on-error: true

      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: test-results
          path: |
            junit.xml
            htmlcov/

  docker:
    name: Validate Docker Build
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v2

      - name: Check if Dockerfile exists
        id: dockerfile_check
        run: |
          if [ -f Dockerfile ]; then
            echo "exists=true" >> $GITHUB_OUTPUT
          else
            echo "exists=false" >> $GITHUB_OUTPUT
          fi

      - name: Build Docker image
        if: steps.dockerfile_check.outputs.exists == 'true'
        uses: docker/build-push-action@v4
        with:
          context: .
          push: false
          tags: mcp-soc:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max

  quality-gate:
    name: Quality Gate
    runs-on: ubuntu-latest
    needs: [lint, test]
    if: always()
    steps:
      - name: Check test status
        run: |
          if [ "${{ needs.test.result }}" == "failure" ]; then
            echo "Tests failed!"
            exit 1
          fi

      - name: Check lint status
        run: |
          if [ "${{ needs.lint.result }}" == "failure" ]; then
            echo "Linting failed!"
            exit 1
          fi

      - name: Summary
        run: |
          echo "## CI/CD Pipeline Summary" >> $GITHUB_STEP_SUMMARY
          echo "✅ All quality gates passed!" >> $GITHUB_STEP_SUMMARY
          echo "- Linting: ${{ needs.lint.result }}" >> $GITHUB_STEP_SUMMARY
          echo "- Tests: ${{ needs.test.result }}" >> $GITHUB_STEP_SUMMARY
EOF

echo "GitHub Actions workflow structure created successfully!"
