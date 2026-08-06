from django.urls import path

from contexts.authorization.views import (
    AccessCatalogueView,
    RoleCloneView,
    RoleCollectionView,
    RoleDetailView,
    UserAccessProfileView,
)


urlpatterns = [
    path("roles/", RoleCollectionView.as_view(), name="authorization-role-list"),
    path(
        "roles/<int:role_id>/",
        RoleDetailView.as_view(),
        name="authorization-role-detail",
    ),
    path(
        "roles/<int:role_id>/clone/",
        RoleCloneView.as_view(),
        name="authorization-role-clone",
    ),
    path(
        "access/",
        AccessCatalogueView.as_view(),
        name="authorization-access-catalogue",
    ),
    path(
        "users/<uuid:account_id>/",
        UserAccessProfileView.as_view(),
        name="authorization-user-access",
    ),
]
