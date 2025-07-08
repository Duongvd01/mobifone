from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from flask_login import (
    LoginManager,
    UserMixin,
    login_user,
    login_required,
    logout_user,
    current_user,
)
from bson.objectid import ObjectId
from werkzeug.utils import secure_filename
import re
import requests
import os
from datetime import datetime
import os
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['SECRET_KEY'] = 'secret123'
app.config['MONGO_URI'] = os.environ.get('MONGO_URI', 'mongodb://mongodb:27017/flaskauth')

# Folder to save uploaded audio for playback
UPLOAD_FOLDER = os.path.join(app.static_folder, 'Uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# External Speech-to-Text API endpoint
API_S2T = "http://180.93.183.64:8502/api/v1/s2t/version2"

# Initialize extensions
mongo = PyMongo(app)
bcrypt = Bcrypt(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

# User class for Flask-Login
class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.username = user_data['username']

@login_manager.user_loader
def load_user(user_id):
    user_data = mongo.db.users.find_one({'_id': ObjectId(user_id)})
    return User(user_data) if user_data else None

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        email = request.form['email'].strip()
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        # Email must be Gmail
        if not re.match(r'^[\w\.-]+@gmail\.com$', email):
            flash('Vui lòng nhập địa chỉ Gmail hợp lệ.')
            return redirect(url_for('register'))

        # Password confirmation
        if password != confirm_password:
            flash('Mật khẩu xác nhận không khớp.')
            return redirect(url_for('register'))

        # Password complexity
        if not re.search(r'[A-Z]', password) or not re.search(r'\d', password):
            flash('Mật khẩu phải có ít nhất 1 chữ in hoa và 1 số.')
            return redirect(url_for('register'))

        # Unique username/email
        existing_user = mongo.db.users.find_one({
            '$or': [{'username': username}, {'email': email}]
        })
        if existing_user:
            flash('Tài khoản hoặc email đã tồn tại trong hệ thống!')
            return redirect(url_for('register'))

        # Create user
        hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
        mongo.db.users.insert_one({
            'username': username,
            'email': email,
            'password': hashed_pw
        })
        flash('Đăng ký thành công! Vui lòng đăng nhập.')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user_data = mongo.db.users.find_one({'username': username})
        if user_data and bcrypt.check_password_hash(user_data['password'], password):
            login_user(User(user_data))
            return redirect(url_for('dashboard'))
        flash('Sai tài khoản hoặc mật khẩu!')
    return render_template('login.html')

@app.route('/dashboard')
@login_required
def dashboard():
    user_history = mongo.db.transcripts.find(
        {'username': current_user.username}
    ).sort('created_at', -1)
    return render_template(
        'dashboard.html',
        username=current_user.username,
        history=user_history,
        transcript=None
    )

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/speech-to-text', methods=['GET', 'POST'])
@login_required
def s2t():
    if request.method == 'POST':
        audio_file = request.files.get('audio_file')
        if not audio_file or not audio_file.filename:
            logger.error("No file selected")
            return jsonify({
                'error': 'Không có file được chọn.',
                'transcript': None,
                'audio_url': None
            }), 400

        # Validate file extension
        allowed_extensions = {'.mp3', '.wav', '.ogg'}
        if not os.path.splitext(audio_file.filename)[1].lower() in allowed_extensions:
            logger.error(f"Invalid file extension: {audio_file.filename}")
            return jsonify({
                'error': 'Định dạng file không được hỗ trợ. Vui lòng chọn file .mp3, .wav hoặc .ogg.',
                'transcript': None,
                'audio_url': None
            }), 400

        # Save file
        filename = secure_filename(audio_file.filename)
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        try:
            audio_file.save(save_path)
            logger.debug(f"File saved to {save_path}")
        except Exception as e:
            logger.error(f"Failed to save file: {e}")
            return jsonify({
                'error': f'Lỗi lưu file: {str(e)}',
                'transcript': None,
                'audio_url': None
            }), 500

        # Verify file exists
        if not os.path.exists(save_path):
            logger.error(f"File not found after saving: {save_path}")
            return jsonify({
                'error': 'Không thể lưu file.',
                'transcript': None,
                'audio_url': None
            }), 500

        # STT API call
        try:
            with open(save_path, 'rb') as f:
                files = {'file': (filename, f, audio_file.mimetype)}
                resp = requests.post(API_S2T, files=files, data={'url': 'string'})
            if resp.status_code == 200:
                api_response = resp.json()
                transcript_blocks = api_response.get('data', {}).get('transcript', [])
                # Map API response to expected format
                transcript_data = [
                    {
                        'text': block['text'],
                        'start_time': block['start'],
                        'end_time': block['end'],
                        'speaker': block.get('speaker', 'Unknown'),
                        'words': [
                            {
                                'text': word['text'],
                                'start_time': word['start'],
                                'end_time': word['end'],
                                'confidence': word['confidence']
                            } for word in block.get('words', [])
                        ]
                    } for block in transcript_blocks
                ]
                logger.debug(f"Transcript data: {transcript_data}")
            else:
                transcript_data = [{'text': f"Lỗi API: {resp.status_code}", 'start_time': 0, 'end_time': 0, 'speaker': 'Unknown', 'words': []}]
                logger.error(f"API error: {resp.status_code}")
        except Exception as e:
            transcript_data = [{'text': f"Lỗi hệ thống: {str(e)}", 'start_time': 0, 'end_time': 0, 'speaker': 'Unknown', 'words': []}]
            logger.error(f"API call failed: {e}")

        # Save to DB
        try:
            mongo.db.transcripts.insert_one({
                'username': current_user.username,
                'filename': filename,
                'transcript': transcript_data,
                'created_at': datetime.utcnow()
            })
            logger.debug("Transcript saved to database")
        except Exception as e:
            logger.error(f"Database error: {e}")
            return jsonify({
                'error': f'Lỗi lưu vào cơ sở dữ liệu: {str(e)}',
                'transcript': transcript_data,
                'audio_url': None
            }), 500

        # Build playback URL
        audio_url = url_for('static', filename=f'Uploads/{filename}', _external=True)
        logger.debug(f"Audio URL: {audio_url}")

        return jsonify({
            'transcript': transcript_data,
            'audio_url': audio_url,
            'error': None
        })

    # GET
    return render_template(
        'speech_to_text.html',
        username=current_user.username,
        transcript=None,
        audio_url=None
    )

@app.route('/history')
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
    app.run(debug=True)
