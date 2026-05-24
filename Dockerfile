FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY app.py ./
COPY cpa_inspection_bridge ./cpa_inspection_bridge
COPY static ./static

EXPOSE 8766

CMD ["python", "-B", "app.py", "--host", "0.0.0.0", "--port", "8766", "--db", "/data/inspection_bridge.db"]
