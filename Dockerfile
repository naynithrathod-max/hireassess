# Standardized Hiring Assessment Platform
#
# One image, built once, run unchanged on a laptop, inside a VirtualBox VM and
# on a cloud VM. That portability is the point of containerising it.

FROM python:3.12-slim

# Keeps Python from writing .pyc files and makes logs appear immediately,
# which matters when you are watching `docker logs` during a demo.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    DB_PATH=/data/assessment.db \
    SCORECARD_DIR=/data/scorecards

WORKDIR /app

# Dependencies are installed before the source is copied, so editing the app
# does not force a reinstall on every rebuild.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Writable volume for the database and the scorecard objects. Mounting a volume
# here is what lets the container be destroyed and recreated without data loss.
RUN mkdir -p /data/scorecards
VOLUME ["/data"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=4s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).status==200 else 1)"

# gunicorn rather than the Flask development server: two worker processes,
# which is also what makes the concurrency point real rather than claimed.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "4", \
     "--access-logfile", "-", "app:app"]
