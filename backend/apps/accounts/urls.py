"""User/role routes mounted at /api/v1/."""
from django.urls import path

from apps.accounts.views import (
    AssignRoleView,
    RoleListView,
    UserDetailView,
    UserListCreateView,
)

urlpatterns = [
    path("roles", RoleListView.as_view(), name="role-list"),
    path("users", UserListCreateView.as_view(), name="user-list-create"),
    path("users/<uuid:pk>", UserDetailView.as_view(), name="user-detail"),
    path("users/<uuid:pk>/role", AssignRoleView.as_view(), name="user-assign-role"),
]
