FROM python:latest

WORKDIR /app

# Download dependencies
ADD requirements.txt .
RUN pip install -r requirements.txt

# Copy Source Code
COPY . .

# Main Entry
CMD [ "python", "client.py" ]