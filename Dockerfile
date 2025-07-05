# Sử dụng Python 3.12 slim image
FROM python:3.12-slim

# Thiết lập thư mục làm việc
WORKDIR /app

# Sao chép requirements.txt và cài đặt dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Sao chép mã nguồn ứng dụng
COPY . .

# Tạo thư mục instance nếu chưa có
RUN mkdir -p instance

# Thiết lập biến môi trường
ENV FLASK_APP=app.py
ENV FLASK_ENV=production

# Mở cổng 8080
EXPOSE 8080

# Chạy ứng dụng Flask
CMD ["python", "app.py"]
