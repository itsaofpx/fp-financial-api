FROM python:3.11-slim

WORKDIR /fp-finance-api

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONPATH=/fp-finance-api

CMD ["python", "app/wsgi.py"]
