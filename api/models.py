import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin


# ----------------------
# Custom User Management
# ----------------------
class UserManager(BaseUserManager):
    def create_user(self, email, name, password=None, **extra_fields):
        if not email:
            raise ValueError("The Email field must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, name=name, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, name, password=None, **extra_fields):
        extra_fields.setdefault("role", "admin")
        extra_fields.setdefault("status", "active")
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self.create_user(email, name, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom User model for RAU-LLS.
    Supports both admin and agent roles.
    """
    ROLE_CHOICES = [
        ("agent", "Agent"),
        ("admin", "Admin"),
    ]
    STATUS_CHOICES = [
        ("active", "Active"),
        ("inactive", "Inactive"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    password = models.CharField(max_length=255)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="agent")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active")
    last_login = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Django admin flags
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.email}) - {self.role}"


# ----------------------
# Google Sheet Config
# ----------------------
class SheetConfig(models.Model):
    """
    Stores the Google Sheet configuration for lead data source.
    Only one configuration should exist (singleton pattern).
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sheet_id = models.CharField(max_length=255, help_text="Google Sheet ID from URL")
    tab_name = models.CharField(max_length=255, help_text="Worksheet/Tab name within the sheet")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Sheet Configuration"
        verbose_name_plural = "Sheet Configuration"

    def __str__(self):
        return f"Sheet: {self.sheet_id}, Tab: {self.tab_name}"

    def save(self, *args, **kwargs):
        """Ensure only one config exists (singleton)."""
        if not self.pk and SheetConfig.objects.exists():
            # If trying to create new but one exists, update the existing one
            existing = SheetConfig.objects.first()
            existing.sheet_id = self.sheet_id
            existing.tab_name = self.tab_name
            existing.save()
            return existing
        return super().save(*args, **kwargs)