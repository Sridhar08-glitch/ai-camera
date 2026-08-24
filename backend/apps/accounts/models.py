"""
Accounts domain models (Phase 1 §12): Role and email-based User.
"""
from __future__ import annotations

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from apps.accounts.managers import UserManager
from apps.common.models import TimeStampedModel, UUIDModel
from apps.common.roles import RoleCode


class Role(UUIDModel, TimeStampedModel):
    """A named platform role. Seeded from RoleCode at migration time."""

    code = models.CharField(max_length=32, unique=True, choices=RoleCode.choices)
    name = models.CharField(max_length=64)
    description = models.TextField(blank=True, default="")

    class Meta:
        db_table = "accounts_role"
        ordering = ["code"]

    def __str__(self) -> str:
        return self.code


class User(UUIDModel, TimeStampedModel, AbstractBaseUser, PermissionsMixin):
    """Email-authenticated platform user with exactly one primary role."""

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150, blank=True, default="")
    role = models.ForeignKey(
        Role,
        on_delete=models.PROTECT,
        related_name="users",
        null=True,
        blank=True,
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        db_table = "accounts_user"
        ordering = ["email"]

    def __str__(self) -> str:
        return self.email

    @property
    def role_code(self) -> str | None:
        return self.role.code if self.role_id else None
