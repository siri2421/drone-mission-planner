import vertexai
from vertexai import agent_engines

vertexai.init(project=PROJECT_ID, location=LOCATION)

planner = agent_engines.get(PLANNER_RESOURCE)

# Create a session
session = planner.create_session(user_id="demo-user")
session_id = session["id"]
print(f"Session created: {session_id}\n")

def run_mission_stream(query: str) -> str:
    """Run a mission query via stream_query() and return the final text response."""
    full_text = ""
    for event in planner.stream_query(
        message=query,
        session_id=session_id,
        user_id="demo-user",
    ):
        if "content" in event and "parts" in event["content"]:
            for part in event["content"]["parts"]:
                if "text" in part:
                    full_text = part["text"]
    return full_text

print("=" * 60)
print("DEMO — Drone Mission Planner via stream_query()")
print("=" * 60)
print()

missions = [
    "Plan a drone delivery mission in Austin, Texas.",
    "Can I fly a delivery drone in Chicago today?",
    "Approve a survey drone flight in Miami, Florida.",
]

for mission in missions:
    print(f"MISSION: {mission}")
    response = run_mission_stream(mission)
    print(f"DECISION:\n{response}")
    print("-" * 60)
    print()
