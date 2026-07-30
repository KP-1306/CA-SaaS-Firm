from core.api.viewsets import TenantModelViewSet
from .models import Client, ClientBranch, ClientContact, ClientGSTRegistration
from .serializers import ClientBranchSerializer, ClientContactSerializer, ClientGSTRegistrationSerializer, ClientSerializer

class ClientViewSet(TenantModelViewSet):
    queryset=Client.objects.all(); serializer_class=ClientSerializer; search_fields=["legal_name","trade_name","pan","cin_or_llpin","industry"]
class _ClientChildViewSet(TenantModelViewSet):
    def get_queryset(self):
        qs=super().get_queryset(); value=self.request.query_params.get("client_id"); return qs.filter(client_id=value) if value else qs
class ClientContactViewSet(_ClientChildViewSet):
    queryset=ClientContact.objects.all(); serializer_class=ClientContactSerializer; search_fields=["name","email","mobile"]
class ClientGSTRegistrationViewSet(_ClientChildViewSet):
    queryset=ClientGSTRegistration.objects.all(); serializer_class=ClientGSTRegistrationSerializer; search_fields=["gstin","state","trade_name"]
class ClientBranchViewSet(_ClientChildViewSet):
    queryset=ClientBranch.objects.all(); serializer_class=ClientBranchSerializer; search_fields=["name","state","contact_name","contact_mobile"]
