"""
Local runner to populate Firebase directly.
Run this to test without deploying to Cloud Functions.
"""

import os
import sys

# Check for required env var or service account
if not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
    # Try to find a service account file
    possible_paths = [
        "serviceAccount.json",
        "service-account.json",
        "../serviceAccount.json",
        os.path.expanduser("~/.config/firebase/serviceAccount.json"),
    ]
    for path in possible_paths:
        if os.path.exists(path):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = path
            print(f"Using service account: {path}")
            break
    else:
        print("""
ERROR: No Firebase credentials found.

Options:
1. Download a service account key from Firebase Console:
   - Go to: https://console.firebase.google.com/project/nextgenpicks-fb759/settings/serviceaccounts/adminsdk
   - Click "Generate new private key"
   - Save as 'serviceAccount.json' in this folder

2. Or login via gcloud:
   gcloud auth application-default login

3. Or set GOOGLE_APPLICATION_CREDENTIALS:
   export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
""")
        sys.exit(1)

# Now import Firebase (after credentials are set)
import firebase_admin
from firebase_admin import credentials, firestore
import json
import datetime
import uuid
from datetime import timezone

# Import our scraper functions
from underdog_scraper import get_underdog_nba_props, get_espn_nba_schedule, format_for_firebase

def init_firebase():
    """Initialize Firebase Admin SDK."""
    try:
        # Check if already initialized
        firebase_admin.get_app()
        print("Firebase already initialized")
    except ValueError:
        # Initialize with default credentials
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred, {
            'projectId': 'nextgenpicks-fb759',
        })
        print("Firebase initialized successfully")

def populate_firebase():
    """Fetch data and populate Firebase."""
    print("\n" + "="*60)
    print("LOCAL FIREBASE POPULATION")
    print("="*60 + "\n")

    # Initialize Firebase
    init_firebase()
    db = firestore.client()

    # Fetch data
    print("Fetching Underdog Fantasy props...")
    underdog_data = get_underdog_nba_props()

    if not underdog_data["players"]:
        print("ERROR: No NBA props found")
        return

    print("Fetching ESPN schedule...")
    espn_games = get_espn_nba_schedule()

    # Format for Firebase
    cards = format_for_firebase(underdog_data, espn_games)

    if not cards:
        print("ERROR: No cards to write")
        return

    # Clear old props
    print("\nClearing old props collection...")
    props_ref = db.collection("props")
    docs = props_ref.stream()
    deleted = 0
    for doc in docs:
        doc.reference.delete()
        deleted += 1
    print(f"Deleted {deleted} old documents")

    # Write new props
    print(f"\nWriting {len(cards)} new player cards...")
    for card in cards:
        doc_id = str(card["id"])
        db.collection("props").document(doc_id).set(card)
        print(f"  ✓ {card['name']}")

    print(f"\n{'='*60}")
    print(f"SUCCESS: Wrote {len(cards)} players to Firebase")
    print("="*60)

    # Verify
    print("\nVerifying write...")
    count = len(list(db.collection("props").stream()))
    print(f"Props collection now has {count} documents")

if __name__ == "__main__":
    populate_firebase()
