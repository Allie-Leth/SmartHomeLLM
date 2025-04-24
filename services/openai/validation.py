import openai
import json
from services.openai.schema import smart_home_command_schema
from jsonschema import validate, ValidationError

class OpenAIValidator:
    def __init__(self, api_key=None, gpt_id=None):
        self.api_key = api_key or openai.api_key
        self.gpt_id = gpt_id  # ID of your prebuilt custom GPT (e.g., 'g-abc123')
        self.model = "gpt-4-1106-preview"  # used only for fallback targeting

    def get_schema(self):
        return smart_home_command_schema

    def validate(self, response_text):
        """
        Validates the given JSON text against the smart home command schema.
        Returns (bool, parsed_json or None)
        """
        try:
            parsed = json.loads(response_text)
            validate(instance=parsed, schema=self.get_schema())
            return True, parsed
        except (json.JSONDecodeError, ValidationError):
            return False, None

    def fallback(self, transcript, raw_response):
        """
        Calls your custom GPT by ID to produce a corrected command.
        Returns (bool, parsed_command_dict or None)
        """
        try:
            response = openai.ChatCompletion.create(
                model=self.model,
                gpt=self.gpt_id,
                temperature=0.0,
                messages=[
                    {"role": "user", "content": f"Transcript: {transcript}\nInvalid output: {raw_response}"}
                ]
            )
            fixed = response.choices[0].message.content
            fixed_parsed = json.loads(fixed)
            return True, fixed_parsed
        except Exception as e:
            print(f"❌ OpenAI fallback error: {e}")
            return False, None

    def validate_or_fallback(self, response_text, transcript):
        valid, parsed = self.validate(response_text)
        if valid:
            return True, parsed
        return self.fallback(transcript, response_text)