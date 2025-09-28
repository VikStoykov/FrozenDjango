from django.http import HttpResponse
from django.contrib.auth.models import Group, User
from django.conf import settings
from django.db import transaction
from django.db.models import Sum
from rest_framework import permissions, viewsets, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
import os
import csv
import io
import time

from thewall.serializers import GroupSerializer, UserSerializer, CSVUploadSerializer
from thewall.models import Profile, Section, DailyProgress

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
    Creates profiles and sections from CSV data and calculates daily progress.
    """
    serializer = CSVUploadSerializer(data=request.data)

    if serializer.is_valid():
        try:
            uploaded_file = serializer.validated_data['file']

            file_path = os.path.join(settings.BASE_DIR, 'wall_construction_plan.csv')
            with open(file_path, 'wb') as destination:
                for chunk in uploaded_file.chunks():
                    destination.write(chunk)

            uploaded_file.seek(0)
            file_content = uploaded_file.read().decode('utf-8')
            csv_reader = csv.reader(io.StringIO(file_content))
            rows = list(csv_reader)

            with transaction.atomic():
                DailyProgress.objects.all().delete()
                Section.objects.all().delete() 
                Profile.objects.all().delete()
                
                # Reset auto-increment counters to ensure IDs start from 1
                from django.db import connection
                cursor = connection.cursor()
                cursor.execute("DELETE FROM sqlite_sequence WHERE name='profiles';")
                cursor.execute("DELETE FROM sqlite_sequence WHERE name='sections';")
                cursor.execute("DELETE FROM sqlite_sequence WHERE name='daily_progress';")
                print("Tables cleared and auto-increment reset.")

                for profile_idx, row in enumerate(rows, 1):
                    if not row or all(cell.strip() == '' for cell in row):
                        continue

                    # create profile
                    profile = Profile.objects.create(name=f"Profile {profile_idx}")

                    # create sections for this profile
                    for section_value in row:
                        if section_value.strip():
                            Section.objects.create(
                                profile=profile,
                                height=int(section_value.strip())
                            )

                # calculate daily progress for all profiles
                # TODO: make it with threading
                start_time = time.time()
                calculate_daily_progress()
                end_time = time.time()
                calculation_time_ms = (end_time - start_time) * 1000

            return Response({
                'success': True,
                'message': 'CSV file uploaded and processed successfully',
                'profiles_created': len(rows),
                'daily_progress_calculated': True,
                'calculation_time_ms': round(calculation_time_ms, 2)
            }, status=status.HTTP_201_CREATED)

        except Exception as e:
            return Response({
                'success': False,
                'errors': {'file': [f'Error processing file: {str(e)}']}
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    else:
        return Response({
            'success': False,
            'errors': serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


def calculate_daily_progress():
    """
    Calculate daily progress for all profiles based on construction rules:
    - Each crew works on one section at a time
    - Each crew produces X cubic yards per day (configurable)
    - Each cubic yard costs Y (configurable)
    - Construction stops when section reaches max height (configurable)
    """
    config = settings.WALL_CONSTRUCTION
    CUBIC_YARDS_PER_CREW_PER_DAY = config['CUBIC_YARDS_PER_CREW_PER_DAY']
    COST_PER_CUBIC_YARD = config['COST_PER_CUBIC_YARD']
    MAX_HEIGHT = config['MAX_HEIGHT']

    profiles = Profile.objects.all()
    day = 1

    # Continue until all work is complete
    while True:
        day_has_work = False

        for profile in profiles:
            sections = profile.sections.all()
            active_crews = 0
            total_ice_amount = 0

            # Count active crews
            for section in sections:
                if section.height < MAX_HEIGHT:
                    active_crews += 1
                    # Add 1 foot per day until max height
                    # This will rewrite the height each day, simulating daily progress
                    new_height = min(section.height + 1, MAX_HEIGHT)
                    section.height = new_height
                    section.save()

                    # Calculate ice amount for this crew
                    total_ice_amount += CUBIC_YARDS_PER_CREW_PER_DAY
                    day_has_work = True

            # Create daily progress record if there's work
            if active_crews > 0:
                total_cost = total_ice_amount * COST_PER_CUBIC_YARD

                DailyProgress.objects.create(
                    profile=profile,
                    day=day,
                    active_crews=active_crews,
                    ice_amount=total_ice_amount,
                    cost=total_cost
                )

        if not day_has_work:
            break

        day += 1


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def profile_day_detail(request, profile_id, day_num):
    """
    GET /thewall/profiles/{id}/days/{day}/
    Returns ice amount for specific profile on specific day
    """
    try:
        progress = DailyProgress.objects.get(profile_id=profile_id, day=day_num)
        return Response({
            'day': str(day_num),
            'ice_amount': str(progress.ice_amount)
        })
    except DailyProgress.DoesNotExist:
        return Response({
            'day': str(day_num),
            'ice_amount': '0'
        })
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def profile_overview(request, profile_id, day_num=1):
    """
    GET /thewall/profiles/{id}/overview/{day}/
    Returns total cost for specific profile up to specified day
    """
    try:
        total_cost = DailyProgress.objects.filter(
            profile_id=profile_id,
            day__lte=day_num
        ).aggregate(total=Sum('cost'))['total'] or 0

        return Response({
            'day': str(day_num),
            'cost': f"{total_cost:,}"
        })
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def profiles_overview(request, day_num=None):
    """
    GET /thewall/profiles/overview/{day}/
    Returns total cost for all profiles up to specified day
    """
    try:
        if day_num:
            day_num = int(day_num)
            total_cost = DailyProgress.objects.filter(
                day__lte=day_num
            ).aggregate(total=Sum('cost'))['total'] or 0

            return Response({
                'day': str(day_num),
                'cost': f"{total_cost:,}"
            })
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def all_profiles_overview(request):
    """
    GET /thewall/profiles/overview/
    Returns total cost for all profiles across all days
    """
    try:
        total_cost = DailyProgress.objects.aggregate(
            total=Sum('cost')
        )['total'] or 0

        return Response({
            'day': None,
            'cost': f"{total_cost:,}"
        })
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

def index(request):
    """
    Show all available thewall API endpoints
    """
    if request.headers.get('Accept') == 'application/json' or 'api' in request.GET:
        # Return JSON response for API clients
        base_url = request.build_absolute_uri('/thewall/')
        endpoints = {
            "message": "The Wall API Endpoints",
            "endpoints": {
                "welcome": {
                    "url": base_url,
                    "method": "GET",
                    "description": "This endpoint"
                },
                "csv_upload": {
                    "url": f"{base_url}upload-csv/",
                    "method": "POST", 
                    "description": "Upload CSV file with wall construction data (Admin only)",
                    "authentication": "Admin required"
                },
                "profile_day_detail": {
                    "url": f"{base_url}profiles/{{profile_id}}/days/{{day}}/",
                    "method": "GET",
                    "description": "Get ice amount for specific profile on specific day",
                    "example": f"{base_url}profiles/1/days/1/"
                },
                "profile_overview": {
                    "url": f"{base_url}profiles/{{profile_id}}/overview/{{day}}/",
                    "method": "GET", 
                    "description": "Get total cost for specific profile up to specified day",
                    "example": f"{base_url}profiles/1/overview/1/"
                },
                "profiles_overview_with_day": {
                    "url": f"{base_url}profiles/overview/{{day}}/",
                    "method": "GET",
                    "description": "Get total cost for all profiles up to specified day",
                    "example": f"{base_url}profiles/overview/1/"
                },
                "profiles_overview_total": {
                    "url": f"{base_url}profiles/overview/",
                    "method": "GET",
                    "description": "Get total cost for all profiles across all days"
                }
            },
            "configuration": {
                "cubic_yards_per_crew_per_day": settings.WALL_CONSTRUCTION['CUBIC_YARDS_PER_CREW_PER_DAY'],
                "cost_per_cubic_yard": settings.WALL_CONSTRUCTION['COST_PER_CUBIC_YARD'],
                "max_height": settings.WALL_CONSTRUCTION['MAX_HEIGHT']
            }
        }
        return HttpResponse(
            content=str(endpoints).replace("'", '"'),
            content_type='application/json'
        )
    else:
        html = f"""
        <h1>The Wall API</h1>
        <p>Available endpoints:</p>
        <ul>
            <li><a href="{request.build_absolute_uri('/thewall/')}?api=1">API Overview (JSON)</a></li>
            <li><strong>POST</strong> <a href="{request.build_absolute_uri('/thewall/upload-csv/')}">/thewall/upload-csv/</a> - Upload CSV (Admin only)</li>
            <li><strong>GET</strong> <a href="{request.build_absolute_uri('/thewall/profiles/1/days/1/')}">/thewall/profiles/1/days/1/</a> - Profile day details</li>
            <li><strong>GET</strong> <a href="{request.build_absolute_uri('/thewall/profiles/1/overview/1/')}">/thewall/profiles/1/overview/1/</a> - Profile overview</li>
            <li><strong>GET</strong> <a href="{request.build_absolute_uri('/thewall/profiles/overview/1/')}">/thewall/profiles/overview/1/</a> - All profiles overview</li>
            <li><strong>GET</strong> <a href="{request.build_absolute_uri('/thewall/profiles/overview/')}">/thewall/profiles/overview/</a> - Total overview</li>
        </ul>
        <p><a href="{request.build_absolute_uri('/api/')}">← Back to main API</a></p>
        """
        return HttpResponse(html)
