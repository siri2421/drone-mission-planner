import os
import vertexai
from vertexai import agent_engines
from vertexai.preview.reasoning_engines import AdkApp
from google.adk.agents import Agent
from google.adk.agents.remote_a2a_agent import RemoteA2aAgent
from google.adk.models import Gemini
import httpx as _httpx
from a2a.client import ClientFactory, ClientConfig
from a2a.client.transports import RestTransport
from a2a.types import AgentCard, AgentCapabilities, AgentSkill, TransportProtocol


# ---------------------------------------------------------------------------
# GCP Auth — lazy init so credentials are never baked into the cloudpickle.
# Credentials are obtained from the metadata server on the first request
# inside the Agent Engine container.
# ---------------------------------------------------------------------------

class _GcpAuth(_httpx.Auth):
    def __init__(self):
        self._credentials = None
        self._transport_request = None

    def _ensure_valid(self):
        import google.auth
        import google.auth.transport.requests as _greq
        if self._credentials is None:
            self._credentials, _ = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            self._transport_request = _greq.Request()
        if not self._credentials.valid:
            self._credentials.refresh(self._transport_request)

    def auth_flow(self, request):
        self._ensure_valid()
        request.headers["Authorization"] = f"Bearer {self._credentials.token}"
        yield request


def _make_auth_transport(card, url, config, interceptors):
    """Fresh httpx.AsyncClient per A2A call — avoids RLock deepcopy and event loop issues."""
    return RestTransport(
        _httpx.AsyncClient(
            timeout=120,
            headers={"Content-Type": "application/json"},
            auth=_GcpAuth(),
        ),
        card, url, interceptors, None,
    )


_authenticated_factory = ClientFactory(
    ClientConfig(
        supported_transports=[TransportProtocol.http_json],
        use_client_preference=True,
    )
)
_authenticated_factory.register(TransportProtocol.http_json, _make_auth_transport)


# ---------------------------------------------------------------------------
# RemoteA2aAgent — ADK-native A2A client for the Weather Agent.
# Agent Engine does not expose /.well-known/agent-card.json so the card
# is constructed directly here.
# ---------------------------------------------------------------------------

def _build_weather_agent(weather_resource: str) -> RemoteA2aAgent:
    resource_parts = weather_resource.split("/")
    location = resource_parts[3]
    weather_a2a_url = (
        f"https://{location}-aiplatform.googleapis.com/v1beta1/{weather_resource}/a2a"
    )

    weather_card = AgentCard(
        name="WeatherAssistant", version="1.0.0", protocolVersion="0.3.0",
        preferredTransport="HTTP+JSON",
        description="Drone weather safety agent — real forecasts via Google Maps MCP + NWS.",
        defaultInputModes=["TEXT"], defaultOutputModes=["TEXT"],
        url=weather_a2a_url,
        capabilities=AgentCapabilities(streaming=False),
        skills=[AgentSkill(
            id="get_weather_forecast", name="Detailed Weather Forecast",
            description="3-day forecasts for US cities using Google Maps and NWS.",
            tags=["Weather", "Forecasting", "DroneSafety"],
        )],
    )

    return RemoteA2aAgent(
        name="WeatherAssistant",
        description=(
            "Drone weather safety agent. Checks real-time conditions for a city "
            "and returns a 3-day forecast with SAFE, CAUTION, or GROUNDED status."
        ),
        agent_card=weather_card,
        a2a_client_factory=_authenticated_factory,
    )


planner_agent = Agent(
    name="DroneMissionPlanner",
    model=Gemini(model="gemini-2.5-flash"),
    instruction=(
        "You are a drone mission planner. When asked to plan or approve a "
        "drone mission, always delegate to WeatherAssistant first to check "
        "weather conditions for the relevant city. Include the user's full "
        "original request when calling WeatherAssistant so the weather agent "
        "has complete context. "
        "If the status is SAFE — approve the mission with details. "
        "If CAUTION — approve with a warning about challenging conditions. "
        "If GROUNDED — reject it and explain the weather conditions."
    ),
    sub_agents=[_build_weather_agent(WEATHER_AGENT_RESOURCE)],
)

print("Drone Mission Planner code defined.")
print(f"  Framework: AdkApp (adk-app)")
print(f"  Sub-agent: WeatherAssistant via RemoteA2aAgent")
print(f"  Weather Agent: {WEATHER_AGENT_RESOURCE}")
