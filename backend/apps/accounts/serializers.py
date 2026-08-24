"""Serializers for accounts (auth + user management)."""
from __future__ import annotations

from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.accounts.models import Role, User
from apps.accounts.permissions import can_manage_target_role
from apps.common.roles import RoleCode


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["code", "name", "description"]


class UserSerializer(serializers.ModelSerializer):
    role = serializers.SlugRelatedField(slug_field="code", read_only=True)
    permissions = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "full_name",
            "role",
            "is_active",
            "is_staff",
            "date_joined",
            "permissions",
        ]
        read_only_fields = fields

    def get_permissions(self, obj: User) -> list[str]:
        return sorted(obj.get_all_permissions())


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        user = authenticate(
            request=self.context.get("request"),
            username=attrs["email"].lower(),
            password=attrs["password"],
        )
        if user is None:
            raise serializers.ValidationError(
                {"detail": "Invalid email or password."}, code="authorization"
            )
        if not user.is_active:
            raise serializers.ValidationError(
                {"detail": "User account is disabled."}, code="authorization"
            )
        attrs["user"] = user
        return attrs


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    role = serializers.SlugRelatedField(
        slug_field="code", queryset=Role.objects.all()
    )

    class Meta:
        model = User
        fields = ["id", "email", "full_name", "role", "password", "is_active"]
        read_only_fields = ["id"]

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value

    def validate_role(self, role: Role) -> Role:
        actor = self.context["request"].user
        actor_code = getattr(getattr(actor, "role", None), "code", None)
        if not can_manage_target_role(actor_code, role.code):
            raise serializers.ValidationError(
                "You may not assign this role."
            )
        return role

    def create(self, validated_data) -> User:
        password = validated_data.pop("password")
        user = User.objects.create_user(password=password, **validated_data)
        return user


class UserUpdateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, required=False, trim_whitespace=False
    )
    role = serializers.SlugRelatedField(
        slug_field="code", queryset=Role.objects.all(), required=False
    )

    class Meta:
        model = User
        fields = ["full_name", "role", "is_active", "password"]

    def validate_password(self, value: str) -> str:
        validate_password(value, user=self.instance)
        return value

    def validate(self, attrs):
        request = self.context["request"]
        actor = request.user
        actor_code = getattr(getattr(actor, "role", None), "code", None)
        is_admin = actor_code in {RoleCode.SYSTEM_ADMIN, RoleCode.TRAFFIC_ADMIN}
        editing_self = self.instance.id == actor.id

        # Non-admins editing themselves may not change role or active status.
        if not is_admin:
            for locked in ("role", "is_active"):
                if locked in attrs:
                    raise serializers.ValidationError(
                        {locked: "You may not change this field."}
                    )
        # Only System Admin may (re)assign roles.
        if "role" in attrs and actor_code != RoleCode.SYSTEM_ADMIN:
            raise serializers.ValidationError(
                {"role": "Only a System Administrator may assign roles."}
            )
        if "role" in attrs and not can_manage_target_role(actor_code, attrs["role"].code):
            raise serializers.ValidationError({"role": "You may not assign this role."})
        _ = editing_self
        return attrs

    def update(self, instance, validated_data) -> User:
        password = validated_data.pop("password", None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance
