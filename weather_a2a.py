import os
import vertexai
from vertexai import agent_engines
from vertexai.preview.reasoning_engines import A2aAgent
from a2a.types import AgentCard, AgentCapabilities, AgentSkill


def _get_maps_api_key() -> str:
    """Read Maps API key from Secret Manager at runtime."""
    from google.cloud import secretmanager
    client = secretmanager.SecretManagerServiceClient()
    response = client.access_secret_version(
        request={"name": f"projects/{os.environ.get('GOOGLE_CLOUD_PROJECT', '')}/secrets/drone-maps-api-key/versions/latest"}
    )
    return response.payload.data.decode("UTF-8")


async def get_lat_long(city: str) -> dict:
    """Use Google Maps MCP to get latitude and longitude for a city."""
    from fastmcp import Client
    from fastmcp.client.transports import StreamableHttpTransport
    maps_api_key = _get_maps_api_key()
    transport = StreamableHttpTransport(
        url="https://mapstools.googleapis.com/mcp",
        headers={"X-Goog-Api-Key": maps_api_key},
    )
    async with Client(transport) as client:
        result = await client.call_tool("search_places", {"text_query": city})
        places = (result.structured_content or {}).get("places", [])
        if places:
            loc = places[0].get("location", {})
            return {"latitude": loc.get("latitude"), "longitude": loc.get("longitude")}
        return {"latitude": None, "longitude": None}


def get_weather(latitude: float, longitude: float) -> str:
    """Fetch 3-day forecast from the National Weather Service API."""
    import requests
    headers = {"User-Agent": "DroneWeatherA2A/1.0"}
    pts = requests.get(
        f"https://api.weather.gov/points/{latitude},{longitude}",
        headers=headers, timeout=10,
    )
    forecast_url = pts.json()["properties"]["forecast"]
    forecast = requests.get(forecast_url, headers=headers, timeout=10)
    periods = forecast.json()["properties"]["periods"]
    return "\n".join([
        f"{p['name']}: {p['temperature']}\u00b0{p['temperatureUnit']}, "
        f"{p['shortForecast']}, Wind: {p['windSpeed']} {p['windDirection']}"
        for p in periods[:3]
    ])


def build_weather_executor():
    import os
    from google.adk.agents import Agent
    from google.adk.models import Gemini
    from google.adk.runners import Runner
    from google.adk.sessions import VertexAiSessionService
    from google.genai import types as genai_types
    from a2a.server.agent_execution import AgentExecutor, RequestContext
    from a2a.server.events import EventQueue
    from a2a.server.tasks import TaskUpdater
    from a2a.types import Part, TextPart, UnsupportedOperationError
    from a2a.utils.errors import ServerError

    app_name = os.environ.get("GOOGLE_CLOUD_AGENT_ENGINE_ID", "WeatherAssistant")
    _sessions = VertexAiSessionService()
    _runner = Runner(
        app_name=app_name,
        agent=Agent(
            name="WeatherAssistant",
            model=Gemini(model="gemini-2.5-flash"),
            instruction=(
                "You are a flight-safety weather assistant for drone operators.\n"
                "1. Use get_lat_long to find the city coordinates.\n"
                "2. Use get_weather to fetch the 3-day forecast.\n"
                "3. Analyse each period wind speed carefully:\n"
                "   - winds > 15mph: say GROUNDED — too risky for drone flight.\n"
                "   - winds 10-15mph: say CAUTION — flyable but challenging.\n"
                "   - winds < 10mph: say SAFE — good conditions.\n"
                "4. Report the forecast for all 3 periods and give a final overall recommendation."
            ),
            tools=[get_lat_long, get_weather],
        ),
        session_service=_sessions,
    )

    class WeatherAgentExecutor(AgentExecutor):
        async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
            updater = TaskUpdater(event_queue, context.task_id, context.context_id)
            await updater.start_work()
            query = context.get_user_input()
            session_id = context.context_id
            try:
                await _sessions.create_session(app_name=app_name, user_id="a2a-user", session_id=session_id)
            except Exception:
                pass
            user_msg = genai_types.Content(role="user", parts=[genai_types.Part(text=query)])
            try:
                full_text = ""
                for event in _runner.run(user_id="a2a-user", session_id=session_id, new_message=user_msg):
                    if hasattr(event, "is_final_response") and event.is_final_response():
                        if hasattr(event, "content") and event.content:
                            for p in event.content.parts:
                                if hasattr(p, "text") and p.text:
                                    full_text = p.text
                                    break
                        break
                    if hasattr(event, "content") and event.content:
                        for p in event.content.parts:
                            if hasattr(p, "text") and p.text:
                                full_text = p.text
                                break
                reply = updater.new_agent_message(parts=[Part(root=TextPart(text=full_text or "No response."))])
                await updater.complete(message=reply)
            except Exception as e:
                err = updater.new_agent_message(parts=[Part(root=TextPart(text=f"Error: {e}"))])
                await updater.failed(message=err)

        async def cancel(self, context, event_queue):
            raise ServerError(UnsupportedOperationError())

    return WeatherAgentExecutor()


weather_agent_card = AgentCard(
    name="WeatherAssistant", version="1.0.0", protocolVersion="0.3.0",
    preferredTransport="HTTP+JSON",
    description="Drone weather safety agent — real forecasts via Google Maps MCP + NWS.",
    defaultInputModes=["TEXT"], defaultOutputModes=["TEXT"],
    url="http://placeholder.url",
    capabilities=AgentCapabilities(streaming=False),
    skills=[AgentSkill(id="get_weather_forecast", name="Detailed Weather Forecast",
                       description="3-day forecasts for US cities via Google Maps and NWS.",
                       tags=["Weather", "Forecasting", "DroneSafety"])],
)
print("Weather Agent code defined.")
weather_app = A2aAgent(agent_card=weather_agent_card, agent_executor_builder=build_weather_executor)