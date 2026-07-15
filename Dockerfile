FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY bot.py /app/
COPY auth.py /app/
COPY rate_limiter.py /app/
COPY db.py /app/
COPY analytics.py /app/
COPY dashboard.py /app/
COPY templates/ /app/templates/
COPY start.sh /app/

# Expose Dashboard Port
EXPOSE 5000

# Run the bot and dashboard concurrently
CMD ["./start.sh"]