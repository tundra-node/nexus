import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { Activity, Zap, GitBranch, AlertCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  ResponsiveContainer,
} from "recharts";

interface StatusCardProps {
  uptime: number;
  active_peers: number;
  tunnel_count: number;
  tunnels_in: number;
  tunnels_out: number;
  status: string;
  loading?: boolean;
  error?: string | null;
}

function formatUptime(seconds: number): string {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${minutes}m`;
  return `${minutes}m`;
}

export default function StatusCard({
  uptime,
  active_peers,
  tunnel_count,
  tunnels_in,
  tunnels_out,
  status,
  loading = false,
  error = null,
}: StatusCardProps) {
  const peersRef = useRef(active_peers);
  peersRef.current = active_peers;
  const [peerHistory, setPeerHistory] = useState<{ t: number; peers: number }[]>([]);

  useEffect(() => {
    const interval = setInterval(() => {
      setPeerHistory((prev) => {
        const next = [...prev, { t: Date.now(), peers: peersRef.current }];
        while (next.length > 300) next.shift();
        return next;
      });
    }, 1000);
    return () => clearInterval(interval);
  }, []);

  const maxPeers = peerHistory.reduce((m, p) => Math.max(m, p.peers), 1);

  const statusColor = status === "online" ? "text-green-500" : "text-yellow-500";
  const statusBg = status === "online" ? "bg-green-500/10" : "bg-yellow-500/10";

  if (error) {
    return (
      <Card className="border-destructive/50 bg-destructive/5">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-destructive" />
            Status Error
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-destructive">{error}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="overflow-hidden">
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Activity className="h-5 w-5" />
            Router Status
          </CardTitle>
          {loading ? (
            <Spinner className="h-4 w-4" />
          ) : (
            <div className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${statusBg}`}>
              <div className={`h-2 w-2 rounded-full ${statusColor}`} />
              <span className={statusColor}>{status === "online" ? "Online" : "Connecting"}</span>
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">Uptime</p>
            <p className="text-lg font-semibold">{formatUptime(uptime)}</p>
          </div>
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">Active Peers</p>
            <p className="text-lg font-semibold">{active_peers}</p>
          </div>
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">Tunnels</p>
            <p className="text-lg font-semibold">{tunnel_count}</p>
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-1">
              <Zap className="h-3.5 w-3.5 text-blue-500" />
              <p className="text-xs font-medium text-muted-foreground">In</p>
            </div>
            <p className="text-lg font-semibold">{tunnels_in}</p>
          </div>
          <div className="space-y-1">
            <div className="flex items-center gap-1">
              <GitBranch className="h-3.5 w-3.5 text-purple-500" />
              <p className="text-xs font-medium text-muted-foreground">Out</p>
            </div>
            <p className="text-lg font-semibold">{tunnels_out}</p>
          </div>
        </div>

        {peerHistory.length > 1 && (
          <div className="mt-4 h-16 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={peerHistory} margin={{ top: 0, right: 0, bottom: 0, left: 0 }}>
                <defs>
                  <linearGradient id="peerGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#22c55e" stopOpacity={0.25} />
                    <stop offset="100%" stopColor="#22c55e" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="t" domain={["dataMin", "dataMax"]} hide />
                <YAxis domain={[0, maxPeers * 1.3]} hide />
                <Area
                  type="monotone"
                  dataKey="peers"
                  stroke="#22c55e"
                  strokeWidth={1.5}
                  fill="url(#peerGrad)"
                  dot={false}
                  isAnimationActive={false}
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
