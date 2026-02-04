# nextgenpicks
some ios app

notes to run the backend: firebase deploy --only functions
to change the scraper frequency: go to batch_analyze_py, line 563
to scrape for current data: curl "https://us-central1-nextgenpicks-fb759.cloudfunctions.net/batch_analyze"