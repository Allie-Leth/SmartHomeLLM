import json
from jsonschema import validate, ValidationError
from services.openai.schema import smart_home_command_schema
from services.openai.validation import OpenAIValidator

validator = OpenAIValidator()

def is_valid_command_structure(response_text):
    """
    Attempts to parse and validate the GPT response as JSON
    matching the smart_home_command_schema.

    Returns:
        (bool, dict | None): Tuple of (is_valid, parsed_json_or_none)
    """
    try:
        parsed = json.loads(response_text)
        validate(instance=parsed, schema=smart_home_command_schema)
        return True, parsed
    except (json.JSONDecodeError, ValidationError):
        return False, None

def get_validation_error_details(response_text):
    """
    Returns full error details for debugging or fallback handling.
    """
    try:
        parsed = json.loads(response_text)
        validate(instance=parsed, schema=smart_home_command_schema)
        return None  # No error
    except json.JSONDecodeError as e:
        return f"JSON Decode Error: {e.msg}"
    except ValidationError as e:
        return f"Schema Validation Error: {e.message}"

def handle_invalid_response(response_text, transcript=None):
    """
    Attempts to validate the response. If invalid and a transcript is available,
    it routes to OpenAIValidator's fallback to repair the structure.
    """
    error = get_validation_error_details(response_text)
    print(f"❌ Invalid response. Reason: {error}")

    if transcript:
        print("🔁 Attempting fallback repair using OpenAIValidator...")
        success, fixed_json = validator.fallback(transcript, response_text)
        if success:
            print("✅ Recovered structured output:")
            print(fixed_json)
            return fixed_json
        else:
            print("❌ Fallback also failed.")
            return None
    return None