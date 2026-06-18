#!/bin/sh

set -e

echo "Running database migrations..."
python manage.py migrate

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Creating superuser..."
DJANGO_SETTINGS_MODULE=fastpass.settings python -c "
import django
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
email = '${ADMIN_EMAIL}'
if not User.objects.filter(email=email).exists():
    User.objects.create_superuser(email=email, nome='${ADMIN_USERNAME}', password='${ADMIN_PASSWORD}')
    print('Superuser created successfully.')
else:
    print('Superuser already exists.')
"

# Execute the main container command (from CMD)
exec "$@"
