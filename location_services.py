#!/usr/bin/env python3
"""
Location Integrity Services
Automatically identifies and verifies user locations with cryptographic verification
"""

import os
import json
import hashlib
import ipaddress
import requests
from datetime import datetime, timedelta
from math import radians, sin, cos, sqrt, atan2
from functools import wraps
from flask import request, jsonify, session, current_app, g
from flask_login import current_user

class LocationIntegrityService:
    """Service for verifying and maintaining location integrity"""
    
    def __init__(self, app=None):
        self.app = app
        self.ip_api_url = "http://ip-api.com/json/"
        self.ip_api_batch_url = "http://ip-api.com/batch"
        self.vpn_detection_api = "https://vpnapi.io/api/"
        self.cache = {}
        
        if app:
            self.init_app(app)
    
    def init_app(self, app):
        """Initialize with Flask app"""
        self.app = app
        self.cache_ttl = app.config.get('LOCATION_CACHE_TTL', 3600)  # 1 hour default
        
        # Register template filters
        app.add_template_filter(self.format_distance, 'distance_format')
        app.add_template_filter(self.get_location_flag, 'location_flag')
        
        # Register context processor
        @app.context_processor
        def inject_location_helpers():
            return {
                'get_user_location': self.get_user_location_data,
                'calculate_distance': self.calculate_distance,
                'location_trust_badge': self.get_trust_badge_html
            }
    
    def get_client_ip(self):
        """Get real client IP address considering proxies"""
        headers_to_check = [
            'X-Forwarded-For',
            'X-Real-IP',
            'CF-Connecting-IP',  # Cloudflare
            'True-Client-IP',     # Akamai
            'X-Cluster-Client-IP'
        ]
        
        for header in headers_to_check:
            if header in request.headers:
                ip = request.headers[header].split(',')[0].strip()
                if self.is_valid_ip(ip):
                    return ip
        
        return request.remote_addr or '0.0.0.0'
    
    def is_valid_ip(self, ip):
        """Validate IP address format"""
        try:
            ipaddress.ip_address(ip)
            return True
        except ValueError:
            return False
    
    def is_vpn_or_proxy(self, ip):
        """Detect if IP is a VPN, proxy, or TOR exit node"""
        try:
            # Check local blacklist first
            from app import LocationBlacklist
            blacklisted = LocationBlacklist.query.filter_by(
                ip_address=ip, 
                is_active=True
            ).first()
            
            if blacklisted:
                return True, blacklisted.threat_type, blacklisted.confidence_score
            
            # Use external API for detection (if configured)
            api_key = current_app.config.get('VPN_DETECTION_API_KEY')
            if api_key:
                response = requests.get(
                    f"{self.vpn_detection_api}{ip}",
                    params={'key': api_key},
                    timeout=5
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get('security', {}).get('vpn') or \
                       data.get('security', {}).get('proxy') or \
                       data.get('security', {}).get('tor'):
                        return True, 'vpn', 95
            
            return False, None, 0
        except Exception as e:
            current_app.logger.error(f"VPN detection error: {e}")
            return False, None, 0
    
    def get_ip_geolocation(self, ip):
        """Get geolocation data from IP address"""
        cache_key = f"ip_geo_{ip}"
        
        # Check cache
        if cache_key in self.cache:
            cached_time, cached_data = self.cache[cache_key]
            if datetime.now().timestamp() - cached_time < self.cache_ttl:
                return cached_data
        
        try:
            # Try batch API first if we have multiple IPs
            response = requests.get(
                f"{self.ip_api_url}{ip}",
                params={'fields': 'status,message,country,regionName,city,lat,lon,isp,org,as,mobile,proxy,hosting'},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('status') == 'success':
                    result = {
                        'ip': ip,
                        'city': data.get('city'),
                        'region': data.get('regionName'),
                        'country': data.get('country'),
                        'latitude': data.get('lat'),
                        'longitude': data.get('lon'),
                        'isp': data.get('isp'),
                        'organization': data.get('org'),
                        'mobile': data.get('mobile', False),
                        'proxy': data.get('proxy', False),
                        'hosting': data.get('hosting', False),
                        'accuracy_radius': 1000  # Default, could be more precise
                    }
                    
                    # Cache the result
                    self.cache[cache_key] = (datetime.now().timestamp(), result)
                    return result
            
            return None
        except Exception as e:
            current_app.logger.error(f"IP geolocation error: {e}")
            return None
    
    def verify_browser_geolocation(self, latitude, longitude, accuracy):
        """Verify and validate browser geolocation data"""
        if not latitude or not longitude:
            return None, "No location data provided"
        
        try:
            lat = float(latitude)
            lng = float(longitude)
            acc = float(accuracy) if accuracy else 1000
            
            # Validate coordinates
            if lat < -90 or lat > 90 or lng < -180 or lng > 180:
                return None, "Invalid coordinates"
            
            # Check if location is plausible (not in ocean, etc.)
            if not self.is_plausible_location(lat, lng):
                return None, "Location appears to be invalid"
            
            return {
                'latitude': lat,
                'longitude': lng,
                'accuracy': acc,
                'timestamp': datetime.now(timezone.utc).isoformat()
            }, None
            
        except (ValueError, TypeError) as e:
            return None, f"Invalid location format: {str(e)}"
    
    def is_plausible_location(self, lat, lng):
        """Basic sanity check for coordinates"""
        # Check if in middle of ocean (simplified)
        # You could integrate with reverse geocoding API for more accuracy
        
        # Rough bounding boxes for major land masses
        plausible_areas = [
            (-60, -180, 90, 180),  # Whole world for now
        ]
        
        for min_lat, min_lng, max_lat, max_lng in plausible_areas:
            if min_lat <= lat <= max_lat and min_lng <= lng <= max_lng:
                return True
        
        return False
    
    def create_location_verification(self, user_id, browser_location=None):
        """Create a cryptographically verified location record"""
        from app import LocationVerification, db
        
        # Get IP data
        ip = self.get_client_ip()
        ip_data = self.get_ip_geolocation(ip)
        
        # Check for VPN/proxy
        is_vpn, vpn_type, vpn_score = self.is_vpn_or_proxy(ip)
        
        # Create verification record
        verification = LocationVerification(
            user_id=user_id,
            ip_address=ip,
            ip_location_city=ip_data.get('city') if ip_data else None,
            ip_location_region=ip_data.get('region') if ip_data else None,
            ip_location_country=ip_data.get('country') if ip_data else None,
            ip_latitude=ip_data.get('latitude') if ip_data else None,
            ip_longitude=ip_data.get('longitude') if ip_data else None,
            ip_accuracy_radius=ip_data.get('accuracy_radius') if ip_data else None,
            isp=ip_data.get('isp') if ip_data else None,
            connection_type='mobile' if ip_data and ip_data.get('mobile') else 'broadband',
            expires_at=datetime.now(timezone.utc) + timedelta(days=30)
        )
        
        # Add browser location if provided
        if browser_location:
            verification.browser_latitude = browser_location.get('latitude')
            verification.browser_longitude = browser_location.get('longitude')
            verification.browser_accuracy = browser_location.get('accuracy')
            verification.browser_timestamp = datetime.fromisoformat(
                browser_location.get('timestamp', datetime.now(timezone.utc).isoformat())
            )
            verification.verification_method = 'both' if ip_data else 'browser'
        else:
            verification.verification_method = 'ip' if ip_data else 'admin'
        
        # Calculate trust score
        verification.calculate_trust_score()
        
        # Generate cryptographic hash
        verification.generate_verification_hash()
        
        # Save to database
        db.session.add(verification)
        db.session.commit()
        
        return verification
    
    def verify_job_location(self, job_id, location_verification_id, latitude, longitude, address_data=None):
        """Verify and store job posting location"""
        from app import VerifiedJobLocation, db
        
        verified_location = VerifiedJobLocation(
            job_id=job_id,
            location_verification_id=location_verification_id,
            latitude=latitude,
            longitude=longitude,
            formatted_address=address_data.get('formatted_address') if address_data else None,
            city=address_data.get('city') if address_data else None,
            region=address_data.get('region') if address_data else None,
            country=address_data.get('country') if address_data else None,
            postal_code=address_data.get('postal_code') if address_data else None,
            verified_by='browser' if request.form.get('browser_location') else 'ip'
        )
        
        db.session.add(verified_location)
        db.session.commit()
        
        return verified_location
    
    def verify_application_location(self, application_id, job_location, user_verification):
        """Verify and store applicant location with distance calculation"""
        from app import VerifiedApplicationLocation, db
        
        # Calculate distance to job
        distance = self.calculate_distance(
            user_verification.browser_latitude or user_verification.ip_latitude,
            user_verification.browser_longitude or user_verification.ip_longitude,
            job_location.latitude,
            job_location.longitude
        )
        
        verified_app_location = VerifiedApplicationLocation(
            application_id=application_id,
            location_verification_id=user_verification.id,
            latitude=user_verification.browser_latitude or user_verification.ip_latitude,
            longitude=user_verification.browser_longitude or user_verification.ip_longitude,
            city=user_verification.ip_location_city,
            region=user_verification.ip_location_region,
            country=user_verification.ip_location_country,
            applied_from_ip=user_verification.ip_address,
            distance_to_job_km=distance
        )
        
        db.session.add(verified_app_location)
        db.session.commit()
        
        return verified_app_location
    
    def calculate_distance(self, lat1, lon1, lat2, lon2):
        """Calculate distance between two points in kilometers"""
        if not all([lat1, lon1, lat2, lon2]):
            return None
            
        R = 6371  # Earth's radius in kilometers
        
        lat1, lon1 = radians(float(lat1)), radians(float(lon1))
        lat2, lon2 = radians(float(lat2)), radians(float(lon2))
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        
        return round(R * c, 2)
    
    def get_user_location_data(self, user_id=None):
        """Get current location data for a user"""
        from app import LocationVerification
        
        if user_id is None and current_user.is_authenticated:
            user_id = current_user.id
        
        if not user_id:
            return None
        
        # Get most recent active verification
        verification = LocationVerification.query.filter_by(
            user_id=user_id,
            is_active=True
        ).order_by(LocationVerification.created_at.desc()).first()
        
        if not verification:
            return None
        
        return {
            'city': verification.ip_location_city,
            'region': verification.ip_location_region,
            'country': verification.ip_location_country,
            'latitude': verification.browser_latitude or verification.ip_latitude,
            'longitude': verification.browser_longitude or verification.ip_longitude,
            'accuracy': verification.browser_accuracy or verification.ip_accuracy_radius,
            'trust_score': verification.trust_score,
            'verified_at': verification.created_at,
            'verification_hash': verification.verification_hash[:16] + '...',
            'method': verification.verification_method
        }
    
    def get_jobs_near_location(self, latitude, longitude, radius_km=50, limit=50):
        """Find jobs within radius of a location"""
        from app import VerifiedJobLocation, Job
        from sqlalchemy import func
        
        # Haversine formula in SQLite
        if 'sqlite' in current_app.config['SQLALCHEMY_DATABASE_URI']:
            # Simplified for SQLite - you might want to use a spatialite extension
            jobs = VerifiedJobLocation.query.join(Job).filter(
                Job.status == 'open',
                VerifiedJobLocation.latitude.between(latitude - 0.5, latitude + 0.5),
                VerifiedJobLocation.longitude.between(longitude - 0.5, longitude + 0.5)
            ).limit(limit).all()
        else:
            # PostgreSQL with PostGIS would be more accurate
            jobs = VerifiedJobLocation.query.join(Job).filter(
                Job.status == 'open',
                func.ST_DWithin(
                    func.ST_MakePoint(VerifiedJobLocation.longitude, VerifiedJobLocation.latitude),
                    func.ST_MakePoint(longitude, latitude),
                    radius_km * 1000
                )
            ).limit(limit).all()
        
        return jobs
    
    def format_distance(self, distance_km):
        """Format distance for display"""
        if distance_km is None:
            return "Unknown distance"
        
        if distance_km < 1:
            return f"{int(distance_km * 1000)} meters away"
        elif distance_km < 10:
            return f"{round(distance_km, 1)} km away"
        else:
            return f"{int(distance_km)} km away"
    
    def get_location_flag(self, country_code):
        """Get emoji flag for country"""
        if not country_code:
            return "🌍"
        
        # Convert country code to regional indicator symbols
        return ''.join(chr(ord(c) + 127397) for c in country_code.upper())
    
    def get_trust_badge_html(self, trust_score):
        """Generate HTML for trust badge"""
        if trust_score >= 80:
            return '<span class="trust-badge trust-high" title="Highly Verified Location"><i class="bi bi-shield-fill-check"></i> Verified</span>'
        elif trust_score >= 50:
            return '<span class="trust-badge trust-medium" title="Partially Verified Location"><i class="bi bi-shield-check"></i> Partially Verified</span>'
        else:
            return '<span class="trust-badge trust-low" title="Unverified Location"><i class="bi bi-shield-exclamation"></i> Unverified</span>'

# Create global instance
location_service = LocationIntegrityService()

def require_location_verification(max_age_days=30):
    """Decorator to require verified location"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                return jsonify({'error': 'Authentication required'}), 401
            
            from app import LocationVerification
            
            verification = LocationVerification.query.filter_by(
                user_id=current_user.id,
                is_active=True
            ).order_by(LocationVerification.created_at.desc()).first()
            
            if not verification:
                flash('Please verify your location to continue', 'warning')
                return redirect(url_for('location.verify'))
            
            # Check if expired
            if verification.expires_at and verification.expires_at < datetime.now(timezone.utc):
                verification.is_active = False
                db.session.commit()
                flash('Your location verification has expired. Please verify again.', 'warning')
                return redirect(url_for('location.verify'))
            
            # Check trust score threshold
            if verification.trust_score < 30:
                flash('Your location could not be verified. Please try again.', 'warning')
                return redirect(url_for('location.verify'))
            
            g.user_location = verification
            return f(*args, **kwargs)
        return decorated_function
    return decorator
