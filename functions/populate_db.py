import urllib.request
import json

# CHANGE THIS URL to your Deployed Cloud Function URL after deploying
# Run: firebase deploy --only functions
# Then look for the batch_analyze function URL in the output
BATCH_FUNCTION_URL = "https://batch-analyze-qqtyxxni4q-uc.a.run.app"

def populate():
    """Call the batch_analyze function to populate all players at once."""
    print(f"Starting batch population using: {BATCH_FUNCTION_URL}")
    print("This will analyze ALL players in ONE request...\n")
    
    try:
        with urllib.request.urlopen(BATCH_FUNCTION_URL, timeout=300.0) as response:
            status_code = response.getcode()
            response_text = response.read().decode('utf-8')
            
            if status_code == 200:
                result = json.loads(response_text)
                print("=" * 50)
                print("SUCCESS!")
                print(f"Status: {result.get('status')}")
                print(f"Message: {result.get('message')}")
                print(f"Players processed: {result.get('players_processed')}")
                print(f"AI analyzed: {result.get('ai_analyzed')}")
                print("=" * 50)
            else:
                print(f"FAILED: {status_code}")
                print(response_text)
                
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code}")
        print(e.read().decode('utf-8'))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    populate()
