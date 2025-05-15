def extract_anomalies(telemetry):
    anomalies = []
    trajectory = telemetry.get("trajectory", [])

    for i in range(1, len(trajectory)):
        try:
            alt_i = trajectory[i].get("alt") if isinstance(trajectory[i], dict) else trajectory[i][3]
            alt_prev = trajectory[i - 1].get("alt") if isinstance(trajectory[i - 1], dict) else trajectory[i - 1][3]
            dz = alt_i - alt_prev
            if abs(dz) > 20:
                anomalies.append(f"Sudden altitude change of {dz:.1f}m at point {i}.")
        except Exception as e:
            anomalies.append(f"[Warning] Could not parse trajectory data at point {i}: {str(e)}")
            break

    return anomalies
