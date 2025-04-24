# services/response_parser.py

import json
import asyncio

from utils.validation import is_valid_command_structure, handle_invalid_response

class ResponseParser:
    """
    Processes raw GPT responses:
      1. Validates JSON against schema.
      2. Falls back to repair if invalid.
      3. Dispatches the final command via an optional dispatcher.
    """

    def __init__(self, dispatcher=None):
        """
        :param dispatcher: An object with an async dispatch(command: dict) method.
        """
        self.dispatcher = dispatcher

    async def process(self, raw_content: str, transcript: str):
        """
        Process a single GPT response:
          - Validate the raw JSON content.
          - If invalid, attempt fallback repair.
          - Print the 'speak' field.
          - Dispatch the 'command' via the dispatcher, if provided.

        :param raw_content: The raw 'content' field from the GPT response.
        :param transcript: The last user transcript for context in fallback.
        """
        valid, parsed = is_valid_command_structure(raw_content)

        if not valid:
            print("⚠️ Response failed validation, attempting fallback repair…")
            fixed = handle_invalid_response(raw_content, transcript)
            if not fixed:
                print("🛑 Could not recover a valid response. Dropping message.")
                return
            parsed = json.loads(fixed)

        # At this point, parsed is guaranteed to be a dict matching schema
        speak = parsed.get('speak')
        command = parsed.get('command')

        print(f"🗣️ {speak}")
        print(f"⚙️ Command: {command}")

        # Dispatch the command if a dispatcher is set
        if self.dispatcher:
            await self.dispatcher.dispatch(command)
