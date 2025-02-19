import datetime
import os.path
from dateutil import parser
import pytz  

# Google API Tools
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

###########################################################################################
# Next Step is Integrating Deepseek AI to automate intelligently based on given scenarios #
###########################################################################################

SCOPES = ["https://www.googleapis.com/auth/calendar"]
SESSION_DURATION = datetime.timedelta(minutes=90) 
DATA_MANAGEMENT_DURATION = datetime.timedelta(minutes=60) 
TIMEZONE = "America/Toronto"

SUBJECTS = [
    ("Physics", 11),
    ("Calculus and Vectors", 7),
    ("English", 8),
    ("Data Management", 7),
]

# Authenticates and returns Google Calendar API credentials. 
def authenticate():
    credentials = None
    if os.path.exists("token.json"):
        credentials = Credentials.from_authorized_user_file("token.json")

    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("~/useful_petprojects/calendar_automation/credentials.json", SCOPES)
            credentials = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(credentials.to_json())

    return credentials

# Fetches existing events from Google Calendar. 
def get_events(service):
    now = datetime.datetime.utcnow().isoformat() + "Z"

    try:
        events_result = service.events().list(
            calendarId="primary",
            timeMin=now,
            maxResults=100,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        return events_result.get("items", [])
    except HttpError as error:
        print("An error occurred:", error)
        return []

# Finds available study slots before and after school for the next 7 days.
def get_free_time(events):
    free_slots = []
    tz = pytz.timezone(TIMEZONE)
    today = datetime.datetime.now(tz).replace(hour=4, minute=35, second=0, microsecond=0)

    for _ in range(7):  
        morning_slots = [
            (today.replace(hour=4, minute=30), today.replace(hour=8, minute=0)),
        ]

        afternoon_slots = [
            (today.replace(hour=15, minute=45), today.replace(hour=21, minute=30)),
        ]

        daily_slots = morning_slots + afternoon_slots

        for event in events:

            start = event["start"].get("dateTime") or event["start"].get("date")
            end = event["end"].get("dateTime") or event["end"].get("date")

            if not start or not end:
                continue  

            start = parser.isoparse(start)
            end = parser.isoparse(end)

            if start.tzinfo is None:
                start = tz.localize(start)
            if end.tzinfo is None:
                end = tz.localize(end)

            daily_slots = [slot for slot in daily_slots if not (slot[0] < end and start < slot[1])]

        free_slots.append(daily_slots)
        today += datetime.timedelta(days=1)

    return free_slots

# Schedules a study session in Google Calendar with assigned color ID.
def add_event(service, start_time, end_time, subject, color_id):
    event = {
        "summary": subject,
        "colorId": str(color_id),  
        "start": {"dateTime": start_time.isoformat(), "timeZone": TIMEZONE},
        "end": {"dateTime": end_time.isoformat(), "timeZone": TIMEZONE},
    }

    try:
        service.events().insert(calendarId="primary", body=event).execute()
        print(f"✅ Scheduled {subject} ({start_time.strftime('%Y-%m-%d %H:%M')}) with color ID {color_id}")
    except HttpError as error:
        print("An error occurred while scheduling:", error)

# Allocates study sessions with priority rules.
def schedule_study_sessions(service):
    events = get_events(service)
    free_slots = get_free_time(events)

    for day_index in range(7): 
        slots = free_slots[day_index]  
        today = datetime.datetime.now(pytz.timezone(TIMEZONE)) + datetime.timedelta(days=day_index)

   
        for i, (start_time, end_time) in enumerate(slots):
            if start_time.hour == 4 and start_time.minute == 30:  
                session_start = start_time
                subject_index = 0  
                while session_start + SESSION_DURATION <= end_time and subject_index < 2:
                    session_end = session_start + SESSION_DURATION
                    subject, color_id = SUBJECTS[subject_index]  
                    add_event(service, session_start, session_end, subject, color_id)
                    session_start = session_end
                    subject_index += 1

        for i, (start_time, end_time) in enumerate(slots):
            if start_time.hour == 15 and start_time.minute == 45:  
                if today.weekday() not in [3, 4]:  
                    subjects_order = [0, 1, 2]  
                    for subject_index in subjects_order:
                        if start_time + SESSION_DURATION <= end_time:
                            session_end = start_time + SESSION_DURATION
                            subject, color_id = SUBJECTS[subject_index]
                            add_event(service, start_time, session_end, subject, color_id)
                            start_time = session_end

                    if start_time + DATA_MANAGEMENT_DURATION <= end_time:
                        session_end = start_time + DATA_MANAGEMENT_DURATION
                        subject, color_id = SUBJECTS[3]   
                        add_event(service, start_time, session_end, subject, color_id)
                else:  
                    physics_start = start_time.replace(hour=16, minute=45)
                    subject_index = 0  
                    while physics_start + SESSION_DURATION <= end_time and subject_index < 2:
                        session_end = physics_start + SESSION_DURATION
                        subject, color_id = SUBJECTS[subject_index]  
                        add_event(service, physics_start, session_end, subject, color_id)
                        physics_start = session_end
                        subject_index += 1

def main():
    credentials = authenticate()
    service = build("calendar", "v3", credentials=credentials)

    print("📅 Scheduling study sessions...")
    schedule_study_sessions(service)

if __name__ == "__main__":
    main()