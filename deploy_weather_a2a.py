




vertexai.init(project=PROJECT_ID, location=LOCATION, staging_bucket=STAGING_BUCKET)

weather_app = A2aAgent(agent_card=weather_agent_card, agent_executor_builder=build_weather_executor)

print("Deploying Weather Agent — takes 3-5 minutes...")
weather_remote = agent_engines.create(
    weather_app,
    display_name="Weather_Drone_A2A",
    requirements=[
        "google-adk[a2a]==1.30.0",
        "a2a-sdk==0.3.26",
        "fastmcp>=2.0.0",
        "httpx",
        "requests",
        "google-cloud-secret-manager",
        "opentelemetry-instrumentation-google-genai",
        "opentelemetry-instrumentation-httpx",
        "opentelemetry-instrumentation-vertexai",
        "setuptools",
        "pydantic>=2.0.0",
    ],
    env_vars={
        "GOOGLE_GENAI_USE_VERTEXAI": "1",
        "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
        "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "SPAN_AND_EVENT",
        "OTEL_INSTRUMENTATION_GENAI_UPLOAD_FORMAT": "jsonl",
        "OTEL_INSTRUMENTATION_GENAI_COMPLETION_HOOK": "upload",
        "OTEL_SEMCONV_STABILITY_OPT_IN": "gen_ai_latest_experimental",
        "OTEL_INSTRUMENTATION_GENAI_UPLOAD_BASE_PATH": f"gs://{BUCKET_NAME}",
    },
)

WEATHER_AGENT_RESOURCE = weather_remote.resource_name
print(f"\nWeather Agent deployed!")
print(f"Resource: {WEATHER_AGENT_RESOURCE}")
print(f"\n*** Save this resource name ***")
