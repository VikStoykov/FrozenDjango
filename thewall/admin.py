from django.contrib import admin
from .models import Profile, Section, DailyProgress

admin.site.register(Profile)
admin.site.register(Section)
admin.site.register(DailyProgress)
