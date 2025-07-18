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

# Hướng dẫn chạy chế độ Development (DEV)

## 1. Chạy MongoDB bằng Docker Compose

Chỉ cần chạy MongoDB, không chạy Flask app và Nginx:

```bash
docker compose up dev
```
- Lệnh này sẽ chỉ khởi động service `mongodb-dev` (MongoDB) và một container placeholder.
- MongoDB sẽ được bind ra port `27017` trên máy host.

## 2. Chạy Flask app ở ngoài Docker

- Đảm bảo bạn đã cài Python và các package cần thiết:
  ```bash
  pip install -r requirements.txt
  ```
- Đặt biến môi trường để Flask app kết nối tới MongoDB vừa khởi động:
  - **Windows (cmd):**
    ```cmd
    set MONGO_URI=mongodb://localhost:27017/flaskauth
    ```
  - **Windows (PowerShell):**
    ```powershell
    $env:MONGO_URI = "mongodb://localhost:27017/flaskauth"
    ```
  - **Linux/macOS (bash):**
    ```bash
    export MONGO_URI=mongodb://localhost:27017/flaskauth
    ```
- Chạy Flask app:
  ```bash
  python app.py
  ```

## 3. Lợi ích chế độ dev
- Có thể sửa code Flask và reload nhanh mà không cần rebuild Docker.
- Dữ liệu MongoDB vẫn được lưu trong volume docker.
- Có thể dùng các công cụ debug, IDE, v.v. trực tiếp trên máy local.

## 4. Khi chuyển sang production
- Dùng lại lệnh:
  ```bash
  docker compose up
  ```
- Lúc này sẽ chạy đầy đủ cả MongoDB, Flask app và Nginx reverse proxy.

---

Nếu gặp lỗi kết nối database, kiểm tra lại biến môi trường `MONGO_URI` và chắc chắn MongoDB đã chạy ở port 27017. 