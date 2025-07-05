from flask import Flask, render_template, request, redirect, url_for, flash
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from bson.objectid import ObjectId
import re
import requests
import os
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret123'
app.config['MONGO_URI'] = os.environ.get('MONGO_URI', 'mongodb://mongodb:27017/flaskauth')
API_S2T = "http://180.93.183.64:8502/api/v1/s2t/version2"

# Khởi tạo các thành phần
mongo = PyMongo(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# User class cho Flask-Login
class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.username = user_data['username']

@login_manager.user_loader
def load_user(user_id):
    user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    if user_data:
        return User(user_data)
    return None

# Trang chủ
@app.route('/')
def index():
    return render_template('index.html')

# Đăng ký
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if not re.match(r'^[\w\.-]+@gmail\.com$', email):
            flash('Vui lòng nhập địa chỉ Gmail hợp lệ.')
            return redirect(url_for('register'))

        if password != confirm_password:
            flash('Mật khẩu xác nhận không khớp.')
            return redirect(url_for('register'))

        if not re.search(r'[A-Z]', password) or not re.search(r'\d', password):
            flash('Mật khẩu phải có ít nhất 1 chữ in hoa và 1 số.')
            return redirect(url_for('register'))

        existing_user = mongo.db.users.find_one({
            "$or": [{'username': username}, {'email': email}]
        })
        if existing_user:
            flash('Tài khoản hoặc email đã tồn tại trong hệ thống!')
            return redirect(url_for('register'))

        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
        mongo.db.users.insert_one({
            'username': username,
            'email': email,
            'password': hashed_pw
        })

        flash('Đăng ký thành công! Vui lòng đăng nhập.')
        return redirect(url_for('login'))

    return render_template('register.html')

# Đăng nhập
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_data = mongo.db.users.find_one({'username': username})
        if user_data and bcrypt.check_password_hash(user_data['password'], password):
            user = User(user_data)
            login_user(user)
            return redirect(url_for('dashboard'))
        flash('Sai tài khoản hoặc mật khẩu!')
    return render_template('login.html')

# Bảng điều khiển
@app.route('/dashboard')
@login_required
def dashboard():
    # Lấy lịch sử người dùng
    user_history = mongo.db.transcripts.find(
        {"username": current_user.username}
    ).sort("created_at", -1)
    return render_template(
        'dashboard.html',
        username=current_user.username,
        history=user_history,
        transcript=None
    )


# Đăng xuất
@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route("/speech-to-text", methods=["GET", "POST"])
@login_required
def s2t():
    if request.method == "GET":
        return render_template("speech_to_text.html", username=current_user.username)

    if 'audio_file' not in request.files:
        return "Không có file", 400

    file = request.files["audio_file"]
    files = {
        'file': (file.filename, file.read(), file.mimetype)
    }
    data = {
        'url': 'string'
    }

    try:
        response = requests.post(API_S2T, files=files, data=data)

        if response.status_code == 200:
            json_data = response.json()
            transcript_blocks = json_data.get("data", {}).get("transcript", [])
            full_text = "\n".join([block["text"] for block in transcript_blocks])

            mongo.db.transcripts.insert_one({
                "username": current_user.username,
                "filename": file.filename,
                "transcript": full_text,
                "created_at": datetime.utcnow()
            })

        else:
            full_text = f"Lỗi API: {response.status_code}"

    except Exception as e:
        full_text = f"Lỗi hệ thống: {str(e)}"

    return render_template("speech_to_text.html", transcript=full_text, username=current_user.username)

# Lịch sử transcript
@app.route("/history")
@login_required
def history():
    user_history = mongo.db.transcripts.find({"username": current_user.username}).sort("created_at", -1)
    return render_template("history.html", history=user_history)

# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

@app.errorhandler(403)
def forbidden_error(error):
    return render_template('404.html'), 403

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=os.environ.get('FLASK_ENV') == 'development')
