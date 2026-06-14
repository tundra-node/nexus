import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Heart, ArrowRightLeft, AlertCircle } from "lucide-react";

interface ContributionCardProps {
  transit: string;
  received: string;
  sent: string;
  uptime: string;
  transit_tunnels: number;
  routers: number;
  floodfills: number;
  tunnel_success_rate: number;
  error?: string | null;
}

function parseBytes(str: string): number {
  const m = str.match(/^([\d.]+)\s*([KMGT]?)i?B/i);
  if (!m) return 0;
  const v = parseFloat(m[1]);
  const u = (m[2] || "B").toUpperCase();
  if (u === "K") return v * 1024;
  if (u === "M") return v * 1024 * 1024;
  if (u === "G") return v * 1024 * 1024 * 1024;
  if (u === "T") return v * 1024 * 1024 * 1024 * 1024;
  return v;
}

function formatBytes(bytes: number): string {
  if (!bytes || bytes <= 0 || !isFinite(bytes)) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.max(0, Math.min(Math.floor(Math.log(bytes) / Math.log(k)), sizes.length - 1));
  return (bytes / Math.pow(k, i)).toFixed(1) + " " + sizes[i];
}

function percentOfTotal(part: string, totalBytes: number): number {
  const pb = parseBytes(part);
  if (totalBytes <= 0) return 0;
  return (pb / totalBytes) * 100;
}

export default function ContributionCard({
  transit,
  received,
  sent,
  uptime,
  transit_tunnels,
  routers,
  floodfills,
  tunnel_success_rate,
  error = null,
}: ContributionCardProps) {
  const transitB = parseBytes(transit);
  const receivedB = parseBytes(received);
  const sentB = parseBytes(sent);
  const totalB = receivedB + sentB;

  const transitPct = percentOfTotal(transit, totalB);

  if (error) {
    return (
      <Card className="border-destructive/50 bg-destructive/5">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-destructive" />
            Contribution Error
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-destructive">{error}</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2">
          <Heart className="h-5 w-5 text-rose-500" />
          Network Contribution
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="rounded-lg bg-rose-500/10 p-3 text-center">
          <p className="text-xs text-muted-foreground">Data Transited for Others</p>
          <p className="text-2xl font-bold text-rose-500">{formatBytes(transitB)}</p>
          {totalB > 0 && (
            <p className="text-xs text-muted-foreground">
              {transitPct.toFixed(1)}% of total traffic
            </p>
          )}
        </div>

        <div className="grid grid-cols-2 gap-3 text-center">
          <div className="rounded-lg bg-muted/50 p-2">
            <p className="text-xs text-muted-foreground">Received</p>
            <p className="text-sm font-semibold">{formatBytes(receivedB)}</p>
          </div>
          <div className="rounded-lg bg-muted/50 p-2">
            <p className="text-xs text-muted-foreground">Sent</p>
            <p className="text-sm font-semibold">{formatBytes(sentB)}</p>
          </div>
        </div>

        <div className="flex items-center justify-center gap-3 rounded-lg bg-muted/50 p-2">
          <div className="flex items-center gap-1.5">
            <ArrowRightLeft className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm">
              <strong>{transit_tunnels}</strong> transit tunnel{transit_tunnels !== 1 ? "s" : ""}
            </span>
          </div>
          <span className="text-xs text-muted-foreground">|</span>
          <div className="text-xs">
            <span className="text-muted-foreground">Transited: </span>
            <span className="font-semibold">{formatBytes(transitB)}</span>
          </div>
        </div>

        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>Uptime: {uptime}</span>
          <span>Success: {tunnel_success_rate}%</span>
        </div>

        <div className="flex items-center justify-between text-xs text-muted-foreground">
          <span>{routers} routers</span>
          <span>{floodfills} floodfills</span>
        </div>
      </CardContent>
    </Card>
  );
}
