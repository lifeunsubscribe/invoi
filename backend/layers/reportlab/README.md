# ReportLab Lambda Layer

Lambda layer containing ReportLab and Pillow for PDF generation in AWS Lambda.

## Contents

- **reportlab** >=4.1.0 - PDF generation library
- **Pillow** >=10.0.0 - Image processing library (ReportLab dependency)

## Building the Layer

The layer must be built on a Linux x86_64 platform to ensure compatibility with AWS Lambda.

### Prerequisites

- Docker installed and running
- Internet connection (to pull Lambda Python image and pip packages)

### Build Command

```bash
cd backend/layers/reportlab
./build.sh
```

This script:
1. Removes any previous build artifacts
2. Uses the official AWS Lambda Python 3.12 Docker image
3. Installs dependencies from `requirements.txt` into the correct directory structure
4. Outputs the layer to `backend/layers/reportlab-build/`

### Directory Structure

After building, the layer will have this structure:

```
reportlab-build/
└── python/
    ├── reportlab/
    ├── PIL/
    └── ... (other dependencies)
```

AWS Lambda expects packages in the `python/` directory at the root of the layer.

## Layer Size

The layer should be under 50MB (Lambda limit). Check size with:

```bash
du -sh backend/layers/reportlab-build
```

If the layer exceeds 50MB, consider:
- Using `--no-deps` for packages with heavy optional dependencies
- Removing unnecessary files (tests, docs) from the layer
- Splitting into multiple layers

## Usage in Lambda Functions

The layer is automatically attached to PDF-generating Lambda functions in `sst.config.ts`.

### Test Import

Test that ReportLab is available:

```bash
curl $(sst output ApiEndpoint)/api/test-reportlab
```

Should return:
```json
{
  "success": true,
  "message": "ReportLab layer working correctly",
  "reportlab_version": "4.1.0",
  "pillow_version": "10.x.x"
}
```

### Using in Your Lambda Function

```python
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from io import BytesIO

def generate_pdf():
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)
    pdf.drawString(100, 750, "Hello from Lambda!")
    pdf.save()
    return buffer.getvalue()
```

## Deployment

The layer is deployed automatically with `sst deploy`:

```bash
sst deploy --stage dev
```

SST reads the layer from `backend/layers/reportlab-build/` and creates a Lambda Layer Version in AWS.

## Troubleshooting

### Import errors in deployed Lambda

**Symptom**: `ImportError: No module named 'reportlab'` in CloudWatch logs

**Solutions**:
1. Verify the layer was built: Check that `backend/layers/reportlab-build/python/` exists
2. Rebuild the layer: Run `./build.sh` again
3. Check layer is attached: Verify `layers: [reportlabLayer.arn]` in route config
4. Redeploy: Run `sst deploy --stage dev`

### Layer size too large

**Symptom**: Deployment fails with "Layer size exceeds limit"

**Solutions**:
1. Remove test files: `find backend/layers/reportlab-build -name '__pycache__' -delete`
2. Remove docs: `find backend/layers/reportlab-build -name 'tests' -delete`
3. Use wheel distributions: They're smaller than source distributions

### Docker not running

**Symptom**: `Cannot connect to the Docker daemon`

**Solution**: Start Docker Desktop or Docker daemon before running `./build.sh`

## References

- [AWS Lambda Layers Documentation](https://docs.aws.amazon.com/lambda/latest/dg/configuration-layers.html)
- [ReportLab Documentation](https://www.reportlab.com/docs/reportlab-userguide.pdf)
- [Lambda Python Runtime](https://docs.aws.amazon.com/lambda/latest/dg/lambda-python.html)
