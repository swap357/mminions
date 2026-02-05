import { useRef, useEffect } from 'react';
import type { TimelineEvent } from '../lib/types';
import { statusColor } from '../lib/status';

interface Props {
  events: TimelineEvent[];
}

export function TimelineView({ events }: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || events.length === 0) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const W = canvas.parentElement?.clientWidth ?? 600;
    const agents = [...new Set(events.map((e) => e.agent))];
    const ROW_H = 28;
    const PAD_L = 80;
    const PAD_T = 24;
    const H = PAD_T + agents.length * ROW_H + 16;

    canvas.width = W * dpr;
    canvas.height = H * dpr;
    canvas.style.width = W + 'px';
    canvas.style.height = H + 'px';
    ctx.scale(dpr, dpr);

    ctx.fillStyle = '#111111';
    ctx.fillRect(0, 0, W, H);

    const tMin = Math.min(...events.map((e) => e.ts));
    const tMax = Math.max(...events.map((e) => e.ts));
    const tRange = Math.max(tMax - tMin, 1000);
    const toX = (t: number) => PAD_L + ((t - tMin) / tRange) * (W - PAD_L - 16);

    ctx.fillStyle = '#555';
    ctx.font = '10px Inter, sans-serif';
    ctx.fillText('agent', 8, 14);
    ctx.fillText('timeline', PAD_L, 14);

    agents.forEach((agent, i) => {
      const y = PAD_T + i * ROW_H;

      ctx.fillStyle = '#888';
      ctx.font = '11px JetBrains Mono, monospace';
      ctx.fillText(agent, 8, y + 18);

      ctx.strokeStyle = '#1a1a1a';
      ctx.beginPath();
      ctx.moveTo(PAD_L, y + ROW_H);
      ctx.lineTo(W - 8, y + ROW_H);
      ctx.stroke();

      const agentEvents = events.filter((e) => e.agent === agent);
      for (let j = 0; j < agentEvents.length; j++) {
        const ev = agentEvents[j];
        const x = toX(ev.ts);
        const nextTs =
          j + 1 < agentEvents.length
            ? agentEvents[j + 1].ts
            : ev.ts + tRange * 0.05;
        const x2 = toX(nextTs);
        const barW = Math.max(x2 - x, 4);

        ctx.fillStyle = statusColor(ev.status) + '66';
        ctx.fillRect(x, y + 6, barW, 16);
        ctx.fillStyle = statusColor(ev.status);
        ctx.fillRect(x, y + 6, 3, 16);

        if (barW > 40) {
          ctx.fillStyle = '#ccc';
          ctx.font = '9px JetBrains Mono, monospace';
          ctx.fillText(ev.status, x + 8, y + 18);
        }
      }
    });
  }, [events]);

  if (events.length === 0) {
    return (
      <div className="text-neutral-600 text-xs p-4">
        no timeline events yet — data accumulates as you poll
      </div>
    );
  }

  return (
    <div className="w-full overflow-x-auto">
      <canvas ref={canvasRef} />
    </div>
  );
}
