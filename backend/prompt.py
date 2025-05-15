from typing import Dict, Any
from data_extractor import DataExtractor

def build_prompt(question: str, data: Dict[str, Any]) -> str:
    """Build a dynamic prompt based on question context and relevant data."""
    
    raw_data = data.get("raw_data", {})
    processed_data = data.get("processed_data", {})
    
    # Get relevant data based on question context
    relevant_data = DataExtractor.get_relevant_data(question, raw_data, processed_data)
    
    # Build base prompt with essential information
    base_prompt = f"""You are an expert UAV flight data analyst providing direct answers to users' questions about flight data.

AVAILABLE FLIGHT DATA:
Duration: {processed_data.get('metadata', {}).get('duration', 'N/A')} seconds
Vehicle: {processed_data.get('metadata', {}).get('vehicle_type', 'N/A')}

Core Flight Data:
- Attitude (rad): Roll [{processed_data.get('attitude', {}).get('roll', {}).get('min', 'N/A'):.2f} to {processed_data.get('attitude', {}).get('roll', {}).get('max', 'N/A'):.2f}], 
  Pitch [{processed_data.get('attitude', {}).get('pitch', {}).get('min', 'N/A'):.2f} to {processed_data.get('attitude', {}).get('pitch', {}).get('max', 'N/A'):.2f}], 
  Yaw [{processed_data.get('attitude', {}).get('yaw', {}).get('min', 'N/A'):.2f} to {processed_data.get('attitude', {}).get('yaw', {}).get('max', 'N/A'):.2f}]
- Altitude: {processed_data.get('trajectory', {}).get('bounds', {}).get('altitude', {}).get('min', 'N/A'):.1f}m to {processed_data.get('trajectory', {}).get('bounds', {}).get('altitude', {}).get('max', 'N/A'):.1f}m
- Distance: {processed_data.get('trajectory', {}).get('distance_traveled', 'N/A')}m"""

    # Add context-specific data sections
    if relevant_data['temporal']:
        base_prompt += f"\n\nTime-based Data:\n{relevant_data['temporal']}"

    if relevant_data['anomaly']:
        base_prompt += f"\n\nAnomalies Detected:\n{relevant_data['anomaly']}"

    if relevant_data['system']:
        base_prompt += f"\n\nSystem Status:\n{relevant_data['system']}"

    # Add question and response instructions
    base_prompt += f"""

USER QUESTION: {question}

RESPONSE INSTRUCTIONS:
1. Provide a direct, clear answer to the user's question
2. Use natural, conversational language
3. Format the response with appropriate spacing and sections for readability
4. Focus on what we know from the data, clearly state if something is unavailable
5. Don't explain your analysis process or mention data limitations unless specifically asked
6. Use bullet points or numbered lists for multiple points
7. Keep the tone helpful and informative

Remember: You are speaking directly to the user. Don't say "Based on the data..." or "The telemetry shows..." - just give the information directly and clearly."""

    return base_prompt
