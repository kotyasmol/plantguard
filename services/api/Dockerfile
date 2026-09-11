FROM python:3.12-slim

WORKDIR /workspace

COPY services/mining /workspace/services/mining
COPY services/api /workspace/services/api

RUN python -m pip install --no-cache-dir /workspace/services/mining /workspace/services/api

EXPOSE 8000

CMD ["uvicorn", "plantguard_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
