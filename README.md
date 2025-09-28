# FrozenDjango

Experimental Django REST API project for parallel wall construction simulation

## Installation

```bash
python3 -m venv myenv
source myenv/bin/activate
pip install -r requirements.txt
```

## Configuration

1. Create DB (sqlite)
```bash
python manage.py makemigrations thewall
python manage.py migrate
```

2. Create superuser
```bash
python manage.py createsuperuser
```

3. Run quick system check to validate everything works correctly
```bash
python manage.py check
```

## Run development server

```bash
python manage.py runserver
```

## API Usage

Basic authentication endpoints:
```bash
curl -u admin -H 'Accept: application/json; indent=4' http://127.0.0.1:8000/api-auth/
curl -u admin -H 'Accept: application/json; indent=4' http://127.0.0.1:8000/users/
curl -u admin -H 'Accept: application/json; indent=4' http://127.0.0.1:8000/groups/
```

### Upload config file

Sequential processing:
```bash
curl -u admin -H 'Accept: application/json; indent=4' http://127.0.0.1:8000/thewall/upload-csv/ -X POST -F "file=@test_valid.csv"
```

Parallel processing with specified team count:
```bash
curl -u admin -H 'Accept: application/json; indent=4' http://127.0.0.1:8000/thewall/upload-csv/?parallel=true&teams=10 -X POST -F "file=@test_valid.csv"
```

## Performance Comparison

The table below shows the performance comparison between sequential processing and parallel processing with different team counts using test datasets of varying sizes. All times are in seconds.

| Dataset | Method               | Execution Time (ms) | Speed-up |
|---------|--------------------- |-------------------- |----------|
| Small   | Sequential           | 317.57              | 1.00x    |
| Small   | Parallel (2 teams)   | 220.71              | 1.44x    |
| Small   | Parallel (6 teams)   | 167.7               | 1.89x    |
| Small   | Parallel (9 teams)   | 141.9               | 2.24x    |
| Medium  | Sequential           | 3354.53             | 1.00x    |
| Medium  | Parallel (13 teams)  | 3173.78             | 1.06x    |
| Medium  | Parallel (21 teams)  | 2399.59             | 1.40x    |
| Medium  | Parallel (27 teams)  | 2255.76             | 1.49x    |

### Dataset Information

- **Small Dataset**: 10 profiles, ~80 sections
- **Medium Dataset**: 60 profiles, ~1500 sections 

### Testing Methodology

Performance tests were conducted by running each configuration multiple times and averaging the results. The tests measure the time taken to calculate the daily progress for wall construction using both sequential and parallel processing methods.
