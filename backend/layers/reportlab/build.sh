#!/usr/bin/env bash
# Build ReportLab Lambda layer for Python 3.12
# This script creates a Lambda-compatible layer structure in backend/layers/reportlab-build/

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${SCRIPT_DIR}/../reportlab-build"
PYTHON_DIR="${BUILD_DIR}/python"

echo "Building ReportLab Lambda layer..."

# Clean previous build
rm -rf "$BUILD_DIR"
mkdir -p "$PYTHON_DIR"

# Install dependencies using Docker to ensure Linux x86_64 compatibility
# Lambda expects packages in python/ directory at the root of the layer
docker run --rm \
  -v "$SCRIPT_DIR:/src" \
  -v "$PYTHON_DIR:/out/python" \
  public.ecr.aws/lambda/python:3.12 \
  pip install -r /src/requirements.txt -t /out/python --no-cache-dir

echo "Layer built successfully at: $BUILD_DIR"
echo "Layer size:"
du -sh "$BUILD_DIR"
