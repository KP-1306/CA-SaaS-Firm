from rest_framework.permissions import IsAuthenticated

from core.api.viewsets import TenantModelViewSet
from contexts.authorization.permissions import ClientAccessPermission

from .models import (
    Client,
    ClientBranch,
    ClientContact,
    ClientGSTRegistration,
)
from .serializers import (
    ClientBranchSerializer,
    ClientContactSerializer,
    ClientGSTRegistrationSerializer,
    ClientSerializer,
)


class _ClientAuthorizedViewSet(TenantModelViewSet):
    permission_classes = [
        IsAuthenticated,
        ClientAccessPermission,
    ]


class ClientViewSet(_ClientAuthorizedViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    search_fields = [
        "legal_name",
        "trade_name",
        "pan",
        "cin_or_llpin",
        "industry",
    ]


class _ClientChildViewSet(_ClientAuthorizedViewSet):
    def get_queryset(self):
        queryset = super().get_queryset()
        client_id = self.request.query_params.get("client_id")

        if client_id:
            return queryset.filter(client_id=client_id)

        return queryset


class ClientContactViewSet(_ClientChildViewSet):
    queryset = ClientContact.objects.all()
    serializer_class = ClientContactSerializer
    search_fields = ["name", "email", "mobile"]


class ClientGSTRegistrationViewSet(_ClientChildViewSet):
    queryset = ClientGSTRegistration.objects.all()
    serializer_class = ClientGSTRegistrationSerializer
    search_fields = ["gstin", "state", "trade_name"]


class ClientBranchViewSet(_ClientChildViewSet):
    queryset = ClientBranch.objects.all()
    serializer_class = ClientBranchSerializer
    search_fields = [
        "name",
        "state",
        "contact_name",
        "contact_mobile",
    ]
