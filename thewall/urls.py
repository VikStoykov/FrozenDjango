from django.urls import path

from . import views

urlpatterns = [
    path("", views.index, name="index"),
    path("upload-csv/", views.upload_csv, name="upload_csv"),
    
    # GET /profiles/1/days/1/
    path("profiles/<int:profile_id>/days/<int:day_num>/", views.profile_day_detail, name="profile_day_detail"),
    
    # GET /profiles/1/overview/1/
    path("profiles/<int:profile_id>/overview/<int:day_num>/", views.profile_overview, name="profile_overview"),
    
    # GET /profiles/overview/1/
    path("profiles/overview/<int:day_num>/", views.profiles_overview, name="profiles_overview"),

    # GET /profiles/overview/
    path("profiles/overview/", views.all_profiles_overview, name="profiles_overview"),
]
