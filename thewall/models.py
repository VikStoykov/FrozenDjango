from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class Profile(models.Model):
    name = models.TextField()
    
    def __str__(self):
        return self.name
    
    class Meta:
        db_table = 'profiles'


class Section(models.Model):
    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='sections'
    )
    height = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(30)],
    )
    
    def __str__(self):
        return f"Section of {self.profile.name} - Height: {self.height}ft"
    
    class Meta:
        db_table = 'sections'


class DailyProgress(models.Model):
    profile = models.ForeignKey(
        Profile,
        on_delete=models.CASCADE,
        related_name='daily_progress'
    )
    day = models.IntegerField(
        validators=[MinValueValidator(1)],
        help_text="Day number of the construction project"
    )
    active_crews = models.IntegerField(
        validators=[MinValueValidator(0)],  # Allow 0 crews when no work
        help_text="Number of active crews working on this day"
    )
    ice_amount = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="Amount of ice/work completed in cubic yards"
    )
    cost = models.IntegerField(
        validators=[MinValueValidator(0)],
        help_text="Cost for this day's work"
    )
    
    def __str__(self):
        return f"Day {self.day} - {self.profile.name}: {self.active_crews} crews, {self.ice_amount} cubic yards"
    
    class Meta:
        db_table = 'daily_progress'
        unique_together = [['profile', 'day']]  # One record per profile per day
