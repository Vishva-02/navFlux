from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import random
import json

app = FastAPI(title="Advanced Robot Simulation HUB")

# CORS Setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global State
robots = []
lane_loads = {}
connections = []
completed_tasks = 0
total_wait_time = 0

# Node Map for logic
NODES = ["A", "B", "C", "D", "E", "F"]
CHARGING_STATIONS = ["A", "E"]
PATHS = [
    ["A", "B", "C", "D", "A"],
    ["C", "E", "F", "D", "C"],
    ["B", "C", "E", "F", "D", "A", "B"]
]

def spawn_robots(n, speed_factor=0.2):
    global robots, completed_tasks, total_wait_time
    robots = []
    completed_tasks = 0
    total_wait_time = 0
    for i in range(n):
        path = random.choice(PATHS)
        start_idx = random.randint(0, len(path)-2)
        robots.append({
            "id": f"R{i+1}",
            "current_node": path[start_idx],
            "next_node": path[start_idx + 1],
            "path": list(path),
            "path_idx": start_idx,
            "progress": 0.0,
            "speed": speed_factor + (random.random() * 0.05),
            "battery_level": 100.0,
            "status": "MOVING"  # MOVING | WAITING | CHARGING
        })

def update_lane_loads():
    global lane_loads
    lane_loads = {}
    for r in robots:
        if r["status"] == "MOVING":
            lane_id = f"{r['current_node']}->{r['next_node']}"
            lane_loads[lane_id] = lane_loads.get(lane_id, 0) + 1

def recalculate_path(current_node, target_node=None):
    if target_node:
        # Simple pathfinding: find a path that contains current and target
        possible = [list(p) for p in PATHS if current_node in p and target_node in p]
        if possible:
            path = random.choice(possible)
            idx = path.index(current_node)
            # Trim path to end at target if needed
            return path, idx
            
    possible_paths = [list(p) for p in PATHS if current_node in p]
    if not possible_paths: return list(random.choice(PATHS)), 0
    new_path = random.choice(possible_paths)
    idx = new_path.index(current_node)
    return new_path, idx

async def broadcast():
    heatmap_data = [
        {"lane_id": lid, "congestion_score": count, "usage_count": count}
        for lid, count in lane_loads.items()
    ]
    
    # Detailed Charging Hub Info
    hubs = []
    for node in CHARGING_STATIONS:
        charging_here = [r["id"] for r in robots if r["current_node"] == node and r["status"] == "CHARGING"]
        hubs.append({
            "id": node,
            "units": charging_here,
            "status": "OPERATIONAL" if len(charging_here) < 3 else "CONGESTED"
        })

    data = {
        "type": "SIMULATION_UPDATE",
        "robots": robots, 
        "activeCount": len(robots),
        "resolvedCount": completed_tasks,
        "heatmap": heatmap_data,
        "lanes": lane_loads,
        "hubs": hubs
    }
    to_remove = []
    for ws in connections:
        try:
            await ws.send_json(data)
        except Exception:
            to_remove.append(ws)
    for ws in to_remove:
        if ws in connections:
            connections.remove(ws)

# Node Coordinates for position calculation
NODE_COORDS = {
    'A': {'x': 1, 'y': 1},
    'B': {'x': 1, 'y': 9},
    'C': {'x': 5, 'y': 9},
    'D': {'x': 5, 'y': 1},
    'E': {'x': 9, 'y': 9},
    'F': {'x': 9, 'y': 1}
}

def run_simulation_tick():
    global completed_tasks, total_wait_time
    occupied_nodes = set()
    for r in robots:
        if r["status"] == "CHARGING" or (r["status"] == "MOVING" and r["progress"] < 0.1):
            occupied_nodes.add(r["current_node"])

    for r in robots:
        # 1. Battery & Charging Logic
        if r["status"] != "CHARGING":
            r["battery_level"] -= 0.08
            if r["battery_level"] < 25:
                if r["current_node"] in CHARGING_STATIONS and r["progress"] < 0.1:
                    r["status"] = "CHARGING"
                else:
                    target = CHARGING_STATIONS[0] if r["current_node"] not in ["E", "F", "C"] else "E"
                    if r["status"] == "MOVING" and r["next_node"] not in CHARGING_STATIONS:
                         r["path"], r["path_idx"] = recalculate_path(r["current_node"], target)
                         r["next_node"] = r["path"][r["path_idx"] + 1]
        
        if r["status"] == "CHARGING":
            r["battery_level"] += 1.5
            if r["battery_level"] >= 100:
                r["battery_level"] = 100
                r["status"] = "MOVING"
            r["x"] = NODE_COORDS[r["current_node"]]['x']
            r["y"] = NODE_COORDS[r["current_node"]]['y']
            continue

        # 2. Collision Avoidance
        if r["status"] in ["MOVING", "WAITING"]:
            if r["progress"] > 0.85 and r["next_node"] in occupied_nodes:
                r["status"] = "WAITING"
                total_wait_time += 1
            else:
                r["status"] = "MOVING"
                occupied_nodes.add(r["next_node"])

        # 3. Movement Execution
        if r["status"] == "MOVING":
            r["progress"] += r["speed"]

            if r["progress"] >= 1.0:
                r["progress"] = 0.0
                r["path_idx"] += 1
                
                if r["path_idx"] >= len(r["path"]) - 1:
                    completed_tasks += 1
                    new_path, new_idx = recalculate_path(r["path"][-1])
                    r["path"] = new_path
                    r["path_idx"] = new_idx
                
                r["current_node"] = r["path"][r["path_idx"]]
                r["next_node"] = r["path"][r["path_idx"] + 1]

                lane = f"{r['current_node']}->{r['next_node']}"
                if lane_loads.get(lane, 0) > 3:
                     new_path, new_idx = recalculate_path(r["current_node"])
                     r["path"] = new_path
                     r["path_idx"] = new_idx
                     r["next_node"] = r["path"][r["path_idx"] + 1]

        # Calculate coordinates
        start_coord = NODE_COORDS[r["current_node"]]
        end_coord = NODE_COORDS[r["next_node"]]
        r["x"] = round(start_coord['x'] + (end_coord['x'] - start_coord['x']) * r["progress"], 2)
        r["y"] = round(start_coord['y'] + (end_coord['y'] - start_coord['y']) * r["progress"], 2)

    update_lane_loads()

async def simulation_loop():
    while True:
        run_simulation_tick()
        await broadcast()
        await asyncio.sleep(0.3)

@app.on_event("startup")
async def startup_event():
    spawn_robots(10) 
    asyncio.create_task(simulation_loop())

@app.get("/")
def root():
    return {"status": "ok"}

@app.get("/simulate/metrics")
def get_metrics():
    avg_wait = round(total_wait_time / max(1, len(robots)), 1)
    return {
        "avg_wait_time": avg_wait,
        "throughput": len(robots) * 2,
        "deadlock_count": completed_tasks,
        "robots": {
            "total": len(robots),
            "moving": len([r for r in robots if r["status"] == "MOVING"])
        }
    }

@app.get("/robots")
def get_robots():
    return robots

@app.get("/map")
def get_map():
    return {"nodes": NODES, "edges": []}

@app.get("/heatmap")
def get_heatmap():
    return [
        {"lane_id": lid, "congestion_score": count, "usage_count": count}
        for lid, count in lane_loads.items()
    ]

@app.post("/api/config")
async def setup_config(data: dict):
    count = data.get("robotCount", 10)
    density = data.get("density", "MEDIUM")
    speed_map = {"LOW": 0.1, "MEDIUM": 0.2, "HIGH": 0.4}
    speed = speed_map.get(density, 0.2)
    spawn_robots(count, speed)
    return {"status": "initialized"}

@app.post("/simulate/start")
async def start_sim():
    return {"status": "started"}

@app.post("/simulate/step")
async def step_sim():
    run_simulation_tick()
    await broadcast()
    return {"status": "stepped"}

@app.post("/simulate/reset")
async def reset_sim(n: int = 8):
    spawn_robots(n)
    return {"status": "reset"}

@app.websocket("/ws/stream")
async def stream(websocket: WebSocket):
    await websocket.accept()
    connections.append(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in connections:
            connections.remove(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
