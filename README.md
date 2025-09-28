# FrozenDjango

Experimental Django REST API project for parallel wall construction simulation.

This project simulates the construction of "The Wall" using Django and REST API, implementing both sequential and parallel processing strategies to compare performance characteristics.

## Story of The Wall

> *\- "The White Walkers sleep beneath the ice for thousands of years. And when they wake up..."*
> *\- "And when they wake up... what?"*
> *\- "I hope the Wall is high enough."*
>
> *The Wall is a colossal fortification which is being built to stretch for 100 leagues (300 miles) along the northern border of the Seven Kingdoms. Its purpose is to defend the realm from the wildlings who live beyond. The Wall is reported to be 30 foot tall and is made of solid ice. The Sworn Brothers of the Ni*

## Project Overview

The Wall construction simulator models the building of wall sections across multiple profiles. Each profile consists of multiple sections that need to be constructed to a maximum height. The system simulates:

- Multiple construction crews working simultaneously
- Daily progress tracking for each profile
- Cost calculations and resource allocation
- Performance comparison between sequential and parallel approaches

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

### Data Endpoints

Entry point: *http://127.0.0.1:8000/thewall/*

Retrieve ice amount for a specific profile on a specific day:
```bash
curl -H 'Accept: application/json; indent=4' http://127.0.0.1:8000/thewall/profiles/1/days/1/
```

Get total cost for a specific profile up to specified day:
```bash
curl -H 'Accept: application/json; indent=4' http://127.0.0.1:8000/thewall/profiles/1/overview/1/
```

Get total cost for all profiles up to specified day:
```bash
curl -H 'Accept: application/json; indent=4' http://127.0.0.1:8000/thewall/profiles/overview/1/
```

Get total cost for all profiles across all days:
```bash
curl -H 'Accept: application/json; indent=4' http://127.0.0.1:8000/thewall/profiles/overview/
```

## Random Data Generator

The project includes a random data generator script to create test datasets of various sizes for performance testing:

```bash
# Generate a small dataset with random distribution
python random_data_generator.py
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

### Implementation Architecture

The project uses two distinct approaches for processing the wall construction:

1. **Sequential Implementation**: A straightforward approach that processes each profile and section one at a time.

2. **Parallel Implementation**: Uses Python's `threading` and `queue` modules to simulate multiple construction teams working simultaneously. This approach includes:
   - Thread-safe work queue for distributing tasks
   - Worker threads representing construction teams
   - Synchronized access to shared data structures
   - Detailed logging of construction progress
