from flask import Blueprint, request, jsonify, redirect, url_for, session
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, decode_token
from app import db
from models import User, CoinWallet, Garden, Seed, StravaAccount
from strava_service import strava_service
from datetime import datetime, timezone, timedelta
import re
import os
import requests
from urllib.parse import urlencode

auth_bp = Blueprint('auth', __name__)

def validate_email(email):
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None

def validate_password(password):
    return len(password) >= 8

@auth_bp.route('/register', methods=['POST'])
def register():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        email = data.get('email', '').lower().strip()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        # Validation
        if not email or not username or not password:
            return jsonify({'error': 'Email, username, and password are required'}), 400
        
        if not validate_email(email):
            return jsonify({'error': 'Invalid email format'}), 400
        
        if not validate_password(password):
            return jsonify({'error': 'Password must be at least 8 characters long'}), 400
        
        if len(username) < 3 or len(username) > 64:
            return jsonify({'error': 'Username must be between 3 and 64 characters'}), 400
        
        # Check if user already exists
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already registered'}), 409
        
        if User.query.filter_by(username=username).first():
            return jsonify({'error': 'Username already taken'}), 409
        
        # Create new user
        user = User()
        user.email = email
        user.username = username
        user.set_password(password)
        
        db.session.add(user)
        db.session.flush()  # Get user ID
        
        # Create coin wallet
        wallet = CoinWallet()
        wallet.user_id = user.id
        db.session.add(wallet)
        
        # Create garden
        garden = Garden()
        garden.user_id = user.id
        db.session.add(garden)
        
        db.session.commit()
        
        # Create access token
        access_token = create_access_token(identity=str(user.id))
        
        return jsonify({
            'message': 'User registered successfully',
            'access_token': access_token,
            'user': user.to_dict()
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Registration failed: {str(e)}'}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({'error': 'No data provided'}), 400
        
        email = data.get('email', '').lower().strip()
        password = data.get('password', '')
        
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
        
        # Find user
        user = User.query.filter_by(email=email).first()
        
        if not user or not user.check_password(password):
            return jsonify({'error': 'Invalid email or password'}), 401
        
        if not user.is_active:
            return jsonify({'error': 'Account is deactivated'}), 401
        
        # Create access token
        access_token = create_access_token(identity=str(user.id))
        
        return jsonify({
            'message': 'Login successful',
            'access_token': access_token,
            'user': user.to_dict()
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Login failed: {str(e)}'}), 500

@auth_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    try:
        user_id = get_jwt_identity()
        user = User.query.get(user_id)
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        return jsonify({'user': user.to_dict()}), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to get profile: {str(e)}'}), 500

@auth_bp.route('/strava/connect', methods=['GET'])
@jwt_required()
def connect_strava():
    """Initiate Strava OAuth connection"""
    try:
        user_id = get_jwt_identity()
        user_id_str = str(user_id)
        print(f"[STRAVA] User ID: {user_id_str}, Type: {type(user_id_str)}")  # Debug

       # Create a short-lived state token
        state_token = create_access_token(identity=user_id_str, expires_delta=False)  # Optional: Add expiry

        params = {
            'client_id': '167433',
            'response_type': 'code',
            'redirect_uri': 'https://runmysticgarden-public-1.onrender.com/auth/strava/callback',
            'approval_prompt': 'auto',
            'scope': 'activity:read_all',
            'state': state_token
        }

        # Generate authorization URL
        auth_url = f"https://www.strava.com/oauth/authorize?{urlencode(params)}"
        print(f"[STRAVA] Generated OAuth URL: {auth_url}") # for debugging
        
        return jsonify({
            'authorization_url': auth_url,
            'message': 'Visit the authorization URL to connect your Strava account'
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to initiate Strava connection: {str(e)}'}), 500

@auth_bp.route('/strava/callback', methods=['GET'])
def strava_callback():
    """Handle Strava OAuth callback"""
    try:
        code = request.args.get('code')
        print(f'Code to get tokens {code}')
        error = request.args.get('error')
        state_token = request.args.get('state')
        
        if error:
            return jsonify({'error': f'Strava authorization failed: {error}'}), 400
        
        if not code:
            return jsonify({'error': 'No authorization code received'}), 400
        
        # Decode JWT to extract user_id
        decoded = decode_token(state_token)
        user_id = decoded.get('sub')  # 'sub' is standard for user identity
        
        user = User.query.get(user_id)

        if not user_id:
            return redirect('https://runmysticgarden-public-1.onrender.com/error?message=Missing+user+session')
        
        # Validate user exists
        user = User.query.get(user_id)
        if not user:
            return redirect(f'https://runmysticgarden-public-1.onrender.com/error?message=Invalid+user+ID')
        
        # Exchange code for tokens
        url = 'https://www.strava.com/oauth/token'
        payload = {
            'client_id':'167433',
            'client_secret':'15e7b8ff9efa35ec7e4d770d7161b3ae7b52f526',
            'code':code,
            'grant_type':'authorization_code',
            'redirect_uri': 'https://runmysticgarden-public-1.onrender.com/auth/strava/callback'
        }

        response = requests.post(url, data=payload)
        response.raise_for_status()
        token_data = response.json()

        print(f"[STRAVA] OAuth Success - Access Token: {token_data.get('access_token')}, User ID: {user_id}")

        # user_id = get_jwt_identity()
        strava_account = StravaAccount.query.filter_by(user_id=user_id).first()
        if strava_account:
            strava_account.access_token = token_data['access_token']
            strava_account.refresh_token = token_data['refresh_token']
            strava_account.expires_at = datetime.fromtimestamp(token_data['expires_at'], timezone.utc)
            strava_account.strava_athlete_id = token_data['athlete']['id']
            strava_account.athlete_firstname = token_data['athlete'].get('firstname')
            strava_account.athlete_lastname = token_data['athlete'].get('lastname')
            strava_account.athlete_city = token_data['athlete'].get('city')
            strava_account.athlete_country = token_data['athlete'].get('country')
            strava_account.athlete_profile_picture = token_data['athlete'].get('profile')
            strava_account.is_active = True
        else:
            strava_account = StravaAccount(
                user_id=user_id,
                strava_athlete_id=token_data['athlete']['id'],
                access_token=token_data['access_token'],
                refresh_token=token_data['refresh_token'],
                expires_at=datetime.fromtimestamp(token_data['expires_at'], timezone.utc),
                athlete_firstname=token_data['athlete'].get('firstname'),
                athlete_lastname=token_data['athlete'].get('lastname'),
                athlete_city=token_data['athlete'].get('city'),
                athlete_country=token_data['athlete'].get('country'),
                athlete_profile_picture=token_data['athlete'].get('profile'),
                is_active=True
            )
            db.session.add(strava_account)
        db.session.commit()

        session.pop('strava_user_id', None)

        return jsonify({
            'message': 'Strava connection successful! Your account has now been linked (token and account is stored in database)',
            'access_token': token_data.get('access_token'),
            'refresh_token': token_data.get('refresh_token'),
            'instructions': 'Use /strava/activites endpoint to access activities / Navigate back to the app to sync your activities.'
        }), 200
        
    except requests.exceptions.HTTPError as http_err:
        return jsonify({'error': f'Strava token exchange failed: {http_err}', 'response': response.text}), 400
    except Exception as e:
        return jsonify({'error': f'Failed to process Strava callback: {str(e)}'}), 500

def refresh_strava_token(strava_account):
    try:
        if not strava_account.is_token_expired():
            print(f"[STRAVA] Token still valid until {strava_account.expires_at}")
            return strava_account.access_token

        print(f"[STRAVA] Refreshing token for athlete {strava_account.strava_athlete_id}")
        url = 'https://www.strava.com/oauth/token'
        payload = {
            'client_id': os.getenv('STRAVA_CLIENT_ID', '167433'),
            'client_secret': os.getenv('STRAVA_CLIENT_SECRET', '15e7b8ff9efa35ec7e4d770d7161b3ae7b52f526'),
            'grant_type': 'refresh_token',
            'refresh_token': strava_account.refresh_token
        }

        response = requests.post(url, data=payload)
        response.raise_for_status()
        token_data = response.json()

        strava_account.access_token = token_data['access_token']
        strava_account.refresh_token = token_data['refresh_token']
        strava_account.expires_at = datetime.fromtimestamp(token_data['expires_at'])
        db.session.commit()

        print(f"[STRAVA] Token refreshed - New Access Token: {token_data['access_token']}")
        return token_data['access_token']
    except requests.exceptions.HTTPError as http_err:
        print(f"[STRAVA] Token refresh failed: {http_err}")
        raise

'''
@auth_bp.route('/strava/activities', methods=['GET'])
@jwt_required()
def get_strava_activities():
    try:
        user_id = get_jwt_identity()
        strava_account = StravaAccount.query.filter_by(user_id=user_id, is_active=True).first()
        if not strava_account:
            return jsonify({'error': 'Strava account not linked'}), 400

        access_token = refresh_strava_token(strava_account)

        headers = {'Authorization': f'Bearer {access_token}'}
        response = requests.get('https://www.strava.com/api/v3/athlete/activities', headers=headers)
        response.raise_for_status()
        activities = response.json()

        strava_account.last_sync = datetime.now(timezone.utc)
        db.session.commit()

        return jsonify({'activities': activities}), 200
    except requests.exceptions.HTTPError as http_err:
        return jsonify({'error': f'Strava API request failed: {http_err}'}), 400
    except Exception as e:
        return jsonify({'error': f'Failed to fetch activities: {str(e)}'}), 500
'''

@auth_bp.route('/strava/activities', methods=['POST'])
@jwt_required()
def get_strava_activities():
    try:
        user_id = get_jwt_identity()
        strava_account = StravaAccount.query.filter_by(user_id=user_id, is_active=True).first()
        if not strava_account:
            return jsonify({'error': 'Strava account not linked'}), 400

        # Get optional 'days_back' from request body, default to 7
        data = request.get_json() or {}
        days_back = int(data.get('days_back', 7))

        access_token = refresh_strava_token(strava_account)

        headers = {'Authorization': f'Bearer {access_token}'}
        
        # Filter by date (using `after` parameter in epoch time)
        after_timestamp = int((datetime.now(timezone.utc) - timedelta(days=days_back)).timestamp())

        response = requests.get(
            'https://www.strava.com/api/v3/athlete/activities',
            headers=headers,
            params={'after': after_timestamp}
        )
        response.raise_for_status()
        activities = response.json()

        strava_account.last_sync = datetime.now(timezone.utc)
        db.session.commit()

        return jsonify({'activities': activities}), 200
    except requests.exceptions.HTTPError as http_err:
        return jsonify({'error': f'Strava API request failed: {http_err}'}), 400
    except Exception as e:
        return jsonify({'error': f'Failed to fetch activities: {str(e)}'}), 500
    
    
@auth_bp.route('/strava/disconnect', methods=['POST'])
@jwt_required()
def disconnect_strava():
    """Disconnect Strava account"""
    try:
        user_id = get_jwt_identity()
        
        strava_account = StravaAccount.query.filter_by(
            user_id=user_id,
            is_active=True
        ).first()
        
        if not strava_account:
            return jsonify({'error': 'No Strava account connected'}), 404
        
        # Deactivate the account instead of deleting to preserve history
        strava_account.is_active = False
        db.session.commit()
        
        return jsonify({'message': 'Strava account disconnected successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Failed to disconnect Strava account: {str(e)}'}), 500

@auth_bp.route('/strava/status', methods=['GET'])
@jwt_required()
def strava_status():
    """Get Strava connection status"""
    try:
        user_id = get_jwt_identity()
        
        strava_account = StravaAccount.query.filter_by(
            user_id=user_id,
            is_active=True
        ).first()
        
        if not strava_account:
            return jsonify({
                'connected': False,
                'message': 'No Strava account connected'
            }), 200
        
        return jsonify({
            'connected': True,
            'strava_account': strava_account.to_dict(),
            'token_expired': strava_account.is_token_expired()
        }), 200
        
    except Exception as e:
        return jsonify({'error': f'Failed to get Strava status: {str(e)}'}), 500
