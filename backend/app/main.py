from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import json
import os
import asyncio

from app.api.routes import robots, simulation, map, heatmap, config
from app.models.lane import Lane
from app.services.path_planner import planner
from app.services.simulation import sim
from app.services.traffic_controller import traffic_manager, LANE_CAPACITY

app = FastAPI(title="Lane-Aware Multi-Robot Traffic System")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

connections = []

def serialize_robots():
    robots_data = []
    for r in sim.robots.values():
        robots_data.append({
            "id": r.id,
            "current_node": r.current_node,
            "goal_node": r.goal_node,
            "status": r.status.value,
            "battery": r.battery,
            "path": r.path
        })
    return robots_data

def get_lane_map():
    lane_map = {}
    for lane_id, lane_obj in traffic_manager.occupancies.items():
        lane_map[lane_obj] = lane_map.get(lane_obj, 0) + 1
    return lane_map

async def broadcast_state():
    lane_map = get_lane_map()
    data = {
        "robots": serialize_robots(),
        "laneLoads": lane_map,
        "activeCount": len(sim.robots)
    }
    # Since existing frontend relies on 'heatmap' field for laneLoads and metric arrays
    # we will send both to avoid breaking existing bindings that aren't explicitly mapped.
    # The prompt specified "robots", "laneLoads", "activeCount".
    data["heatmap"] = [
        {
            "lane_id": edge.id,
            "congestion_score": edge.congestion_score,
            "is_full": lane_map.get(edge.id, 0) >= LANE_CAPACITY
        }
        for edges in planner.adj_list.values() for edge in edges
    ]

    to_remove = []
    for ws in connections:
        try:
            await ws.send_json(data)
        except:
            to_remove.append(ws)
    for ws in to_remove:
        connections.remove(ws)

async def simulation_loop():
    while True:
        if sim.running:
            sim.step()
        await broadcast_state()
        await asyncio.sleep(0.5)

@app.on_event("startup")
async def startup_event():
    # Load default map
    base_dir = os.path.dirname(__file__)
    map_path = os.path.join(base_dir, "data", "sample_map.json")
    if os.path.exists(map_path):
        with open(map_path, "r") as f:
            data = json.load(f)
            lanes = [Lane(**lane) for lane in data.get("edges", [])]
            planner.load_graph(lanes)
            
    asyncio.create_task(simulation_loop())

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

app.include_router(robots.router)
app.include_router(simulation.router)
app.include_router(map.router)
app.include_router(heatmap.router)
app.include_router(config.router)

@app.get("/health")
def health_check():
    return {"status": "ok"}
