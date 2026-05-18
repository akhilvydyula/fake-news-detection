FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY src /app/src
COPY newstrust /app/newstrust
COPY platformapp /app/platformapp
COPY requirements.txt manage.py streamlit_app.py /app/

RUN pip install --upgrade pip && pip install -e .

COPY . /app

EXPOSE 8501

CMD streamlit run streamlit_app.py --server.address 0.0.0.0 --server.port ${PORT:-8501} --server.headless true --browser.gatherUsageStats false
