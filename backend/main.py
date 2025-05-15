from typing import Dict, Any
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from prompt import build_prompt
from openai import OpenAI
from dotenv import load_dotenv
from anomaly_checker import extract_anomalies

import os

# Load environment variables from .env
load_dotenv()

# Initialize OpenAI client (e.g., for Groq)
client = OpenAI(
    api_key=os.getenv("OPENAI_API_KEY"),
    base_url=os.getenv("OPENAI_API_BASE")  # e.g., https://api.groq.com/openai/v1
)

# Initialize FastAPI app
app = FastAPI()

# Enable CORS for frontend requests (adjust allowed origins as needed)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or use ["http://localhost:8080"] for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def analyze_telemetry(telemetry_data: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze telemetry data and return processed statistics."""
    print("\n=== 📊 Processing Flight Statistics ===")
    
    def calculate_stats(values, name):
        """Calculate basic statistics for a list of values."""
        if not values:
            return None
        stats = {
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "total_points": len(values)
        }
        print(f"✓ {name} stats: min={stats['min']:.2f}, max={stats['max']:.2f}, avg={stats['avg']:.2f}")
        return stats
    
    def process_attitude_data(attitude_data):
        """Process attitude data with detailed statistics."""
        if not attitude_data:
            return None
            
        # Extract roll, pitch, yaw from attitude data
        roll_values = []
        pitch_values = []
        yaw_values = []
        timestamps = []
        
        for timestamp, values in attitude_data.items():
            if len(values) >= 3:
                roll_values.append(values[0])
                pitch_values.append(values[1])
                yaw_values.append(values[2])
                timestamps.append(float(timestamp))
        
        if not roll_values:
            return None
            
        return {
            "roll": calculate_stats(roll_values, "Roll"),
            "pitch": calculate_stats(pitch_values, "Pitch"),
            "yaw": calculate_stats(yaw_values, "Yaw"),
            "time_range": {
                "start": min(timestamps),
                "end": max(timestamps),
                "duration": max(timestamps) - min(timestamps)
            }
        }
    
    def process_trajectory_data(trajectory):
        """Process trajectory data with geographic bounds and statistics."""
        if not trajectory or not isinstance(trajectory, list) or len(trajectory) < 1:
            return None
            
        # Extract lat, lon, alt from trajectory points
        lats = [p[1] for p in trajectory if len(p) > 2]
        lons = [p[0] for p in trajectory if len(p) > 2]
        alts = [p[2] for p in trajectory if len(p) > 2]
        
        stats = {
            "bounds": {
                "latitude": calculate_stats(lats, "Latitude"),
                "longitude": calculate_stats(lons, "Longitude"),
                "altitude": calculate_stats(alts, "Altitude")
            },
            "total_points": len(trajectory),
            "distance_traveled": 0  # TODO: Calculate actual distance
        }
        
        # Calculate some basic flight characteristics
        if len(trajectory) > 1:
            stats["flight_characteristics"] = {
                "start_point": trajectory[0],
                "end_point": trajectory[-1],
                "duration": trajectory[-1][3] - trajectory[0][3] if len(trajectory[0]) > 3 else None
            }
        
        return stats
    
    def process_mavlink_messages(messages):
        """Process raw MAVLink messages for additional flight data."""
        if not messages:
            return {}
            
        stats = {}
        
        # Process VFR_HUD data if available
        if 'VFR_HUD' in messages:
            vfr_data = messages['VFR_HUD']
            for field in ['airspeed', 'groundspeed', 'alt', 'climb']:
                if field in vfr_data:
                    stats[f'vfr_{field}'] = calculate_stats(vfr_data[field], f'VFR {field}')
        
        # Process GPS data if available
        if 'GPS' in messages:
            gps_data = messages['GPS']
            if 'vel' in gps_data:
                stats['gps_velocity'] = calculate_stats(gps_data['vel'], 'GPS Velocity')
        
        # Process direct airspeed sensor data
        for sensor in ['ARSP', 'ASP2']:
            if sensor in messages and 'airspeed' in messages[sensor]:
                stats[f'{sensor.lower()}_airspeed'] = calculate_stats(
                    messages[sensor]['airspeed'],
                    f'{sensor} Airspeed'
                )
        
        return stats

    # Start processing all data
    processed = {
        # Process core flight data
        "attitude": process_attitude_data(telemetry_data.get('attitude')),
        "trajectory": process_trajectory_data(telemetry_data.get('trajectory')),
        
        # Process flight modes
        "flight_modes": {
            "sequence": telemetry_data.get('flightModes', []),
            "total_changes": len(telemetry_data.get('flightModes', [])),
            "modes_used": list(set(mode[1] for mode in telemetry_data.get('flightModes', []) if len(mode) > 1))
        }
    }
    
    # Add processed MAVLink message data
    mavlink_stats = process_mavlink_messages(telemetry_data.get('messages', {}))
    processed.update(mavlink_stats)
    
    # Calculate flight duration and metadata
    if processed["attitude"] and processed["attitude"]["time_range"]:
        duration = processed["attitude"]["time_range"]["duration"]
    elif processed["trajectory"] and processed["trajectory"].get("flight_characteristics", {}).get("duration"):
        duration = processed["trajectory"]["flight_characteristics"]["duration"]
    else:
        duration = None
    
    processed["metadata"] = {
        "duration": duration,
        "vehicle_type": (
            next((mode[1] for mode in telemetry_data.get('flightModes', []) 
                 if mode[1] in ["MANUAL", "STABILIZE", "AUTO", "GUIDED", "QLOITER", "QLAND"]), 
            "unknown")
        ),
        "data_sources": list(telemetry_data.get('messages', {}).keys())
    }
    
    print("\n=== Analysis Summary ===")
    print(f"Total data types processed: {len(processed)}")
    print(f"Available metrics: {[k for k, v in processed.items() if v is not None]}")
    print(f"Vehicle type: {processed['metadata']['vehicle_type']}")
    if duration:
        print(f"Flight duration: {duration:.1f} seconds")
    print("=" * 30 + "\n")
    
    return processed

# Define request schemas
class TelemetryData(BaseModel):
    telemetry: Dict[str, Any]

class ChatRequest(BaseModel):
    question: str
    telemetry: Dict[str, Any]

@app.post("/analyze_telemetry")
async def analyze(data: TelemetryData):
    """Endpoint to analyze telemetry data when file is first loaded."""
    processed_data = analyze_telemetry(data.telemetry)
    
    print("\n=== Telemetry Analysis Results ===")
    print("\n1. Flight Overview:")
    print(f"Duration: {processed_data['metadata']['duration']} seconds")
    print(f"Vehicle Type: {processed_data['metadata']['vehicle_type']}")
    
    print("\n2. Data Points Available:")
    for key, count in processed_data['metadata']['data_points'].items():
        print(f"- {key}: {count} points")
    
    print("\n3. Flight Characteristics:")
    if processed_data.get('altitude'):
        alt = processed_data['altitude']
        print(f"Altitude - Min: {alt.get('min', 'N/A')}m, Max: {alt.get('max', 'N/A')}m, Avg: {alt.get('avg', 'N/A')}m")
    
    if processed_data.get('airspeed'):
        speed = processed_data['airspeed']
        print(f"Airspeed - Min: {speed.get('min', 'N/A')}m/s, Max: {speed.get('max', 'N/A')}m/s, Avg: {speed.get('avg', 'N/A')}m/s")
    
    if processed_data.get('flightModes'):
        modes = processed_data['flightModes']
        print("\n4. Flight Modes:")
        print(f"Total Changes: {modes.get('total_changes', 0)}")
        print(f"Modes Used: {', '.join(modes.get('modes_used', []))}")
    
    if processed_data.get('trajectory'):
        traj = processed_data['trajectory']
        print("\n5. Geographic Bounds:")
        bounds = traj.get('bounds', {})
        print(f"Latitude: {bounds.get('lat', {}).get('min', 'N/A')} to {bounds.get('lat', {}).get('max', 'N/A')}")
        print(f"Longitude: {bounds.get('lon', {}).get('min', 'N/A')} to {bounds.get('lon', {}).get('max', 'N/A')}")
    
    return {"analysis": processed_data}

def display_final_data(processed_data: Dict[str, Any]):
    """Display the final processed data structure that will be sent to LLM."""
    print("\n=== 🤖 Final Data Structure for LLM ===")
    
    def format_value(value, indent=0):
        """Format a value for display with proper indentation."""
        indent_str = "  " * indent
        if isinstance(value, dict):
            if not value:
                return f"{indent_str}{{}}"
            lines = ["{"]
            for k, v in value.items():
                lines.append(f"{indent_str}  {k}: {format_value(v, indent + 1)}")
            lines.append(f"{indent_str}}}")
            return "\n".join(lines)
        elif isinstance(value, list):
            if not value:
                return "[]"
            if len(value) > 3:
                return f"[{value[0]}, ... ({len(value)} items)]"
            return str(value)
        elif isinstance(value, float):
            return f"{value:.2f}"
        else:
            return str(value)

    # Display core flight data
    print("\n1. Core Flight Data:")
    if processed_data.get("attitude"):
        print("\n📊 Attitude Statistics:")
        print(format_value(processed_data["attitude"], 1))
    
    if processed_data.get("trajectory"):
        print("\n🛫 Trajectory Analysis:")
        print(format_value(processed_data["trajectory"], 1))
    
    if processed_data.get("flight_modes"):
        print("\n🔄 Flight Modes:")
        print(format_value(processed_data["flight_modes"], 1))
    
    # Display speed and movement data
    print("\n2. Speed and Movement Data:")
    speed_fields = [k for k in processed_data.keys() if any(x in k.lower() for x in ['speed', 'velocity', 'vfr'])]
    for field in speed_fields:
        print(f"\n💨 {field}:")
        print(format_value(processed_data[field], 1))
    
    # Display position and altitude data
    print("\n3. Position and Altitude Data:")
    position_fields = [k for k in processed_data.keys() if any(x in k.lower() for x in ['gps', 'alt', 'position'])]
    for field in position_fields:
        print(f"\n📍 {field}:")
        print(format_value(processed_data[field], 1))
    
    # Display metadata
    if processed_data.get("metadata"):
        print("\n4. Flight Metadata:")
        print(format_value(processed_data["metadata"], 1))
    
    print("\n=== End of Data Structure ===")
    print("=" * 50)

@app.post("/chat")
async def chat(req: ChatRequest):
    """Endpoint for chat interactions using processed telemetry data."""
    
    # Process telemetry for structured analysis
    processed_data = analyze_telemetry(req.telemetry)
    
    # Prepare data for prompt building
    data = {
        "raw_data": {
            "attitude": req.telemetry.get("attitude", {}),
            "trajectory": req.telemetry.get("trajectory", []),
            "flightModes": req.telemetry.get("flightModes", []),
            "messages": req.telemetry.get("messages", {})
        },
        "processed_data": processed_data
    }
    
    # Build dynamic prompt based on question context
    prompt = build_prompt(req.question, data)
    
    print("\nProcessing Question:", req.question)
    print("Using dynamic prompt with relevant data sections:")
    print("- Base flight overview and statistics")
    if "TEMPORAL ANALYSIS:" in prompt:
        print("- Temporal analysis included")
    if "ANOMALY ANALYSIS:" in prompt:
        print("- Anomaly analysis included")
    if "SYSTEM PERFORMANCE:" in prompt:
        print("- System performance included")
    print("=" * 50)
    
    # Call LLM via OpenAI-compatible API (Groq)
    response = client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[
            {"role": "system", "content": prompt}
        ]
    )

    return {"answer": response.choices[0].message.content}
