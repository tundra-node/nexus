import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AlertCircle, Package } from "lucide-react";

interface ServicesCardProps {
  services: Record<string, string>;
  error?: string | null;
}

export default function ServicesCard({ services, error }: ServicesCardProps) {
  if (error) {
    return (
      <Card className="border-destructive/50 bg-destructive/5">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-destructive" />
            Services Error
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-destructive">{error}</p>
        </CardContent>
      </Card>
    );
  }

  const entries = Object.entries(services);
  if (entries.length === 0) {
    return null;
  }

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2">
          <Package className="h-5 w-5" />
          Services
        </CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-2">
          {entries.map(([name, status]) => (
            <div
              key={name}
              className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-xs font-medium ${
                status === "enabled"
                  ? "bg-green-500/10 text-green-700 dark:text-green-400"
                  : "bg-muted text-muted-foreground"
              }`}
            >
              <div
                className={`h-1.5 w-1.5 rounded-full ${
                  status === "enabled" ? "bg-green-500" : "bg-muted-foreground/40"
                }`}
              />
              {name}
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
