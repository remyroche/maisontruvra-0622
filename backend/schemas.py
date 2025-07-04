"""
This module defines Marshmallow schemas for data validation and serialization.
Schemas ensure that data moving in and out of the API is well-structured and secure,
separating input validation from output serialization.
"""

import re
from datetime import datetime
from typing import Optional

from marshmallow import Schema, ValidationError, fields, validate
from pydantic import BaseModel, EmailStr, Field

from .extensions import ma
from .models.enums import B2BStatus, OrderStatus, PaymentStatus

# --- Base Schema & Custom Validators ---


class BaseSchema(ma.Schema):
    """Base schema with common configuration."""

    class Meta:
        unknown = "EXCLUDE"


def validate_password_complexity(password):
    """
    Custom validator for password strength. Ensures at least 8 characters,
    one uppercase, one lowercase, and one digit.
    """
    if len(password) < 8:
        raise ValidationError("Password must be at least 8 characters long.")
    if not re.search(r"[A-Z]", password):
        raise ValidationError("Password must contain at least one uppercase letter.")
    if not re.search(r"[a-z]", password):
        raise ValidationError("Password must contain at least one lowercase letter.")
    if not re.search(r"\d", password):
        raise ValidationError("Password must contain at least one digit.")


# --- Core Model Schemas ---


class RoleSchema(BaseSchema):
    """Schema for serializing Role data."""

    id = fields.Int(dump_only=True)
    name = fields.Str(dump_only=True)


class AddressSchema(BaseModel):
    id: int | None = None
    address_line_1: str
    address_line_2: str | None = None
    city: str
    state_province_region: str
    postal_code: str
    country: str
    is_default_shipping: bool | None = False
    is_default_billing: bool | None = False

    class Config:
        from_attributes = True


class CategorySchema(BaseSchema):
    """Schema for Product Categories."""

    id = fields.Int(dump_only=True)
    name = fields.Str(required=True)


class TagSchema(BaseSchema):
    """Schema for Product Tags."""

    id = fields.Int(dump_only=True)
    name = fields.Str(required=True)


class B2BUserSchema(BaseModel):
    """
    Schema for representing a user associated with a B2B account.
    """

    id: int
    email: EmailStr
    first_name: str
    last_name: str
    roles: list[str] = []

    class Config:
        from_attributes = True


class B2BUserRemoveSchema(BaseModel):
    """
    Schema for removing a user from a B2B account.
    """

    user_id: int


class VariantSchema(BaseSchema):
    """Schema for Product Variants."""

    id = fields.Int(dump_only=True)
    sku = fields.Str(required=True)
    price_offset = fields.Decimal(as_string=True, required=True)
    stock = fields.Int(required=True, validate=validate.Range(min=0))


class B2BProfileSchema(BaseModel):
    """
    Schema for representing a B2B account's profile data.
    """

    id: int
    company_name: str
    vat_number: str | None = None
    status: str
    user: "UserSchema"  # Embed the user details

    class Config:
        from_attributes = True


class B2BProfileUpdateSchema(BaseModel):
    """
    Schema for validating updates to a B2B profile.
    A B2B user can update their company info and their personal info.
    """

    company_name: str | None = Field(default=None, min_length=1)
    vat_number: str | None = Field(default=None, min_length=1)
    # Nested schema for updating the associated user details
    user_details: Optional["UserProfileUpdateSchema"] = None

    class Config:
        from_attributes = True


class ProductSchema(BaseSchema):
    """Schema for serializing a full Product object."""

    id = fields.Int(dump_only=True)
    name = fields.Str(required=True)
    description = fields.Str(required=True)
    price = fields.Decimal(as_string=True, required=True)
    is_active = fields.Bool(required=True)
    is_featured = fields.Bool(required=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
    category_id = fields.Int(required=True, load_only=True)
    tag_ids = fields.List(fields.Int(), load_only=True, required=False)
    category = fields.Nested(CategorySchema, dump_only=True)
    tags = fields.List(fields.Nested(TagSchema), dump_only=True)
    variants = fields.List(fields.Nested(VariantSchema), required=True)


class ReviewSchema(BaseSchema):
    """Schema for product reviews."""

    id = fields.Int(dump_only=True)
    rating = fields.Int(required=True, validate=validate.Range(min=1, max=5))
    title = fields.Str(required=True, validate=validate.Length(max=100))
    comment = fields.Str(validate=validate.Length(max=1000))
    is_approved = fields.Bool(dump_only=True)
    user = fields.Nested("UserSchema", dump_only=True, only=("id", "first_name"))
    product = fields.Nested(ProductSchema, dump_only=True, only=("id", "name"))


# --- User & Auth Schemas ---


class UserSchema(BaseModel):
    id: int
    email: EmailStr
    first_name: str
    last_name: str
    is_active: bool
    is_b2b: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UserRegistrationSchema(BaseSchema):
    """Schema for new user registration."""

    first_name = fields.Str(required=True, validate=validate.Length(min=1, max=50))
    last_name = fields.Str(required=True, validate=validate.Length(min=1, max=50))
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate_password_complexity)
    user_type = fields.Str(validate=validate.OneOf(["b2c", "b2b"]), missing="b2c")
    setup_2fa = fields.Bool(missing=False)  # Optional 2FA setup during registration
    two_fa_method = fields.Str(
        validate=validate.OneOf(["totp", "magic_link"]), allow_none=True
    )


class LoginSchema(BaseSchema):
    """Schema for user login."""

    email = fields.Email(required=True)
    password = fields.Str(required=True)


class UserProfileUpdateSchema(BaseModel):
    """
    Schema for validating data when a user updates their own profile.
    They can only update a limited set of fields.
    """

    email: EmailStr | None = None
    first_name: str | None = Field(default=None, min_length=1)
    last_name: str | None = Field(default=None, min_length=1)
    language: str | None = Field(default=None, min_length=2, max_length=10)

    class Config:
        from_attributes = True


class ChangePasswordSchema(BaseSchema):
    """Schema for changing a password."""

    old_password = fields.Str(required=True)
    new_password = fields.Str(required=True, validate=validate_password_complexity)


class PasswordResetRequestSchema(BaseSchema):
    """Schema for requesting a password reset."""

    email = fields.Email(required=True)


class PasswordResetConfirmSchema(BaseSchema):
    """Schema for confirming a password reset with a token."""

    token = fields.Str(required=True)
    new_password = fields.Str(required=True, validate=validate_password_complexity)


class LanguageUpdateSchema(BaseSchema):
    """Schema for updating user language preference."""

    language = fields.Str(required=True, validate=validate.Length(min=2, max=10))


class TwoFactorSetupSchema(BaseSchema):
    """Schema for initiating 2FA setup."""

    pass


class TwoFactorVerifySchema(BaseSchema):
    """Schema for verifying 2FA token."""

    totp_code = fields.Str(required=True, validate=validate.Length(equal=6))


class MfaVerificationSchema(BaseSchema):
    """Schema for MFA verification during login."""

    user_id = fields.Int(required=True)
    mfa_token = fields.Str(required=True)
    mfa_type = fields.Str(
        validate=validate.OneOf(["totp", "magic_link"]), required=True
    )


class SetupTotpSchema(BaseSchema):
    """Schema for TOTP setup."""

    totp_code = fields.Str(required=True, validate=validate.Length(equal=6))


class MagicLinkRequestSchema(BaseSchema):
    """Schema for requesting a magic link."""

    email = fields.Email(required=True)


class AuthMethodUpdateSchema(BaseSchema):
    """Schema for updating authentication methods."""

    action = fields.Str(
        validate=validate.OneOf(
            ["enable_totp", "disable_totp", "enable_magic_link", "disable_magic_link"]
        ),
        required=True,
    )
    current_password = fields.Str(
        required=True
    )  # Always require current password for security
    totp_code = fields.Str(
        validate=validate.Length(equal=6), allow_none=True
    )  # Required when disabling TOTP
    magic_link_token = fields.Str(allow_none=True)  # Required when disabling magic link


class PasswordChangeSchema(BaseSchema):
    """Schema for changing password."""

    current_password = fields.Str(required=True)
    new_password = fields.Str(required=True, validate=validate_password_complexity)


# --- Cart & Checkout Schemas ---


class AddToCartSchema(BaseSchema):
    """Schema for adding an item to the cart."""

    variant_id = fields.Int(required=True)
    quantity = fields.Int(required=True, validate=validate.Range(min=1))


class UpdateCartItemSchema(BaseSchema):
    """Schema for updating an item's quantity in the cart."""

    quantity = fields.Int(required=True, validate=validate.Range(min=0))


class ApplyDiscountSchema(BaseSchema):
    """Schema for applying a discount code to the cart."""

    code = fields.Str(required=True)


class CheckoutSchema(BaseSchema):
    """Schema for validating the final checkout payload."""

    shipping_address_id = fields.Int(required=True)
    billing_address_id = fields.Int(required=True)
    delivery_method_id = fields.Int(required=True)
    payment_token = fields.Str(required=True)
    notes = fields.Str(allow_none=True)


# --- Blog Schemas ---


class BlogCategorySchema(BaseSchema):
    """Schema for blog categories."""

    id = fields.Int(dump_only=True)
    name = fields.Str(required=True, validate=validate.Length(min=3))
    slug = fields.Str(dump_only=True)


class BlogPostSchema(BaseSchema):
    """Schema for validating and serializing Blog Posts."""

    id = fields.Int(dump_only=True)
    title = fields.Str(required=True, validate=validate.Length(min=5))
    content = fields.Str(required=True)
    slug = fields.Str(dump_only=True)
    is_published = fields.Bool(default=False)
    created_at = fields.DateTime(dump_only=True)
    author_id = fields.Int(load_only=True, required=True)
    category_id = fields.Int(load_only=True, required=True)
    author = fields.Nested(
        UserSchema, dump_only=True, only=("id", "first_name", "last_name")
    )
    category = fields.Nested(BlogCategorySchema, dump_only=True)


# --- Admin-Specific Schemas ---


class UserUpdateSchema(BaseModel):
    """
    More permissive schema for admins updating a user.
    """

    email: EmailStr | None = None
    first_name: str | None = None
    last_name: str | None = None
    is_active: bool | None = None
    is_b2b: bool | None = None
    roles: list[str] | None = None

    class Config:
        from_attributes = True


class OrderUpdateSchema(BaseSchema):
    """Schema for admins updating an order's status."""

    status = fields.Str(
        required=True,
        validate=validate.OneOf(
            ["pending", "processing", "shipped", "delivered", "cancelled"]
        ),
    )
    tracking_number = fields.Str(allow_none=True, validate=validate.Length(max=100))


class DiscountSchema(BaseSchema):
    """Schema for creating/updating discounts."""

    id = fields.Int(dump_only=True)
    code = fields.Str(required=True, validate=validate.Length(min=4, max=50))
    discount_type = fields.Str(
        required=True, validate=validate.OneOf(["percentage", "fixed"])
    )
    value = fields.Decimal(
        as_string=True, required=True, validate=validate.Range(min=0)
    )
    is_active = fields.Bool(default=True)
    valid_from = fields.DateTime(allow_none=True)
    valid_to = fields.DateTime(allow_none=True)
    usage_limit = fields.Int(allow_none=True, validate=validate.Range(min=1))


class DeliveryMethodSchema(BaseSchema):
    """Schema for creating/updating delivery methods."""

    id = fields.Int(dump_only=True)
    name = fields.Str(required=True, validate=validate.Length(min=3, max=100))
    description = fields.Str(allow_none=True)
    price = fields.Decimal(
        as_string=True, required=True, validate=validate.Range(min=0)
    )
    is_active = fields.Bool(default=True)
    tier_ids = fields.List(fields.Int(), load_only=True, required=False)


# --- B2B Schemas ---
class B2BPartnershipRequestSchema(BaseSchema):
    """Schema for B2B partnership requests."""

    id = fields.Int(dump_only=True)
    company_name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    contact_person = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    contact_email = fields.Email(required=True)
    phone_number = fields.Str(required=True, validate=validate.Length(min=1, max=20))
    message = fields.Str(allow_none=True, validate=validate.Length(max=1000))
    status = fields.Str(dump_only=True)
    created_at = fields.DateTime(dump_only=True)


class B2BTierSchema(BaseSchema):
    """Schema for B2B pricing tiers."""

    id = fields.Int(dump_only=True)
    name = fields.Str(required=True, validate=validate.Length(min=1, max=50))
    discount_percentage = fields.Decimal(
        as_string=True, required=True, validate=validate.Range(min=0, max=100)
    )
    minimum_spend = fields.Decimal(
        as_string=True, allow_none=True, validate=validate.Range(min=0)
    )
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class B2BAccountSchema(BaseSchema):
    """Schema for B2B accounts."""

    id = fields.Int(dump_only=True)
    company_name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    contact_email = fields.Email(required=True)
    phone_number = fields.Str(required=True, validate=validate.Length(min=1, max=20))
    status = fields.Str(dump_only=True)
    tier_id = fields.Int(allow_none=True)
    user_id = fields.Int(required=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
    tier = fields.Nested(B2BTierSchema, dump_only=True)
    user = fields.Nested(
        UserSchema, dump_only=True, only=("id", "email", "first_name", "last_name")
    )


class B2BAccountStatusUpdateSchema(BaseSchema):
    """Schema for updating a B2B account's status."""

    status = fields.Str(
        required=True, validate=validate.OneOf([s.value for s in B2BStatus])
    )


class B2BApplicationRejectSchema(BaseSchema):
    """Schema for rejecting a B2B application."""

    reason = fields.Str(required=True, validate=validate.Length(min=1, max=500))


class B2BTierCreateSchema(BaseSchema):
    """Schema for creating a B2B pricing tier."""

    name = fields.Str(required=True, validate=validate.Length(min=1, max=50))
    discount_percentage = fields.Decimal(
        as_string=True, required=True, validate=validate.Range(min=0, max=100)
    )
    minimum_spend = fields.Decimal(
        as_string=True, allow_none=True, validate=validate.Range(min=0)
    )


class B2BTierUpdateSchema(BaseSchema):
    """Schema for updating an existing B2B pricing tier."""

    name = fields.Str(validate=validate.Length(min=1, max=50))
    discount_percentage = fields.Decimal(
        as_string=True, validate=validate.Range(min=0, max=100)
    )
    minimum_spend = fields.Decimal(
        as_string=True, allow_none=True, validate=validate.Range(min=0)
    )


class B2BUserAssignTierSchema(BaseSchema):
    """Schema for assigning a tier to a B2B user."""

    tier_id = fields.Int(required=True)


# --- Order Schemas ---
class OrderItemSchema(BaseSchema):
    """Schema for items within an order."""

    id = fields.Int(dump_only=True)
    product_id = fields.Int(required=True)
    variant_id = fields.Int(required=True)
    quantity = fields.Int(required=True, validate=validate.Range(min=1))
    price_at_purchase = fields.Decimal(as_string=True, required=True)
    product = fields.Nested(
        ProductSchema, dump_only=True, only=("id", "name", "price", "image_url")
    )  # Added image_url
    variant = fields.Nested(
        VariantSchema, dump_only=True, only=("id", "sku", "price_offset")
    )


class PaymentSchema(BaseSchema):
    """Schema for payment details of an order."""

    id = fields.Int(dump_only=True)
    amount = fields.Decimal(as_string=True, required=True)
    currency = fields.Str(required=True, validate=validate.Length(equal=3))
    payment_method = fields.Str(required=True)
    transaction_id = fields.Str(required=True)
    status = fields.Str(
        required=True, validate=validate.OneOf([s.value for s in PaymentStatus])
    )
    created_at = fields.DateTime(dump_only=True)


class OrderSchema(BaseSchema):
    """Comprehensive schema for an Order, including nested details."""

    id = fields.Int(dump_only=True)
    user_id = fields.Int(allow_none=True)
    session_id = fields.Str(allow_none=True)
    total_amount = fields.Decimal(as_string=True, dump_only=True)
    status = fields.Str(
        dump_only=True, validate=validate.OneOf([s.value for s in OrderStatus])
    )
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)
    tracking_number = fields.Str(allow_none=True)

    items = fields.List(fields.Nested(OrderItemSchema), dump_only=True)
    payments = fields.List(fields.Nested(PaymentSchema), dump_only=True)
    shipping_address = fields.Nested(AddressSchema, dump_only=True)
    billing_address = fields.Nested(AddressSchema, dump_only=True)

    shipping_address_id = fields.Int(load_only=True, required=False)
    billing_address_id = fields.Int(load_only=True, required=False)
    delivery_method_id = fields.Int(load_only=True, required=False)
    payment_token = fields.Str(load_only=True, required=False)
    notes = fields.Str(load_only=True, allow_none=True)


class GuestOrderSchema(BaseSchema):
    """Schema for creating a guest order."""

    session_id = fields.Str(required=True)
    email = fields.Email(required=True)
    shipping_address = fields.Nested(AddressSchema, required=True)
    billing_address = fields.Nested(AddressSchema, required=True)
    delivery_method_id = fields.Int(required=True)
    payment_token = fields.Str(required=True)
    notes = fields.Str(allow_none=True)


class AuthenticatedOrderSchema(BaseSchema):
    """Schema for creating an order for an authenticated user."""

    shipping_address_id = fields.Int(required=True)
    billing_address_id = fields.Int(required=True)
    delivery_method_id = fields.Int(required=True)
    payment_token = fields.Str(required=True)
    notes = fields.Str(allow_none=True)


class CheckoutOrderSchema(BaseSchema):
    """
    Combined schema for checkout, handling both guest and authenticated user fields.
    Fields are optional based on whether user_id or session_id is present.
    """

    user_id = fields.Int(load_only=True, allow_none=True)
    session_id = fields.Str(load_only=True, allow_none=True)
    email = fields.Email(load_only=True, allow_none=True)

    shipping_address_id = fields.Int(load_only=True, allow_none=True)
    billing_address_id = fields.Int(load_only=True, allow_none=True)
    shipping_address = fields.Nested(AddressSchema, load_only=True, allow_none=True)
    billing_address = fields.Nested(AddressSchema, load_only=True, allow_none=True)

    delivery_method_id = fields.Int(required=True)
    payment_token = fields.Str(required=True)
    notes = fields.Str(allow_none=True)

    @validate.post_load
    def validate_user_or_guest_info(self, data, **kwargs):
        if data.get("user_id") is None:
            if not data.get("session_id"):
                raise ValidationError(
                    "session_id is required for guest checkout.", "session_id"
                )
            if not data.get("email"):
                raise ValidationError("email is required for guest checkout.", "email")
            if not data.get("shipping_address"):
                raise ValidationError(
                    "shipping_address is required for guest checkout.",
                    "shipping_address",
                )
            if not data.get("billing_address"):
                raise ValidationError(
                    "billing_address is required for guest checkout.", "billing_address"
                )
        else:
            if not data.get("shipping_address_id"):
                raise ValidationError(
                    "shipping_address_id is required for authenticated checkout.",
                    "shipping_address_id",
                )
            if not data.get("billing_address_id"):
                raise ValidationError(
                    "billing_address_id is required for authenticated checkout.",
                    "billing_address_id",
                )
        return data


# --- Wishlist Schemas ---
class WishlistItemSchema(BaseSchema):
    """Schema for a WishlistItem."""

    id = fields.Int(dump_only=True)
    user_id = fields.Int(dump_only=True)
    product_id = fields.Int(required=True)  # For adding/removing
    created_at = fields.DateTime(dump_only=True)
    product = fields.Nested(
        ProductSchema, dump_only=True, only=("id", "name", "price", "image_url", "slug")
    )  # Include relevant product details


class AddToWishlistSchema(BaseSchema):
    """Schema for adding an item to the wishlist (input)."""

    product_id = fields.Int(required=True)


# --- Miscellaneous Schemas ---


class ContactFormSchema(BaseSchema):
    """Schema for the public contact form."""

    name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    email = fields.Email(required=True)
    message = fields.Str(required=True, validate=validate.Length(min=1, max=2000))
    company_name = fields.Str(validate=validate.Length(max=100), allow_none=True)
    phone_number = fields.Str(validate=validate.Length(max=20), allow_none=True)


class NewsletterSubscriptionSchema(BaseSchema):
    """Schema for newsletter signups."""

    email = fields.Email(required=True)
    first_name = fields.Str(validate=validate.Length(max=50))
    list_type = fields.Str(missing="b2c", validate=validate.OneOf(["b2c", "b2b"]))


class SiteSettingsSchema(Schema):
    """A dynamic schema for updating site settings."""

    settings = fields.Dict(keys=fields.Str(), values=fields.Str(), required=True)
