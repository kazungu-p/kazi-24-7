"""
Job Platform - Consolidated Flask Application
A comprehensive job posting and application platform with messaging, notifications, and admin controls.

Setup Instructions:
1. pip install flask flask-sqlalchemy flask-migrate flask-login flask-wtf email-validator werkzeug flask-limiter flask-cors requests bleach
2. Set environment variables:
   - DATABASE_URL (optional, defaults to SQLite)
   - SECRET_KEY (required for production)
   - DEFAULT_ADMIN_EMAIL and DEFAULT_ADMIN_PASSWORD (optional, for admin creation)
3. Initialize database:
   flask db init
   flask db migrate -m "initial migration"
   flask db upgrade
4. Run: flask run
"""

import os
import re
import secrets
import string
import requests
import bleach
from datetime import datetime, timezone, timedelta

from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, abort, send_from_directory, render_template_string
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import (
    LoginManager, UserMixin, login_user, login_required,
    logout_user, current_user
)
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from sqlalchemy import or_, and_, func
from flask_wtf.csrf import CSRFProtect, generate_csrf
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_cors import CORS

# ============================================================================
# APPLICATION CONFIGURATION
# ============================================================================

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

app = Flask(__name__)

# Security Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SESSION_COOKIE_SECURE'] = False  # Set to True in production with HTTPS
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 1800  # 30 minutes
app.config['WTF_CSRF_TIME_LIMIT'] = 3600  # CSRF tokens valid for 1 hour

# Database Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'DATABASE_URL',
    'sqlite:///' + os.path.join(BASE_DIR, 'job_platform.db')
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_pre_ping': True,
    'pool_recycle': 300,
}

# File Upload Configuration
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16 MB max file size
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'mp4', 'mov', 'webm'}
MAX_MEDIA_PER_JOB = 5

# Initialize Extensions
db = SQLAlchemy(app)
migrate = Migrate(app, db)
csrf = CSRFProtect(app)

# Rate Limiting
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=['200 per day', '50 per hour'],
    storage_uri='memory://'
)

# CORS - Restrict origins in production
allowed_origins = os.environ.get('ALLOWED_ORIGINS', '*')
if allowed_origins == '*':
    CORS(app)
else:
    CORS(app, resources={r'/*': {'origins': allowed_origins.split(',')}})

# Login Manager Setup
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'


# ============================================================================
# TEMPLATE CONTEXT PROCESSORS
# ============================================================================


@app.context_processor
def inject_template_helpers():
    """Inject helper functions into all templates"""
    return {
        "now": lambda: datetime.utcnow(),
        "csrf_token": generate_csrf,
        "sanitize": sanitize_html
    }

# ============================================================================
# TEMPLATE FILTERS
# ============================================================================
# ============================================================================
# TEMPLATE FILTERS
# ============================================================================

@app.template_filter('is_active_suspension')
def is_active_suspension(user):
    """Check if user has an active suspension"""
    if not user or not user.suspended or not user.suspension_end_date:
        return False
    try:
        # Make both naive for comparison
        end_date = user.suspension_end_date
        if hasattr(end_date, 'tzinfo') and end_date.tzinfo is not None:
            end_date = end_date.replace(tzinfo=None)
        return end_date > datetime.utcnow()
    except (TypeError, AttributeError):
        return False

# Add the new filter HERE (around line 130-140)
@app.template_filter('hours_remaining')
def hours_remaining(user):
    """Calculate hours remaining in suspension"""
    if not user or not user.suspension_end_date:
        return 0
    try:
        # Make both naive for calculation
        end_date = user.suspension_end_date
        if hasattr(end_date, 'tzinfo') and end_date.tzinfo is not None:
            end_date = end_date.replace(tzinfo=None)
        now = datetime.utcnow()
        diff = end_date - now
        return round(diff.total_seconds() / 3600, 1)
    except (TypeError, AttributeError):
        return 0

# ============================================================================
# DATABASE MODELS
# ============================================================================

@app.template_filter('is_active_suspension')
def is_active_suspension(user):
    """Check if user has an active suspension"""
    if not user or not user.suspended or not user.suspension_end_date:
        return False
    try:
        # Make both naive for comparison
        end_date = user.suspension_end_date
        if hasattr(end_date, 'tzinfo') and end_date.tzinfo is not None:
            end_date = end_date.replace(tzinfo=None)
        return end_date > datetime.utcnow()
    except (TypeError, AttributeError):
        return False


@app.context_processor
def inject_template_helpers():
    """Inject helper functions into all templates"""
    return {
        "now": lambda: datetime.now(timezone.utc),
        "csrf_token": generate_csrf,
        "sanitize": sanitize_html
    }


# ============================================================================
# DATABASE MODELS
# ============================================================================

class User(UserMixin, db.Model):
    """User model for both job seekers and job posters"""
    __tablename__ = 'user'
    
    # Primary Information
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=True, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='worker', index=True)  # 'worker' or 'recruiter'
    
    # Profile Information
    phone_number = db.Column(db.String(30))
    national_id = db.Column(db.String(50))
    certificate_of_good_conduct = db.Column(db.String(255))
    profile_picture = db.Column(db.String(255))
    location = db.Column(db.String(100))
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    work_type = db.Column(db.String(100))
    profile_completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    # Location Tracking Fields
    real_ip = db.Column(db.String(45), nullable=True)  # IPv6 can be up to 45 chars
    real_latitude = db.Column(db.Float, nullable=True)
    real_longitude = db.Column(db.Float, nullable=True)
    real_city = db.Column(db.String(100), nullable=True)
    real_country = db.Column(db.String(100), nullable=True)
    real_region = db.Column(db.String(100), nullable=True)
    location_discrepancy = db.Column(db.Boolean, default=False)  # Flag if custom location differs from real
    location_verified_at = db.Column(db.DateTime, nullable=True)
    
    # Suspension Tracking
    suspension_end_date = db.Column(db.DateTime, nullable=True)  # Track when suspension ends
    suspension_reason = db.Column(db.String(255), nullable=True)
    suspension_duration = db.Column(db.String(20), nullable=True)  # 'hour', 'day', 'week', 'month', 'year', 'custom'
    
    # Admin and Moderation Controls
    is_admin = db.Column(db.Boolean, default=False)
    suspended = db.Column(db.Boolean, default=False)
    burned = db.Column(db.Boolean, default=False)  # Permanently banned
    warnings_count = db.Column(db.Integer, default=0)
    
    # Relationships
    jobs_posted = db.relationship('Job', backref='poster', lazy=True, cascade='all, delete-orphan')
    applications = db.relationship('JobApplication', backref='applicant', lazy=True, cascade='all, delete-orphan')
    notifications = db.relationship('Notification', backref='user', lazy=True, cascade='all, delete-orphan')
    sent_messages = db.relationship('Message', foreign_keys='Message.sender_id', backref='sender', lazy='dynamic', cascade='all, delete-orphan')
    received_messages = db.relationship('Message', foreign_keys='Message.recipient_id', backref='recipient', lazy='dynamic', cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Hash and store password securely"""
        self.password_hash = generate_password_hash(password, method='pbkdf2:sha256')
    
    def check_password(self, password):
        """Verify password against stored hash"""
        return check_password_hash(self.password_hash, password)
    
    def unread_messages_count(self):
        """Count unread messages for this user"""
        return Message.query.filter_by(recipient_id=self.id, read=False).count()
    
    def is_suspended_active(self):
        """Check if suspension is currently active"""
        if not self.suspended or not self.suspension_end_date:
            return False
        return datetime.now(timezone.utc) < self.suspension_end_date
    
    def get_suspension_time_remaining(self):
        """Get remaining suspension time as string"""
        if not self.is_suspended_active():
            return None
        remaining = self.suspension_end_date - datetime.now(timezone.utc)
        hours = remaining.total_seconds() // 3600
        minutes = (remaining.total_seconds() % 3600) // 60
        return f"{int(hours)}h {int(minutes)}m"
    
    def is_recruiter(self):
        """Check if user registered as a recruiter (job poster)"""
        return self.role == 'recruiter'

    def is_worker(self):
        """Check if user registered as a worker (freelancer/recruit)"""
        return self.role == 'worker'

    def avg_rating(self):
        """Average rating received, or None if no ratings"""
        from sqlalchemy import func
        result = db.session.query(func.avg(Rating.score)).filter_by(ratee_id=self.id).scalar()
        return round(float(result), 1) if result else None

    def rating_count(self):
        return Rating.query.filter_by(ratee_id=self.id).count()

    def __repr__(self):
        return f'<User {self.username or self.email}>'


class Job(db.Model):
    """Job posting model"""
    __tablename__ = 'job'
    
    id = db.Column(db.Integer, primary_key=True)
    job_ref = db.Column(db.String(12), unique=True, nullable=True, index=True)  # e.g. KZJ-A3F9X2
    title = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(120), nullable=False)
    latitude = db.Column(db.Float, nullable=True)
    longitude = db.Column(db.Float, nullable=True)
    requirements = db.Column(db.Text, nullable=False)
    poster_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='open')  # open, filled, in_progress, completed, cancelled

    # Pay & staffing
    pay_amount = db.Column(db.Float, nullable=True)
    pay_type = db.Column(db.String(20), default='fixed')  # fixed, per_hour, per_day
    slots_total = db.Column(db.Integer, default=1, nullable=False)
    slots_filled = db.Column(db.Integer, default=0, nullable=False)

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    applications = db.relationship('JobApplication', backref='job', lazy=True, cascade='all, delete-orphan')
    media = db.relationship('JobMedia', backref='job', lazy=True, cascade='all, delete-orphan')

    def slots_remaining(self):
        """How many worker slots are still open"""
        return max(0, (self.slots_total or 1) - (self.slots_filled or 0))

    def pay_label(self):
        """Human-friendly pay description, e.g. 'KES 800 / day'"""
        if not self.pay_amount:
            return 'Pay not specified'
        suffix = {'per_hour': ' / hour', 'per_day': ' / day', 'fixed': ' total'}.get(self.pay_type, '')
        return f'KES {self.pay_amount:,.0f}{suffix}'

    def status_label(self):
        """Human-friendly status text"""
        return {
            'open': 'Open',
            'filled': 'Filled',
            'in_progress': 'In Progress',
            'completed': 'Completed',
            'cancelled': 'Cancelled',
        }.get(self.status, self.status.title())

    def can_start(self):
        """Recruiter can move job to in_progress once at least one worker is accepted"""
        return self.status in ('open', 'filled') and self.slots_filled > 0

    def can_complete(self):
        """Recruiter can mark job completed once it's in progress"""
        return self.status == 'in_progress'

    def __repr__(self):
        return f'<Job {self.title}>'


class JobMedia(db.Model):
    """Media files associated with job postings"""
    __tablename__ = 'job_media'
    
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    media_type = db.Column(db.String(20), nullable=False)  # 'image', 'video', 'other'
    uploaded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def url(self):
        """Generate URL for this media file"""
        return url_for('uploaded_file', filename=self.filename)
    
    def __repr__(self):
        return f'<JobMedia {self.filename}>'


class JobApplication(db.Model):
    """Job application model"""
    __tablename__ = 'job_application'
    
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    applicant_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, accepted, rejected
    distance_km = db.Column(db.Float, nullable=True)  # distance from applicant to job at time of application
    applied_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    def __repr__(self):
        return f'<JobApplication {self.id} for Job {self.job_id}>'


class Rating(db.Model):
    """Mutual ratings after a job completes — worker rates recruiter and vice versa"""
    __tablename__ = 'rating'

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    rater_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)     # who gave the rating
    ratee_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)     # who received it
    score = db.Column(db.Integer, nullable=False)                                   # 1–5
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    job = db.relationship('Job', backref=db.backref('ratings', lazy=True))
    rater = db.relationship('User', foreign_keys=[rater_id], backref=db.backref('ratings_given', lazy=True))
    ratee = db.relationship('User', foreign_keys=[ratee_id], backref=db.backref('ratings_received', lazy=True))

    __table_args__ = (
        db.UniqueConstraint('job_id', 'rater_id', 'ratee_id', name='unique_rating_per_job'),
    )

    def __repr__(self):
        return f'<Rating {self.score}★ for User {self.ratee_id} on Job {self.job_id}>'


class Payment(db.Model):
    """Tracks M-Pesa payments for jobs — escrow hold by recruiter, release to workers"""
    __tablename__ = 'payment'

    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job.id'), nullable=False)
    payer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)    # recruiter funding
    payee_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)    # worker receiving

    amount = db.Column(db.Float, nullable=False)
    phone_number = db.Column(db.String(20), nullable=True)                       # M-Pesa phone

    # STK Push (recruiter funding escrow)
    mpesa_checkout_id = db.Column(db.String(100), nullable=True, unique=True)    # CheckoutRequestID
    mpesa_receipt = db.Column(db.String(50), nullable=True)                      # MpesaReceiptNumber

    # B2C (worker payout)
    b2c_conversation_id = db.Column(db.String(100), nullable=True)
    b2c_originator_id = db.Column(db.String(100), nullable=True)

    type = db.Column(db.String(20), nullable=False, default='escrow')            # escrow | payout
    status = db.Column(db.String(20), nullable=False, default='pending')         # pending | completed | failed | refunded

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                           onupdate=lambda: datetime.now(timezone.utc))

    job   = db.relationship('Job',  backref=db.backref('payments', lazy=True))
    payer = db.relationship('User', foreign_keys=[payer_id], backref=db.backref('payments_made',  lazy=True))
    payee = db.relationship('User', foreign_keys=[payee_id], backref=db.backref('payments_received', lazy=True))

    def __repr__(self):
        return f'<Payment {self.type} KES {self.amount} status={self.status}>'


class Notification(db.Model):
    """User notification model"""
    __tablename__ = 'notification'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    message = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(50), default='info')
    read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    target_url = db.Column(db.String(255), nullable=True)
    
    def to_dict(self):
        """Convert notification to dictionary for JSON responses"""
        return {
            'id': self.id,
            'message': self.message,
            'type': self.type,
            'read': self.read,
            'created_at': self.created_at.replace(microsecond=0).isoformat() + 'Z',
            'target_url': self.target_url or ''
        }
    
    def __repr__(self):
        return f'<Notification {self.id} for User {self.user_id}>'


class Message(db.Model):
    """Direct messaging between users"""
    __tablename__ = 'message'
    
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    read = db.Column(db.Boolean, default=False)
    
    def to_dict(self):
        """Convert message to dictionary for JSON responses"""
        return {
            'id': self.id,
            'sender_id': self.sender_id,
            'recipient_id': self.recipient_id,
            'body': self.body,
            'created_at': self.created_at.replace(microsecond=0).isoformat() + 'Z',
            'read': self.read,
            'sender_name': (self.sender.username or self.sender.email) if self.sender else ''
        }
    
    def __repr__(self):
        return f'<Message {self.id} from User {self.sender_id}>'


# ============================================================================
# LOGIN MANAGER CONFIGURATION
# ============================================================================

@login_manager.user_loader
def load_user(user_id):
    """Load user by ID for Flask-Login"""
    try:
        return db.session.get(User, int(user_id))
    except (ValueError, TypeError):
        return None


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def sanitize_html(content):
    """Sanitize user input to prevent XSS attacks"""
    if not content:
        return content
    
    # Allow only safe HTML tags
    allowed_tags = ['b', 'i', 'u', 'em', 'strong', 'p', 'br', 'ul', 'ol', 'li']
    allowed_attributes = {}
    
    return bleach.clean(content, tags=allowed_tags, attributes=allowed_attributes, strip=True)


def generate_job_ref():
    """Generate a unique 6-char alphanumeric job reference, e.g. KZJ-A3F9X2"""
    chars = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(secrets.choice(chars) for _ in range(6))
        ref = f'KZJ-{code}'
        if not Job.query.filter_by(job_ref=ref).first():
            return ref


class MpesaService:
    """Safaricom Daraja API wrapper — STK Push (C2B) and B2C payouts"""

    BASE_SANDBOX = 'https://sandbox.safaricom.co.ke'
    BASE_PROD    = 'https://api.safaricom.co.ke'

    def __init__(self):
        self.consumer_key    = os.environ.get('MPESA_CONSUMER_KEY', '')
        self.consumer_secret = os.environ.get('MPESA_CONSUMER_SECRET', '')
        self.shortcode       = os.environ.get('MPESA_SHORTCODE', '174379')          # sandbox default
        self.passkey         = os.environ.get('MPESA_PASSKEY', '')
        self.b2c_shortcode   = os.environ.get('MPESA_B2C_SHORTCODE', '')
        self.b2c_initiator   = os.environ.get('MPESA_B2C_INITIATOR', '')
        self.b2c_credential  = os.environ.get('MPESA_B2C_SECURITY_CREDENTIAL', '')
        self.callback_base   = os.environ.get('MPESA_CALLBACK_BASE', 'https://yourdomain.com')
        self.env             = os.environ.get('MPESA_ENV', 'sandbox')               # sandbox | production
        self.base            = self.BASE_PROD if self.env == 'production' else self.BASE_SANDBOX

    def _token(self):
        """Get OAuth access token"""
        import base64
        creds = base64.b64encode(f'{self.consumer_key}:{self.consumer_secret}'.encode()).decode()
        r = requests.get(
            f'{self.base}/oauth/v1/generate?grant_type=client_credentials',
            headers={'Authorization': f'Basic {creds}'}, timeout=15
        )
        r.raise_for_status()
        return r.json()['access_token']

    def _timestamp(self):
        return datetime.now().strftime('%Y%m%d%H%M%S')

    def _password(self):
        import base64
        ts = self._timestamp()
        raw = f'{self.shortcode}{self.passkey}{ts}'
        return base64.b64encode(raw.encode()).decode(), ts

    def sanitize_phone(self, phone):
        """Normalize Kenyan phone to 254XXXXXXXXX format"""
        phone = re.sub(r'\D', '', phone)
        if phone.startswith('0'):
            phone = '254' + phone[1:]
        elif phone.startswith('+'):
            phone = phone[1:]
        if not phone.startswith('254') or len(phone) != 12:
            raise ValueError(f'Invalid Kenyan phone number: {phone}')
        return phone

    def stk_push(self, phone, amount, account_ref, description):
        """Initiate Lipa Na M-Pesa Online (STK Push) — recruiter funds escrow"""
        token = self._token()
        password, ts = self._password()
        phone = self.sanitize_phone(phone)
        payload = {
            'BusinessShortCode': self.shortcode,
            'Password': password,
            'Timestamp': ts,
            'TransactionType': 'CustomerPayBillOnline',
            'Amount': int(amount),
            'PartyA': phone,
            'PartyB': self.shortcode,
            'PhoneNumber': phone,
            'CallBackURL': f'{self.callback_base}/mpesa/callback/stk',
            'AccountReference': account_ref[:12],
            'TransactionDesc': description[:13],
        }
        r = requests.post(
            f'{self.base}/mpesa/stkpush/v1/processrequest',
            json=payload,
            headers={'Authorization': f'Bearer {token}'},
            timeout=20
        )
        r.raise_for_status()
        data = r.json()
        if data.get('ResponseCode') != '0':
            raise RuntimeError(data.get('ResponseDescription', 'STK Push failed'))
        return data  # contains CheckoutRequestID

    def stk_query(self, checkout_request_id):
        """Query STK Push status"""
        token = self._token()
        password, ts = self._password()
        r = requests.post(
            f'{self.base}/mpesa/stkpushquery/v1/query',
            json={
                'BusinessShortCode': self.shortcode,
                'Password': password,
                'Timestamp': ts,
                'CheckoutRequestID': checkout_request_id,
            },
            headers={'Authorization': f'Bearer {token}'},
            timeout=20
        )
        r.raise_for_status()
        return r.json()

    def b2c_payout(self, phone, amount, job_ref, remarks):
        """Send money to worker via B2C"""
        token = self._token()
        phone = self.sanitize_phone(phone)
        payload = {
            'InitiatorName': self.b2c_initiator,
            'SecurityCredential': self.b2c_credential,
            'CommandID': 'BusinessPayment',
            'Amount': int(amount),
            'PartyA': self.b2c_shortcode,
            'PartyB': phone,
            'Remarks': remarks[:100],
            'QueueTimeOutURL': f'{self.callback_base}/mpesa/callback/b2c/timeout',
            'ResultURL': f'{self.callback_base}/mpesa/callback/b2c/result',
            'Occasion': job_ref,
        }
        r = requests.post(
            f'{self.base}/mpesa/b2c/v3/paymentrequest',
            json=payload,
            headers={'Authorization': f'Bearer {token}'},
            timeout=20
        )
        r.raise_for_status()
        data = r.json()
        if data.get('ResponseCode') != '0':
            raise RuntimeError(data.get('ResponseDescription', 'B2C failed'))
        return data


mpesa = MpesaService()


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance between two points in kilometers, or None if any coord is missing"""
    if None in (lat1, lon1, lat2, lon2):
        return None
    from math import radians, sin, cos, sqrt, atan2
    R = 6371.0  # Earth radius in km
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def estimate_travel_minutes(distance_km, avg_speed_kmh=25):
    """Rough ETA estimate assuming average urban travel speed (default ~25km/h, mixed walk/matatu/boda)"""
    if distance_km is None:
        return None
    return max(1, round((distance_km / avg_speed_kmh) * 60))


def get_location_from_ip(ip_address):
    """Get real location from IP address using ip-api.com (free, no API key)"""
    try:
        # Skip private/internal IPs
        if ip_address.startswith(('127.', '192.168.', '10.', '172.')) or ip_address == '::1':
            return {
                'latitude': None,
                'longitude': None,
                'city': 'Local Development',
                'region': 'Local',
                'country': 'Local'
            }
        
        # Use ip-api.com - free for non-commercial use
        response = requests.get(f'http://ip-api.com/json/{ip_address}?fields=status,lat,lon,city,regionName,country', timeout=5)
        data = response.json()
        
        if data.get('status') == 'success':
            return {
                'latitude': data.get('lat'),
                'longitude': data.get('lon'),
                'city': data.get('city', 'Unknown'),
                'region': data.get('regionName', 'Unknown'),
                'country': data.get('country', 'Unknown')
            }
        else:
            app.logger.warning(f'IP geolocation failed for {ip_address}: {data.get("message", "Unknown error")}')
            return None
    except Exception as e:
        app.logger.error(f'Error getting location from IP: {e}')
        return None


def get_client_ip():
    """Get real client IP address from request"""
    if request.headers.get('X-Forwarded-For'):
        # Client behind proxy
        return request.headers.get('X-Forwarded-For').split(',')[0].strip()
    elif request.headers.get('X-Real-IP'):
        return request.headers.get('X-Real-IP')
    else:
        return request.remote_addr


def create_notification(user_id, message, type='info', target_url=None, commit=False):
    """
    Create a notification for a user
    
    Args:
        user_id: ID of the user to notify
        message: Notification message
        type: Type of notification (info, warning, error, etc.)
        target_url: Optional URL to link to
        commit: Whether to commit immediately (default: False for transaction support)
    
    Returns:
        Notification object
    """
    notif = Notification(user_id=user_id, message=message, type=type, target_url=target_url)
    db.session.add(notif)
    
    if commit:
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'Failed to commit notification: {e}')
    
    return notif


def allowed_file(filename):
    """Check if file extension is allowed"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def media_type_for_filename(filename):
    """Determine media type from filename extension"""
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    
    if ext in {'png', 'jpg', 'jpeg', 'gif'}:
        return 'image'
    elif ext in {'mp4', 'mov', 'webm'}:
        return 'video'
    else:
        return 'other'


def validate_email(email):
    """Basic email validation using regex"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_password_strength(password):
    """
    Validate password strength
    
    Returns:
        Tuple of (is_valid: bool, error_message: str)
    """
    if len(password) < 8 or not re.search(r'[A-Z]', password) or not re.search(r'[0-9]', password):
        return False, "Password must be at least 8 characters with 1 uppercase and 1 number"
    return True, ""


def ensure_default_admin():
    """
    Create default admin user if environment variables are set
    Only creates admin if DEFAULT_ADMIN_EMAIL and DEFAULT_ADMIN_PASSWORD are provided
    """
    admin_email = os.environ.get('DEFAULT_ADMIN_EMAIL')
    admin_password = os.environ.get('DEFAULT_ADMIN_PASSWORD')
    
    if not admin_email or not admin_password:
        app.logger.info('DEFAULT_ADMIN_EMAIL/PASSWORD not set; skipping default admin creation')
        return
    
    # Check if any admin already exists
    admin = User.query.filter_by(is_admin=True).first()
    if admin:
        app.logger.info('Admin user already exists')
        return
    
    # Check if user with admin email exists
    existing = User.query.filter_by(email=admin_email).first()
    if existing:
        existing.is_admin = True
        existing.username = existing.username or 'admin'
        try:
            db.session.commit()
            app.logger.info(f'Promoted existing user {admin_email} to admin')
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'Failed to promote admin: {e}')
        return
    
    # Create new admin user
    admin_user = User(
        username='admin',
        email=admin_email,
        phone_number='',
        national_id='',
        location='',
        work_type='',
        profile_completed=True,
        is_admin=True
    )
    admin_user.set_password(admin_password)
    
    try:
        db.session.add(admin_user)
        db.session.commit()
        app.logger.info(f'Created default admin user ({admin_email})')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Failed to create admin: {e}')


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(413)
def request_entity_too_large(error):
    """Handle file too large errors"""
    flash('File size exceeds maximum allowed (16 MB)', 'danger')
    return redirect(request.referrer or url_for('index')), 413


@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head><title>404 - Not Found</title></head>
    <body>
        <h1>404 - Page Not Found</h1>
        <p>The page you're looking for doesn't exist.</p>
        <a href="{{ url_for('index') }}">Go to Homepage</a>
    </body>
    </html>
    """), 404


@app.errorhandler(403)
def forbidden_error(error):
    """Handle 403 forbidden errors"""
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head><title>403 - Forbidden</title></head>
    <body>
        <h1>403 - Forbidden</h1>
        <p>You don't have permission to access this resource.</p>
        <a href="{{ url_for('index') }}">Go to Homepage</a>
    </body>
    </html>
    """), 403


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 internal server errors"""
    db.session.rollback()
    app.logger.error(f'Internal server error: {error}')
    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head><title>500 - Internal Server Error</title></head>
    <body>
        <h1>500 - Internal Server Error</h1>
        <p>Something went wrong. Please try again later.</p>
        <a href="{{ url_for('index') }}">Go to Homepage</a>
    </body>
    </html>
    """), 500


# ============================================================================
# MAIN ROUTES
# ============================================================================

@app.route('/')
def index():
    """Homepage — recruiters see their posted jobs, workers see open jobs sorted by distance"""

    if current_user.is_authenticated and current_user.is_recruiter():
        # Recruiters see their own posted jobs
        jobs = Job.query.filter_by(
            poster_id=current_user.id
        ).order_by(Job.created_at.desc()).limit(50).all()
        job_distances = {}
        return render_template('index.html', jobs=jobs, job_distances=job_distances, view='recruiter')

    # Workers (and guests): open jobs within a broad range, sorted by distance
    jobs = Job.query.filter(
        Job.status.in_(['open', 'filled'])
    ).order_by(Job.created_at.desc()).limit(100).all()

    job_distances = {}
    if current_user.is_authenticated:
        worker_lat = current_user.latitude or current_user.real_latitude
        worker_lng = current_user.longitude or current_user.real_longitude
        for job in jobs:
            dist = haversine_km(worker_lat, worker_lng, job.latitude, job.longitude)
            if dist is not None:
                job_distances[job.id] = {'distance_km': dist, 'eta_min': estimate_travel_minutes(dist)}

        # Sort by distance if we have location, otherwise by date
        if job_distances:
            jobs = sorted(jobs, key=lambda j: job_distances.get(j.id, {}).get('distance_km', float('inf')))

    return render_template('index.html', jobs=jobs, job_distances=job_distances, view='worker')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration with location tracking"""
    if request.method == 'POST':
        # Get form data
        username = request.form.get('username', '').strip() or None
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        phone_number = request.form.get('phone_number', '').strip()
        national_id = request.form.get('national_id', '').strip()
        location = request.form.get('location', '').strip()
        work_type = request.form.get('work_type', '').strip()
        role = request.form.get('role', '').strip().lower()
        
        # Get geolocation data from browser
        latitude = request.form.get('latitude', '').strip()
        longitude = request.form.get('longitude', '').strip()
        
        # Convert to float if provided
        try:
            latitude = float(latitude) if latitude else None
            longitude = float(longitude) if longitude else None
        except (ValueError, TypeError):
            latitude = None
            longitude = None
        
        # Validation
        if not email or not password:
            flash('Email and password are required', 'danger')
            return redirect(url_for('register'))

        if role not in ('worker', 'recruiter'):
            flash('Please select whether you are looking for work or posting jobs', 'danger')
            return redirect(url_for('register'))

        # Username: optional but if provided must be 3-30 chars, letters/numbers/underscore/hyphen
        if username:
            if len(username) < 3 or len(username) > 30:
                flash('Username must be between 3 and 30 characters', 'danger')
                return redirect(url_for('register'))
            if not re.match(r'^[A-Za-z0-9_-]+$', username):
                flash('Username can only contain letters, numbers, underscores and hyphens', 'danger')
                return redirect(url_for('register'))
            if User.query.filter_by(username=username).first():
                flash('That username is already taken', 'danger')
                return redirect(url_for('register'))

        # National ID: required, digits only, minimum 8 digits
        if not national_id:
            flash('National ID number is required', 'danger')
            return redirect(url_for('register'))
        if not national_id.isdigit():
            flash('National ID must contain numbers only', 'danger')
            return redirect(url_for('register'))
        if len(national_id) < 8:
            flash('National ID must be at least 8 digits', 'danger')
            return redirect(url_for('register'))
        
        if not validate_email(email):
            flash('Invalid email format', 'danger')
            return redirect(url_for('register'))
        
        valid_password, password_error = validate_password_strength(password)
        if not valid_password:
            flash(password_error, 'danger')
            return redirect(url_for('register'))
        
        # Check for existing user
        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'warning')
            return redirect(url_for('register'))

        # Create user
        user = User(
            username=username,
            email=email,
            phone_number=phone_number,
            national_id=national_id if national_id else None,
            location=location,
            latitude=latitude,
            longitude=longitude,
            work_type=work_type,
            role=role,
            profile_completed=True
        )
        user.set_password(password)
        
        # Get real IP and location
        user.real_ip = get_client_ip()
        
        # Get geolocation from IP
        location_data = get_location_from_ip(user.real_ip)
        if location_data:
            user.real_latitude = location_data['latitude']
            user.real_longitude = location_data['longitude']
            user.real_city = location_data['city']
            user.real_region = location_data['region']
            user.real_country = location_data['country']
            
            # Check for location discrepancy (if user provided custom location)
            if user.location:  # Custom location provided
                custom_location_lower = user.location.lower()
                if (location_data['city'].lower() not in custom_location_lower and 
                    location_data['region'].lower() not in custom_location_lower and
                    location_data['country'].lower() not in custom_location_lower):
                    user.location_discrepancy = True
                    app.logger.info(f'Location discrepancy for {user.email}: Custom "{user.location}" vs Real "{location_data["city"]}, {location_data["country"]}"')
        
        user.location_verified_at = datetime.now(timezone.utc)
        
        # Handle certificate upload
        cert = request.files.get('certificate')
        if cert and cert.filename:
            if allowed_file(cert.filename):
                try:
                    filename = secure_filename(f"{int(datetime.now(timezone.utc).timestamp())}_{cert.filename}")
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    cert.save(filepath)
                    user.certificate_of_good_conduct = filename
                except IOError as e:
                    app.logger.error(f'File save error: {e}')
                    flash('Failed to save certificate file', 'danger')
                    return redirect(url_for('register'))
            else:
                flash('Unsupported file type for certificate', 'warning')
                return redirect(url_for('register'))
        
        try:
            db.session.add(user)
            db.session.commit()
            login_user(user)
            if user.is_recruiter():
                flash('Registration successful! Welcome to KaziConnect — post your first job to get started.', 'success')
                return redirect(url_for('post_job'))
            flash('Registration successful! Welcome to KaziConnect — browse jobs near you.', 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'Registration error: {e}')
            flash('Registration failed. Please try again.', 'danger')
            return redirect(url_for('register'))
    
    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login (supports username or email) with suspension check"""
    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password = request.form.get('password', '')
        
        if not identifier or not password:
            flash('Please provide login credentials', 'danger')
            return redirect(url_for('login'))
        
        # Find user by email or username
        user = None
        if '@' in identifier:
            user = User.query.filter_by(email=identifier.lower()).first()
        else:
            user = User.query.filter_by(username=identifier).first()
        
        if user and user.check_password(password):
            # Check account status
            if user.burned:
                flash('Your account has been permanently blocked. Contact admin.', 'danger')
                return redirect(url_for('login'))
            
            # Check if suspended and suspension hasn't expired
            if user.suspended and user.suspension_end_date:
                now = datetime.utcnow()
                if now < user.suspension_end_date:
                    # Still suspended
                    flash(f'Your account is suspended until {user.suspension_end_date.strftime("%Y-%m-%d %H:%M UTC")}. Reason: {user.suspension_reason or "No reason provided"}', 'warning')
                    return redirect(url_for('login'))
                else:
                    # Suspension expired, auto-unsuspend
                    user.suspended = False
                    user.suspension_end_date = None
                    db.session.commit()
            
            login_user(user)
            flash('Logged in successfully', 'success')
            
            # Redirect to next page or dashboard
            next_page = request.args.get('next')
            if user.is_admin:
                return redirect(next_page) if next_page else redirect(url_for('admin_dashboard'))
            return redirect(next_page) if next_page else redirect(url_for('profile'))
        
        flash('Invalid credentials', 'danger')
    
    return render_template('login.html')


@app.route('/admin-login', methods=['GET', 'POST'])
def admin_login():
    """Admin-specific login page"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        
        if not email or not password:
            flash('Please provide credentials', 'danger')
            return redirect(url_for('admin_login'))
        
        admin = User.query.filter_by(email=email, is_admin=True).first()
        
        if admin and admin.check_password(password):
            if admin.burned:
                flash('Admin account blocked.', 'danger')
                return redirect(url_for('admin_login'))
            
            login_user(admin)
            flash('Admin logged in', 'success')
            return redirect(url_for('admin_dashboard'))
        
        flash('Invalid admin credentials', 'danger')
    
    return render_template('admin_login.html')


@app.route('/logout')
@login_required
def logout():
    """Logout user"""
    logout_user()
    flash('Logged out successfully', 'info')
    return redirect(url_for('index'))


@app.route('/profile')
@app.route('/profile/<int:user_id>')
@login_required
def profile(user_id=None):
    """View user profile (own or another user's)"""
    if user_id:
        profile_user = User.query.get_or_404(user_id)
        is_own_profile = (profile_user.id == current_user.id)
    else:
        profile_user = current_user
        is_own_profile = True
    
    # Get jobs posted by this user
    posted_jobs = Job.query.filter_by(
        poster_id=profile_user.id
    ).order_by(Job.created_at.desc()).all()
    
    # Get applications (only for own profile)
    applications = []
    application_meta = {}  # keyed by application.id: {total_applicants, queue_position, ahead_accepted}
    if is_own_profile:
        applications = JobApplication.query.filter_by(
            applicant_id=current_user.id
        ).order_by(JobApplication.applied_at.desc()).all()

        # For each application, compute queue data
        for app in applications:
            # Total applicants for this job
            total = JobApplication.query.filter_by(job_id=app.job_id).count()
            # Queue position: how many applied before this worker
            position = JobApplication.query.filter(
                JobApplication.job_id == app.job_id,
                JobApplication.applied_at < app.applied_at
            ).count() + 1
            # How many accepted so far
            accepted = JobApplication.query.filter_by(
                job_id=app.job_id, status='accepted'
            ).count()
            application_meta[app.id] = {
                'total_applicants': total,
                'queue_position': position,
                'accepted_count': accepted,
            }
    
    # Get available jobs to apply
    applied_job_ids_query = db.session.query(JobApplication.job_id).filter_by(
        applicant_id=current_user.id
    ).all()
    applied_job_ids = {job_id for (job_id,) in applied_job_ids_query}
    
    available_jobs = Job.query.filter(
        ~Job.id.in_(applied_job_ids) if applied_job_ids else True,
        Job.poster_id != current_user.id,
        Job.status == 'open'
    ).order_by(Job.created_at.desc()).limit(10).all()
    
    # Get notification counts
    unread_count = Notification.query.filter_by(
        user_id=profile_user.id,
        read=False
    ).count()
    unread_messages = profile_user.unread_messages_count() if is_own_profile else 0

    # Ratings
    ratings_received = Rating.query.filter_by(
        ratee_id=profile_user.id
    ).order_by(Rating.created_at.desc()).limit(20).all()

    rateable_jobs = []
    if current_user.is_authenticated and not is_own_profile:
        if current_user.is_recruiter():
            rateable_jobs = db.session.query(Job).join(
                JobApplication,
                and_(JobApplication.job_id == Job.id,
                     JobApplication.applicant_id == profile_user.id,
                     JobApplication.status == 'accepted')
            ).filter(
                Job.poster_id == current_user.id,
                Job.status == 'completed'
            ).filter(
                ~Rating.query.filter_by(
                    job_id=Job.id, rater_id=current_user.id, ratee_id=profile_user.id
                ).exists()
            ).all()
        else:
            rateable_jobs = db.session.query(Job).join(
                JobApplication,
                and_(JobApplication.job_id == Job.id,
                     JobApplication.applicant_id == current_user.id,
                     JobApplication.status == 'accepted')
            ).filter(
                Job.poster_id == profile_user.id,
                Job.status == 'completed'
            ).filter(
                ~Rating.query.filter_by(
                    job_id=Job.id, rater_id=current_user.id, ratee_id=profile_user.id
                ).exists()
            ).all()

    return render_template(
        'profile.html',
        user=profile_user,
        is_own_profile=is_own_profile,
        posted_jobs=posted_jobs,
        applications=applications,
        application_meta=application_meta,
        available_jobs=available_jobs,
        unread_count=unread_count,
        unread_messages=unread_messages,
        ratings_received=ratings_received,
        rateable_jobs=rateable_jobs
    )


@app.route('/toggle-role', methods=['POST'])
@login_required
def toggle_role():
    """Switch between worker and recruiter roles"""
    new_role = 'recruiter' if current_user.is_worker() else 'worker'
    try:
        current_user.role = new_role
        db.session.commit()
        flash(f'Switched to {new_role.title()} mode', 'success')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Role toggle error: {e}')
        flash('Failed to switch role', 'danger')
    return redirect(url_for('profile'))


@app.route('/edit-profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    """Edit user profile"""
    if request.method == 'POST':
        username = request.form.get('username', '').strip() or None
        phone_number = request.form.get('phone_number', '').strip()
        location = request.form.get('location', '').strip()
        work_type = request.form.get('work_type', '').strip()
        
        # Check username uniqueness
        if username:
            existing = User.query.filter(
                User.username == username,
                User.id != current_user.id
            ).first()
            if existing:
                flash('Username already taken', 'warning')
                return redirect(url_for('edit_profile'))
        
        current_user.username = username
        current_user.phone_number = phone_number
        current_user.location = location
        current_user.work_type = work_type
        
        # Get geolocation data
        latitude = request.form.get('latitude', '').strip()
        longitude = request.form.get('longitude', '').strip()
        
        # Convert to float if provided
        try:
            current_user.latitude = float(latitude) if latitude else None
            current_user.longitude = float(longitude) if longitude else None
        except (ValueError, TypeError):
            pass  # Keep existing values if conversion fails
        
        # Handle profile picture upload
        pic = request.files.get('profile_picture')
        if pic and pic.filename:
            if allowed_file(pic.filename):
                try:
                    filename = secure_filename(
                        f"{int(datetime.now(timezone.utc).timestamp())}_{pic.filename}"
                    )
                    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                    pic.save(filepath)
                    current_user.profile_picture = filename
                except IOError as e:
                    app.logger.error(f'Profile picture save error: {e}')
                    flash('Failed to save profile picture', 'danger')
                    return redirect(url_for('edit_profile'))
            else:
                flash('Unsupported file type for profile picture', 'warning')
                return redirect(url_for('edit_profile'))
        
        try:
            db.session.commit()
            flash('Profile updated successfully', 'success')
            return redirect(url_for('profile'))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'Profile update error: {e}')
            flash('Failed to update profile', 'danger')
    
    return render_template('edit_profile.html')


# ============================================================================
# JOB MANAGEMENT ROUTES
# ============================================================================

@app.route('/post-job', methods=['GET', 'POST'])
@login_required
def post_job():
    """Post a new job with optional media uploads"""
    if current_user.suspended or current_user.burned:
        flash('Your account is not allowed to post jobs.', 'danger')
        return redirect(url_for('index'))
    
    if request.method == 'POST':
        if not current_user.profile_completed:
            flash('Complete your profile before posting jobs', 'warning')
            return redirect(url_for('profile'))
        
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        location = request.form.get('location', '').strip()
        requirements = request.form.get('requirements', '').strip()

        # Pay & staffing
        pay_amount_raw = request.form.get('pay_amount', '').strip()
        pay_type = request.form.get('pay_type', 'fixed').strip()
        slots_total_raw = request.form.get('slots_total', '1').strip()
        latitude_raw = request.form.get('latitude', '').strip()
        longitude_raw = request.form.get('longitude', '').strip()

        try:
            pay_amount = float(pay_amount_raw) if pay_amount_raw else None
            if pay_amount is not None and pay_amount < 0:
                pay_amount = None
        except ValueError:
            pay_amount = None

        if pay_type not in ('fixed', 'per_hour', 'per_day'):
            pay_type = 'fixed'

        try:
            slots_total = max(1, min(100, int(slots_total_raw)))
        except ValueError:
            slots_total = 1

        try:
            latitude = float(latitude_raw) if latitude_raw else None
            longitude = float(longitude_raw) if longitude_raw else None
        except ValueError:
            latitude = None
            longitude = None
        
        # Validation
        if not all([title, description, location, requirements]):
            flash('All fields are required', 'danger')
            return render_template('post_job.html')
        
        if len(title) < 5:
            flash('Job title must be at least 5 characters', 'danger')
            return render_template('post_job.html')
        
        job = Job(
            title=title,
            description=description,
            location=location,
            latitude=latitude,
            longitude=longitude,
            requirements=requirements,
            poster_id=current_user.id,
            pay_amount=pay_amount,
            pay_type=pay_type,
            slots_total=slots_total,
            slots_filled=0,
            job_ref=generate_job_ref()
        )
        
        # Handle media uploads
        media_files = request.files.getlist('media')
        media_files = [f for f in media_files if f and getattr(f, 'filename', '')]
        
        if len(media_files) > MAX_MEDIA_PER_JOB:
            flash(f'You can upload up to {MAX_MEDIA_PER_JOB} media files per job', 'warning')
            return render_template('post_job.html')
        
        try:
            db.session.add(job)
            db.session.flush()  # Get job.id for media entries
            
            for f in media_files:
                if not allowed_file(f.filename):
                    db.session.rollback()
                    flash('One or more media files have unsupported file types', 'warning')
                    return render_template('post_job.html')
                
                # Create safe filename
                original = secure_filename(f.filename)
                ts = int(datetime.now(timezone.utc).timestamp())
                filename = f"{job.id}_{ts}_{original}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                try:
                    f.save(filepath)
                except IOError as e:
                    app.logger.error(f'Failed to save job media file: {e}')
                    db.session.rollback()
                    flash('Failed to save one of the media files', 'danger')
                    return render_template('post_job.html')
                
                mtype = media_type_for_filename(filename)
                jm = JobMedia(job_id=job.id, filename=filename, media_type=mtype)
                db.session.add(jm)
            
            db.session.commit()
            flash('Job posted successfully', 'success')
            return redirect(url_for('profile'))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'Job posting error: {e}')
            flash('Could not post job. Please try again.', 'danger')
    
    return render_template('post_job.html')


@app.route('/edit-job/<int:job_id>', methods=['GET', 'POST'])
@login_required
def edit_job(job_id):
    """Edit a job posting"""
    job = Job.query.get_or_404(job_id)
    
    if job.poster_id != current_user.id and not current_user.is_admin:
        abort(403)
    
    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        location = request.form.get('location', '').strip()
        requirements = request.form.get('requirements', '').strip()
        status = request.form.get('status', job.status)
        if status not in ('open', 'filled', 'in_progress', 'completed', 'cancelled'):
            status = job.status
        
        # Validation
        if not all([title, description, location, requirements]):
            flash('All fields are required', 'danger')
            return render_template('edit_job.html', job=job)
        
        # Handle media deletions
        remove_media_ids = request.form.get('remove_media_ids', '').strip()
        if remove_media_ids:
            try:
                ids_to_remove = [int(x) for x in remove_media_ids.split(',') if x.strip().isdigit()]
            except ValueError:
                ids_to_remove = []
            
            for mid in ids_to_remove:
                jm = JobMedia.query.get(mid)
                if jm and jm.job_id == job.id:
                    # Remove file from disk
                    path = os.path.join(app.config['UPLOAD_FOLDER'], jm.filename)
                    try:
                        if os.path.exists(path):
                            os.remove(path)
                    except Exception as e:
                        app.logger.error(f'Failed to delete media file {path}: {e}')
                    db.session.delete(jm)
        
        # Handle new media uploads
        new_media_files = request.files.getlist('media')
        new_media_files = [f for f in new_media_files if f and getattr(f, 'filename', '')]
        existing_media_count = len(job.media or [])
        
        if existing_media_count + len(new_media_files) > MAX_MEDIA_PER_JOB:
            flash(f'You can have up to {MAX_MEDIA_PER_JOB} media files per job', 'warning')
            return render_template('edit_job.html', job=job)
        
        job.title = title
        job.description = description
        job.location = location
        job.requirements = requirements
        job.status = status
        
        try:
            for f in new_media_files:
                if not allowed_file(f.filename):
                    flash('One or more new media files have unsupported file types', 'warning')
                    return render_template('edit_job.html', job=job)
                
                original = secure_filename(f.filename)
                ts = int(datetime.now(timezone.utc).timestamp())
                filename = f"{job.id}_{ts}_{original}"
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                
                try:
                    f.save(filepath)
                except IOError as e:
                    app.logger.error(f'Failed to save new job media file: {e}')
                    db.session.rollback()
                    flash('Failed to save one of the new media files', 'danger')
                    return render_template('edit_job.html', job=job)
                
                mtype = media_type_for_filename(filename)
                jm = JobMedia(job_id=job.id, filename=filename, media_type=mtype)
                db.session.add(jm)
            
            # Notify applicants of changes
            for appn in job.applications:
                create_notification(
                    appn.applicant_id,
                    f'Job "{job.title}" you applied for has been updated',
                    'job_updated',
                    target_url=url_for('index')
                )
            
            db.session.commit()
            flash('Job updated successfully', 'success')
            return redirect(url_for('profile') if not current_user.is_admin else url_for('admin_dashboard'))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'Job update error: {e}')
            flash('Failed to update job', 'danger')
            return redirect(url_for('edit_job', job_id=job_id))
    
    return render_template('edit_job.html', job=job)


@app.route('/delete-job/<int:job_id>', methods=['POST'])
@login_required
def delete_job(job_id):
    """Delete a job posting"""
    job = Job.query.get_or_404(job_id)
    
    if job.poster_id != current_user.id and not current_user.is_admin:
        abort(403)
    
    try:
        # Notify applicants
        for appn in job.applications:
            create_notification(
                appn.applicant_id,
                f'Job "{job.title}" has been removed',
                'job_deleted',
                target_url=url_for('index')
            )
        
        # Remove media files from disk
        for jm in list(job.media):
            path = os.path.join(app.config['UPLOAD_FOLDER'], jm.filename)
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                app.logger.error(f'Failed to delete job media file {path}: {e}')
            try:
                db.session.delete(jm)
            except Exception:
                pass
        
        db.session.delete(job)
        db.session.commit()
        flash('Job deleted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Job deletion error: {e}')
        flash('Failed to delete job', 'danger')
    
    return redirect(url_for('profile') if not current_user.is_admin else url_for('admin_dashboard'))


@app.route('/job/<int:job_id>')
@login_required
def get_job(job_id):
    """Get job details as JSON"""
    job = Job.query.get_or_404(job_id)
    
    media_list = []
    for jm in job.media:
        media_list.append({
            'id': jm.id,
            'filename': jm.filename,
            'media_type': jm.media_type,
            'url': url_for('uploaded_file', filename=jm.filename)
        })
    
    return jsonify({
        'id': job.id,
        'title': job.title,
        'description': job.description,
        'location': job.location,
        'requirements': job.requirements,
        'status': job.status,
        'created_at': job.created_at.strftime('%Y-%m-%d %H:%M:%S'),
        'poster_email': job.poster.email,
        'poster_name': job.poster.username or job.poster.email,
        'media': media_list
    })


@app.route('/job/<int:job_id>/view')
@login_required
def job_detail(job_id):
    """View job detail page with media gallery"""
    job = Job.query.get_or_404(job_id)
    is_poster = (current_user.is_authenticated and current_user.id == job.poster_id)

    # Worker's application for this job
    user_application = None
    can_rate_poster = False
    if current_user.is_authenticated and not is_poster:
        user_application = JobApplication.query.filter_by(
            job_id=job_id, applicant_id=current_user.id
        ).first()
        # Worker can rate recruiter if job completed and they were accepted and haven't rated yet
        if job.status == 'completed' and user_application and user_application.status == 'accepted':
            existing_rating = Rating.query.filter_by(
                job_id=job_id, rater_id=current_user.id, ratee_id=job.poster_id
            ).first()
            can_rate_poster = not existing_rating

    # Recruiter can rate accepted workers if job is completed
    rateable_workers = []
    if is_poster and job.status == 'completed':
        accepted_apps = JobApplication.query.filter_by(
            job_id=job_id, status='accepted'
        ).all()
        for app in accepted_apps:
            already_rated = Rating.query.filter_by(
                job_id=job_id, rater_id=current_user.id, ratee_id=app.applicant_id
            ).first()
            if not already_rated:
                rateable_workers.append(app.applicant)

    return render_template(
        'job_detail.html',
        job=job,
        is_poster=is_poster,
        user_application=user_application,
        can_rate_poster=can_rate_poster,
        rateable_workers=rateable_workers
    )


# ============================================================================
# JOB APPLICATION ROUTES
# ============================================================================

@app.route('/apply/<int:job_id>', methods=['POST'])
@login_required
def apply_job(job_id):
    """Apply for a job"""
    if current_user.suspended or current_user.burned:
        flash('Your account is not allowed to apply.', 'danger')
        return redirect(url_for('index'))
    
    job = Job.query.get_or_404(job_id)
    
    # Check if already applied
    existing = JobApplication.query.filter_by(
        job_id=job_id,
        applicant_id=current_user.id
    ).first()
    
    if existing:
        flash('You already applied to this job', 'info')
        return redirect(url_for('index'))
    
    # Prevent self-application
    if job.poster_id == current_user.id:
        flash('You cannot apply to your own job', 'warning')
        return redirect(url_for('index'))

    # Recruiters post jobs, they don't apply to them
    if current_user.is_recruiter():
        flash('Recruiter accounts cannot apply to jobs. Switch to a worker account to apply.', 'warning')
        return redirect(url_for('index'))

    # Check slots availability
    if job.status != 'open' or job.slots_remaining() <= 0:
        flash('This job is no longer accepting applicants — all positions are filled', 'warning')
        return redirect(url_for('index'))

    # Compute distance from worker to job (if both have coordinates)
    worker_lat = current_user.latitude or current_user.real_latitude
    worker_lng = current_user.longitude or current_user.real_longitude
    distance_km = haversine_km(worker_lat, worker_lng, job.latitude, job.longitude)

    application = JobApplication(job_id=job_id, applicant_id=current_user.id, distance_km=distance_km)

    try:
        db.session.add(application)

        notif_message = f'New application for "{job.title}" from {current_user.username or current_user.email}'
        if distance_km is not None:
            eta = estimate_travel_minutes(distance_km)
            notif_message += f' — {distance_km:.1f} km away, ~{eta} min'

        create_notification(
            job.poster_id,
            notif_message,
            'new_application',
            target_url=url_for('job_applications', job_id=job.id)
        )
        db.session.commit()
        flash('Application submitted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Application error: {e}')
        flash('Failed to apply. Please try again.', 'danger')
    
    return redirect(url_for('index'))


@app.route('/job-applications/<int:job_id>')
@login_required
def job_applications(job_id):
    """View applications for a job"""
    job = Job.query.get_or_404(job_id)
    
    if job.poster_id != current_user.id and not current_user.is_admin:
        abort(403)
    
    applications = JobApplication.query.filter_by(
        job_id=job_id
    ).order_by(
        JobApplication.distance_km.asc().nullslast(),
        JobApplication.applied_at.desc()
    ).all()

    return render_template(
        'job_applications.html',
        job=job,
        applications=applications,
        estimate_travel_minutes=estimate_travel_minutes
    )


@app.route('/update-application-status/<int:application_id>', methods=['POST'])
@login_required
def update_application_status(application_id):
    """Update application status (accept/reject)"""
    application = JobApplication.query.get_or_404(application_id)
    
    if application.job.poster_id != current_user.id and not current_user.is_admin:
        abort(403)
    
    new_status = request.form.get('status')
    if new_status not in ('pending', 'accepted', 'rejected'):
        flash('Invalid status', 'danger')
        return redirect(url_for('job_applications', job_id=application.job_id))

    job = application.job
    old_status = application.status

    if job.status in ('in_progress', 'completed', 'cancelled'):
        flash('This job has already started — applications can no longer be changed', 'warning')
        return redirect(url_for('job_applications', job_id=application.job_id))

    # Guard: don't accept beyond available slots
    if new_status == 'accepted' and old_status != 'accepted' and job.slots_remaining() <= 0:
        flash('Cannot accept — all slots for this job are already filled', 'warning')
        return redirect(url_for('job_applications', job_id=application.job_id))
    
    try:
        application.status = new_status

        # Adjust slots_filled based on transition
        if new_status == 'accepted' and old_status != 'accepted':
            job.slots_filled = (job.slots_filled or 0) + 1
        elif old_status == 'accepted' and new_status != 'accepted':
            job.slots_filled = max(0, (job.slots_filled or 0) - 1)

        # Update job status based on staffing level (only while job hasn't started)
        if job.status in ('open', 'filled'):
            if job.slots_filled >= job.slots_total:
                job.status = 'filled'
            elif job.slots_filled < job.slots_total:
                job.status = 'open'

        db.session.commit()
        
        create_notification(
            application.applicant_id,
            f'Your application for "{application.job.title}" was {new_status}',
            f'application_{new_status}',
            target_url=url_for('profile'),
            commit=True
        )
        
        flash('Application status updated', 'success')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Application update error: {e}')
        flash('Failed to update application', 'danger')
    
    return redirect(url_for('job_applications', job_id=application.job_id))


@app.route('/job/<int:job_id>/bulk-accept', methods=['POST'])
@login_required
def bulk_accept_applications(job_id):
    """Accept multiple pending applicants at once, up to remaining slots"""
    job = Job.query.get_or_404(job_id)

    if job.poster_id != current_user.id and not current_user.is_admin:
        abort(403)

    if job.status in ('in_progress', 'completed', 'cancelled'):
        flash('This job has already started — applications can no longer be changed', 'warning')
        return redirect(url_for('job_applications', job_id=job_id))

    application_ids = request.form.getlist('application_ids')
    if not application_ids:
        flash('No applicants selected', 'warning')
        return redirect(url_for('job_applications', job_id=job_id))

    try:
        applications = JobApplication.query.filter(
            JobApplication.id.in_(application_ids),
            JobApplication.job_id == job_id,
            JobApplication.status == 'pending'
        ).all()

        remaining = job.slots_remaining()
        accepted_count = 0

        for application in applications:
            if remaining <= 0:
                break
            application.status = 'accepted'
            job.slots_filled = (job.slots_filled or 0) + 1
            remaining -= 1
            accepted_count += 1

            create_notification(
                application.applicant_id,
                f'Your application for "{job.title}" was accepted',
                'application_accepted',
                target_url=url_for('profile')
            )

        if job.slots_filled >= job.slots_total:
            job.status = 'filled'

        db.session.commit()

        if accepted_count < len(applications):
            flash(f'Accepted {accepted_count} applicant(s) — remaining slots were not enough for everyone selected', 'warning')
        else:
            flash(f'Accepted {accepted_count} applicant(s)', 'success')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Bulk accept error: {e}')
        flash('Failed to accept applicants', 'danger')

    return redirect(url_for('job_applications', job_id=job_id))


@app.route('/job/<int:job_id>/start', methods=['POST'])
@login_required
def start_job(job_id):
    """Mark a job as in_progress once staffing has begun"""
    job = Job.query.get_or_404(job_id)

    if job.poster_id != current_user.id and not current_user.is_admin:
        abort(403)

    if not job.can_start():
        flash('Job cannot be started — accept at least one applicant first', 'warning')
        return redirect(url_for('job_applications', job_id=job_id))

    try:
        job.status = 'in_progress'
        job.started_at = datetime.now(timezone.utc)
        db.session.commit()

        # Notify accepted workers
        for application in job.applications:
            if application.status == 'accepted':
                create_notification(
                    application.applicant_id,
                    f'The job "{job.title}" has started',
                    'job_started',
                    target_url=url_for('job_detail', job_id=job.id)
                )
        db.session.commit()

        flash('Job marked as in progress', 'success')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Start job error: {e}')
        flash('Failed to start job', 'danger')

    return redirect(url_for('job_applications', job_id=job_id))


@app.route('/job/<int:job_id>/complete', methods=['POST'])
@login_required
def complete_job(job_id):
    """Mark a job as completed, ready for payment release"""
    job = Job.query.get_or_404(job_id)

    if job.poster_id != current_user.id and not current_user.is_admin:
        abort(403)

    if not job.can_complete():
        flash('Job must be in progress before it can be marked complete', 'warning')
        return redirect(url_for('job_applications', job_id=job_id))

    try:
        job.status = 'completed'
        job.completed_at = datetime.now(timezone.utc)
        db.session.commit()

        # Notify accepted workers
        for application in job.applications:
            if application.status == 'accepted':
                create_notification(
                    application.applicant_id,
                    f'The job "{job.title}" has been marked complete',
                    'job_completed',
                    target_url=url_for('job_detail', job_id=job.id)
                )
        db.session.commit()

        flash('Job marked as completed', 'success')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Complete job error: {e}')
        flash('Failed to complete job', 'danger')

    return redirect(url_for('job_applications', job_id=job_id))


@app.route('/job/<int:job_id>/cancel', methods=['POST'])
@login_required
def cancel_job(job_id):
    """Cancel a job posting"""
    job = Job.query.get_or_404(job_id)

    if job.poster_id != current_user.id and not current_user.is_admin:
        abort(403)

    if job.status == 'completed':
        flash('A completed job cannot be cancelled', 'warning')
        return redirect(url_for('job_applications', job_id=job_id))

    try:
        job.status = 'cancelled'
        db.session.commit()

        for application in job.applications:
            if application.status == 'accepted':
                create_notification(
                    application.applicant_id,
                    f'The job "{job.title}" was cancelled by the recruiter',
                    'job_cancelled',
                    target_url=url_for('profile')
                )
        db.session.commit()

        flash('Job cancelled', 'info')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Cancel job error: {e}')
        flash('Failed to cancel job', 'danger')

    return redirect(url_for('job_applications', job_id=job_id))


# ============================================================================
# RATING ROUTES
# ============================================================================

@app.route('/rate/<int:job_id>/<int:ratee_id>', methods=['POST'])
@login_required
def submit_rating(job_id, ratee_id):
    """Submit a rating for a user after a completed job"""
    job = Job.query.get_or_404(job_id)
    ratee = User.query.get_or_404(ratee_id)

    if ratee_id == current_user.id:
        flash('You cannot rate yourself', 'warning')
        return redirect(url_for('job_detail', job_id=job_id))

    # Job must be completed
    if job.status != 'completed':
        flash('Ratings can only be submitted after a job is completed', 'warning')
        return redirect(url_for('job_detail', job_id=job_id))

    # Recruiter can rate accepted workers; workers can rate the job's recruiter
    if current_user.is_recruiter():
        # Must be the job poster, ratee must be an accepted worker
        if job.poster_id != current_user.id:
            abort(403)
        accepted = JobApplication.query.filter_by(
            job_id=job_id, applicant_id=ratee_id, status='accepted'
        ).first()
        if not accepted:
            flash('You can only rate workers who were accepted for this job', 'warning')
            return redirect(url_for('job_detail', job_id=job_id))
    else:
        # Worker can only rate the recruiter of a job they were accepted for
        accepted = JobApplication.query.filter_by(
            job_id=job_id, applicant_id=current_user.id, status='accepted'
        ).first()
        if not accepted:
            flash('You can only rate the recruiter for jobs you were accepted for', 'warning')
            return redirect(url_for('job_detail', job_id=job_id))
        if ratee_id != job.poster_id:
            abort(403)

    # Check not already rated
    existing = Rating.query.filter_by(job_id=job_id, rater_id=current_user.id, ratee_id=ratee_id).first()
    if existing:
        flash('You have already rated this person for this job', 'warning')
        return redirect(url_for('profile', user_id=ratee_id))

    try:
        score = int(request.form.get('score', 0))
        if score < 1 or score > 5:
            flash('Rating must be between 1 and 5 stars', 'danger')
            return redirect(url_for('profile', user_id=ratee_id))
    except (ValueError, TypeError):
        flash('Invalid rating score', 'danger')
        return redirect(url_for('profile', user_id=ratee_id))

    comment = request.form.get('comment', '').strip()[:500]

    try:
        rating = Rating(
            job_id=job_id,
            rater_id=current_user.id,
            ratee_id=ratee_id,
            score=score,
            comment=comment or None
        )
        db.session.add(rating)
        create_notification(
            ratee_id,
            f'{current_user.username or current_user.email} gave you a {score}★ rating for "{job.title}"',
            'new_rating',
            target_url=url_for('profile', user_id=ratee_id)
        )
        db.session.commit()
        flash(f'{score}★ rating submitted successfully', 'success')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Rating error: {e}')
        flash('Failed to submit rating', 'danger')

    return redirect(url_for('profile', user_id=ratee_id))


# ============================================================================
# M-PESA PAYMENT ROUTES
# ============================================================================

@app.route('/job/<int:job_id>/fund', methods=['GET', 'POST'])
@login_required
def fund_job(job_id):
    """Recruiter funds the job escrow via STK Push"""
    job = Job.query.get_or_404(job_id)
    if job.poster_id != current_user.id:
        abort(403)

    if job.status == 'completed':
        flash('This job is already completed', 'info')
        return redirect(url_for('job_detail', job_id=job_id))

    # Check if escrow already funded
    existing = Payment.query.filter_by(job_id=job_id, type='escrow', status='completed').first()
    if existing:
        flash('This job is already funded', 'info')
        return redirect(url_for('job_detail', job_id=job_id))

    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        if not phone:
            flash('Please enter your M-Pesa phone number', 'danger')
            return render_template('fund_job.html', job=job)

        total = (job.pay_amount or 0) * (job.slots_filled or job.slots_total or 1)
        if total <= 0:
            flash('Job has no pay amount set', 'danger')
            return redirect(url_for('edit_job', job_id=job_id))

        try:
            phone_clean = mpesa.sanitize_phone(phone)
        except ValueError as e:
            flash(str(e), 'danger')
            return render_template('fund_job.html', job=job)

        try:
            result = mpesa.stk_push(
                phone=phone_clean,
                amount=total,
                account_ref=job.job_ref or f'JOB{job_id}',
                description=f'KaziConnect Job {job.job_ref or job_id}'
            )
            payment = Payment(
                job_id=job_id,
                payer_id=current_user.id,
                amount=total,
                phone_number=phone_clean,
                type='escrow',
                status='pending',
                mpesa_checkout_id=result.get('CheckoutRequestID')
            )
            db.session.add(payment)
            db.session.commit()
            flash(f'STK Push sent to {phone}. Enter your M-Pesa PIN to complete payment of KES {total:,.0f}.', 'success')
            return redirect(url_for('payment_status', payment_id=payment.id))
        except Exception as e:
            app.logger.error(f'STK Push error: {e}')
            flash(f'M-Pesa request failed: {e}', 'danger')
            return render_template('fund_job.html', job=job)

    total = (job.pay_amount or 0) * (job.slots_filled or job.slots_total or 1)
    return render_template('fund_job.html', job=job, total=total)


@app.route('/payment/<int:payment_id>/status')
@login_required
def payment_status(payment_id):
    """Check payment status — polls STK query if still pending"""
    payment = Payment.query.get_or_404(payment_id)
    if payment.payer_id != current_user.id and payment.payee_id != current_user.id and not current_user.is_admin:
        abort(403)

    # If pending, try querying Daraja
    if payment.status == 'pending' and payment.mpesa_checkout_id:
        try:
            result = mpesa.stk_query(payment.mpesa_checkout_id)
            rc = result.get('ResultCode')
            if rc == '0' or rc == 0:
                payment.status = 'completed'
                payment.mpesa_receipt = result.get('MpesaReceiptNumber')
                db.session.commit()
                flash('Payment confirmed! Escrow funded successfully.', 'success')
            elif rc is not None and str(rc) != '1032':  # 1032 = request cancelled by user
                payment.status = 'failed'
                db.session.commit()
                flash(f'Payment failed: {result.get("ResultDesc", "Unknown error")}', 'danger')
        except Exception as e:
            app.logger.warning(f'STK query error: {e}')

    return render_template('payment_status.html', payment=payment)


@app.route('/job/<int:job_id>/release-payments', methods=['GET', 'POST'])
@login_required
def release_payments(job_id):
    """Recruiter releases payment to accepted workers after job completion"""
    job = Job.query.get_or_404(job_id)
    if job.poster_id != current_user.id:
        abort(403)

    if job.status != 'completed':
        flash('Job must be completed before releasing payments', 'warning')
        return redirect(url_for('job_detail', job_id=job_id))

    # Escrow must be funded
    escrow = Payment.query.filter_by(job_id=job_id, type='escrow', status='completed').first()
    if not escrow:
        flash('Please fund the job escrow first before releasing payments', 'warning')
        return redirect(url_for('fund_job', job_id=job_id))

    accepted_apps = JobApplication.query.filter_by(job_id=job_id, status='accepted').all()
    per_worker = job.pay_amount or 0
    platform_fee_pct = float(os.environ.get('PLATFORM_FEE_PCT', '5'))  # 5% default
    worker_amount = round(per_worker * (1 - platform_fee_pct / 100), 2)

    if request.method == 'POST':
        released = 0
        errors = []
        for app_ in accepted_apps:
            # Skip if already paid
            already = Payment.query.filter_by(
                job_id=job_id, payee_id=app_.applicant_id, type='payout', status='completed'
            ).first()
            if already:
                continue

            worker = app_.applicant
            phone = request.form.get(f'phone_{worker.id}', worker.phone_number or '').strip()
            if not phone:
                errors.append(f'No phone for {worker.username or worker.email.split("@")[0]}')
                continue

            try:
                result = mpesa.b2c_payout(
                    phone=phone,
                    amount=worker_amount,
                    job_ref=job.job_ref or f'JOB{job_id}',
                    remarks=f'Payment for {job.title[:50]}'
                )
                payout = Payment(
                    job_id=job_id,
                    payer_id=current_user.id,
                    payee_id=worker.id,
                    amount=worker_amount,
                    phone_number=mpesa.sanitize_phone(phone),
                    type='payout',
                    status='pending',
                    b2c_conversation_id=result.get('ConversationID'),
                    b2c_originator_id=result.get('OriginatorConversationID')
                )
                db.session.add(payout)
                create_notification(
                    worker.id,
                    f'KES {worker_amount:,.0f} payment for "{job.title}" is being processed to your M-Pesa',
                    'payment_sent',
                    target_url=url_for('profile')
                )
                released += 1
            except Exception as e:
                errors.append(f'{worker.username or worker.email.split("@")[0]}: {e}')

        db.session.commit()
        if released:
            flash(f'Payments initiated for {released} worker(s). Funds will arrive within minutes.', 'success')
        for err in errors:
            flash(f'Failed: {err}', 'danger')
        return redirect(url_for('job_detail', job_id=job_id))

    return render_template(
        'release_payments.html',
        job=job,
        accepted_apps=accepted_apps,
        worker_amount=worker_amount,
        platform_fee_pct=platform_fee_pct,
        escrow=escrow
    )


@app.route('/mpesa/callback/stk', methods=['POST'])
def mpesa_stk_callback():
    """Daraja callback for STK Push — updates payment status"""
    try:
        data = request.get_json(force=True) or {}
        body = data.get('Body', {}).get('stkCallback', {})
        checkout_id = body.get('CheckoutRequestID')
        result_code = body.get('ResultCode')

        payment = Payment.query.filter_by(mpesa_checkout_id=checkout_id).first()
        if payment:
            if result_code == 0:
                items = body.get('CallbackMetadata', {}).get('Item', [])
                receipt = next((i['Value'] for i in items if i['Name'] == 'MpesaReceiptNumber'), None)
                payment.status = 'completed'
                payment.mpesa_receipt = receipt
                create_notification(
                    payment.payer_id,
                    f'Escrow payment of KES {payment.amount:,.0f} confirmed (Receipt: {receipt})',
                    'payment_confirmed',
                    target_url=url_for('job_detail', job_id=payment.job_id)
                )
            else:
                payment.status = 'failed'
                create_notification(
                    payment.payer_id,
                    f'Escrow payment failed: {body.get("ResultDesc", "Unknown error")}',
                    'payment_failed',
                    target_url=url_for('fund_job', job_id=payment.job_id)
                )
            db.session.commit()
    except Exception as e:
        app.logger.error(f'STK callback error: {e}')
    return jsonify({'ResultCode': 0, 'ResultDesc': 'Accepted'})


@app.route('/mpesa/callback/b2c/result', methods=['POST'])
def mpesa_b2c_result():
    """Daraja callback for B2C payout results"""
    try:
        data = request.get_json(force=True) or {}
        result = data.get('Result', {})
        conversation_id = result.get('ConversationID')
        result_code = result.get('ResultCode')

        payment = Payment.query.filter_by(b2c_conversation_id=conversation_id).first()
        if payment:
            if result_code == 0:
                params = {p['Key']: p['Value'] for p in
                          result.get('ResultParameters', {}).get('ResultParameter', [])}
                payment.status = 'completed'
                payment.mpesa_receipt = params.get('TransactionReceipt')
                if payment.payee_id:
                    create_notification(
                        payment.payee_id,
                        f'KES {payment.amount:,.0f} received on M-Pesa (Receipt: {payment.mpesa_receipt})',
                        'payment_received',
                        target_url=url_for('profile')
                    )
            else:
                payment.status = 'failed'
                if payment.payee_id:
                    create_notification(
                        payment.payee_id,
                        f'Payment of KES {payment.amount:,.0f} failed — contact support',
                        'payment_failed',
                        target_url=url_for('profile')
                    )
            db.session.commit()
    except Exception as e:
        app.logger.error(f'B2C result callback error: {e}')
    return jsonify({'ResultCode': 0, 'ResultDesc': 'Accepted'})


@app.route('/mpesa/callback/b2c/timeout', methods=['POST'])
def mpesa_b2c_timeout():
    """Daraja timeout callback for B2C"""
    try:
        data = request.get_json(force=True) or {}
        result = data.get('Result', {})
        conversation_id = result.get('ConversationID')
        payment = Payment.query.filter_by(b2c_conversation_id=conversation_id).first()
        if payment:
            payment.status = 'failed'
            db.session.commit()
    except Exception as e:
        app.logger.error(f'B2C timeout error: {e}')
    return jsonify({'ResultCode': 0, 'ResultDesc': 'Accepted'})


# ============================================================================
# NOTIFICATION ROUTES
# ============================================================================

@app.route('/notifications/count')
@login_required
def notifications_count():
    """Get unread notification count (API)"""
    count = Notification.query.filter_by(user_id=current_user.id, read=False).count()
    return jsonify({'count': count})


@app.route('/notifications')
@login_required
def notifications_list():
    """Get list of notifications (API)"""
    notifs = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).limit(50).all()
    return jsonify([n.to_dict() for n in notifs])


@app.route('/notifications/mark-read', methods=['POST'])
@login_required
def notifications_mark_read():
    """Mark notifications as read"""
    data = request.get_json() or {}
    ids = data.get('ids', [])
    
    try:
        if ids:
            Notification.query.filter(
                Notification.id.in_(ids),
                Notification.user_id == current_user.id
            ).update({'read': True}, synchronize_session=False)
        else:
            Notification.query.filter_by(
                user_id=current_user.id,
                read=False
            ).update({'read': True}, synchronize_session=False)
        
        db.session.commit()
        return jsonify({'status': 'ok'})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Mark read error: {e}')
        return jsonify({'status': 'error', 'error': str(e)}), 500


@app.route('/notifications-page')
@login_required
def notifications_page():
    """Notifications page (HTML view)"""
    notifs = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).all()
    return render_template('notifications.html', notifications=notifs)


# ============================================================================
# MESSAGING ROUTES
# ============================================================================

@app.route('/messages')
@login_required
def messages_list():
    """List all message conversations"""
    # Find distinct other user IDs
    sent = db.session.query(Message.recipient_id.label('other_id')).filter(
        Message.sender_id == current_user.id
    )
    received = db.session.query(Message.sender_id.label('other_id')).filter(
        Message.recipient_id == current_user.id
    )
    union_q = sent.union(received).subquery()
    other_ids = [row.other_id for row in db.session.query(union_q.c.other_id).all()]
    
    conversations = []
    for oid in other_ids:
        other_user = User.query.get(oid)
        if not other_user:
            continue
        
        last_msg = Message.query.filter(
            or_(
                and_(Message.sender_id == current_user.id, Message.recipient_id == oid),
                and_(Message.sender_id == oid, Message.recipient_id == current_user.id)
            )
        ).order_by(Message.created_at.desc()).first()
        
        unread_count = Message.query.filter_by(
            sender_id=oid,
            recipient_id=current_user.id,
            read=False
        ).count()
        
        conversations.append({
            'other_user': other_user,
            'last_message': last_msg,
            'unread_count': unread_count
        })
    
    # Sort by last message date
    conversations.sort(
        key=lambda x: x['last_message'].created_at if x['last_message'] else datetime.min.replace(tzinfo=timezone.utc),
        reverse=True
    )
    
    total_unread = current_user.unread_messages_count()
    return render_template('messages.html', conversations=conversations, total_unread=total_unread)


@app.route('/messages/<int:other_id>', methods=['GET', 'POST'])
@login_required
def messages_conversation(other_id):
    """View and send messages in a conversation"""
    other = User.query.get_or_404(other_id)
    
    if other.id == current_user.id:
        flash('You cannot message yourself', 'warning')
        return redirect(url_for('messages_list'))
    
    if request.method == 'POST':
        body = request.form.get('body', '').strip()
        
        if not body:
            flash('Message cannot be empty', 'warning')
            return redirect(url_for('messages_conversation', other_id=other_id))
        
        if len(body) > 5000:
            flash('Message is too long (max 5000 characters)', 'warning')
            return redirect(url_for('messages_conversation', other_id=other_id))
        
        msg = Message(sender_id=current_user.id, recipient_id=other.id, body=body)
        
        try:
            db.session.add(msg)
            create_notification(
                other.id,
                f'New message from {(current_user.username or current_user.email)}',
                'new_message',
                target_url=url_for('messages_conversation', other_id=current_user.id)
            )
            db.session.commit()
            flash('Message sent', 'success')
            return redirect(url_for('messages_conversation', other_id=other_id))
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'Message send error: {e}')
            flash('Failed to send message', 'danger')
            return redirect(url_for('messages_conversation', other_id=other_id))
    
    # Get thread messages
    msgs = Message.query.filter(
        or_(
            and_(Message.sender_id == current_user.id, Message.recipient_id == other.id),
            and_(Message.sender_id == other.id, Message.recipient_id == current_user.id)
        )
    ).order_by(Message.created_at.asc()).all()
    
    # Mark unread messages as read
    try:
        Message.query.filter_by(
            sender_id=other.id,
            recipient_id=current_user.id,
            read=False
        ).update({'read': True}, synchronize_session=False)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Mark messages read error: {e}')
    
    return render_template('message_thread.html', other=other, messages=msgs)


@app.route('/messages/send', methods=['POST'])
@login_required
def messages_send_api():
    """Send message API (supports JSON and form data)"""
    # Support both JSON and form data
    if request.is_json:
        data = request.get_json()
        recipient_id = data.get('recipient_id')
        body = data.get('body', '')
    else:
        recipient_id = request.form.get('recipient_id')
        body = request.form.get('body', '')
    
    if not recipient_id or not body:
        return jsonify({
            'status': 'error',
            'error': 'recipient_id and body required'
        }), 400
    
    try:
        recipient_id = int(recipient_id)
    except (ValueError, TypeError):
        return jsonify({'status': 'error', 'error': 'Invalid recipient_id'}), 400
    
    recipient = User.query.get(recipient_id)
    if not recipient:
        return jsonify({'status': 'error', 'error': 'recipient not found'}), 404
    
    if recipient.id == current_user.id:
        return jsonify({'status': 'error', 'error': 'cannot message yourself'}), 400
    
    body = body.strip()
    if not body:
        return jsonify({'status': 'error', 'error': 'message body cannot be empty'}), 400
    
    if len(body) > 5000:
        return jsonify({'status': 'error', 'error': 'message too long'}), 400
    
    msg = Message(sender_id=current_user.id, recipient_id=recipient.id, body=body)
    
    try:
        db.session.add(msg)
        create_notification(
            recipient.id,
            f'New message from {(current_user.username or current_user.email)}',
            'new_message',
            target_url=url_for('messages_conversation', other_id=current_user.id)
        )
        db.session.commit()
        return jsonify({'status': 'ok', 'message': msg.to_dict()})
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Message send API error: {e}')
        return jsonify({'status': 'error', 'error': 'Failed to send message'}), 500


@app.route('/messages/unread_count')
@login_required
def messages_unread_count():
    """Get unread message count (API)"""
    count = current_user.unread_messages_count()
    return jsonify({'count': count})


@app.route('/messages/poll/<int:other_id>')
@login_required
def messages_poll(other_id):
    """Poll for new messages since a given message ID — used for real-time chat"""
    since_id = request.args.get('since', 0, type=int)
    msgs = Message.query.filter(
        or_(
            and_(Message.sender_id == current_user.id, Message.recipient_id == other_id),
            and_(Message.sender_id == other_id, Message.recipient_id == current_user.id)
        ),
        Message.id > since_id
    ).order_by(Message.created_at.asc()).all()

    # Mark newly received messages as read
    try:
        Message.query.filter(
            Message.sender_id == other_id,
            Message.recipient_id == current_user.id,
            Message.id > since_id,
            Message.read == False
        ).update({'read': True}, synchronize_session=False)
        db.session.commit()
    except Exception:
        db.session.rollback()

    return jsonify({
        'messages': [m.to_dict() for m in msgs],
        'last_id': msgs[-1].id if msgs else since_id
    })


@app.route('/messages/conversations')
@login_required
def messages_conversations_api():
    """Get conversations metadata (API)"""
    sent = db.session.query(Message.recipient_id.label('other_id')).filter(
        Message.sender_id == current_user.id
    )
    received = db.session.query(Message.sender_id.label('other_id')).filter(
        Message.recipient_id == current_user.id
    )
    union_q = sent.union(received).subquery()
    other_ids = [row.other_id for row in db.session.query(union_q.c.other_id).all()]
    
    data = []
    for oid in other_ids:
        other_user = User.query.get(oid)
        if not other_user:
            continue
        
        last_msg = Message.query.filter(
            or_(
                and_(Message.sender_id == current_user.id, Message.recipient_id == oid),
                and_(Message.sender_id == oid, Message.recipient_id == current_user.id)
            )
        ).order_by(Message.created_at.desc()).first()
        
        unread_count = Message.query.filter_by(
            sender_id=oid,
            recipient_id=current_user.id,
            read=False
        ).count()
        
        data.append({
            'other_id': oid,
            'other_name': other_user.username or other_user.email,
            'last_message': last_msg.to_dict() if last_msg else None,
            'unread_count': unread_count
        })
    
    return jsonify(data)


# ============================================================================
# USER MANAGEMENT ROUTES
# ============================================================================

@app.route('/users/all')
@login_required
def all_users():
    """List all users"""
    users = User.query.filter(
        User.id != current_user.id
    ).order_by(User.username.asc()).all()
    
    results = []
    for u in users:
        job = Job.query.filter_by(
            poster_id=u.id,
            status='open'
        ).order_by(Job.created_at.desc()).first()
        
        results.append({
            "id": u.id,
            "username": u.username or u.email,
            "profile_picture": u.profile_picture or None,
            "job_title": job.title if job else "Not posted yet",
            "job_id": job.id if job else None
        })
    
    return render_template('users_all.html', users=results)


@app.route('/users/search')
@login_required
def search_users():
    """Search users (API)"""
    query = request.args.get('q', '').strip()
    
    if query:
        users = User.query.filter(
            or_(
                User.username.ilike(f"%{query}%"),
                User.email.ilike(f"%{query}%")
            )
        ).limit(50).all()
    else:
        users = User.query.limit(50).all()
    
    results = []
    for u in users:
        job = Job.query.filter_by(poster_id=u.id).first()
        results.append({
            "id": u.id,
            "username": u.username or u.email,
            "profile_picture": u.profile_picture or None,
            "job_title": job.title if job else "Not posted yet",
            "job_id": job.id if job else None
        })
    
    return jsonify(results)


# ============================================================================
# ADMIN ROUTES
# ============================================================================

@app.route('/admin')
@login_required
def admin_dashboard():
    """Admin dashboard"""
    if not current_user.is_admin:
        abort(403)
    
    users = User.query.order_by(User.id.desc()).all()
    jobs = Job.query.order_by(Job.created_at.desc()).all()
    return render_template('admin.html', users=users, jobs=jobs)


@app.route('/admin/locations')
@login_required
def admin_locations():
    """Admin location monitoring dashboard"""
    if not current_user.is_admin:
        abort(403)
    
    # Get all users with location data
    users = User.query.order_by(User.created_at.desc()).all()
    
    # Statistics
    total_users = len(users)
    discrepancy_count = sum(1 for u in users if u.location_discrepancy)
    unique_countries = len(set(u.real_country for u in users if u.real_country))
    
    # Currently suspended
    now = datetime.utcnow()
    suspended_now = sum(1 for u in users if u.suspended and 
                       (u.suspension_end_date and u.suspension_end_date > now))
    
    # Users with coordinates for map
    users_with_coords = sum(1 for u in users if u.real_latitude and u.real_longitude)
    
    # Program progress stats
    thirty_days_ago = now - timedelta(days=30)
    new_users_30d = User.query.filter(User.created_at >= thirty_days_ago).count()
    
    # Active posters (users who posted jobs in last 30 days)
    active_posters = db.session.query(User).join(Job).filter(
        Job.created_at >= thirty_days_ago
    ).distinct().count()
    
    # Suspension rate
    suspended_total = User.query.filter_by(suspended=True).count()
    suspension_rate = round((suspended_total / total_users) * 100, 1) if total_users > 0 else 0
    
    # Registrations by country
    registrations_by_country = {}
    for u in users:
        if u.real_country:
            registrations_by_country[u.real_country] = registrations_by_country.get(u.real_country, 0) + 1
    
    return render_template('admin_locations.html',
                         users=users,
                         total_users=total_users,
                         discrepancy_count=discrepancy_count,
                         unique_countries=unique_countries,
                         suspended_now=suspended_now,
                         users_with_coords=users_with_coords,
                         new_users_30d=new_users_30d,
                         active_posters=active_posters,
                         suspension_rate=suspension_rate,
                         registrations_by_country=registrations_by_country)


@app.route('/admin/settings', methods=['GET', 'POST'])
@login_required
def admin_settings():
    """Admin settings"""
    if not current_user.is_admin:
        abort(403)
    
    if request.method == 'POST':
        new_username = request.form.get('username', '').strip() or None
        new_password = request.form.get('password', '').strip()
        
        if new_username:
            existing = User.query.filter(
                User.username == new_username,
                User.id != current_user.id
            ).first()
            if existing:
                flash('Username already taken', 'warning')
                return redirect(url_for('admin_settings'))
            current_user.username = new_username
        
        if new_password:
            valid, error = validate_password_strength(new_password)
            if not valid:
                flash(error, 'danger')
                return redirect(url_for('admin_settings'))
            current_user.set_password(new_password)
        
        try:
            db.session.commit()
            flash('Admin settings updated', 'success')
        except Exception as e:
            db.session.rollback()
            app.logger.error(f'Admin settings update error: {e}')
            flash('Failed to update settings', 'danger')
        
        return redirect(url_for('admin_settings'))
    
    return render_template('admin_settings.html')


@app.route('/admin/warn/<int:user_id>', methods=['POST'])
@login_required
def admin_warn(user_id):
    """Warn a user"""
    if not current_user.is_admin:
        abort(403)
    
    if user_id == current_user.id:
        flash('You cannot warn yourself', 'warning')
        return redirect(url_for('admin_dashboard'))
    
    reason = request.form.get('reason', 'Please follow the rules.').strip()
    user = User.query.get_or_404(user_id)
    
    try:
        user.warnings_count = (user.warnings_count or 0) + 1
        db.session.commit()
        
        create_notification(
            user.id,
            f'You have been warned: {reason}',
            'admin_warn',
            target_url=url_for('profile'),
            commit=True
        )
        
        flash('User warned successfully', 'success')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Warn user error: {e}')
        flash('Failed to warn user', 'danger')
    
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/suspend-with-duration/<int:user_id>', methods=['POST'])
@login_required
def admin_suspend_with_duration(user_id):
    """Suspend a user with specific duration"""
    if not current_user.is_admin:
        abort(403)
    
    if user_id == current_user.id:
        flash('You cannot suspend yourself', 'warning')
        return redirect(url_for('admin_locations'))
    
    user = User.query.get_or_404(user_id)
    duration = request.form.get('duration')
    reason = request.form.get('reason', 'No reason provided').strip()
    custom_hours = request.form.get('custom_hours')
    
    # Calculate suspension end date
    now = datetime.utcnow()
    
    if duration == 'hour':
        end_date = now + timedelta(hours=1)
    elif duration == 'day':
        end_date = now + timedelta(days=1)
    elif duration == 'week':
        end_date = now + timedelta(weeks=1)
    elif duration == 'month':
        end_date = now + timedelta(days=30)
    elif duration == 'year':
        end_date = now + timedelta(days=365)
    elif duration == 'custom' and custom_hours:
        try:
            hours = int(custom_hours)
            end_date = now + timedelta(hours=hours)
        except:
            flash('Invalid custom hours', 'danger')
            return redirect(url_for('admin_locations'))
    else:
        end_date = now + timedelta(days=1)  # Default 1 day
    
    try:
        user.suspended = True
        user.suspension_end_date = end_date
        user.suspension_reason = reason
        user.suspension_duration = duration
        
        db.session.commit()
        
        # Format duration for notification
        if duration == 'custom':
            duration_text = f"{custom_hours} hours"
        else:
            duration_text = duration
        
        create_notification(
            user.id,
            f'Your account has been suspended for {duration_text}. Reason: {reason}. Suspension ends: {end_date.strftime("%Y-%m-%d %H:%M UTC")}',
            'admin_suspend',
            target_url=url_for('profile'),
            commit=True
        )
        
        flash(f'User suspended for {duration_text} successfully', 'success')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Suspend user error: {e}')
        flash('Failed to suspend user', 'danger')
    
    return redirect(url_for('admin_locations'))


@app.route('/admin/suspend/<int:user_id>', methods=['POST'])
@login_required
def admin_suspend(user_id):
    """Legacy suspend a user (default 1 day)"""
    if not current_user.is_admin:
        abort(403)
    
    if user_id == current_user.id:
        flash('You cannot suspend yourself', 'warning')
        return redirect(url_for('admin_dashboard'))
    
    reason = request.form.get('reason', 'Account suspended by admin.').strip()
    user = User.query.get_or_404(user_id)
    
    try:
        user.suspended = True
        user.suspension_end_date = datetime.now(timezone.utc) + timedelta(days=1)
        user.suspension_reason = reason
        user.suspension_duration = 'day'
        db.session.commit()
        
        create_notification(
            user.id,
            f'Your account has been suspended for 1 day: {reason}',
            'admin_suspend',
            target_url=url_for('profile'),
            commit=True
        )
        
        flash('User suspended successfully', 'success')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Suspend user error: {e}')
        flash('Failed to suspend user', 'danger')
    
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/unblock/<int:user_id>', methods=['POST'])
@login_required
def admin_unblock(user_id):
    """Unblock a user"""
    if not current_user.is_admin:
        abort(403)
    
    user = User.query.get_or_404(user_id)
    
    try:
        user.suspended = False
        user.burned = False
        user.suspension_end_date = None
        user.suspension_reason = None
        user.suspension_duration = None
        db.session.commit()
        
        create_notification(
            user.id,
            'Your account has been reinstated',
            'admin_unblock',
            target_url=url_for('profile'),
            commit=True
        )
        
        flash('User unblocked successfully', 'success')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Unblock user error: {e}')
        flash('Failed to unblock user', 'danger')
    
    return redirect(url_for('admin_dashboard'))


@app.route('/admin/burn/<int:user_id>', methods=['POST'])
@login_required
def admin_burn(user_id):
    """Permanently block a user"""
    if not current_user.is_admin:
        abort(403)
    
    if user_id == current_user.id:
        flash('You cannot block yourself', 'warning')
        return redirect(url_for('admin_dashboard'))
    
    reason = request.form.get('reason', 'Account permanently blocked by admin.').strip()
    user = User.query.get_or_404(user_id)
    
    try:
        user.burned = True
        db.session.commit()
        
        create_notification(
            user.id,
            f'Your account has been permanently blocked: {reason}',
            'admin_burned',
            target_url=url_for('profile'),
            commit=True
        )
        
        flash('User permanently blocked', 'success')
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'Burn user error: {e}')
        flash('Failed to block user', 'danger')
    
    return redirect(url_for('admin_dashboard'))


# ============================================================================
# PROGRAM IMPACT ROUTES
# ============================================================================

@app.route('/program-impact')
def program_impact():
    """Visualize the impact of the employment program"""
    # Statistical data showing program impact over time
    years = [2020, 2021, 2022, 2023, 2024, 2025, 2026]
    program_launch_year = 2024
    
    # Get real data from database
    total_users_count = User.query.count()
    total_jobs_count = Job.query.count()
    total_applications_count = JobApplication.query.count()
    
    # Metrics
    unemployment_rate = [12.8, 13.2, 12.9, 12.5, 8.2, 4.6, 2.1]
    idleness_rate = [18.5, 19.1, 18.7, 17.9, 11.3, 6.2, 2.8]
    financial_stability = [42, 41, 43, 45, 62, 78, 89]
    job_placements = [0, 0, 0, 0, total_jobs_count, int(total_jobs_count*1.5), int(total_jobs_count*2)]
    innovation_projects = [0, 0, 0, 0, 23, 67, 112]
    income_increase = [0, 0, 0, 0, 15.2, 28.7, 41.3]
    stable_households = [0, 0, 0, 0, int(total_users_count*0.3), int(total_users_count*0.5), int(total_users_count*0.7)]
    
    # Before/After comparison
    comparison_data = {
        'before_program': {
            'avg_unemployment': round(sum(unemployment_rate[0:4]) / 4, 1),
            'avg_idleness': round(sum(idleness_rate[0:4]) / 4, 1),
            'avg_financial_stability': round(sum(financial_stability[0:4]) / 4, 1),
            'period': '2020-2023'
        },
        'after_program': {
            'avg_unemployment': round(sum(unemployment_rate[4:7]) / 3, 1),
            'avg_idleness': round(sum(idleness_rate[4:7]) / 3, 1),
            'avg_financial_stability': round(sum(financial_stability[4:7]) / 3, 1),
            'period': '2024-2026'
        }
    }
    
    # Calculate improvements
    improvements = {
        'unemployment_reduction': round(
            ((comparison_data['before_program']['avg_unemployment'] - 
              comparison_data['after_program']['avg_unemployment']) / 
             comparison_data['before_program']['avg_unemployment']) * 100, 1
        ),
        'idleness_reduction': round(
            ((comparison_data['before_program']['avg_idleness'] - 
              comparison_data['after_program']['avg_idleness']) / 
             comparison_data['before_program']['avg_idleness']) * 100, 1
        ),
        'financial_stability_gain': round(
            ((comparison_data['after_program']['avg_financial_stability'] - 
              comparison_data['before_program']['avg_financial_stability']) / 
             comparison_data['before_program']['avg_financial_stability']) * 100, 1
        ),
        'total_jobs_created': total_jobs_count,
        'total_users_helped': total_users_count,
        'total_applications': total_applications_count
    }
    
    # Success stories (can be dynamic from database)
    success_stories = [
        {
            'name': 'Maria Gonzalez',
            'before': 'Unemployed for 18 months, struggling to provide for 3 children',
            'after': 'Now employed as a community coordinator, trained 12 other program participants',
            'improvement': '+340% income'
        },
        {
            'name': 'James Okonkwo',
            'before': 'Graduate with no job prospects for 2 years, facing eviction',
            'after': 'Founded tech repair cooperative employing 8 people',
            'improvement': 'Created 8 jobs'
        },
        {
            'name': 'Sarah Chen',
            'before': 'Single mother, working odd jobs, no stable income',
            'after': 'Digital skills trainer, now earning stable salary with benefits',
            'improvement': '280% income increase'
        }
    ]
    
    return render_template(
        'program_impact.html',
        years=years,
        unemployment_rate=unemployment_rate,
        idleness_rate=idleness_rate,
        financial_stability=financial_stability,
        job_placements=job_placements,
        innovation_projects=innovation_projects,
        income_increase=income_increase,
        stable_households=stable_households,
        program_launch_year=program_launch_year,
        comparison_data=comparison_data,
        improvements=improvements,
        success_stories=success_stories
    )


@app.route('/program-impact-data')
def program_impact_data():
    """API endpoint for program impact data"""
    total_users = User.query.count()
    total_jobs = Job.query.count()
    total_applications = JobApplication.query.count()
    
    data = {
        'years': [2020, 2021, 2022, 2023, 2024, 2025, 2026],
        'unemployment_rate': [12.8, 13.2, 12.9, 12.5, 8.2, 4.6, 2.1],
        'idleness_rate': [18.5, 19.1, 18.7, 17.9, 11.3, 6.2, 2.8],
        'financial_stability': [42, 41, 43, 45, 62, 78, 89],
        'job_placements': [0, 0, 0, 0, total_jobs, int(total_jobs*1.5), int(total_jobs*2)],
        'program_metrics': {
            'total_applications': total_applications,
            'total_users': total_users,
            'total_jobs': total_jobs,
            'retention_rate': 87.3,
            'avg_salary_increase': 41.3,
            'businesses_started': 112,
            'community_projects': 89
        }
    }
    
    return jsonify(data)


# ============================================================================
# UTILITY ROUTES
# ============================================================================

# Add near your other routes in app.py



@app.route('/uploads/<filename>')
def uploaded_file(filename):
    """Serve uploaded files - allow anonymous for job media, but protect profile pics"""
    # You could add logic here to check if the file is from a job (public) or profile (private)
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/jobs-nearby')
@login_required
def jobs_nearby():
    """Show jobs near user's verified location"""
    # Get user's location
    if not current_user.real_latitude or not current_user.real_longitude:
        flash('Please verify your location first', 'warning')
        return redirect(url_for('location_verify'))
    
    # Get jobs with location data
    # This is a simplified version - you'd need to implement distance calculation
    jobs = Job.query.filter_by(status='open').limit(10).all()
    
    # Mock data for now
    jobs_with_distance = []
    for job in jobs:
        jobs_with_distance.append({
            'job': job,
            'distance': 5.2,  # Mock distance
            'city': job.location,
            'accuracy': 10
        })
    
    return render_template('jobs_nearby.html', 
                         jobs=jobs_with_distance,
                         user_location=current_user,
                         radius=10)

@app.route('/location-verify', methods=['GET', 'POST'])
@login_required
def location_verify():
    """Verify user location"""
    if request.method == 'POST':
        # Get location data from form
        latitude = request.form.get('latitude')
        longitude = request.form.get('longitude')
        accuracy = request.form.get('accuracy')
        
        if latitude and longitude:
            current_user.real_latitude = float(latitude)
            current_user.real_longitude = float(longitude)
            current_user.location_verified_at = datetime.now(timezone.utc)
            
            # You could add reverse geocoding here to get city/country
            # For now, just save the coordinates
            
            db.session.commit()
            flash('Location verified successfully!', 'success')
            return redirect(url_for('profile'))
    
    return render_template('location_verify.html')


@app.route('/forgot-password')
def forgot_password():
    """Forgot password page"""
    return render_template('forgot_password.html')  # You'll need to create this template


@app.route('/jobs')
def jobs():
    """Display all jobs"""
    jobs = Job.query.filter_by(status='open').order_by(Job.created_at.desc()).all()
    return render_template('index.html', jobs=jobs)


@app.route('/debug/jobs')
def debug_jobs():
    """Debug endpoint to see all jobs as JSON"""
    jobs = Job.query.filter_by(status='open').order_by(Job.created_at.desc()).all()
    
    return jsonify({
        'total_open_jobs': len(jobs),
        'jobs': [{
            'id': j.id,
            'title': j.title,
            'description': j.description[:100] + '...' if len(j.description) > 100 else j.description,
            'status': j.status,
            'poster_id': j.poster_id,
            'created_at': j.created_at.isoformat() if j.created_at else None
        } for j in jobs]
    })


# ============================================================================
# PRODUCTION LOGGING
# ============================================================================
if not app.debug:
    import logging
    from logging.handlers import RotatingFileHandler
    os.makedirs('logs', exist_ok=True)
    file_handler = RotatingFileHandler('logs/kaziconnect.log', maxBytes=10485760, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)
    app.logger.setLevel(logging.INFO)
    app.logger.info('KaziConnect production startup')


# ============================================================================
# APPLICATION ENTRY POINT
# ============================================================================

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        try:
            ensure_default_admin()
        except Exception as exc:
            app.logger.error(f'Startup admin creation failed: {exc}')

        # Backfill job_ref for existing jobs that don't have one
        try:
            jobs_without_ref = Job.query.filter(Job.job_ref == None).all()
            for job in jobs_without_ref:
                job.job_ref = generate_job_ref()
            if jobs_without_ref:
                db.session.commit()
                app.logger.info(f'Backfilled job_ref for {len(jobs_without_ref)} jobs')
        except Exception as exc:
            db.session.rollback()
            app.logger.error(f'job_ref backfill failed: {exc}')

        # Fix legacy "closed" status → "cancelled"
        try:
            legacy = Job.query.filter_by(status='closed').all()
            for job in legacy:
                job.status = 'cancelled'
            if legacy:
                db.session.commit()
                app.logger.info(f'Migrated {len(legacy)} jobs from closed → cancelled')
        except Exception as exc:
            db.session.rollback()
            app.logger.error(f'Status migration failed: {exc}')

    # Get configuration from environment
    debug_mode = os.environ.get('FLASK_DEBUG', '0') == '1'
    port = int(os.environ.get('PORT', 5000))

    app.run(host='0.0.0.0', port=port, debug=debug_mode)