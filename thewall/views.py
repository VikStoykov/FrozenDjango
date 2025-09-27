from django.http import HttpResponse
from django.contrib.auth.models import Group, User
from django.conf import settings
from rest_framework import permissions, viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
import os

from thewall.serializers import GroupSerializer, UserSerializer, CSVUploadSerializer

class UserViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows users to be viewed or edited.
    """
    queryset = User.objects.all().order_by('-date_joined')
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]


class GroupViewSet(viewsets.ModelViewSet):
    """
    API endpoint that allows groups to be viewed or edited.
    """
    queryset = Group.objects.all().order_by('name')
    serializer_class = GroupSerializer
    permission_classes = [permissions.IsAuthenticated]


@api_view(['POST'])
@permission_classes([permissions.IsAdminUser])
def upload_csv(request):
    """
    API for upload mechanism of CSV file config for the wall sections.
    Saves to wall_construction_plan.csv
    """
    serializer = CSVUploadSerializer(data=request.data)

    if serializer.is_valid():
        try:
            uploaded_file = serializer.validated_data['file']

            file_path = os.path.join(settings.BASE_DIR, 'wall_construction_plan.csv')

            with open(file_path, 'wb') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)

            return Response({
                'success': True,
                'message': 'CSV file uploaded successfully',
                #'filename': 'wall_construction_plan.csv',
                #'saved_to': file_path
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({
                'success': False,
                'errors': {'file': [f'Error saving file: {str(e)}']}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    else:
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

def index(request):
    return HttpResponse("Hello, world. This is The Wall.")
