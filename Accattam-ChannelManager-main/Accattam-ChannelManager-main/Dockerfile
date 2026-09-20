FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 
ENV PYTHONUNBUFFERED=1

COPY . /root/

WORKDIR /root/

RUN pip install --upgrade pip && pip install -r requirements.txt

EXPOSE 5000

ENV FLASK_APP=app

CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]