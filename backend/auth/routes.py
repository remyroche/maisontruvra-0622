import logging

from flask import Blueprint, current_app, g, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    create_refresh_token,
    get_jwt_identity,
    jwt_required,
)
from flask_login import current_user, login_required, login_user, logout_user
from marshmallow import ValidationError

from backend.schemas import (
    MfaVerificationSchema,
    PasswordResetConfirmSchema,
    ResetPasswordSchema,
    User,
    UserRegistrationSchema,
    UserSchema,
)
from backend.services.auth_service import AuthService
from backend.services.exceptions import InvalidCredentialsError
from backend.utils.decorators import api_resource_handler
from backend.utils.rate_limiter import limiter

from ..services.exceptions import (
    NotFoundException,
    UnauthorizedException,
)

auth_service = AuthService()
user_schema = UserSchema()
user_registration_schema = UserRegistrationSchema()

auth_bp = Blueprint("auth_bp", __name__, url_prefix="/api/auth")
security_logger = logging.getLogger("security")


@auth_bp.route("/login/verify-mfa", methods=["POST"])
@limiter.limit(limit=5, per=60)  # 5 requests per minute
def verify_mfa():
    """Verifies the MFA token and returns JWTs upon success."""
    json_data = request.get_json()
    if not json_data:
        return jsonify(error="Invalid JSON data provided."), 400

    # Validate input using marshmallow schema
    try:
        schema = MfaVerificationSchema()
        validated_data = schema.load(json_data)
    except ValidationError as err:
        return jsonify(error="Validation failed.", errors=err.messages), 400

    user_id = validated_data["user_id"]
    mfa_token = validated_data["mfa_token"]

    try:
        if AuthService.verify_mfa_login(user_id, mfa_token):
            access_token = create_access_token(identity=user_id)
            refresh_token = create_refresh_token(identity=user_id)
            return jsonify(access_token=access_token, refresh_token=refresh_token), 200
        else:
            raise UnauthorizedException("Invalid MFA token.")
    except (UnauthorizedException, NotFoundException) as e:
        security_logger.warning(
            f"Failed MFA attempt for user_id: {user_id} from IP: {request.remote_addr}"
        )
        return jsonify(error=str(e)), 401
    except Exception as e:
        security_logger.error(f"MFA verification error: {str(e)}")
        return jsonify(error="An internal server error occurred."), 500


@auth_bp.route("/register", methods=["POST"])
@limiter.limit("10 per minute")
@api_resource_handler(
    model=User,
    request_schema=UserRegistrationSchema,
    response_schema=UserSchema,
    log_action=True,
)
def register():
    """
    Registers a new user.
    The decorator handles input validation, database session management,
    and serializing the new user object in the response.
    """
    new_user = AuthService.register_user(g.validated_data)
    # The decorator will commit the session and serialize the returned user.
    return new_user


@auth_bp.route("/login", methods=["POST"])
@limiter.limit("10 per minute")
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    auth_service = AuthService()
    try:
        user = auth_service.authenticate_user(email, password)
        login_user(user)
        user_data = {
            "id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
        }
        return jsonify({"message": "Logged in successfully.", "user": user_data}), 200
    except InvalidCredentialsError as e:
        return jsonify({"error": str(e)}), 401
    except Exception as e:
        current_app.logger.error(f"Error during login: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred."}), 500


@auth_bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return jsonify({"message": "Logged out successfully."}), 200


@auth_bp.route("/status", methods=["GET"])
def status():
    if current_user.is_authenticated:
        user_data = {
            "id": current_user.id,
            "first_name": current_user.first_name,
            "last_name": current_user.last_name,
            "email": current_user.email,
            "is_authenticated": True,
        }
        return jsonify(user_data)
    return jsonify({"is_authenticated": False})


@auth_bp.route("/request-password-reset", methods=["POST"])
@limiter.limit("5 per hour")
def request_password_reset():
    data = request.get_json()
    email = data.get("email")
    if not email:
        return jsonify({"error": "Email is required."}), 400

    auth_service = AuthService()
    try:
        auth_service.send_password_reset_email(email)
        return jsonify(
            {
                "message": "If an account with that email exists, a password reset link has been sent."
            }
        ), 200
    except Exception as e:
        current_app.logger.error(f"Error requesting password reset: {e}", exc_info=True)
        # Generic message to avoid leaking info
        return jsonify(
            {
                "message": "If an account with that email exists, a password reset link has been sent."
            }
        ), 200


@auth_bp.route("/reset-password", methods=["POST"])
@limiter.limit("5 per hour")
def reset_password():
    """Resets user password with a valid token."""
    schema = ResetPasswordSchema()
    try:
        data = schema.load(request.json)
    except ValidationError as err:
        return jsonify(err.messages), 400

    auth_service = AuthService()
    try:
        auth_service.reset_password_with_token(data["token"], data["new_password"])
        return jsonify({"message": "Password has been reset successfully."}), 200
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error resetting password: {e}", exc_info=True)
        return jsonify({"error": "An unexpected error occurred."}), 500


@auth_bp.route("/refresh", methods=["POST"])
@jwt_required(refresh=True)
def refresh():
    """Refreshes an access token."""
    current_user_id = get_jwt_identity()
    new_access_token = create_access_token(identity=current_user_id)
    return jsonify(access_token=new_access_token)


@auth_bp.route("/password/confirm-reset", methods=["POST"])
@limiter.limit(limit=5, per=600)  # 5 requests per 10 minutes
def confirm_password_reset():
    """Resets the user's password using a valid token."""
    json_data = request.get_json()
    if not json_data:
        return jsonify(error="Invalid JSON data provided."), 400

    # Validate input using marshmallow schema
    try:
        schema = PasswordResetConfirmSchema()
        validated_data = schema.load(json_data)
    except ValidationError as err:
        return jsonify(error="Validation failed.", errors=err.messages), 400

    if AuthService.reset_password_with_token(
        validated_data["token"], validated_data["new_password"]
    ):
        return jsonify(message="Password has been reset successfully."), 200
    return jsonify(error="Invalid or expired token."), 400
