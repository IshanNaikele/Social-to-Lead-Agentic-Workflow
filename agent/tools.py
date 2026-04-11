from langchain_core.tools import tool

@tool
def mock_lead_capture(name: str, email: str, platform: str) -> str:
    """
    Captures a qualified lead. Call this ONLY when name, email,
    and platform have all been explicitly provided by the user.
    """
    print(f"\n✅ Lead captured successfully: {name}, {email}, {platform}\n")
    return f"Lead captured: {name} | {email} | {platform}"