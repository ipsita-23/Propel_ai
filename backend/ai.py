from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
# In a real implementation, we'd use an LLM API client like google.generativeai or openai
# For this simulator, we will use a mocked AI response if no key is provided, or a basic stub.

router = APIRouter(prefix="/ai")

class FieldNote(BaseModel):
    ticket_id: int
    note: str

@router.post("/process_note")
async def process_field_note(payload: FieldNote):
    # This is the AI Feature: Converting free-text to structured data.
    # LLM Prompt would be something like:
    # "Extract the following fields from the lineman's note: cause, component_fixed, action_taken. 
    # Return ONLY valid JSON."
    
    note_lower = payload.note.lower()
    
    # Mocking the AI intelligence for the sake of the exercise
    cause = "Unknown"
    if "tree" in note_lower or "branch" in note_lower or "vegetation" in note_lower:
        cause = "Vegetation"
    elif "fuse" in note_lower or "blown" in note_lower:
        cause = "Equipment Failure (Fuse)"
    elif "jumper" in note_lower or "cut" in note_lower:
        cause = "Cut Jumper"
    elif "snapped" in note_lower or "wire" in note_lower:
        cause = "Snapped Wire"
        
    action = "Repaired"
    if "spliced" in note_lower:
        action = "Spliced"
    elif "replaced" in note_lower:
        action = "Replaced"
    elif "cleared" in note_lower:
        action = "Cleared Debris"

    # The actual LLM integration would sit here.
    return {
        "status": "success",
        "structured_data": {
            "cause": cause,
            "action_taken": action,
            "original_note": payload.note
        }
    }
