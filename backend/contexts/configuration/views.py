from core.api.viewsets import TenantModelViewSet
from .models import Domain, Service, Vertical
from .serializers import DomainSerializer, ServiceSerializer, VerticalSerializer

class VerticalViewSet(TenantModelViewSet):
    queryset = Vertical.objects.all(); serializer_class = VerticalSerializer; search_fields = ["name", "code", "description"]
class DomainViewSet(TenantModelViewSet):
    queryset = Domain.objects.all(); serializer_class = DomainSerializer; search_fields = ["name", "code", "description"]
    def get_queryset(self):
        qs=super().get_queryset(); value=self.request.query_params.get("vertical_id"); return qs.filter(vertical_id=value) if value else qs
class ServiceViewSet(TenantModelViewSet):
    queryset = Service.objects.all(); serializer_class = ServiceSerializer; search_fields = ["name", "code", "description"]
    def get_queryset(self):
        qs=super().get_queryset(); value=self.request.query_params.get("domain_id"); return qs.filter(domain_id=value) if value else qs
