from core.api.viewsets import TenantModelViewSet
from .models import Branch, FirmProfile, Team
from .serializers import BranchSerializer, FirmProfileSerializer, TeamSerializer

class FirmProfileViewSet(TenantModelViewSet):
    queryset = FirmProfile.objects.all(); serializer_class = FirmProfileSerializer; search_fields = ["name", "legal_name", "pan", "gstin"]
class BranchViewSet(TenantModelViewSet):
    queryset = Branch.objects.all(); serializer_class = BranchSerializer; search_fields = ["name", "code", "email", "mobile"]
class TeamViewSet(TenantModelViewSet):
    queryset = Team.objects.all(); serializer_class = TeamSerializer; search_fields = ["name", "code"]
