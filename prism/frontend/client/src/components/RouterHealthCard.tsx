import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Activity, AlertCircle, Wifi, WifiOff } from "lucide-react";

function formatBps(bps: number): string {
  if (bps <= 0) return "0 B/s";
  const units = ["B/s", "KB/s", "MB/s", "GB/s"];
  const i = Math.min(units.length - 1, Math.floor(Math.log(bps) / Math.log(1000)));
  const val = bps / Math.pow(1000, i);
  return `${val < 10 ? val.toFixed(1) : Math.round(val)} ${units[i]}`;
}

interface RouterHealthCardProps {
  score: number;
  status: string;
  active_peers: number;
  tunnels: { inbound: number; outbound: number; total: number };
  bandwidth: { inbound_kbps: number; outbound_kbps: number };
  network: {
    status: string;
    routers_known: number;
    floodfills: number;
    tunnel_success_rate_pct: number;
  };
  flags: { floodfill: boolean; reachable: boolean };
  loading: boolean;
  error?: string | null;
}

function scoreColor(score: number): string {
  if (score >= 70) return "text-emerald-500";
  if (score >= 40) return "text-amber-500";
  return "text-rose-500";
}

function scoreBg(score: number): string {
  if (score >= 70) return "bg-emerald-500/10";
  if (score >= 40) return "bg-amber-500/10";
  return "bg-rose-500/10";
}

function scoreRing(score: number): string {
  if (score >= 70) return "stroke-emerald-500";
  if (score >= 40) return "stroke-amber-500";
  return "stroke-rose-500";
}

export default function RouterHealthCard({
  score,
  status,
  active_peers,
  tunnels,
  bandwidth,
  network,
  flags,
  loading,
  error = null,
}: RouterHealthCardProps) {
  if (error) {
    return (
      <Card className="border-destructive/50 bg-destructive/5">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-destructive" />
            Health Error
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-destructive">{error}</p>
        </CardContent>
      </Card>
    );
  }

  const circumference = 2 * Math.PI * 42;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2">
          <Activity className="h-5 w-5 text-primary" />
          Router Health
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className={`rounded-lg ${scoreBg(score)} p-4 text-center`}>
          <div className="flex justify-center mb-2">
            <svg width="100" height="100" className="transform -rotate-90">
              <circle cx="50" cy="50" r="42" fill="none" stroke="currentColor" strokeWidth="8" className="text-muted/20" />
              <circle
                cx="50" cy="50" r="42" fill="none"
                strokeWidth="8" strokeLinecap="round"
                className={scoreRing(score)}
                strokeDasharray={circumference}
                strokeDashoffset={circumference * (1 - score / 100)}
              />
            </svg>
          </div>
          <p className={`text-4xl font-bold ${scoreColor(score)}`}>{score}</p>
          <p className="text-xs text-muted-foreground">out of 100</p>
        </div>

        <div className="flex items-center justify-center gap-2">
          {status === "online" ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-500">
              <Wifi className="h-3 w-3" /> Online
            </span>
          ) : (
            <span className="inline-flex items-center gap-1 rounded-full bg-rose-500/10 px-3 py-1 text-xs font-medium text-rose-500">
              <WifiOff className="h-3 w-3" /> {status}
            </span>
          )}
          {flags.floodfill && (
            <span className="inline-flex items-center gap-1 rounded-full bg-blue-500/10 px-3 py-1 text-xs font-medium text-blue-500">
              Floodfill
            </span>
          )}
          {flags.reachable && (
            <span className="inline-flex items-center gap-1 rounded-full bg-green-500/10 px-3 py-1 text-xs font-medium text-green-500">
              Reachable
            </span>
          )}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-lg bg-muted/50 p-2 text-center">
            <p className="text-xs text-muted-foreground">Peers</p>
            <p className="text-sm font-semibold">{active_peers}</p>
          </div>
          <div className="rounded-lg bg-muted/50 p-2 text-center">
            <p className="text-xs text-muted-foreground">Tunnels</p>
            <p className="text-sm font-semibold">{tunnels.total}</p>
          </div>
          <div className="rounded-lg bg-muted/50 p-2 text-center">
            <p className="text-xs text-muted-foreground">Routers Known</p>
            <p className="text-sm font-semibold">{network.routers_known}</p>
          </div>
          <div className="rounded-lg bg-muted/50 p-2 text-center">
            <p className="text-xs text-muted-foreground">Success Rate</p>
            <p className="text-sm font-semibold">{network.tunnel_success_rate_pct}%</p>
          </div>
        </div>

        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>In: {formatBps(bandwidth.inbound_kbps * 1000)}</span>
          <span>Out: {formatBps(bandwidth.outbound_kbps * 1000)}</span>
        </div>

        <div className="text-xs text-muted-foreground text-center">
          {network.status}
        </div>
      </CardContent>
    </Card>
  );
}
