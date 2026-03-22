FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir httpx

COPY . .

ENV PYTHONUNBUFFERED=1

CMD python seed_historical.py && python tap_simulator.py \
    --api-url ${API_URL:-http://backend:8000} \
    --rate ${RATE:-3} \
    ${BURST:+--burst}
