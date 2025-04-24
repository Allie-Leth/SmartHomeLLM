smart_home_command_schema = {
    "type": "object",
    "required": ["speak", "command"],
    "properties": {
        "speak": {"type": "string"},
        "command": {
            "anyOf": [
                {
                    "type": "object",
                    "required": ["action", "device", "target"],
                    "properties": {
                        "action": {
                            "type": "string",
                            "enum": ["turn_on", "turn_off", "set_brightness", "set_temperature", "lock", "unlock"]
                        },
                        "device": {
                            "type": "string",
                            "enum": ["lights", "thermostat", "door", "fan"]
                        },
                        "target": {
                            "anyOf": [
                                {"type": "string", "enum": ["red", "blue", "green"]},
                                {
                                    "type": "array",
                                    "items": {"type": "string", "enum": ["red", "blue", "green"]},
                                    "minItems": 1,
                                    "maxItems": 3,
                                    "uniqueItems": True
                                }
                            ]
                        }
                    }
                },
                {"type": "null"}
            ]
        }
    }
}

fallback_repair_schema = {
    "type": "object",
    "required": ["transcript", "raw_response"],
    "properties": {
        "transcript": {"type": "string"},
        "raw_response": {"type": "string"}
    }
}