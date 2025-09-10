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
import logging
from functools import wraps

# Set up logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler

# Ensure logs directory exists
os.makedirs('logs', exist_ok=True)

# Configure logging to file and console
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Get root logger and remove existing handlers
root_logger = logging.getLogger()
for handler in root_logger.handlers[:]:
    root_logger.removeHandler(handler)

# Add custom handlers
# Size-based rotation (10MB)
file_handler = RotatingFileHandler(
    'logs/app.log', 
    maxBytes=10485760,  # 10MB
    backupCount=10
)
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
file_handler.setLevel(logging.DEBUG)
root_logger.addHandler(file_handler)

# Time-based rotation (daily) with custom naming
from datetime import date
current_date = date.today().strftime('%Y-%m-%d')
daily_log_filename = f'logs/app_{current_date}.log'

# Create daily log handler with custom suffix
daily_handler = TimedRotatingFileHandler(
    daily_log_filename,
    when='midnight',
    interval=1,
    backupCount=30  # Keep logs for 30 days
)
# Set a custom suffix so new files will be named with the date
daily_handler.suffix = "%Y-%m-%d"
daily_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
daily_handler.setLevel(logging.DEBUG)
root_logger.addHandler(daily_handler)

# Log startup with date information
logger = logging.getLogger(__name__)
logger.info(f"Starting application with daily log file: {daily_log_filename}")

# Console handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
console_handler.setLevel(logging.INFO)  # Only INFO and above to console
root_logger.addHandler(console_handler)

# Get module-specific logger
logger = logging.getLogger(__name__)

app = Flask(__name__, static_url_path='/static', static_folder='static')
app.config['SECRET_KEY'] = 'secret123'
app.config['MONGO_URI'] = os.environ.get('MONGO_URI', 'mongodb://mongodb:27017/flaskauth')

# app.config['MONGO_URI'] = 'mongodb://localhost:27017/flaskauth'
# API key for diagnostic endpoints
API_KEY = os.environ.get('DIAGNOSTIC_API_KEY', 'default_key_for_development')
logger.info(f"Diagnostic API key set: {'Yes' if API_KEY != 'default_key_for_development' else 'No (using default)'}")

# API key authentication decorator
def require_api_key(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        provided_key = request.headers.get('X-API-Key') or request.args.get('api_key')
        if not provided_key or provided_key != API_KEY:
            logger.warning(f"Unauthorized access attempt to {request.path} from {request.remote_addr}")
            return jsonify({"error": "Unauthorized access. Valid API key required."}), 401
        return f(*args, **kwargs)
    return decorated_function

# Log static file configuration
logger.info(f"Flask app initialized with static_url_path: {app.static_url_path}")
logger.info(f"Flask app initialized with static_folder: {app.static_folder}")
logger.info(f"Flask app absolute static folder path: {os.path.abspath(app.static_folder)}")
logger.info(f"Current working directory: {os.getcwd()}")
logger.info(f"Files in static directory: {os.listdir(app.static_folder) if os.path.exists(app.static_folder) else 'Static folder not found'}")

# Folder to save uploaded audio for playback
UPLOAD_FOLDER = os.path.join(app.static_folder, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
logger.info(f"Upload folder path: {UPLOAD_FOLDER}")
logger.info(f"Upload folder exists: {os.path.exists(UPLOAD_FOLDER)}")
if os.path.exists(UPLOAD_FOLDER):
    logger.info(f"Files in upload folder: {os.listdir(UPLOAD_FOLDER)}")

# External API endpoints
API_S2T = "http://49.213.89.71:8502/api/v1/s2t/version2"
API_TTS = "http://49.213.89.71:8502/api/v1/tts"  # Text-to-Speech API endpoint
API_OCR = "http://49.213.89.71:8502/api/v1/ocr"  # OCR API endpoint

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
    logger.info("Endpoint '/' accessed")
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    logger.info("Endpoint '/register' accessed")
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
    logger.info("Endpoint '/login' accessed")
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
    logger.info(f"Endpoint '/dashboard' accessed by user: {current_user.username}")
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
    username = current_user.username
    logger.info(f"User '{username}' logged out")
    logout_user()
    return redirect(url_for('index'))

@app.route('/speech-to-text', methods=['GET', 'POST'])
@login_required
def s2t():
    logger.info(f"Endpoint '/speech-to-text' accessed by user: {current_user.username}")
    if request.method == 'POST':
        logger.info("Processing POST request to /speech-to-text")
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
        file_ext = os.path.splitext(audio_file.filename)[1].lower()
        logger.info(f"File extension: {file_ext}")
        if not file_ext in allowed_extensions:
            logger.error(f"Invalid file extension: {audio_file.filename}")
            return jsonify({
                'error': 'Định dạng file không được hỗ trợ. Vui lòng chọn file .mp3, .wav hoặc .ogg.',
                'transcript': None,
                'audio_url': None
            }), 400

        # Save file
        filename = secure_filename(audio_file.filename)
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        logger.info(f"Attempting to save file to: {save_path}")
        try:
            audio_file.save(save_path)
            logger.info(f"File saved successfully to {save_path}")
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
        else:
            logger.info(f"File exists at {save_path}, size: {os.path.getsize(save_path)} bytes")

        # STT API call
        try:
            with open(save_path, 'rb') as f:
                files = {'file': (filename, f, audio_file.mimetype)}
                logger.info(f"Sending file to API with mimetype: {audio_file.mimetype}")
                resp = requests.post(API_S2T, files=files, data={'url': 'string'})
            logger.info(f"API response status code: {resp.status_code}")
            if resp.status_code == 200:
                logger.info(f"API response success")
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
                logger.error(f"API error: {resp.status_code}, response: {resp.text}")
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
        audio_url = url_for('static', filename=f'uploads/{filename}', _external=True)
        logger.info(f"Generated audio URL: {audio_url}")
        
        # Check if the file is accessible via the URL
        try:
            test_path = os.path.join(app.static_folder, f'uploads/{filename}')
            logger.info(f"Testing file accessibility at path: {test_path}")
            logger.info(f"File exists at test path: {os.path.exists(test_path)}")
            if os.path.exists(test_path):
                logger.info(f"File permissions: {oct(os.stat(test_path).st_mode)[-3:]}")
            else:
                logger.info("File not found")
        except Exception as e:
            logger.error(f"Error checking file accessibility: {e}")

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
@app.route('/text-to-speech', methods=['GET', 'POST'])
@login_required
def tts():
    logger.info(f"Endpoint '/text-to-speech' accessed by user: {current_user.username}")
    if request.method == 'POST':
        logger.info("Processing POST request to /text-to-speech")
        data = request.get_json()
        text = data.get('text', '').strip()
        voice = data.get('voice', 'male')  # Mặc định là giọng nam nếu không có

        if not text:
            logger.error("No text provided")
            return jsonify({
                'error': 'Vui lòng nhập văn bản để chuyển đổi.',
                'audio_url': None
            }), 400

        # TTS API call (giả định)
        try:
            resp = requests.post(API_TTS, json={'text': text, 'voice': voice})
            logger.info(f"TTS API response status code: {resp.status_code}")
            if resp.status_code == 200:
                api_response = resp.json()
                audio_data = api_response.get('audio', '')  # Giả định API trả về base64 audio hoặc URL
                # Lưu file âm thanh
                filename = f"tts_{current_user.username}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}.mp3"
                save_path = os.path.join(UPLOAD_FOLDER, filename)
                try:
                    with open(save_path, 'wb') as f:
                        f.write(requests.get(audio_data).content)  # Giả định audio_data là URL
                    logger.info(f"Audio file saved to {save_path}")
                except Exception as e:
                    logger.error(f"Failed to save audio file: {e}")
                    return jsonify({
                        'error': f'Lỗi lưu file âm thanh: {str(e)}',
                        'audio_url': None
                    }), 500
            else:
                logger.error(f"TTS API error: {resp.status_code}, response: {resp.text}")
                return jsonify({
                    'error': f'Lỗi API TTS: {resp.status_code}',
                    'audio_url': None
                }), 500
        except Exception as e:
            logger.error(f"TTS API call failed: {e}")
            return jsonify({
                'error': f'Lỗi hệ thống: {str(e)}',
                'audio_url': None
            }), 500

        # Verify file exists
        if not os.path.exists(save_path):
            logger.error(f"Audio file not found after saving: {save_path}")
            return jsonify({
                'error': 'Không thể lưu file âm thanh.',
                'audio_url': None
            }), 500
        else:
            logger.info(f"Audio file exists at {save_path}, size: {os.path.getsize(save_path)} bytes")

        # Save to DB
        try:
            mongo.db.tts_history.insert_one({
                'username': current_user.username,
                'text': text,
                'voice': voice,
                'filename': filename,
                'created_at': datetime.utcnow()
            })
            logger.debug("TTS result saved to database")
        except Exception as e:
            logger.error(f"Database error: {e}")
            return jsonify({
                'error': f'Lỗi lưu vào cơ sở dữ liệu: {str(e)}',
                'audio_url': None
            }), 500

        # Build audio URL
        audio_url = url_for('static', filename=f'uploads/{filename}', _external=True)
        logger.info(f"Generated audio URL: {audio_url}")

        return jsonify({
            'audio_url': audio_url,
            'error': None
        })

    # GET
    return render_template(
        'text-to-speech.html',
        username=current_user.username,
        history=mongo.db.tts_history.find({'username': current_user.username}).sort('created_at', -1)
    )
@app.route('/history')
@login_required
def history():
    logger.info(f"Endpoint '/history' accessed by user: {current_user.username}")
    user_history = mongo.db.transcripts.find({"username": current_user.username}).sort("created_at", -1)
    return render_template("history.html", history=user_history)

@app.route('/delete-history/<string:id>', methods=['DELETE'])
@login_required
def delete_history(id):
    logger.info(f"Delete history request for ID {id} by user: {current_user.username}")
    try:
        item = mongo.db.transcripts.find_one({"_id": ObjectId(id), "username": current_user.username})
        if not item:
            logger.error(f"History item not found or unauthorized: {id}")
            return jsonify({"success": False, "error": "Bản ghi không tồn tại hoặc không có quyền xóa."}), 404
        # Delete audio file
        file_path = os.path.join(UPLOAD_FOLDER, item['filename'])
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.debug(f"Deleted file: {file_path}")
        # Delete from database
        mongo.db.transcripts.delete_one({"_id": ObjectId(id)})
        logger.debug(f"Deleted history item: {id}")
        return jsonify({"success": True})
    except Exception as e:
        logger.error(f"Error deleting history item {id}: {e}")
        return jsonify({"success": False, "error": str(e)}), 500
    
@app.route("/chatbot", methods=["GET", "POST"])
@login_required
def chatbot():
    logger.info(f"Endpoint '/chatbot' accessed by user: {current_user.username}")
    if request.method == "GET":
        return render_template("chatbot.html", username=current_user.username)

    if request.method == "POST":
        data = request.get_json()
        user_msg = data.get("message", "").strip()

        # 🔁 Dummy bot trả lời — bạn thay bằng call OpenAI hoặc API riêng
        if user_msg:
            bot_reply = f"Bạn vừa nói: “{user_msg}”"
        else:
            bot_reply = "Tôi không hiểu bạn nói gì."

        return jsonify({"reply": bot_reply})
@app.route('/translate', methods=['POST'])
@login_required
def translate():
    logger.info(f"Endpoint '/translate' accessed by user: {current_user.username}")
    try:
        data = request.get_json()
        transcript = data.get('transcript')
        target_language = data.get('target_language')

        if not transcript or not target_language:
            logger.error("Missing transcript or target_language")
            return jsonify({
                'error': 'Thiếu transcript hoặc ngôn ngữ đích.',
                'translated_transcript': None
            }), 400

        # Placeholder for translation API call
        # Replace with actual translation API (e.g., Google Translate, DeepL)
        translated_transcript = []
        for segment in transcript:
            # Simulated translation (replace with real API call)
            translated_text = f"[Translated to {target_language}] {segment['text']}"
            translated_transcript.append({
                'text': translated_text,
                'start_time': segment['start_time'],
                'end_time': segment['end_time'],
                'speaker': segment.get('speaker', 'Unknown'),
                'words': segment.get('words', [])
            })

        return jsonify({
            'translated_transcript': translated_transcript,
            'error': None
        })

    except Exception as e:
        logger.error(f"Error translating transcript: {e}")
        return jsonify({
            'error': f'Lỗi khi dịch transcript: {str(e)}',
            'translated_transcript': None
        }), 500
@app.route('/ocr', methods=['GET', 'POST'])
@login_required
def ocr():
    logger.info(f"Endpoint '/ocr' accessed by user: {current_user.username}")
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or not file.filename:
            logger.error("No file selected")
            return jsonify({
                'error': 'Không có file được chọn.',
                'text': None,
                'file_url': None
            }), 400

        # Validate file extension
        allowed_extensions = {'.jpg', '.jpeg', '.png', '.pdf'}
        if not os.path.splitext(file.filename)[1].lower() in allowed_extensions:
            logger.error(f"Invalid file extension: {file.filename}")
            return jsonify({
                'error': 'Định dạng file không được hỗ trợ. Vui lòng chọn file .jpg, .jpeg, .png hoặc .pdf.',
                'text': None,
                'file_url': None
            }), 400

        # Save file
        filename = secure_filename(file.filename)
        save_path = os.path.join(UPLOAD_FOLDER, filename)
        try:
            file.save(save_path)
            logger.debug(f"File saved to {save_path}")
        except Exception as e:
            logger.error(f"Failed to save file: {e}")
            return jsonify({
                'error': f'Lỗi lưu file: {str(e)}',
                'text': None,
                'file_url': None
            }), 500

        # Verify file exists
        if not os.path.exists(save_path):
            logger.error(f"File not found after saving: {save_path}")
            return jsonify({
                'error': 'Không thể lưu file.',
                'text': None,
                'file_url': None
            }), 500

        # OCR API call (placeholder)
        try:
            with open(save_path, 'rb') as f:
                files = {'file': (filename, f, file.mimetype)}
                resp = requests.post(API_OCR, files=files)
            if resp.status_code == 200:
                api_response = resp.json()
                ocr_text = api_response.get('text', '')
                logger.debug(f"OCR text: {ocr_text}")
            else:
                ocr_text = f"Lỗi API: {resp.status_code}"
                logger.error(f"API error: {resp.status_code}")
        except Exception as e:
            ocr_text = f"Lỗi hệ thống: {str(e)}"
            logger.error(f"API call failed: {e}")

        # Save to DB
        try:
            mongo.db.ocr_history.insert_one({
                'username': current_user.username,
                'filename': filename,
                'text': ocr_text,
                'created_at': datetime.utcnow()
            })
            logger.debug("OCR result saved to database")
        except Exception as e:
            logger.error(f"Database error: {e}")
            return jsonify({
                'error': f'Lỗi lưu vào cơ sở dữ liệu: {str(e)}',
                'text': ocr_text,
                'file_url': None
            }), 500

        # Build file URL
        file_url = url_for('static', filename=f'uploads/{filename}', _external=True)
        logger.debug(f"File URL: {file_url}")

        return jsonify({
            'text': ocr_text,
            'file_url': file_url,
            'error': None
        })

    # GET
    return render_template(
        'OCR.html',
        username=current_user.username,
        history=mongo.db.ocr_history.find({'username': current_user.username}).sort('created_at', -1)
    )
@app.route('/test-static')
@require_api_key
def test_static():
    """Diagnostic route to test static file access"""
    logger.info("Test static route accessed")
    
    # Check static folder
    static_exists = os.path.exists(app.static_folder)
    logger.info(f"Static folder exists: {static_exists}")
    
    # List files in static folder
    static_files = os.listdir(app.static_folder) if static_exists else []
    logger.info(f"Files in static folder: {static_files}")
    
    # Check uploads folder
    uploads_path = os.path.join(app.static_folder, 'uploads')
    uploads_exists = os.path.exists(uploads_path)
    logger.info(f"Uploads folder exists: {uploads_exists}")
    
    # List files in uploads folder
    upload_files = os.listdir(uploads_path) if uploads_exists else []
    logger.info(f"Files in uploads folder: {upload_files}")
    
    # Generate test URLs
    test_urls = []
    for file in upload_files:
        url = url_for('static', filename=f'uploads/{file}', _external=True)
        test_urls.append({'file': file, 'url': url})
    
    # Return diagnostic info
    return jsonify({
        'static_folder': app.static_folder,
        'static_url_path': app.static_url_path,
        'static_exists': static_exists,
        'static_files': static_files,
        'uploads_exists': uploads_exists,
        'upload_files': upload_files,
        'test_urls': test_urls
    })

@app.route('/test-nginx')
@require_api_key
def test_nginx():
    """Test route to diagnose Nginx proxy configuration"""
    logger.info("Test Nginx route accessed")
    
    # Get request headers - ensure all values are JSON serializable
    headers = {}
    for k, v in request.headers.items():
        # Convert all header values to strings to ensure they're serializable
        headers[k] = str(v)
    logger.info(f"Request headers: {headers}")
    
    # Check if request came through Nginx
    proxied = 'X-Forwarded-For' in headers or 'X-Real-IP' in headers
    logger.info(f"Request appears to be proxied: {proxied}")
    
    # Get server environment - ensure all values are JSON serializable
    env_info = {
        'hostname': os.uname().nodename if hasattr(os, 'uname') else 'Unknown',
        'server_software': str(request.environ.get('SERVER_SOFTWARE', 'Unknown')),
        # Filter and stringify wsgi environment variables
        'wsgi_env': {k: str(v) for k, v in request.environ.items() 
                    if k.startswith('wsgi.') and not hasattr(v, 'read')},  # Exclude file-like objects
        'flask_env': str(app.config.get('ENV', 'Unknown')),
        'request_scheme': request.scheme,
        'request_host': request.host,
        'request_url': request.url,
        'remote_addr': request.remote_addr
    }
    logger.info(f"Server environment: {env_info}")
    
    # Ensure all data is serializable
    return jsonify({
        'headers': headers,
        'proxied': proxied,
        'env_info': env_info,
        'static_url_path': app.static_url_path,
        'static_folder': app.static_folder
    })
# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    logger.error(f"404 error: {request.url}")
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    logger.error(f"500 error: {str(error)}")
    return render_template('500.html'), 500

@app.errorhandler(403)
def forbidden_error(error):
    logger.error(f"403 error: {request.url}")
    return render_template('404.html'), 403

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=os.environ.get('FLASK_ENV') == 'development')
# if __name__ == '__main__':
#     app.run(debug=True)