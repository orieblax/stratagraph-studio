import React from 'react';
import { BaseEdge, EdgeProps, getBezierPath } from '@xyflow/react';

export default function AnimatedPulseEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  style = {},
  markerEnd,
  data,
}: EdgeProps) {
  const [edgePath] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  });

  const isActive = Boolean(data?.active);

  return (
    <>
      {/* Base path line */}
      <BaseEdge
        path={edgePath}
        markerEnd={markerEnd}
        style={{
          ...style,
          stroke: isActive ? '#06b6d4' : '#334155',
          strokeWidth: isActive ? 2.5 : 1.5,
          transition: 'stroke 0.3s ease, stroke-width 0.3s ease',
        }}
      />

      {/* Animated glow pulse effect along the SVG path when active */}
      {isActive && (
        <>
          <path
            d={edgePath}
            fill="none"
            stroke="#22d3ee"
            strokeWidth={4}
            strokeDasharray="8 8"
            className="animate-pulse opacity-75"
            filter="drop-shadow(0 0 6px #06b6d4)"
          />
          <circle r="4" fill="#67e8f9" filter="drop-shadow(0 0 8px #38bdf8)">
            <animateMotion dur="1.2s" repeatCount="indefinite" path={edgePath} />
          </circle>
        </>
      )}
    </>
  );
}
