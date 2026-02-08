from firebase_admin import initialize_app
# Import both for Firebase discovery
from batch_analyze import batch_analyze, scheduled_refresh

# Initialize Firebase Admin
initialize_app()
