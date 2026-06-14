import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import { AlertCircle, Info } from "lucide-react";

interface RouterInfoProps {
  version: string;
  identity: string;
  uptime: number;
  net_id: number;
  loading?: boolean;
  error?: string | null;
}

function formatIdentity(identity: string): string {
  if (identity.length > 20) {
    return identity.substring(0, 10) + "..." + identity.substring(identity.length - 10);
  }
  return identity;
}

export default function RouterInfo({
  version,
  identity,
  uptime,
  net_id,
  loading = false,
  error = null,
}: RouterInfoProps) {
  if (error) {
    return (
      <Card className="border-destructive/50 bg-destructive/5">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-destructive" />
            Router Info Error
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
            <Info className="h-5 w-5" />
            Router Information
          </CardTitle>
          {loading && <Spinner className="h-4 w-4" />}
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1">
          <p className="text-xs font-medium text-muted-foreground">Version</p>
          <p className="font-mono text-sm font-semibold">{version || "Unknown"}</p>
        </div>

        <div className="space-y-1">
          <p className="text-xs font-medium text-muted-foreground">Identity</p>
          <code className="block break-all rounded-md bg-muted p-2 text-xs font-mono">
            {formatIdentity(identity) || "Unknown"}
          </code>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">Network ID</p>
            <p className="font-semibold">{net_id}</p>
          </div>
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">Uptime</p>
            <p className="font-semibold">{Math.floor(uptime / 86400)} days</p>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
