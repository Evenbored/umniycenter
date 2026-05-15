#!/bin/bash
set -e

echo "Collecting static files..."
python manage.py collectstatic --noinput

if [ "$DJANGO_DEBUG_MODE" = "true" ]; then
    echo "Starting Django development server..."
    exec python manage.py runserver 0.0.0.0:8000
else
    echo "Starting Gunicorn..."
    exec gunicorn umniycenter.wsgi:application --bind 0.0.0.0:8000 --workers 4
fi