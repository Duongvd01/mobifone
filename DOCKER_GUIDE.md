# Hướng dẫn chạy ứng dụng Flask với Docker

## Yêu cầu
- Docker
- Docker Compose

## Cách chạy ứng dụng

### 1. Build và chạy với Docker Compose
```bash
# Build và chạy tất cả services
docker-compose up --build

# Chạy ở chế độ background
docker-compose up -d --build
```

### 2. Truy cập ứng dụng
- Ứng dụng Flask: http://localhost:8080
- MongoDB: localhost:27017

### 3. Dừng ứng dụng
```bash
# Dừng tất cả services
docker-compose down

# Dừng và xóa volumes (xóa dữ liệu database)
docker-compose down -v
```

### 4. Xem logs
```bash
# Xem logs tất cả services
docker-compose logs

# Xem logs của Flask app
docker-compose logs flask-app

# Xem logs của MongoDB
docker-compose logs mongodb
```

### 5. Chạy riêng từng service

#### Chỉ chạy MongoDB:
```bash
docker-compose up mongodb
```

#### Chỉ chạy Flask app (cần MongoDB đã chạy):
```bash
docker-compose up flask-app
```

## Cấu trúc Docker

### Services:
- **mongodb**: MongoDB database server
- **flask-app**: Ứng dụng Flask chính

### Networks:
- **mobifone-network**: Mạng bridge cho các services giao tiếp

### Volumes:
- **mongodb_data**: Lưu trữ dữ liệu MongoDB persistent
- **./instance**: Mount thư mục instance từ host

## Troubleshooting

### Lỗi kết nối MongoDB:
- Đảm bảo MongoDB service đã khởi động hoàn toàn trước khi Flask app chạy
- Kiểm tra logs: `docker-compose logs mongodb`

### Lỗi port đã được sử dụng:
- Thay đổi port trong docker-compose.yml nếu port 8080 hoặc 27017 đã được sử dụng

### Reset database:
```bash
docker-compose down -v
docker-compose up --build
``` 