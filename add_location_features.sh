#!/bin/bash
# add_location_features.sh - Add location integrity with NO API KEYS required

echo "📍 Adding location integrity features (NO API KEYS required)..."

# 1. ADD LOCATION VERIFICATION MODEL
cat >> app.py << 'MODELS_EOF'

# ============================================================================
# LOCATION VERIFICATION MODELS - NO API KEYS, BROWSER GPS ONLY
# ============================================================================

class LocationVerification(db.Model):
    """Track verified locations with cryptographic integrity - BROWSER GPS ONLY"""
    __tablename__ = 'location_verifications'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    # IP address only for tracking, not geolocation
    ip_address = db.Column(db.String(45), nullable=False)
    
    # Browser geolocation (ONLY source of truth)
    browser_latitude = db.Column(db.Float)
    browser_longitude = db.Column(db.Float)
    browser_accuracy = db.Column(db.Float)  # in meters
    browser_timestamp = db.Column(db.DateTime)
    
    # Reverse geocoded address (from OpenStreetMap - FREE)
    formatted_address = db.Column(db.String(500))
    city = db.Column(db.String(100))
    region = db.Column(db.String(100))
    country = db.Column(db.String(100))
    postal_code = db.Column(db.String(20))
    
    # Cryptographic verification hash
    verification_hash = db.Column(db.String(128), unique=True)
    verification_method = db.Column(db.String(50), default='browser')
    
    # Trust score (0-100) - based on accuracy only
    trust_score = db.Column(db.Integer, default=0)
    
    # Metadata
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    user = db.relationship('User', backref='location_verifications')
    
    def calculate_trust_score(self):
        """Calculate trust score based on browser accuracy only"""
        score = 0
        if self.browser_latitude and self.browser_longitude:
            score += 50
            if self.browser_accuracy:
                if self.browser_accuracy < 20:
                    score += 50
                elif self.browser_accuracy < 50:
                    score += 40
                elif self.browser_accuracy < 100:
                    score += 30
                elif self.browser_accuracy < 500:
                    score += 20
                else:
                    score += 10
        self.trust_score = min(score, 100)
        return self.trust_score
    
    def generate_verification_hash(self):
        """Generate cryptographic hash for location verification"""
        data = {
            'user_id': self.user_id,
            'ip': self.ip_address,
            'lat': self.browser_latitude,
            'lng': self.browser_longitude,
            'timestamp': str(self.created_at)
        }
        hash_string = json.dumps(data, sort_keys=True)
        self.verification_hash = hashlib.sha256(
            (hash_string + app.config['SECRET_KEY']).encode()
        ).hexdigest()
        return self.verification_hash


class VerifiedJobLocation(db.Model):
    """Job postings with verified location"""
    __tablename__ = 'verified_job_locations'
    
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('jobs.id'), nullable=False, unique=True, index=True)
    location_verification_id = db.Column(db.Integer, db.ForeignKey('location_verifications.id'), nullable=False)
    
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    accuracy = db.Column(db.Float)
    
    formatted_address = db.Column(db.String(500))
    city = db.Column(db.String(100))
    region = db.Column(db.String(100))
    country = db.Column(db.String(100))
    postal_code = db.Column(db.String(20))
    
    verification_timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    verified_by = db.Column(db.String(50), default='browser')
    is_remote_work = db.Column(db.Boolean, default=False)
    
    job = db.relationship('Job', backref='verified_location')
    verification = db.relationship('LocationVerification', backref='verified_jobs')
    
    def distance_to(self, lat, lng):
        """Calculate distance to another location in kilometers"""
        R = 6371
        lat1, lon1 = radians(self.latitude), radians(self.longitude)
        lat2, lon2 = radians(lat), radians(lng)
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        return R * c


class VerifiedApplicationLocation(db.Model):
    """Job applications with verified applicant location"""
    __tablename__ = 'verified_application_locations'
    
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('job_applications.id'), nullable=False, unique=True, index=True)
    location_verification_id = db.Column(db.Integer, db.ForeignKey('location_verifications.id'), nullable=False)
    
    latitude = db.Column(db.Float, nullable=False)
    longitude = db.Column(db.Float, nullable=False)
    accuracy = db.Column(db.Float)
    
    formatted_address = db.Column(db.String(500))
    city = db.Column(db.String(100))
    region = db.Column(db.String(100))
    country = db.Column(db.String(100))
    
    applied_from_ip = db.Column(db.String(45))
    applied_at_timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    
    distance_to_job_km = db.Column(db.Float)
    
    application = db.relationship('JobApplication', backref='verified_location')
    verification = db.relationship('LocationVerification', backref='verified_applications')

MODELS_EOF

# 2. ADD LOCATION SERVICE
cat >> app.py << 'SERVICE_EOF'

# ============================================================================
# LOCATION INTEGRITY SERVICE - BROWSER GPS ONLY, NO API KEYS
# ============================================================================

class LocationIntegrityService:
    """Service for verifying location - BROWSER GEOLOCATION ONLY"""
    
    def __init__(self, app=None):
        self.app = app
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        self.app = app
    
    def get_client_ip(self):
        """Get real client IP address considering proxies"""
        headers_to_check = [
            'X-Forwarded-For', 'X-Real-IP', 'CF-Connecting-IP',
            'True-Client-IP', 'X-Cluster-Client-IP'
        ]
        for header in headers_to_check:
            if header in request.headers:
                ip = request.headers[header].split(',')[0].strip()
                return ip
        return request.remote_addr or '0.0.0.0'
    
    def reverse_geocode(self, lat, lng):
        """Get address from coordinates using OpenStreetMap - FREE, NO API KEY"""
        try:
            url = "https://nominatim.openstreetmap.org/reverse"
            params = {
                'lat': lat,
                'lon': lng,
                'format': 'json',
                'addressdetails': 1
            }
            headers = {
                'User-Agent': 'KaziConnect/1.0 (employment platform)'
            }
            response = requests.get(url, params=params, headers=headers, timeout=5)
            if response.status_code == 200:
                data = response.json()
                address = data.get('address', {})
                return {
                    'formatted_address': data.get('display_name', ''),
                    'city': address.get('city') or address.get('town') or address.get('village', ''),
                    'region': address.get('state') or address.get('region', ''),
                    'country': address.get('country', ''),
                    'postal_code': address.get('postcode', '')
                }
            return None
        except Exception as e:
            print(f"Reverse geocoding error: {e}")
            return None
    
    def create_location_verification(self, user_id, browser_location):
        """Create a cryptographically verified location record"""
        if not browser_location:
            return None
        
        ip = self.get_client_ip()
        address_data = browser_location.get('address', {})
        
        verification = LocationVerification(
            user_id=user_id,
            ip_address=ip,
            browser_latitude=browser_location.get('latitude'),
            browser_longitude=browser_location.get('longitude'),
            browser_accuracy=browser_location.get('accuracy'),
            browser_timestamp=datetime.now(timezone.utc),
            formatted_address=address_data.get('formatted_address'),
            city=address_data.get('city'),
            region=address_data.get('region'),
            country=address_data.get('country'),
            postal_code=address_data.get('postal_code'),
            verification_method='browser',
            expires_at=datetime.now(timezone.utc) + timedelta(days=30)
        )
        
        verification.calculate_trust_score()
        verification.generate_verification_hash()
        
        db.session.add(verification)
        db.session.commit()
        return verification
    
    def get_user_location_data(self, user_id=None):
        """Get current location data for a user"""
        if user_id is None and current_user.is_authenticated:
            user_id = current_user.id
        if not user_id:
            return None
        
        verification = LocationVerification.query.filter_by(
            user_id=user_id,
            is_active=True
        ).order_by(LocationVerification.created_at.desc()).first()
        
        if not verification:
            return None
        
        return {
            'city': verification.city,
            'region': verification.region,
            'country': verification.country,
            'latitude': verification.browser_latitude,
            'longitude': verification.browser_longitude,
            'accuracy': verification.browser_accuracy,
            'trust_score': verification.trust_score,
            'verified_at': verification.created_at,
            'address': verification.formatted_address
        }


# Create location service instance
location_service = LocationIntegrityService()
location_service.init_app(app)

SERVICE_EOF

# 3. ADD LOCATION VERIFICATION ROUTES
cat >> app.py << 'ROUTES_EOF'

# ============================================================================
# LOCATION VERIFICATION ROUTES
# ============================================================================

@app.route('/verify-location', methods=['GET', 'POST'])
@login_required
def verify_location():
    """Verify user location with browser GPS"""
    if request.method == 'POST':
        browser_lat = request.form.get('latitude')
        browser_lng = request.form.get('longitude')
        browser_accuracy = request.form.get('accuracy')
        
        if browser_lat and browser_lng:
            # Get address from OpenStreetMap
            address_data = location_service.reverse_geocode(
                float(browser_lat), float(browser_lng)
            )
            
            browser_location = {
                'latitude': float(browser_lat),
                'longitude': float(browser_lng),
                'accuracy': float(browser_accuracy) if browser_accuracy else 1000,
                'address': address_data
            }
            
            verification = location_service.create_location_verification(
                current_user.id,
                browser_location
            )
            
            if verification:
                accuracy_text = f"{verification.browser_accuracy:.0f} meters" if verification.browser_accuracy else "Unknown"
                flash(f'✅ Location verified! Accuracy: {accuracy_text}, Trust score: {verification.trust_score}%', 'success')
                return redirect(url_for('profile'))
            else:
                flash('❌ Could not verify your location. Please try again.', 'danger')
        else:
            flash('❌ No location data received. Please allow location access.', 'warning')
    
    current_verification = LocationVerification.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).order_by(LocationVerification.created_at.desc()).first()
    
    return render_template('location_verify.html', verification=current_verification)


@app.route('/jobs-nearby')
@login_required
def jobs_nearby():
    """Find jobs near user's verified location"""
    radius = request.args.get('radius', 50, type=int)
    
    verification = LocationVerification.query.filter_by(
        user_id=current_user.id,
        is_active=True
    ).order_by(LocationVerification.created_at.desc()).first()
    
    if not verification or not verification.browser_latitude:
        flash('Please verify your location first', 'warning')
        return redirect(url_for('verify_location'))
    
    # Simple bounding box filter
    lat_range = radius / 111.0
    lng_range = radius / (111.0 * abs(cos(radians(verification.browser_latitude))))
    
    jobs = VerifiedJobLocation.query.join(Job).filter(
        Job.status == 'open',
        VerifiedJobLocation.latitude.between(
            verification.browser_latitude - lat_range,
            verification.browser_latitude + lat_range
        ),
        VerifiedJobLocation.longitude.between(
            verification.browser_longitude - lng_range,
            verification.browser_longitude + lng_range
        )
    ).all()
    
    # Calculate distances
    for job_loc in jobs:
        job_loc.distance = job_loc.distance_to(
            verification.browser_latitude,
            verification.browser_longitude
        )
    
    jobs.sort(key=lambda x: x.distance)
    
    user_location = {
        'city': verification.city,
        'region': verification.region,
        'country': verification.country,
        'latitude': verification.browser_latitude,
        'longitude': verification.browser_longitude,
        'accuracy': verification.browser_accuracy,
        'trust_score': verification.trust_score
    }
    
    return render_template('jobs_nearby.html', jobs=jobs, user_location=user_location, radius=radius)

ROUTES_EOF

# 4. ADD CONTEXT PROCESSOR HELPERS
cat >> app.py << 'CONTEXT_EOF'

# ============================================================================
# TEMPLATE CONTEXT PROCESSORS
# ============================================================================

@app.context_processor
def inject_template_helpers():
    """Inject helper functions into templates"""
    return {
        "now": lambda: datetime.now(timezone.utc),
        "csrf_token": generate_csrf,
        "program_launch_year": Config.PROGRAM_LAUNCH_YEAR,
        "is_active": lambda path: "active" if request.path == path else "",
        "app_version": "2.0.0",
        "get_user_location": lambda: location_service.get_user_location_data() if current_user.is_authenticated else None,
        "location_service": location_service
    }

CONTEXT_EOF

echo ""
echo "✅ SUCCESS! Location integrity features added with ZERO API KEYS!"
echo ""
echo "📌 Next steps:"
echo "   1. Copy your existing User, Job, etc. models into app.py"
echo "   2. Run: flask db migrate -m 'Add location verification'"
echo "   3. Run: flask db upgrade"
echo "   4. Run: flask run"
echo ""

