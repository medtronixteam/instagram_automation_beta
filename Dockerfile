# Use the official Python 3.10 image as the base image
FROM python:3.10

# Set the working directory
WORKDIR /app

# Copy your application files to the working directory.
COPY . /app

# Install necessary dependencies, including Chrome and ChromeDriver
RUN apt-get update && apt-get install -y wget unzip && \
    wget https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/117.0.5938.149/linux64/chrome-linux64.zip && \
    unzip chrome-linux64.zip -d /usr/local/bin/ && \
    wget https://edgedl.me.gvt1.com/edgedl/chrome/chrome-for-testing/117.0.5938.149/linux64/chromedriver-linux64.zip && \
    unzip chromedriver-linux64.zip -d /usr/local/bin/ && \
    rm -rf chrome-linux64.zip chromedriver-linux64.zip && \
    apt-get clean && \
    pip3 --no-cache-dir install -r requirements.txt && \
    apt-get install -y libnss3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libx11-xcb1 \
    libxcb-dri3-0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libcups2 \
    libdrm2 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    libpangocairo-1.0-0 \
    libgtk-3-0 \
    libxkbcommon0

# Expose the port that your application will run on
EXPOSE 6000

# Specify the default command to run your application
CMD ["gunicorn", "--timeout", "1000", "--bind", "0.0.0.0:6000", "app:app"]