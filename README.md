# NextGenPicks 
A personal iOS analytics app for NBA (currently) player prop betting. Used to replace manual research with an automated and data-driven pipeline that provides the best opportunities everyday.
#
### What it does
Everyday during the NBA season, NextGenPicks will:
<ul>
  <li>Pull more than 200+ props from Underdog Fantasy</li>
  <li>Cross reference stats with NBA API (swar) and ESPN's API endpoint</li>
  <li>Runs an algorithm that scores each prop</li>
  <li>Showcases results through a filterable iOS interface</li>
  <li>Refreshes ourly from 6am to midnight, with full analysis completing in ~3 minutes</li>
</ul>

### Tech Stack:
Backend: Python, Firebase <br>
Data Sources: NBA API (unofficial by swar), ESPN API, Underdog Fantasy API <br>
Database: Firebase Firestore <br>


### Notes:
Repository is public for portfolio purposes and not for public use.

### Limitations:
Quite literally only works for NBA and is not scaled for any other sport. 

### Citations:
functions/batch_analyze.py & functions/retrieve.py & functions/underdog_scraper were heavily AI-Assisted using Claude Code. <br>
Most swift files as a backbone were created by me, but were also AI-Assisted for specific features.
UI designed by me, (lordtimzki).
