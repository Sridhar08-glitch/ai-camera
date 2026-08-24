"""
Accounts views: auth (login/refresh/logout/me) + user management.

Refresh tokens are delivered via an HttpOnly cookie, never in the JSON body
(clarification #1). Access tokens are short-lived and returned in the body for
in-memory use by the SPA.
"""
from __future__ import annotations

from django.db import transaction
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.serializers import TokenRefreshSerializer
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.cookies import (
    clear_refresh_cookie,
    get_refresh_from_cookie,
    set_refresh_cookie,
)
from apps.audit.models import EventType, Outcome
from apps.audit.services import record_audit, record_audit_on_commit
from apps.accounts.models import Role, User
from apps.accounts.permissions import IsSelfOrAdmin
from apps.accounts.serializers import (
    LoginSerializer,
    RoleSerializer,
    UserCreateSerializer,
    UserSerializer,
    UserUpdateSerializer,
)
from apps.common.permissions import IsAdminRole, IsSystemAdmin


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_scope = "auth"

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        try:
            serializer.is_valid(raise_exception=True)
        except ValidationError:
            # Best-effort failure audit — never store the submitted password.
            record_audit_on_commit(
                EventType.LOGIN_FAILURE,
                action="login",
                outcome=Outcome.FAILURE,
                request=request,
                metadata={"email": str(request.data.get("email", ""))[:254]},
            )
            raise
        user = serializer.validated_data["user"]

        refresh = RefreshToken.for_user(user)
        response = Response(
            {
                "data": {
                    "access": str(refresh.access_token),
                    "user": UserSerializer(user).data,
                }
            },
            status=status.HTTP_200_OK,
        )
        set_refresh_cookie(response, str(refresh))
        record_audit_on_commit(
            EventType.LOGIN_SUCCESS, action="login", actor=user, request=request
        )
        return response


class RefreshView(APIView):
    """Rotate the refresh token from the HttpOnly cookie; return a new access."""

    permission_classes = [AllowAny]
    throttle_scope = "auth"

    def post(self, request):
        refresh = get_refresh_from_cookie(request)
        if not refresh:
            return Response(
                {"error": {"code": "not_authenticated", "message": "No refresh token."}},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        serializer = TokenRefreshSerializer(data={"refresh": refresh})
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError:
            resp = Response(
                {"error": {"code": "not_authenticated", "message": "Invalid refresh token."}},
                status=status.HTTP_401_UNAUTHORIZED,
            )
            clear_refresh_cookie(resp)
            return resp

        data = serializer.validated_data
        response = Response({"data": {"access": data["access"]}}, status=status.HTTP_200_OK)
        # With ROTATE_REFRESH_TOKENS the serializer returns a fresh refresh token.
        if "refresh" in data:
            set_refresh_cookie(response, data["refresh"])
        return response


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        refresh = get_refresh_from_cookie(request)
        response = Response(status=status.HTTP_204_NO_CONTENT)
        if refresh:
            try:
                RefreshToken(refresh).blacklist()
            except TokenError:
                pass  # already invalid/expired — nothing to revoke
        clear_refresh_cookie(response)
        record_audit_on_commit(
            EventType.LOGOUT, action="logout", actor=request.user, request=request
        )
        return response


class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class RoleListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RoleSerializer
    queryset = Role.objects.all()
    pagination_class = None


class UserListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        qs = User.objects.select_related("role").all()
        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(email__icontains=search)
        return qs

    def get_serializer_class(self):
        return UserCreateSerializer if self.request.method == "POST" else UserSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            user = serializer.save()
            record_audit(
                EventType.USER_CREATED,
                action="create_user",
                request=request,
                target_type="User",
                target_id=user.id,
                metadata={"email": user.email, "role": user.role_code},
            )
        return Response(
            UserSerializer(user).data, status=status.HTTP_201_CREATED
        )


class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated, IsSelfOrAdmin]
    queryset = User.objects.select_related("role").all()

    def get_serializer_class(self):
        if self.request.method in ("PUT", "PATCH"):
            return UserUpdateSerializer
        return UserSerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        was_active = instance.is_active
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            serializer.save()
            instance.refresh_from_db()
            if was_active and not instance.is_active:
                event = EventType.USER_DEACTIVATED
            elif not was_active and instance.is_active:
                event = EventType.USER_ACTIVATED
            else:
                event = EventType.USER_UPDATED
            record_audit(
                event,
                action="update_user",
                request=request,
                target_type="User",
                target_id=instance.id,
                metadata={"fields": sorted(serializer.validated_data.keys())},
            )
        return Response(UserSerializer(instance).data)

    def destroy(self, request, *args, **kwargs):
        # Deletion is restricted to System Administrators (clarification of §11).
        if not IsSystemAdmin().has_permission(request, self):
            return Response(
                {"error": {"code": "permission_denied", "message": "Only a System Administrator may delete users."}},
                status=status.HTTP_403_FORBIDDEN,
            )
        instance = self.get_object()
        if instance.id == request.user.id:
            return Response(
                {"error": {"code": "bad_request", "message": "You cannot delete your own account."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        deleted_email, deleted_id = instance.email, str(instance.id)
        with transaction.atomic():
            instance.delete()
            record_audit(
                EventType.USER_DELETED,
                action="delete_user",
                request=request,
                target_type="User",
                target_id=deleted_id,
                metadata={"email": deleted_email},
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class AssignRoleView(APIView):
    permission_classes = [IsSystemAdmin]

    def post(self, request, pk):
        try:
            user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response(
                {"error": {"code": "not_found", "message": "User not found."}},
                status=status.HTTP_404_NOT_FOUND,
            )
        code = request.data.get("role")
        try:
            role = Role.objects.get(code=code)
        except Role.DoesNotExist:
            return Response(
                {"error": {"code": "validation_error", "message": "Unknown role."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        previous = user.role_code
        with transaction.atomic():
            user.role = role
            user.save(update_fields=["role", "updated_at"])
            record_audit(
                EventType.ROLE_CHANGED,
                action="assign_role",
                request=request,
                target_type="User",
                target_id=user.id,
                metadata={"from": previous, "to": role.code, "email": user.email},
            )
        return Response(UserSerializer(user).data)
