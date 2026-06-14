import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { AlertCircle, Fingerprint, Globe, Server, Wifi, Shield, ChevronRight } from "lucide-react";

interface RouterIdentityCardProps {
  identity: string;
  caps: string;
  external_address: string;
  routers: number;
  floodfills: number;
  leasesets: number;
  client_tunnels: number;
  transit_tunnels: number;
  network_status: string;
  loading?: boolean;
  error?: string | null;
}

export default function RouterIdentityCard({
  identity,
  caps,
  external_address,
  routers,
  floodfills,
  leasesets,
  client_tunnels,
  transit_tunnels,
  network_status,
  loading = false,
  error = null,
}: RouterIdentityCardProps) {
  const isFirewalled = network_status.toLowerCase().includes("firewalled");

  if (error) {
    return (
      <Card className="border-destructive/50 bg-destructive/5">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-destructive" />
            Network Info Error
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
        <div className="flex items-center justify-between">
          <CardTitle className="flex items-center gap-2">
            <Globe className="h-5 w-5" />
            Network
          </CardTitle>
          {loading && <Spinner className="h-4 w-4" />}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex items-center gap-2">
          <Shield className={`h-4 w-4 ${isFirewalled ? "text-yellow-500" : "text-green-500"}`} />
          <span className="text-sm">
            Network: <span className={isFirewalled ? "text-yellow-500 font-medium" : "text-green-500 font-medium"}>{network_status}</span>
          </span>
        </div>

        <div className="flex items-center gap-2">
          <Server className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm text-muted-foreground">Caps:</span>
          <code className="text-xs font-mono">{caps}</code>
        </div>

        <div className="flex items-center gap-2">
          <Wifi className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm text-muted-foreground">External:</span>
          <span className="text-xs font-mono">{external_address}</span>
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div className="rounded-lg bg-muted/50 p-2 text-center">
            <p className="text-xs text-muted-foreground">Routers</p>
            <p className="text-lg font-semibold">{routers}</p>
          </div>
          <div className="rounded-lg bg-muted/50 p-2 text-center">
            <p className="text-xs text-muted-foreground">Floodfills</p>
            <p className="text-lg font-semibold">{floodfills}</p>
          </div>
          <div className="rounded-lg bg-muted/50 p-2 text-center">
            <p className="text-xs text-muted-foreground">LeaseSets</p>
            <p className="text-lg font-semibold">{leasesets}</p>
          </div>
          <div className="rounded-lg bg-muted/50 p-2 text-center">
            <p className="text-xs text-muted-foreground">Transit</p>
            <p className="text-lg font-semibold">{transit_tunnels}</p>
          </div>
        </div>

        <Collapsible>
          <CollapsibleTrigger className="flex w-full items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground [&[data-state=open]>svg]:rotate-90">
            <ChevronRight className="h-3 w-3 transition-transform" />
            Router Identity
          </CollapsibleTrigger>
          <CollapsibleContent className="mt-1">
            <code className="block truncate rounded bg-muted p-1.5 text-[10px] font-mono">{identity}</code>
          </CollapsibleContent>
        </Collapsible>
      </CardContent>
    </Card>
  );
}
