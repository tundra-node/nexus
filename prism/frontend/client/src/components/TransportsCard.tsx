import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Radio, AlertCircle } from "lucide-react";
import type { TransportInfo } from "@/hooks/useI2pdApi";

interface TransportsCardProps {
  transports: TransportInfo[];
  error?: string | null;
}

export default function TransportsCard({ transports, error }: TransportsCardProps) {
  if (error) {
    return (
      <Card className="border-destructive/50 bg-destructive/5">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-destructive" />
            Transports Error
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-destructive">{error}</p>
        </CardContent>
      </Card>
    );
  }

  if (transports.length === 0) return null;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2">
          <Radio className="h-5 w-5" />
          Transports
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-2">
          {transports.map((t) => (
            <div
              key={t.name}
              className="flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-xs font-medium"
            >
              <div className="h-1.5 w-1.5 rounded-full bg-green-500" />
              {t.name}
              <span className="text-muted-foreground">({t.peers})</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
