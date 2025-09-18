import os
import sys
import time
import traci
from collections import defaultdict

# SUMO configuration
sumo_config_path = r"C:\Users\User\Desktop\sumo\test.sumocfg"
sumo_binary = "sumo-gui"  # or "sumo" for headless mode

# Lane to traffic light phase mapping
LANE_PHASE_MAPPING = {
    "lane1_0": 0,  # Green for Lane 1 (Right road)
    "lane2_0": 1,  # Green for Lane 2 (Down road)
    "lane3_0": 2   # Green for Lane 3 (Left road)
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
    """Count vehicles in each lane dynamically"""
    lane_counts = defaultdict(int)
    
    # Count vehicles in each approach lane
    try:
        lane_counts["lane1_0"] = traci.lane.getLastStepVehicleNumber("lane1_0")
        lane_counts["lane2_0"] = traci.lane.getLastStepVehicleNumber("lane2_0")
        lane_counts["lane3_0"] = traci.lane.getLastStepVehicleNumber("lane3_0")
    except traci.TraCIException as e:
        print(f"Error accessing lane data: {e}")
        # Try to get available lanes
        all_lanes = traci.lane.getIDList()
        print(f"Available lanes: {all_lanes}")
        
        # Try to find the correct lane names
        for lane in all_lanes:
            if "lane1" in lane:
                lane_counts["lane1_0"] = traci.lane.getLastStepVehicleNumber(lane)
            elif "lane2" in lane:
                lane_counts["lane2_0"] = traci.lane.getLastStepVehicleNumber(lane)
            elif "lane3" in lane:
                lane_counts["lane3_0"] = traci.lane.getLastStepVehicleNumber(lane)
    
    return lane_counts

def get_lane_with_max_vehicles(lane_counts):
    """Get the lane with the maximum number of vehicles"""
    max_count = 0
    max_lane = None
    
    for lane, count in lane_counts.items():
        if count > max_count:
            max_count = count
            max_lane = lane
    
    # If all lanes have same count or no vehicles, use round-robin
    if max_lane is None or max_count == 0:
        try:
            current_phase = traci.trafficlight.getPhase("tls")
            if current_phase == 0:
                return "lane2_0"
            elif current_phase == 1:
                return "lane3_0"
            else:
                return "lane1_0"
        except:
            return "lane1_0"  # Default fallback
    
    return max_lane

def set_traffic_lights(green_lane):
    """Set traffic lights based on which lane should be green"""
    if green_lane in LANE_PHASE_MAPPING:
        phase = LANE_PHASE_MAPPING[green_lane]
        try:
            traci.trafficlight.setPhase("tls", phase)
            print(f"Successfully set phase {phase} for {green_lane}")
        except traci.TraCIException as e:
            print(f"Error setting traffic light phase: {e}")
            # Try to get available traffic lights
            all_tls = traci.trafficlight.getIDList()
            print(f"Available traffic lights: {all_tls}")

def main():
    """Main function to control traffic lights based on vehicle counts"""
    try:
        start_simulation()
        
        # Wait a few steps for simulation to initialize
        for _ in range(10):
            traci.simulationStep()
        
        # Main simulation loop
        step = 0
        green_time = 0
        current_green_lane = None
        
        while traci.simulation.getMinExpectedNumber() > 0:
            # Count vehicles in each lane
            lane_counts = count_vehicles_per_lane()
            
            # Print current counts every 10 steps
            if step % 10 == 0:
                print(f"Step {step}: Lane counts - {dict(lane_counts)}")
                print(f"Current traffic light phase: {traci.trafficlight.getPhase('tls')}")
            
            # Change traffic light every 50 steps (5 seconds with default step length)
            # Or when the current green phase has been active for enough time
            if step % 50 == 0 or green_time >= 50:
                # Get the lane with the most vehicles
                priority_lane = get_lane_with_max_vehicles(lane_counts)
                
                # Only change if it's different from current green lane
                if priority_lane != current_green_lane:
                    print(f"Setting green light for {priority_lane} with {lane_counts[priority_lane]} vehicles")
                    
                    # Set the traffic light for the priority lane
                    set_traffic_lights(priority_lane)
                    current_green_lane = priority_lane
                    green_time = 0
                else:
                    print(f"Keeping green light for {current_green_lane}")
                    green_time = 0
            
            # Advance simulation by one step
            traci.simulationStep()
            step += 1
            green_time += 1
            time.sleep(0.05)  # Slow down the simulation for better visualization
            
        traci.close()
        print("Simulation ended")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        traci.close()

if __name__ == "__main__":
    main()
<configuration>
    <input>
        <net-file value="test.net.xml"/>
        ...
    </input>
    ...
</configuration>