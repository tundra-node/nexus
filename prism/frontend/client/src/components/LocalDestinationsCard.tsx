import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Globe, ChevronRight, ArrowRight, AlertCircle } from "lucide-react";

interface LocalDestinationsCardProps {
  destinations: { name: string; b32: string }[];
  error?: string | null;
}

export default function LocalDestinationsCard({ destinations, error }: LocalDestinationsCardProps) {
  if (error) {
    return (
      <Card className="border-destructive/50 bg-destructive/5">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <AlertCircle className="h-5 w-5 text-destructive" />
            Local Destinations Error
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-destructive">{error}</p>
        </CardContent>
      </Card>
    );
  }

  if (destinations.length === 0) return null;

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2">
          <Globe className="h-5 w-5" />
          Local Destinations
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {destinations.map((d) => (
          <div key={d.b32} className="rounded-lg border border-border p-2">
            <div className="flex items-center gap-1.5 text-sm font-medium">
              <ArrowRight className="h-3 w-3 text-muted-foreground" />
              {d.name}
            </div>
            <Collapsible>
              <CollapsibleTrigger className="mt-0.5 flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground [&[data-state=open]>svg]:rotate-90">
                <ChevronRight className="h-3 w-3 transition-transform" />
                Show address
              </CollapsibleTrigger>
              <CollapsibleContent className="mt-1">
                <code className="block truncate rounded bg-muted p-1 text-[10px] font-mono">
                  {d.b32}.b32.i2p
                </code>
              </CollapsibleContent>
            </Collapsible>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
