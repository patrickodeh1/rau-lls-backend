import sys
import os

# Add your project directory to sys.path
INTERP = "/home/gpnbaf79msbm/virtualenv/rau-lls-backend/3.9/bin/python3"
if sys.executable != INTERP:
    os.execl(INTERP, INTERP, *sys.argv)

sys.path.insert(0, '/home/gpnbaf79msbm/rau-lls-backend')

# Environment variables
os.environ['DJANGO_SETTINGS_MODULE'] = 'rau_lls.settings'

# Import WSGI application
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()