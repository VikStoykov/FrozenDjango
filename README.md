# FrozenDjango
Experimental Django project

# Installation
python3 -m venv myenv
source myenv/bin/activate
pip install -r requirements.txt

# Configure

1. Create DB (sqlite)
python manage.py migrate

2. Create superuser
python manage.py createsuperuser

# Run development server
python manage.py runserver
