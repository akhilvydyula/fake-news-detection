# Deploy Streamlit App On Render

This project is ready for Render as a Python web service.

## Option 1: Render Blueprint

1. Push this repository to GitHub.
2. In Render, choose **New > Blueprint**.
3. Connect the repository.
4. Render will read `render.yaml` and create the web service.
5. Open the generated Render URL after the build completes.

## Option 2: Manual Web Service

Use these settings:

- **Environment:** Python
- **Build command:** `pip install --upgrade pip && pip install -e .`
- **Start command:** `streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port $PORT --server.headless true --browser.gatherUsageStats false`
- **Python version:** `3.11.9`

## Model Artifact Requirement

The app needs the trained classical model at:

```text
artifacts/classical/logreg_tfidf.joblib
```

If Render deploys without that file, the UI can load but prediction will not work. Because `artifacts/*` is currently ignored by git, use one of these approaches before production deployment:

- Commit the small classical model artifact if the file size is acceptable.
- Upload the artifact during Render build from private storage.
- Run a training/build step on Render, only if you want Render to generate fresh artifacts.

For the MVP UI deployment, the recommended path is to include the classical artifact and avoid TensorFlow training dependencies.
