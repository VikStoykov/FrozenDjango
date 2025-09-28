# FrozenDjango

Experimental Django project

# Installation

python3 -m venv myenv
source myenv/bin/activate
pip install -r requirements.txt

# Configure

1. Create DB (sqlite)
python manage.py makemigrations thewall
python manage.py migrate

2. Create superuser
python manage.py createsuperuser

3. Run quick system check to validate everyting works correctly
python manage.py check

# Run development server

python manage.py runserver

# APIs

curl -u admin -H 'Accept: application/json; indent=4' http://127.0.0.1:8000/api-auth/
curl -u admin -H 'Accept: application/json; indent=4' http://127.0.0.1:8000/users/
curl -u admin -H 'Accept: application/json; indent=4' http://127.0.0.1:8000/groups/

## Upload config

curl -u admin -H 'Accept: application/json; indent=4' http://127.0.0.1:8000/thewall/upload-csv/ -X POST -F "file=@test_valid.csv"
