FROM python:3.10-slim

WORKDIR /app

ADD requirements.txt .
RUN pip install -r requirements.txt

COPY *.py /app/

CMD [ "python", "invoke-receiver.py" ]
