#!/bin/sh

set -e

echo "Running database migrations..."
python manage.py migrate

echo "Collecting static files..."
python manage.py collectstatic --noinput

# Execute the main container command (from CMD)
exec "$@"
