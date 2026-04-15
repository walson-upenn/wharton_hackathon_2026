from openai import OpenAI
from flask import current_app


def init_openai(app) -> None:
    api_key = app.config.get("OPENAI_API_KEY")
    if not api_key:
        app.extensions["openai_client"] = None
        return

    app.extensions["openai_client"] = OpenAI(api_key=api_key)


def get_openai_client() -> OpenAI:
    client = current_app.extensions.get("openai_client")
    if client is None:
        raise RuntimeError("OpenAI client has not been initialized.")
    return client


def chat(
    message: str,
    model: str = "gpt-5.4",
    instructions: str = "You are a helpful assistant."
) -> str:
    client = get_openai_client()
    response = client.responses.create(
        model=model,
        instructions=instructions,
        input=message,
    )
    return response.output_text
