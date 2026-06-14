import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { Badge } from "@/components/ui/badge";
import { AlertCircle, GitBranch, Clock, ArrowDown, ArrowUp } from "lucide-react";

interface TunnelEntry {
  id: string;
  state: string;
  direction: string;
  latency_ms: number;
  data_kib: number;
}

interface TunnelManagerProps {
  tunnels: TunnelEntry[];
  loading?: boolean;
  error?: string | null;
}

function formatId(id: string): string {
  return id.length > 12 ? id.substring(0, 12) + "..." : id;
}

function formatData(kib: number): string {
  if (kib >= 1024) return `${(kib / 1024).toFixed(1)}MiB`;
  return `${Math.round(kib)}KiB`;
}

function TunnelSection({ label, icon: Icon, tunnels }: { label: string; icon: any; tunnels: TunnelEntry[] }) {
  return (
    <div>
      <h4 className="mb-2 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
        <Icon className="h-3.5 w-3.5" />
        {label}
        <span className="text-muted-foreground/60">({tunnels.length})</span>
      </h4>
      <div className="space-y-1.5">
        {tunnels.map((t) => (
          <div
            key={t.id}
            className="flex items-center justify-between rounded-lg border border-border bg-card p-2.5 transition-colors hover:bg-muted/50"
          >
            <div className="flex items-center gap-2">
              <code className="text-xs font-mono text-muted-foreground">{formatId(t.id)}</code>
              <Badge variant="outline" className={
                t.direction === "inbound"
                  ? "bg-blue-500/10 text-blue-700 dark:text-blue-400"
                  : "bg-purple-500/10 text-purple-700 dark:text-purple-400"
              }>
                {t.direction === "inbound" ? "In" : "Out"}
              </Badge>
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground">
              <span>{t.latency_ms}ms</span>
              <span>{formatData(t.data_kib)}</span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function TunnelManager({
  tunnels,
  loading = false,
  error = null,
}: TunnelManagerProps) {
  if (error) {
    return (
      <Card className="border-destructive/50 bg-destructive/5">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-destructive" />
            Tunnel Manager Error
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-destructive">{error}</p>
        </CardContent>
      </Card>
    );
  }

  const established = tunnels.filter((t) => t.state === "established" || t.state === "active");
  const expiring = tunnels.filter((t) => t.state === "expiring");
  const building = tunnels.filter((t) => t.state === "building");
  const failed = tunnels.filter((t) => t.state === "failed");

  const establishedIn = established.filter((t) => t.direction === "inbound");
  const establishedOut = established.filter((t) => t.direction !== "inbound");
  const expiringIn = expiring.filter((t) => t.direction === "inbound");
  const expiringOut = expiring.filter((t) => t.direction !== "inbound");

  const latencies = tunnels.filter((t) => t.latency_ms > 0).map((t) => t.latency_ms);
  const min = latencies.length > 0 ? Math.min(...latencies) : 0;
  const max = latencies.length > 0 ? Math.max(...latencies) : 0;
  const avg = latencies.length > 0 ? Math.round(latencies.reduce((a, b) => a + b, 0) / latencies.length) : 0;

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <GitBranch className="h-5 w-5" />
            Tunnels
          </CardTitle>
          {loading && <Spinner className="h-4 w-4" />}
        </div>
      </CardHeader>
      <CardContent>
        {latencies.length > 1 && (
          <div className="mb-4 flex items-center gap-3 text-xs text-muted-foreground">
            <Clock className="h-3.5 w-3.5" />
            <span>min <strong className="text-foreground">{min}ms</strong></span>
            <span>avg <strong className="text-foreground">{avg}ms</strong></span>
            <span>max <strong className="text-foreground">{max}ms</strong></span>
            <span className="text-muted-foreground/60">({latencies.length} tunnels)</span>
          </div>
        )}

        <div className="space-y-4">
          {established.length > 0 && (
            <div>
              <h3 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-green-500">
                <span className="h-2 w-2 rounded-full bg-green-500" />
                Established ({established.length})
              </h3>
              <div className="space-y-2">
                {establishedIn.length > 0 && (
                  <TunnelSection label="Inbound" icon={ArrowDown} tunnels={establishedIn} />
                )}
                {establishedOut.length > 0 && (
                  <TunnelSection label="Outbound" icon={ArrowUp} tunnels={establishedOut} />
                )}
              </div>
            </div>
          )}

          {expiring.length > 0 && (
            <div>
              <h3 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-yellow-500">
                <span className="h-2 w-2 rounded-full bg-yellow-500" />
                Expiring ({expiring.length})
              </h3>
              <div className="space-y-2">
                {expiringIn.length > 0 && (
                  <TunnelSection label="Inbound" icon={ArrowDown} tunnels={expiringIn} />
                )}
                {expiringOut.length > 0 && (
                  <TunnelSection label="Outbound" icon={ArrowUp} tunnels={expiringOut} />
                )}
              </div>
            </div>
          )}

          {building.length > 0 && (
            <div>
              <h3 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-yellow-500">
                <span className="h-2 w-2 rounded-full bg-yellow-500" />
                Building ({building.length})
              </h3>
              <div className="space-y-1.5">
                {building.map((t) => (
                  <div key={t.id} className="rounded-lg border border-border bg-card p-2.5 text-xs text-muted-foreground">
                    {formatId(t.id)}
                  </div>
                ))}
              </div>
            </div>
          )}

          {failed.length > 0 && (
            <div>
              <h3 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-red-500">
                <span className="h-2 w-2 rounded-full bg-red-500" />
                Failed ({failed.length})
              </h3>
              <div className="space-y-1.5">
                {failed.map((t) => (
                  <div key={t.id} className="rounded-lg border border-border bg-card p-2.5 text-xs text-muted-foreground">
                    {formatId(t.id)}
                  </div>
                ))}
              </div>
            </div>
          )}

          {tunnels.length === 0 && (
            <div className="rounded-lg border border-dashed border-muted-foreground/25 py-8 text-center">
              <p className="text-sm text-muted-foreground">No active tunnels</p>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
