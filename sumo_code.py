import os
import sys
import time
import traci
from collections import defaultdict

# SUMO configuration
sumo_config_path = r"C:\Users\User\Desktop\_sumo_\test.sumocfg"
sumo_binary = "sumo-gui"  # or "sumo" for headless mode

# Lane to traffic light phase mapping - updated based on your network file
LANE_PHASE_MAPPING = {
    "-E0_0": 0,  # Green for Right road (from J1 to J2)
    "E1_0": 2,   # Green for Down road (from J3 to J2)
    "E0_0": 4    # Green for Left road (from J0 to J2)
}

def start_simulation():
    """Start the SUMO simulation"""
    # Set SUMO environment path if needed
    if 'SUMO_HOME' in os.environ:
        tools = os.path.join(os.environ['SUMO_HOME'], 'tools')
        sys.path.append(tools)
    else:
        sys.exit("Please declare environment variable 'SUMO_HOME'")
    
    # Start SUMO with TraCI
    sumo_cmd = [sumo_binary, "-c", sumo_config_path, "--start"]
    traci.start(sumo_cmd)

def count_vehicles_per_lane():
    """Count vehicles in each approach lane dynamically"""
    lane_counts = defaultdict(int)
    
    # Count vehicles in each approach lane based on your network file
    lane_counts["-E0_0"] = traci.lane.getLastStepVehicleNumber("-E0_0")  # Right road
    lane_counts["E1_0"] = traci.lane.getLastStepVehicleNumber("E1_0")    # Down road
    lane_counts["E0_0"] = traci.lane.getLastStepVehicleNumber("E0_0")    # Left road
    
    return lane_counts

def get_lane_with_max_vehicles(lane_counts):
    """Get the lane with the maximum number of vehicles"""
    max_count = 0
    max_lane = None
    
    for lane, count in lane_counts.items():
        if count > max_count:
            max_count = count
            max_lane = lane
    
    # If all lanes have same count, use round-robin
    if max_lane is None:
        current_phase = traci.trafficlight.getPhase("J2")
        if current_phase == 0:
            return "E1_0"
        elif current_phase == 2:
            return "E0_0"
        else:
            return "-E0_0"
    
    return max_lane

def set_traffic_lights(green_lane):
    """Set traffic lights based on which lane should be green"""
    if green_lane in LANE_PHASE_MAPPING:
        phase = LANE_PHASE_MAPPING[green_lane]
        traci.trafficlight.setPhase("J2", phase)

def main():
    """Main function to control traffic lights based on vehicle counts"""
    try:
        start_simulation()
        
        # Main simulation loop
        step = 0
        while traci.simulation.getMinExpectedNumber() > 0:
            # Count vehicles in each lane
            lane_counts = count_vehicles_per_lane()
            
            # Print current counts every 10 steps
            if step % 10 == 0:
                print(f"Step {step}: Lane counts - {dict(lane_counts)}")
            
            # Change traffic light every 30 steps (3 seconds with default step length)
            if step % 30 == 0:
                # Get the lane with the most vehicles
                priority_lane = get_lane_with_max_vehicles(lane_counts)
                
                print(f"Setting green light for {priority_lane} with {lane_counts[priority_lane]} vehicles")
                
                # Set the traffic light for the priority lane
                set_traffic_lights(priority_lane)
            
            # Advance simulation by one step
            traci.simulationStep()
            step += 1
            time.sleep(0.05)  # Slow down the simulation for better visualization
            
        traci.close()
        print("Simulation ended")
        
    except Exception as e:
        print(f"Error: {e}")
        traci.close()

if __name__ == "__main__":
    main()