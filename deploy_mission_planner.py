vertexai.init(project=PROJECT_ID, location=LOCATION, staging_bucket=STAGING_BUCKET)

app = AdkApp(agent=planner_agent)

print("Deploying Drone Mission Planner (AdkApp + sub_agents + Agent Identity) — takes 3-5 minutes...")
planner_remote = agent_engines.create(
    app,
    display_name="Drone_Mission_Planner_v3_AR",
    requirements=[
        "google-adk[a2a]==1.30.0",
        "a2a-sdk==0.3.26",
        "google-auth>=2.29.0",
        "opentelemetry-instrumentation-google-genai",
        "opentelemetry-instrumentation-httpx",
        "opentelemetry-instrumentation-vertexai",
        "setuptools",
        "pydantic>=2.0.0",
    ],
    env_vars={
        "WEATHER_AGENT_RESOURCE": WEATHER_AGENT_RESOURCE,
        "GOOGLE_GENAI_USE_VERTEXAI": "1",
        "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY": "true",
        "OTEL_INSTRUMENTATION_GENAI_CAPTURE_MESSAGE_CONTENT": "SPAN_AND_EVENT",
        "OTEL_INSTRUMENTATION_GENAI_UPLOAD_FORMAT": "jsonl",
        "OTEL_INSTRUMENTATION_GENAI_COMPLETION_HOOK": "upload",
        "OTEL_SEMCONV_STABILITY_OPT_IN": "gen_ai_latest_experimental",
        "OTEL_INSTRUMENTATION_GENAI_UPLOAD_BASE_PATH": f"gs://{BUCKET_NAME}",
    },
    service_account=PLANNER_SA,
)

PLANNER_RESOURCE = planner_remote.resource_name

