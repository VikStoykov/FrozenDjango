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
                start_time = time.time()

                # Check if parallel processing is requested
                use_parallel = request.GET.get('parallel', 'false').lower() == 'true'
                teams_param = request.GET.get('teams', None)

                if use_parallel and teams_param:
                    try:
                        num_teams = int(teams_param)

                        # Call the parallel implementation with specified teams
                        calculate_daily_progress_parallel(num_teams=num_teams)
                        print(f"Parallel calculation with {num_teams} teams completed.")

                        calculation_method = f"parallel (with {num_teams} teams)"
                    except ValueError:
                        return Response({
                            'success': False,
                            'errors': {'teams': ['Number of teams must be a valid integer']}
                        }, status=status.HTTP_400_BAD_REQUEST)
                else:
                    # Default calculation
                    calculate_daily_progress()
                    calculation_method = "sequential"

                end_time = time.time()
                calculation_time_ms = (end_time - start_time) * 1000

            return Response({
                'success': True,
                'message': 'CSV file uploaded and processed successfully',
                'profiles_created': len(rows),
                'daily_progress_calculated': True,
                'calculation_method': calculation_method if 'calculation_method' in locals() else "sequential",
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


def calculate_daily_progress_parallel(num_teams=None):
    """
    Calculate daily progress for all profiles based on construction rules:
    - Limited number of teams available
    - Each team works on one section at a time
    - Each team produces X cubic yards per day (configurable)
    - Each cubic yard costs Y (configurable)
    - Construction stops when section reaches max height (configurable)
    - Teams move to the next available section after finishing one

    Args:
        num_teams (int): Number of available teams. If None, one team per section.
    """
    import threading
    import queue
    import os
    import logging
    from datetime import datetime

    # Setup logging to file with timestamps
    log_file = os.path.join(settings.BASE_DIR, 'wall_progress.log')
    logging.basicConfig(
        filename=log_file,
        level=logging.INFO,
        format='%(asctime)s - Team %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # Clear the log file at the start of a new calculation
    with open(log_file, 'w') as f:
        start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        f.write(f"Wall Construction Progress Log - Started on {start_time}\n")
        f.write("-" * 80 + "\n\n")

    # Load config values from settings
    config = settings.WALL_CONSTRUCTION
    CUBIC_YARDS_PER_CREW_PER_DAY = config['CUBIC_YARDS_PER_CREW_PER_DAY']
    COST_PER_CUBIC_YARD = config['COST_PER_CUBIC_YARD']
    MAX_HEIGHT = config['MAX_HEIGHT']

    # Load profiles and sections from database (read-only)
    profiles = list(Profile.objects.all().prefetch_related('sections'))

    # Create a dictionary to track the current state of all sections (in-memory only)
    section_heights = {}
    section_profiles = {}

    # Initial population of section heights dictionary
    for profile in profiles:
        for section in profile.sections.all():
            section_heights[(profile.id, section.id)] = section.height
            section_profiles[section.id] = profile.name

    #print(f"Configuration: {CUBIC_YARDS_PER_CREW_PER_DAY} cubic yards per crew per day")
    #print(f"Cost per cubic yard: ${COST_PER_CUBIC_YARD}")
    #print(f"Max wall height: {MAX_HEIGHT} feet")

    logging.getLogger("Simulation").info(f"Started with {num_teams} teams - Max height: {MAX_HEIGHT}ft")

    if num_teams is None:
        total_sections = sum(1 for height in section_heights.values() if height < MAX_HEIGHT)
        num_teams = total_sections
        #print(f"No team count specified. Using {num_teams} teams (one per unfinished section)")
    else:
        pass
        #print(f"Using {num_teams} teams")

    if num_teams <= 0:
        #print("WARNING: No teams specified or zero teams provided. Setting to 1 team.")
        num_teams = 1

    day = 1
    total_project_ice = 0

    # Track teams that have already been relieved to avoid duplicate log entries
    relieved_teams = set()

    # Continue until all work is complete
    while True:
        #print(f"\n=== DAY {day} ===")
        day_has_work = False
        daily_work = {}  # Format: {profile_id: {'active_crews': count, 'ice_amount': total}}

        # Create a list of work items for sections that still need work
        work_items = []
        for (profile_id, section_id), height in section_heights.items():
            if height < MAX_HEIGHT:
                work_items.append((profile_id, section_id))

        if not work_items:
            #print("All sections completed! Construction finished.")
            break

        # Create a work queue with all the work items
        work_queue = queue.Queue()
        for item in work_items:
            work_queue.put(item)

        lock = threading.Lock()

        def team_worker(team_id):
            """
            Worker function that will be executed by each team
            """
            team_logger = logging.getLogger(str(team_id))

            try:
                # Try to get work from the queue
                profile_id, section_id = work_queue.get(block=False)

                # Get current height from our local copy
                current_height = section_heights[(profile_id, section_id)]

                if current_height < MAX_HEIGHT:
                    # Add 1 foot per day until max height
                    new_height = min(current_height + 1, MAX_HEIGHT)

                    # Get profile name for output
                    profile_name = section_profiles[section_id]

                    # Update our in-memory section height
                    with lock:
                        section_heights[(profile_id, section_id)] = new_height

                        # Only log to file when the section reaches maximum height
                        if new_height == MAX_HEIGHT:
                            team_logger.info(f"Day {day} - Completed section on {profile_name}, Section {section_id} - Final height {new_height}")

                        # Add to the daily work counter for this profile
                        if profile_id not in daily_work:
                            daily_work[profile_id] = {'active_crews': 0, 'ice_amount': 0}

                        daily_work[profile_id]['active_crews'] += 1
                        daily_work[profile_id]['ice_amount'] += CUBIC_YARDS_PER_CREW_PER_DAY

                        # Mark that we have work for this day
                        nonlocal day_has_work
                        day_has_work = True

                work_queue.task_done()
                return True
            except queue.Empty:
                # Only log to file when the team is relieved and there's no more work at all
                # and this team hasn't already been logged as relieved
                if work_queue.empty() and team_id not in relieved_teams:
                    team_logger.info(f"Day {day} - Relieved (all sections completed)")
                    # Add this team to the set of relieved teams
                    relieved_teams.add(team_id)
                return False

        # Process work with threads
        threads = []
        for team_id in range(1, num_teams + 1):

            # Start worker thread
            thread = threading.Thread(target=team_worker, args=(team_id,))
            thread.start()
            threads.append(thread)

        # Wait for all workers to finish the day's work
        for thread in threads:
            thread.join()

        if not day_has_work:
            #print("All sections completed! Construction finished.")
            break
        day += 1

    # Print final statistics
    #print("\n=== FINAL STATISTICS ===")
    #print(f"Days required: {day-1}")

    # Calculate total statistics
    total_cost = total_project_ice * COST_PER_CUBIC_YARD
    #print(f"Total ice used: {total_project_ice} cubic yards")
    #print(f"Total cost: ${total_cost:,}")

    # Log only completion information to file
    completion_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    summary_logger = logging.getLogger("Summary")
    summary_logger.info(f"Construction completed in {day-1} days with {num_teams} teams")

    # Add separator to log file for readability
    with open(log_file, 'a') as f:
        f.write("\n" + "-" * 80 + "\n")
        f.write(f"End of simulation - {completion_time}\n")

    # Always update the database
    #print("\nUpdating database with simulation results...")
    try:
        with transaction.atomic():
            # First, reset all sections to their initial heights as loaded from DB
                for profile in profiles:
                    profile_sections = list(profile.sections.all())
                    for section in profile_sections:
                        section.height = section_heights.get((profile.id, section.id), section.height)
                        section.save()

                # Then create daily progress records based on the simulation
                DailyProgress.objects.all().delete()  # Clear existing records

                current_heights = {}
                for profile in profiles:
                    for section in profile.sections.all():
                        current_heights[(profile.id, section.id)] = 0

                for day_num in range(1, day):
                    for profile in profiles:
                        active_crews = 0
                        total_ice_amount = 0
                        sections = profile.sections.all()

                        for section in sections:
                            current_height = current_heights.get((profile.id, section.id), 0)
                            target_height = min(current_height + 1, MAX_HEIGHT)
                            
                            if current_height < MAX_HEIGHT:
                                active_crews += 1
                                total_ice_amount += CUBIC_YARDS_PER_CREW_PER_DAY
                                current_heights[(profile.id, section.id)] = target_height

                        if active_crews > 0:
                            total_cost = total_ice_amount * COST_PER_CUBIC_YARD
                            DailyProgress.objects.create(
                                profile=profile,
                                day=day_num,
                                active_crews=active_crews,
                                ice_amount=total_ice_amount,
                                cost=total_cost
                            )

                print("Database updated successfully!")

    except Exception as e:
        print(f"Error updating database: {str(e)}")
        logging.getLogger("Error").error(f"Failed to update database: {str(e)}")

    print(f"See full logs in {log_file}")

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
                "csv_upload_parallel_with_teams": {
                    "url": f"{base_url}upload-csv/?parallel=true&teams=10",
                    "method": "POST", 
                    "description": "Upload CSV file with parallel calculation using 10 teams (Admin only)",
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
        log_content = ""
        log_file_path = os.path.join(settings.BASE_DIR, 'wall_progress.log')
        if os.path.exists(log_file_path):
            try:
                with open(log_file_path, 'r') as log_file:
                    log_content = log_file.read()
            except Exception as e:
                log_content = f"Error reading log file: {str(e)}"
        
        styles = """
        <style>
            body {
                font-family: 'Helvetica Neue', Arial, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 1200px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            h1, h2 {
                color: #2c3e50;
                margin-top: 20px;
            }
            h1 {
                border-bottom: 2px solid #3498db;
                padding-bottom: 10px;
                font-size: 28px;
            }
            h2 {
                font-size: 22px;
                margin-top: 30px;
            }
            .container {
                display: flex;
                flex-wrap: wrap;
                gap: 20px;
            }
            .endpoints {
                flex: 1;
                min-width: 300px;
                background-color: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }
            .log-container {
                flex: 2;
                min-width: 500px;
                background-color: white;
                padding: 20px;
                border-radius: 8px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }
            .log-viewer {
                height: 600px;
                overflow-y: auto;
                background-color: #2c3e50;
                color: #ecf0f1;
                padding: 15px;
                border-radius: 5px;
                font-family: monospace;
                font-size: 14px;
                white-space: pre-wrap;
                line-height: 1.5;
            }
            ul {
                padding-left: 20px;
            }
            li {
                margin-bottom: 8px;
            }
            a {
                color: #3498db;
                text-decoration: none;
            }
            a:hover {
                text-decoration: underline;
                color: #2980b9;
            }
            .back-link {
                display: inline-block;
                margin-top: 20px;
                font-size: 16px;
            }
            .team-line {
                margin: 2px 0;
            }
            .highlight {
                color: #2ecc71;
                font-weight: bold;
            }
            .header-line {
                color: #e74c3c;
                font-weight: bold;
            }
        </style>
        """
        
        # Format log content with syntax highlighting
        formatted_log = ""
        if log_content:
            lines = log_content.split('\n')
            for line in lines:
                if "Wall Construction Progress Log" in line or "Started on" in line or "End of simulation" in line or "-"*10 in line:
                    formatted_log += f'<div class="header-line">{line}</div>'
                elif "Completed section" in line:
                    formatted_log += f'<div class="team-line highlight">{line}</div>'
                else:
                    formatted_log += f'<div class="team-line">{line}</div>'
        else:
            formatted_log = "No construction log available."

        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>The Wall API - Construction Dashboard</title>
            {styles}
        </head>
        <body>
            <h1>The Wall API - Construction Dashboard</h1>
            
            <div class="container">
                <div class="endpoints">
                    <h2>API Endpoints</h2>
                    <ul>
                        <li><a href="{request.build_absolute_uri('/thewall/')}?api=1">API Overview (JSON)</a></li>
                        <li><strong>POST</strong> <a href="{request.build_absolute_uri('/thewall/upload-csv/')}">/thewall/upload-csv/</a> - Upload CSV (Admin only)</li>
                        <li><strong>POST</strong> <a href="{request.build_absolute_uri('/thewall/upload-csv/?parallel=true&teams=10')}">/thewall/upload-csv/?parallel=true&teams=10</a> - Upload CSV with parallel simulation (Admin only)</li>
                        <li><strong>GET</strong> <a href="{request.build_absolute_uri('/thewall/profiles/1/days/1/')}">/thewall/profiles/1/days/1/</a> - Profile day details</li>
                        <li><strong>GET</strong> <a href="{request.build_absolute_uri('/thewall/profiles/1/overview/1/')}">/thewall/profiles/1/overview/1/</a> - Profile overview</li>
                        <li><strong>GET</strong> <a href="{request.build_absolute_uri('/thewall/profiles/overview/1/')}">/thewall/profiles/overview/1/</a> - All profiles overview</li>
                        <li><strong>GET</strong> <a href="{request.build_absolute_uri('/thewall/profiles/overview/')}">/thewall/profiles/overview/</a> - Total overview</li>
                    </ul>
                    
                    <h2>Configuration</h2>
                    <ul>
                        <li><strong>Cubic yards per crew per day:</strong> {settings.WALL_CONSTRUCTION['CUBIC_YARDS_PER_CREW_PER_DAY']}</li>
                        <li><strong>Cost per cubic yard:</strong> ${settings.WALL_CONSTRUCTION['COST_PER_CUBIC_YARD']}</li>
                        <li><strong>Maximum wall height:</strong> {settings.WALL_CONSTRUCTION['MAX_HEIGHT']} feet</li>
                    </ul>
                    
                    <p class="back-link"><a href="{request.build_absolute_uri('/api/')}">← Back to main API</a></p>
                </div>
                
                <div class="log-container">
                    <h2>Wall Construction Progress Log</h2>
                    <div class="log-viewer">
                        {formatted_log}
                    </div>
                </div>
            </div>
        </body>
        </html>
        """
        return HttpResponse(html)
