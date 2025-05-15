from typing import Dict, Any, List
import re
from datetime import datetime

class DataExtractor:
    """Utility class for extracting relevant data based on question context."""
    
    @staticmethod
    def extract_temporal_data(raw_data: Dict[str, Any], processed_data: Dict[str, Any], question: str) -> Dict[str, Any]:
        """Extract time-relevant data based on the question."""
        # Extract any time references from the question
        time_patterns = {
            'timestamp': r'\d{2}:\d{2}:\d{2}',
            'duration': r'\d+\s*(seconds|minutes|hours)',
            'relative': r'(start|beginning|end|middle|during)'
        }
        
        temporal_data = {}
        
        # Get flight duration from metadata
        flight_duration = processed_data.get('metadata', {}).get('duration', 0)
        
        # Extract messages around relevant timestamps
        messages = raw_data.get('messages', {})
        if messages:
            # Get SYSTEM_TIME messages for time reference
            system_time = messages.get('SYSTEM_TIME', {})
            if system_time:
                temporal_data['time_reference'] = {
                    'boot_time': system_time.get('time_boot_ms', [])[:3],
                    'unix_time': system_time.get('time_unix_usec', [])[:3]
                }
        
        # Add relevant attitude data
        attitude_data = processed_data.get('attitude', {})
        if attitude_data and attitude_data.get('time_range'):
            temporal_data['attitude_timeline'] = {
                'start_time': attitude_data['time_range']['start'],
                'end_time': attitude_data['time_range']['end'],
                'duration': attitude_data['time_range']['duration']
            }
        
        return temporal_data

    @staticmethod
    def extract_anomaly_data(raw_data: Dict[str, Any], processed_data: Dict[str, Any], question: str) -> Dict[str, Any]:
        """Extract data relevant to anomaly detection."""
        anomaly_data = {}
        
        # Check for sudden attitude changes
        attitude = processed_data.get('attitude', {})
        if attitude:
            for axis in ['roll', 'pitch', 'yaw']:
                if attitude.get(axis):
                    stats = attitude[axis]
                    # Check for significant variations
                    if abs(stats['max'] - stats['min']) > 1.0:  # More than 1 radian change
                        anomaly_data[f'{axis}_variation'] = {
                            'range': abs(stats['max'] - stats['min']),
                            'max': stats['max'],
                            'min': stats['min']
                        }
        
        # Check flight modes for unusual changes
        flight_modes = raw_data.get('flightModes', [])
        if flight_modes:
            mode_changes = []
            for i in range(1, min(len(flight_modes), 10)):  # Look at up to 10 mode changes
                if flight_modes[i][1] != flight_modes[i-1][1]:
                    mode_changes.append({
                        'time': flight_modes[i][0],
                        'from': flight_modes[i-1][1],
                        'to': flight_modes[i][1]
                    })
            anomaly_data['mode_changes'] = mode_changes
        
        return anomaly_data

    @staticmethod
    def extract_system_data(raw_data: Dict[str, Any], processed_data: Dict[str, Any], question: str) -> Dict[str, Any]:
        """Extract system-specific performance data."""
        system_data = {}
        
        # Extract relevant system messages
        messages = raw_data.get('messages', {})
        if messages:
            # Extract attitude rates from ATTITUDE message
            if 'ATTITUDE' in messages:
                att_data = messages['ATTITUDE']
                
                # Get angular rates
                rollspeed = att_data.get('rollspeed', [])
                pitchspeed = att_data.get('pitchspeed', [])
                yawspeed = att_data.get('yawspeed', [])
                
                if any([rollspeed, pitchspeed, yawspeed]):
                    system_data['angular_rates'] = {
                        'roll_rate': {
                            'current': f"{rollspeed[-1]:.3f}" if rollspeed else "N/A",
                            'min': f"{min(rollspeed):.3f}" if rollspeed else "N/A",
                            'max': f"{max(rollspeed):.3f}" if rollspeed else "N/A",
                            'avg': f"{sum(rollspeed)/len(rollspeed):.3f}" if rollspeed else "N/A"
                        } if rollspeed else None,
                        'pitch_rate': {
                            'current': f"{pitchspeed[-1]:.3f}" if pitchspeed else "N/A",
                            'min': f"{min(pitchspeed):.3f}" if pitchspeed else "N/A",
                            'max': f"{max(pitchspeed):.3f}" if pitchspeed else "N/A",
                            'avg': f"{sum(pitchspeed)/len(pitchspeed):.3f}" if pitchspeed else "N/A"
                        } if pitchspeed else None,
                        'yaw_rate': {
                            'current': f"{yawspeed[-1]:.3f}" if yawspeed else "N/A",
                            'min': f"{min(yawspeed):.3f}" if yawspeed else "N/A",
                            'max': f"{max(yawspeed):.3f}" if yawspeed else "N/A",
                            'avg': f"{sum(yawspeed)/len(yawspeed):.3f}" if yawspeed else "N/A"
                        } if yawspeed else None,
                        'samples': len(next(iter([x for x in [rollspeed, pitchspeed, yawspeed] if x]), [])),
                        'units': 'rad/s'
                    }
            
            # GPS Performance from GPS_RAW_INT
            if 'GPS_RAW_INT' in messages:
                gps_data = messages['GPS_RAW_INT']
                
                # Extract all relevant GPS fields
                fix_types = gps_data.get('fix_type', [])
                satellites = gps_data.get('satellites_visible', [])
                hdop = gps_data.get('eph', [])  # Horizontal dilution of precision
                vdop = gps_data.get('epv', [])  # Vertical dilution of precision
                vel = gps_data.get('vel', [])   # Ground speed
                lat = gps_data.get('lat', [])   # Latitude
                lon = gps_data.get('lon', [])   # Longitude
                
                if fix_types and satellites:
                    system_data['gps_status'] = {
                        'fix_quality': {
                            'current': fix_types[-1],
                            'description': {
                                0: 'No GPS',
                                1: 'No Fix',
                                2: '2D Fix',
                                3: '3D Fix',
                                4: 'DGPS',
                                5: 'RTK Float',
                                6: 'RTK Fixed'
                            }.get(fix_types[-1], 'Unknown'),
                            'stability': f"{fix_types.count(fix_types[-1]) / len(fix_types) * 100:.1f}% stable"
                        },
                        'satellites': {
                            'current': satellites[-1],
                            'average': sum(satellites) / len(satellites),
                            'minimum': min(satellites)
                        }
                    }
                    
                    if hdop:
                        system_data['gps_status']['accuracy'] = {
                            'horizontal': f"{hdop[-1]/100:.1f}m",
                            'best': f"{min(hdop)/100:.1f}m"
                        }
                    
                    if vdop:
                        system_data['gps_status']['accuracy']['vertical'] = f"{vdop[-1]/100:.1f}m"
                    
                    if vel:
                        system_data['gps_status']['speed'] = {
                            'current': f"{vel[-1]/100:.1f}m/s",
                            'maximum': f"{max(vel)/100:.1f}m/s"
                        }
                    
                    if lat and lon:
                        system_data['gps_status']['position'] = {
                            'samples': len(lat),
                            'movement': len(set(zip(lat, lon))) > 1
                        }
            
            # Additional position data from GLOBAL_POSITION_INT
            if 'GLOBAL_POSITION_INT' in messages:
                pos_data = messages['GLOBAL_POSITION_INT']
                rel_alt = pos_data.get('relative_alt', [])
                if rel_alt:
                    rel_alt_meters = [alt/1000.0 for alt in rel_alt]  # Convert from mm to meters
                    system_data['position_stability'] = {
                        'altitude_variation': {
                            'range': f"{max(rel_alt_meters) - min(rel_alt_meters):.1f}m",
                            'maximum': f"{max(rel_alt_meters):.1f}m"
                        }
                    }
        
        return system_data

    @staticmethod
    def extract_ahrs_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract AHRS (Attitude and Heading Reference System) data."""
        ahrs_data = {}
        messages = raw_data.get('messages', {})
        
        # Process AHRS, AHRS2, and AHRS3 messages
        for ahrs_type in ['AHRS', 'AHRS2', 'AHRS3']:
            if ahrs_type in messages:
                data = messages[ahrs_type]
                ahrs_data[ahrs_type.lower()] = {
                    'roll': data.get('roll', []),
                    'pitch': data.get('pitch', []),
                    'yaw': data.get('yaw', []),
                    'error_rp': data.get('error_rp', []),
                    'error_yaw': data.get('error_yaw', [])
                }
        
        return ahrs_data

    @staticmethod
    def extract_airspeed_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract airspeed calibration and measurement data."""
        messages = raw_data.get('messages', {})
        airspeed_data = {}
        
        if 'AIRSPEED_AUTOCAL' in messages:
            data = messages['AIRSPEED_AUTOCAL']
            airspeed_data['calibration'] = {
                'raw_airspeed': data.get('raw_airspeed', []),
                'calibrated_airspeed': data.get('calibrated_airspeed', []),
                'calibration_factor': data.get('calibration_factor', [])
            }
        
        return airspeed_data

    @staticmethod
    def extract_attitude_detailed(raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract detailed attitude information."""
        messages = raw_data.get('messages', {})
        attitude_data = {}
        
        if 'ATTITUDE' in messages:
            data = messages['ATTITUDE']
            attitude_data = {
                'roll': data.get('roll', []),
                'pitch': data.get('pitch', []),
                'yaw': data.get('yaw', []),
                'rollspeed': data.get('rollspeed', []),
                'pitchspeed': data.get('pitchspeed', []),
                'yawspeed': data.get('yawspeed', [])
            }
        
        return attitude_data

    @staticmethod
    def extract_ekf_status(raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract EKF (Extended Kalman Filter) status information."""
        messages = raw_data.get('messages', {})
        ekf_data = {}
        
        if 'EKF_STATUS_REPORT' in messages:
            data = messages['EKF_STATUS_REPORT']
            ekf_data = {
                'velocity_variance': data.get('velocity_variance', []),
                'pos_horiz_variance': data.get('pos_horiz_variance', []),
                'pos_vert_variance': data.get('pos_vert_variance', []),
                'compass_variance': data.get('compass_variance', []),
                'terrain_alt_variance': data.get('terrain_alt_variance', [])
            }
        
        return ekf_data

    @staticmethod
    def extract_position_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract comprehensive position data."""
        messages = raw_data.get('messages', {})
        position_data = {}
        
        # Global position
        if 'GLOBAL_POSITION_INT' in messages:
            data = messages['GLOBAL_POSITION_INT']
            position_data['global'] = {
                'lat': [lat/1e7 for lat in data.get('lat', [])],
                'lon': [lon/1e7 for lon in data.get('lon', [])],
                'alt': [alt/1000 for alt in data.get('alt', [])],
                'relative_alt': [rel_alt/1000 for rel_alt in data.get('relative_alt', [])]
            }
        
        # Local position
        if 'LOCAL_POSITION_NED' in messages:
            data = messages['LOCAL_POSITION_NED']
            position_data['local'] = {
                'x': data.get('x', []),
                'y': data.get('y', []),
                'z': data.get('z', []),
                'vx': data.get('vx', []),
                'vy': data.get('vy', []),
                'vz': data.get('vz', [])
            }
        
        return position_data

    @staticmethod
    def extract_rc_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract RC channels data."""
        messages = raw_data.get('messages', {})
        rc_data = {}
        
        # Process both RC_CHANNELS and RC_CHANNELS_RAW
        for rc_type in ['RC_CHANNELS', 'RC_CHANNELS_RAW']:
            if rc_type in messages:
                data = messages[rc_type]
                channels = {}
                for i in range(1, 19):  # Channels 1-18
                    chan_value = data.get(f'chan{i}_raw', [])
                    if chan_value:
                        channels[f'channel_{i}'] = chan_value
                rc_data[rc_type.lower()] = channels
        
        return rc_data

    @staticmethod
    def extract_sensor_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract comprehensive sensor data."""
        messages = raw_data.get('messages', {})
        sensor_data = {}
        
        # Scaled IMU2 data
        if 'SCALED_IMU2' in messages:
            data = messages['SCALED_IMU2']
            sensor_data['imu2'] = {
                'xacc': data.get('xacc', []),
                'yacc': data.get('yacc', []),
                'zacc': data.get('zacc', []),
                'xgyro': data.get('xgyro', []),
                'ygyro': data.get('ygyro', []),
                'zgyro': data.get('zgyro', [])
            }
        
        # Scaled pressure data
        if 'SCALED_PRESSURE' in messages:
            data = messages['SCALED_PRESSURE']
            sensor_data['pressure'] = {
                'press_abs': data.get('press_abs', []),
                'press_diff': data.get('press_diff', []),
                'temperature': data.get('temperature', [])
            }
        
        # Sensor offsets
        if 'SENSOR_OFFSETS' in messages:
            data = messages['SENSOR_OFFSETS']
            sensor_data['offsets'] = {
                'mag_ofs_x': data.get('mag_ofs_x', []),
                'mag_ofs_y': data.get('mag_ofs_y', []),
                'mag_ofs_z': data.get('mag_ofs_z', []),
                'accel_cal_x': data.get('accel_cal_x', []),
                'accel_cal_y': data.get('accel_cal_y', []),
                'accel_cal_z': data.get('accel_cal_z', [])
            }
        
        return sensor_data

    @staticmethod
    def extract_servo_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract servo output data."""
        messages = raw_data.get('messages', {})
        servo_data = {}
        
        if 'SERVO_OUTPUT_RAW' in messages:
            data = messages['SERVO_OUTPUT_RAW']
            outputs = {}
            for i in range(1, 17):  # Servos 1-16
                servo_value = data.get(f'servo{i}_raw', [])
                if servo_value:
                    outputs[f'servo_{i}'] = servo_value
            servo_data['raw_output'] = outputs
        
        return servo_data

    @staticmethod
    def extract_vibration_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract vibration data."""
        messages = raw_data.get('messages', {})
        vibration_data = {}
        
        if 'VIBRATION' in messages:
            data = messages['VIBRATION']
            vibration_data = {
                'vibration_x': data.get('vibration_x', []),
                'vibration_y': data.get('vibration_y', []),
                'vibration_z': data.get('vibration_z', []),
                'clipping_0': data.get('clipping_0', []),
                'clipping_1': data.get('clipping_1', []),
                'clipping_2': data.get('clipping_2', [])
            }
        
        return vibration_data

    @staticmethod
    def extract_wind_data(raw_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract wind estimation data."""
        messages = raw_data.get('messages', {})
        wind_data = {}
        
        if 'WIND' in messages:
            data = messages['WIND']
            wind_data = {
                'direction': data.get('direction', []),
                'speed': data.get('speed', []),
                'speed_z': data.get('speed_z', [])
            }
        
        return wind_data

    @staticmethod
    def get_relevant_data(question: str, raw_data: Dict[str, Any], processed_data: Dict[str, Any]) -> Dict[str, Any]:
        """Main method to extract all relevant data based on question context."""
        relevant_data = {
            'temporal': None,
            'anomaly': None,
            'system': None,
            'ahrs': None,
            'airspeed': None,
            'attitude': None,
            'ekf_status': None,
            'position': None,
            'rc_channels': None,
            'sensors': None,
            'servo': None,
            'vibration': None,
            'wind': None
        }
        
        question_lower = question.lower()
        
        # Time-related questions
        time_keywords = {
            'when', 'time', 'duration', 'long', 'start', 'end', 'begin', 'finish',
            'during', 'period', 'interval', 'timestamp', 'moment', 'timing',
            'frequency', 'rate', 'schedule', 'sequence', 'timeline'
        }
        if any(word in question_lower for word in time_keywords):
            relevant_data['temporal'] = DataExtractor.extract_temporal_data(raw_data, processed_data, question)
        
        # Anomaly-related questions
        anomaly_keywords = {
            'why', 'what happened', 'issue', 'problem', 'error', 'fault', 'failure',
            'malfunction', 'abnormal', 'unusual', 'unexpected', 'irregular',
            'deviation', 'fluctuation', 'variation', 'change', 'difference',
            'unstable', 'inconsistent', 'wrong', 'bad', 'poor', 'concern',
            'warning', 'alert', 'critical', 'emergency', 'danger'
        }
        if any(word in question_lower for word in anomaly_keywords):
            relevant_data['anomaly'] = DataExtractor.extract_anomaly_data(raw_data, processed_data, question)
        
        # System performance questions
        system_keywords = {
            # General system terms
            'performance', 'system', 'status', 'condition', 'health', 'state',
            'operation', 'operating', 'function', 'functional', 'working',
            'behavior', 'quality', 'level', 'metric', 'measure', 'reading',
            
            # GPS and positioning
            'gps', 'signal', 'position', 'positioning', 'location', 'coordinate',
            'satellite', 'navigation', 'fix', 'accuracy', 'precision', 'drift',
            'tracking', 'lock', 'rtk', 'dgps', 'gnss', 'waas', 'eph', 'hdop',
            'vdop', 'pdop', 'latitude', 'longitude', 'altitude',
            
            # Movement and speed
            'speed', 'velocity', 'movement', 'moving', 'travel', 'distance',
            'direction', 'heading', 'course', 'track', 'path', 'route',
            'trajectory', 'motion', 'acceleration', 'groundspeed', 'airspeed',
            
            # Attitude and orientation
            'attitude', 'orientation', 'rotation', 'angle', 'tilt', 'lean',
            'roll', 'pitch', 'yaw', 'bearing', 'level', 'horizontal', 'vertical',
            'stabilization', 'balance', 'steady',
            
            # Communication and data
            'connection', 'link', 'telemetry', 'data', 'transmission', 'receive',
            'strength', 'quality', 'bandwidth', 'rate', 'throughput', 'loss',
            
            # Hardware and sensors
            'sensor', 'hardware', 'device', 'equipment', 'instrument', 'unit',
            'module', 'component', 'part', 'battery', 'power', 'voltage',
            'current', 'temperature', 'pressure', 'compass', 'imu', 'magnetometer'
        }
        if any(word in question_lower for word in system_keywords):
            relevant_data['system'] = DataExtractor.extract_system_data(raw_data, processed_data, question)
        
        # Check for compound words and phrases
        compound_phrases = [
            'how far', 'how high', 'how fast', 'how long', 'how many',
            'how well', 'how good', 'how stable', 'how accurate',
            'what is the', 'what was the', 'what are the',
            'can you tell', 'could you show', 'please show',
            'tell me about', 'show me', 'give me'
        ]
        if any(phrase in question_lower for phrase in compound_phrases):
            # Extract data based on the rest of the question context
            if not any(relevant_data.values()):
                relevant_data['system'] = DataExtractor.extract_system_data(raw_data, processed_data, question)
        
        # Add new data extraction based on keywords
        if any(word in question_lower for word in {'ahrs', 'attitude', 'heading', 'reference'}):
            relevant_data['ahrs'] = DataExtractor.extract_ahrs_data(raw_data)
            
        if any(word in question_lower for word in {'airspeed', 'speed', 'velocity', 'air'}):
            relevant_data['airspeed'] = DataExtractor.extract_airspeed_data(raw_data)
            
        if any(word in question_lower for word in {'attitude', 'orientation', 'roll', 'pitch', 'yaw'}):
            relevant_data['attitude'] = DataExtractor.extract_attitude_detailed(raw_data)
            
        if any(word in question_lower for word in {'ekf', 'kalman', 'filter', 'estimation'}):
            relevant_data['ekf_status'] = DataExtractor.extract_ekf_status(raw_data)
            
        if any(word in question_lower for word in {'position', 'location', 'coordinate', 'where'}):
            relevant_data['position'] = DataExtractor.extract_position_data(raw_data)
            
        if any(word in question_lower for word in {'rc', 'radio', 'channel', 'control'}):
            relevant_data['rc_channels'] = DataExtractor.extract_rc_data(raw_data)
            
        if any(word in question_lower for word in {'sensor', 'imu', 'pressure', 'temperature'}):
            relevant_data['sensors'] = DataExtractor.extract_sensor_data(raw_data)
            
        if any(word in question_lower for word in {'servo', 'output', 'actuator'}):
            relevant_data['servo'] = DataExtractor.extract_servo_data(raw_data)
            
        if any(word in question_lower for word in {'vibration', 'shake', 'oscillation'}):
            relevant_data['vibration'] = DataExtractor.extract_vibration_data(raw_data)
            
        if any(word in question_lower for word in {'wind', 'air', 'weather'}):
            relevant_data['wind'] = DataExtractor.extract_wind_data(raw_data)
        
        return relevant_data 