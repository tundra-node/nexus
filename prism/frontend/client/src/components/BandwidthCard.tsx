import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { ArrowDown, ArrowUp, AlertCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

interface BandwidthCardProps {
  inbound_rate: number;
  outbound_rate: number;
  total_inbound: number;
  total_outbound: number;
  loading?: boolean;
  error?: string | null;
}

function formatBytes(bytes: number): string {
  if (!bytes || bytes <= 0 || !isFinite(bytes)) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB"];
  const i = Math.max(0, Math.min(Math.floor(Math.log(bytes) / Math.log(k)), sizes.length - 1));
  return Math.round(bytes / Math.pow(k, i)) + " " + sizes[i];
}

function formatRate(bytesPerSec: number): string {
  return formatBytes(bytesPerSec) + "/s";
}

interface DataPoint {
  t: number;
  in: number;
  out: number;
}

function TimeTooltip({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload as DataPoint;
  const s = Math.floor((Date.now() - d.t) / 1000);
  const ago = s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s ago` : `${s}s ago`;
  return (
    <div className="rounded-lg border bg-background/95 px-3 py-2 text-xs shadow-lg backdrop-blur">
      <p className="text-muted-foreground">{ago}</p>
      {payload.map((p: any) => (
        <p key={p.name} style={{ color: p.color }}>
          {p.name === "in" ? "Down" : "Up"}: {formatBytes(p.value)}/s
        </p>
      ))}
    </div>
  );
}

export default function BandwidthCard({
  inbound_rate,
  outbound_rate,
  total_inbound,
  total_outbound,
  loading = false,
  error = null,
}: BandwidthCardProps) {
  const [history, setHistory] = useState<DataPoint[]>([]);
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setHistory((prev) => {
      const next = [...prev, { t: Date.now(), in: inbound_rate, out: outbound_rate }];
      while (next.length > 300) next.shift();
      return next;
    });
  }, [inbound_rate, outbound_rate]);

  if (error) {
    return (
      <Card className="border-destructive/50 bg-destructive/5">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-destructive" />
            Bandwidth Error
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-destructive">{error}</p>
        </CardContent>
      </Card>
    );
  }

  const maxVal = history.reduce((m, p) => Math.max(m, p.in, p.out), 1);

  return (
    <Card className="overflow-hidden">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle>Bandwidth Usage</CardTitle>
          {loading && <Spinner className="h-4 w-4" />}
        </div>
      </CardHeader>
      <CardContent>
        <div className="mb-4 grid grid-cols-2 gap-4">
          <div className="flex items-center gap-2">
            <ArrowDown className="h-4 w-4 text-blue-500" />
            <span className="text-sm text-muted-foreground">Down</span>
            <span className="text-sm font-semibold">{formatRate(inbound_rate)}</span>
          </div>
          <div className="flex items-center gap-2">
            <ArrowUp className="h-4 w-4 text-purple-500" />
            <span className="text-sm text-muted-foreground">Up</span>
            <span className="text-sm font-semibold">{formatRate(outbound_rate)}</span>
          </div>
          <div className="text-xs text-muted-foreground">
            Total received: {formatBytes(total_inbound)}
          </div>
          <div className="text-xs text-muted-foreground">
            Total sent: {formatBytes(total_outbound)}
          </div>
        </div>

        <div ref={containerRef} className="h-48 w-full">
          {history.length > 1 ? (
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={history} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
                <defs>
                  <linearGradient id="inGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#3b82f6" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#3b82f6" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="outGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#a855f7" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#a855f7" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis
                  dataKey="t"
                  domain={["dataMin", "dataMax"]}
                  tickFormatter={(ts) => {
                    const s = Math.floor((Date.now() - ts) / 1000);
                    if (s >= 120) return `${Math.floor(s / 60)}m`;
                    if (s >= 60) return "1m";
                    return `${s}s`;
                  }}
                  type="number"
                  stroke="hsl(var(--muted-foreground))"
                  tick={{ fontSize: 10 }}
                  tickLine={false}
                  axisLine={false}
                  minTickGap={40}
                />
                <YAxis
                  domain={[0, maxVal * 1.2]}
                  tickFormatter={(v) => formatBytes(v)}
                  stroke="hsl(var(--muted-foreground))"
                  tick={{ fontSize: 10 }}
                  tickLine={false}
                  axisLine={false}
                  width={52}
                />
                <Tooltip content={<TimeTooltip />} />
                <Area
                  type="monotone"
                  dataKey="in"
                  stroke="#3b82f6"
                  fill="url(#inGrad)"
                  strokeWidth={1.5}
                  dot={false}
                  isAnimationActive={false}
                />
                <Area
                  type="monotone"
                  dataKey="out"
                  stroke="#a855f7"
                  fill="url(#outGrad)"
                  strokeWidth={1.5}
                  dot={false}
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-full items-center justify-center rounded-lg border border-dashed border-muted-foreground/25">
              <p className="text-sm text-muted-foreground">Collecting data...</p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
