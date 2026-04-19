import heapq
from typing import Dict, List, Optional
from app.models.lane import Lane, LaneType, SafetyLevel

class PathPlanner:
    def __init__(self):
        self.adj_list: Dict[str, List[Lane]] = {}

    def load_graph(self, lanes: List[Lane]):
        self.adj_list.clear()
        for lane in lanes:
            if lane.start_node not in self.adj_list:
                self.adj_list[lane.start_node] = []
            if lane.end_node not in self.adj_list:
                self.adj_list[lane.end_node] = []
            self.adj_list[lane.start_node].append(lane)

    def calculate_cost(self, lane: Lane) -> float:
        base_cost = 10.0 / max(lane.speed_limit, 0.1)
        congestion_cost = lane.congestion_score * 3.0
        
        safety_cost = 0.0
        if lane.safety_level == SafetyLevel.LOW:
            safety_cost = 5.0
        elif lane.safety_level == SafetyLevel.MEDIUM:
            safety_cost = 2.0
            
        type_mult = 1.0
        if lane.lane_type == LaneType.HUMAN_ZONE:
            type_mult = 5.0
        elif lane.lane_type == LaneType.NARROW:
            type_mult = 2.0
            
        return (base_cost + congestion_cost + safety_cost) * type_mult

    def find_path(self, start_node: str, goal_node: str) -> Optional[List[str]]:
        if start_node not in self.adj_list or goal_node not in self.adj_list:
            return None

        open_set = []
        heapq.heappush(open_set, (0.0, 0.0, start_node, [start_node]))
        g_scores = {start_node: 0.0}

        while open_set:
            f, current_g, current_node, path = heapq.heappop(open_set)

            if current_node == goal_node:
                return path

            if current_g > g_scores.get(current_node, float('inf')):
                continue

            for edge in self.adj_list.get(current_node, []):

                tentative_g = current_g + self.calculate_cost(edge)
                neighbor = edge.end_node

                if tentative_g < g_scores.get(neighbor, float('inf')):
                    g_scores[neighbor] = tentative_g
                    heapq.heappush(open_set, (tentative_g, tentative_g, neighbor, path + [neighbor]))
                    
        return None

planner = PathPlanner()
