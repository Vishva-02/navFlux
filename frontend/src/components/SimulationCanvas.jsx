import React, { useRef, useEffect, useState } from 'react';

const SimulationCanvas = ({ robots, nodes, heatmap, gridSettings, isAuto }) => {
  const canvasRef = useRef(null);
  const animationRef = useRef(null);
  const [robotPositions, setRobotPositions] = useState({}); // visual x/y positions

  // Helper to map node ID to grid coordinates
  const getNodePos = (nodeId) => {
    const mapping = {
      'A': { r: 0, c: 0 },
      'B': { r: 0, c: 1 },
      'C': { r: 1, c: 1 },
      'D': { r: 1, c: 0 },
      'E': { r: 2, c: 1 },
      'F': { r: 2, c: 0 },
    };
    return mapping[nodeId] || { r: 0, c: 0 };
  };

  const CHARGING_STATIONS = ['A', 'E'];

  const getCanvasCoords = (r, c, width, height) => {
    const padding = 60;
    const cellW = (width - padding * 2) / (gridSettings.cols - 1 || 1);
    const cellH = (height - padding * 2) / (gridSettings.rows - 1 || 1);
    return {
      x: padding + c * cellW,
      y: padding + r * cellH
    };
  };

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    
    // Resize handler
    const resize = () => {
      const container = canvas.parentElement;
      canvas.width = container.offsetWidth;
      canvas.height = container.offsetHeight;
    };
    resize();
    window.addEventListener('resize', resize);

    const render = (time) => {
      ctx.clearRect(0, 0, canvas.width, canvas.height);
      
      const { width, height } = canvas;
      const nodesList = ['A', 'B', 'C', 'D', 'E', 'F'];

      // 1. Draw Grid & Congestion Glow
      ctx.setLineDash([5, 5]);
      ctx.lineWidth = 1;

      for (let r = 0; r < gridSettings.rows; r++) {
        const start = getCanvasCoords(r, 0, width, height);
        const end = getCanvasCoords(r, gridSettings.cols - 1, width, height);
        
        // Find if this row segment is "hot" via heatmap
        const rowHeat = heatmap?.reduce((acc, h) => acc + (h.congestion || 0), 0) / (heatmap?.length || 1);
        ctx.strokeStyle = `rgba(0, 242, 255, ${0.05 + Math.min(0.4, rowHeat * 0.01)})`;
        
        ctx.beginPath(); ctx.moveTo(start.x, start.y); ctx.lineTo(end.x, end.y); ctx.stroke();
      }
      for (let c = 0; c < gridSettings.cols; c++) {
        const start = getCanvasCoords(0, c, width, height);
        const end = getCanvasCoords(gridSettings.rows - 1, c, width, height);
        
        ctx.strokeStyle = 'rgba(0, 242, 255, 0.05)';
        ctx.beginPath(); ctx.moveTo(start.x, start.y); ctx.lineTo(end.x, end.y); ctx.stroke();
      }
      ctx.setLineDash([]);

      // 2. Draw Nodes & Stations
      nodesList.forEach(nodeId => {
        const { r, c } = getNodePos(nodeId);
        const { x, y } = getCanvasCoords(r, c, width, height);
        const isStation = CHARGING_STATIONS.includes(nodeId);

        if (isStation) {
          // Glow Pulse for Station
          const pulse = (Math.sin(time / 200) + 1) / 2;
          ctx.beginPath();
          ctx.arc(x, y, 15 + pulse * 10, 0, Math.PI * 2);
          ctx.fillStyle = `rgba(245, 158, 11, ${0.1 * pulse})`;
          ctx.fill();
          
          ctx.beginPath();
          ctx.arc(x, y, 6, 0, Math.PI * 2);
          ctx.fillStyle = '#f59e0b';
          ctx.shadowBlur = 10;
          ctx.shadowColor = '#f59e0b';
          ctx.fill();
          ctx.shadowBlur = 0;
          
          ctx.font = 'bold 8px Rajdhani';
          ctx.fillStyle = '#f59e0b';
          ctx.fillText('⚡ POWER HUB', x + 15, y + 3);
        } else {
          ctx.beginPath();
          ctx.arc(x, y, 4, 0, Math.PI * 2);
          ctx.fillStyle = 'rgba(255, 255, 255, 0.2)';
          ctx.fill();
        }
        
        ctx.font = '10px Orbitron';
        ctx.fillStyle = isStation ? '#f59e0b' : 'rgba(255, 255, 255, 0.4)';
        ctx.fillText(nodeId, x + 10, y - 10);
      });

      // 3. Draw Robots & Interpolate
      robots.forEach(robot => {
        const { r, c } = getNodePos(robot.current_node);
        const target = getCanvasCoords(r, c, width, height);
        
        const currentPos = robotPositions[robot.id] || target;
        const dx = target.x - currentPos.x;
        const dy = target.y - currentPos.y;
        
        const lerpX = currentPos.x + dx * 0.1;
        const lerpY = currentPos.y + dy * 0.1;

        // Path Projection
        if (robot.goal_node && robot.goal_node !== robot.current_node) {
          const goal = getNodePos(robot.goal_node);
          const goalCoords = getCanvasCoords(goal.r, goal.c, width, height);
          ctx.beginPath();
          ctx.moveTo(lerpX, lerpY);
          ctx.lineTo(goalCoords.x, goalCoords.y);
          ctx.strokeStyle = robot.battery < 20 ? 'rgba(239, 68, 68, 0.3)' : 'rgba(0, 242, 255, 0.1)';
          ctx.setLineDash([2, 5]);
          ctx.stroke();
          ctx.setLineDash([]);
        }

        // --- Battery HUD Visual ---
        const batColor = robot.battery > 70 ? '#10b981' : (robot.battery > 30 ? '#f59e0b' : '#ef4444');
        
        // Mini battery bar above robot
        ctx.fillStyle = 'rgba(0,0,0,0.5)';
        ctx.fillRect(lerpX - 10, lerpY - 20, 20, 3);
        ctx.fillStyle = batColor;
        ctx.fillRect(lerpX - 10, lerpY - 20, Math.max(0, (robot.battery / 100) * 20), 3);

        // --- Emergency Pulse for Critical States ---
        if (robot.battery < 20 || robot.status === 'waiting') {
           const warnPulse = (Math.sin(time / 100) + 1) / 2;
           ctx.beginPath();
           ctx.arc(lerpX, lerpY, 12 + warnPulse * 6, 0, Math.PI * 2);
           ctx.strokeStyle = robot.battery < 20 ? `rgba(239, 68, 68, ${0.4 * warnPulse})` : `rgba(255, 255, 255, ${0.2 * warnPulse})`;
           ctx.stroke();
        }

        // Draw Robot
        ctx.beginPath();
        ctx.arc(lerpX, lerpY, 10, 0, Math.PI * 2);
        
        let robotColor = 'var(--color-neon-cyan)';
        if (robot.status === 'charging') robotColor = '#f59e0b';
        else if (robot.battery < 20) robotColor = '#ef4444';
        else if (robot.status === 'waiting') robotColor = '#fde68a';
        else if (robot.status === 'stopped') robotColor = 'rgba(255,255,255,0.2)';
        
        ctx.fillStyle = robotColor;
        ctx.shadowBlur = (robot.status === 'charging' || robot.battery < 20) ? 20 : 12;
        ctx.shadowColor = robotColor;
        ctx.fill();
        ctx.shadowBlur = 0;

        // Label
        ctx.font = 'bold 8px Inter';
        ctx.fillStyle = (robot.status === 'stopped' || robot.status === 'waiting') ? '#fff' : '#000';
        ctx.textAlign = 'center';
        ctx.fillText(robot.id, lerpX, lerpY + 3);

        robotPositions[robot.id] = { x: lerpX, y: lerpY };
      });

      animationRef.current = requestAnimationFrame(render);
    };

    render(0);

    return () => {
      cancelAnimationFrame(animationRef.current);
      window.removeEventListener('resize', resize);
    };
  }, [robots, gridSettings, robotPositions]);

  return (
    <div className="glass h-full w-full relative overflow-hidden bg-black/40 border border-white/5">
      <div className="absolute top-4 left-4 z-10">
        <span className="text-[10px] font-bold text-slate-500 uppercase tracking-widest bg-black/30 px-2 py-1 rounded">
          Operational Live Matrix // {gridSettings.rows}x{gridSettings.cols}
        </span>
      </div>
      <canvas ref={canvasRef} className="w-full h-full" />
    </div>
  );
};

export default SimulationCanvas;
