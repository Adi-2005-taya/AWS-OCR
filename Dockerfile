# Use an official lightweight Python image
FROM python:3.11-slim

# Prevent Python from buffering stdout/stderr and prevent apt-get from asking questions
ENV PYTHONUNBUFFERED=1
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies needed for OCR and PDF processing
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    poppler-utils \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code into the container
COPY . .

# Expose the port the app runs on
EXPOSE 7860

# Command to start the Uvicorn server
CMD ["uvicorn", "src.web:app", "--host", "0.0.0.0", "--port", "7860"]
