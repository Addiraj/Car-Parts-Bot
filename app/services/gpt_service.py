"""
GPT/OpenAI service for natural language understanding and response formatting.
Handles multilingual queries and generates conversational responses.
"""

from typing import Any
from openai import OpenAI
from flask import current_app
from .translation_service import TranslationService
import json
import re

class GPTService:
    """Service for GPT-based natural language understanding and response generation."""

    def __init__(self):
        self.client = None
        api_key = current_app.config.get("OPENAI_API_KEY")
        if api_key:
            self.client = OpenAI(api_key=api_key)
        self.translation_service = TranslationService()

    def extract_intent(self, user_message: str) -> dict[str, Any]:
        """
        Extract intent from user message using GPT.
        Returns: {
            'intent': 'part_number' | 'chassis' | 'car_part' | 'greeting' | 'unknown',
            'entities': {...},
            'language': 'en' | 'ar' | etc.
        }
        """
        if not self.client:
            return self._fallback_intent(user_message)

        model = current_app.config.get("OPENAI_MODEL", "gpt-4o-mini")

        system_prompt = """You are a car parts assistant. Analyze user messages and extract:
1. Intent: one of: 'part_number', 'chassis', 'car_part', 'greeting', 'unknown'
2. Entities:
   - part_number: if user mentions a part number/SKU
   - chassis: if user mentions chassis/VIN number
   - car_make: car manufacturer (Toyota, Nissan, etc.)
   - car_model: car model name
   - part_name: name of the part (alternator, brake pad, etc.)
3. Language: detected language code (en, ar, etc.)

Respond ONLY with valid JSON in this format:
{
  "intent": "...",
  "entities": {...},
  "language": "..."
}
"""

        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.3,
                max_tokens=200,
            )
            
            result = json.loads(response.choices[0].message.content.strip())
            return result
        except Exception:
            return self._fallback_intent(user_message)

    def format_response(
        self, search_results: list[dict], intent: str, language: str = "en"
    ) -> str:
        """
        Format search results into a natural language response.
        Supports multilingual responses.
        """
        if not self.client:
            return self._fallback_response(search_results, language)

        model = current_app.config.get("OPENAI_MODEL", "gpt-4o-mini")

        # Build context about results
        results_text = ""
        if search_results:
            for r in search_results[:5]:  # Limit to top 5 for context
                results_text += f"- {r.get('name', 'N/A')} (Part #{r.get('part_number', 'N/A')})"
                if r.get("price"):
                    results_text += f" - Price: {r.get('price')} AED"
                if r.get("brand"):
                    results_text += f" - Brand: {r.get('brand')}"
                results_text += "\n"
        else:
            results_text = "No parts found matching your query."

        user_prompt = f"""Format the following car parts search results into a friendly, conversational message.
The user's language preference is: {language}

Results:
{results_text}

Provide a helpful response that:
- Greets the user naturally
- Lists the parts found (or mentions if none found)
- Includes prices when available
- Suggests next steps if needed
- Is appropriate for the detected language
"""

        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful car parts assistant. Respond naturally and conversationally.",
                    },
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.7,
                max_tokens=500,
            )
            return response.choices[0].message.content.strip()
        except Exception:
            return self._fallback_response(search_results, language)

    def _fallback_intent(self, message: str) -> dict[str, Any]:
        """Fallback intent extraction without GPT."""
        language = self.translation_service.detect_language(message)
        message_lower = message.lower()

        # Simple keyword-based intent detection
        if any(word in message_lower for word in ["hello", "hi", "hey", "مرحبا"]):
            return {"intent": "greeting", "entities": {}, "language": language or "en"}

        # Check for part number pattern (alphanumeric, often with dashes)
        if re.search(r"\b[A-Z0-9\-]{4,}\b", message.upper()):
            return {"intent": "part_number", "entities": {}, "language": language or "en"}

        # Check for chassis/VIN pattern
        if "chassis" in message_lower or "vin" in message_lower:
            return {"intent": "chassis", "entities": {}, "language": language or "en"}

        # Assume car + part query
        return {"intent": "car_part", "entities": {}, "language": language or "en"}

    def _fallback_response(self, results: list[dict], language: str) -> str:
        """Fallback response formatting without GPT."""
        base_language = language or "en"
        if not results:
            fallback = "Sorry, we couldn't find any parts matching your query. Please try again with different keywords."
            return self._translate_if_needed(fallback, base_language)

        msg = f"Found {len(results)} part(s):\n\n"
        for r in results[:5]:
            msg += f"{r.get('name', 'N/A')} - Part #{r.get('part_number', 'N/A')}"
            if r.get("price"):
                msg += f" | Price: {r.get('price')} AED"
            if r.get("brand"):
                msg += f" | Brand: {r.get('brand')}"
            msg += "\n"

        if len(results) > 5:
            msg += f"\n... and {len(results) - 5} more. Please contact us for details."

        return self._translate_if_needed(msg, base_language)

    def _translate_if_needed(self, text: str, target_language: str) -> str:
        if not target_language or target_language.lower().startswith("en"):
            return text
        return self.translation_service.translate(text, target_language)

