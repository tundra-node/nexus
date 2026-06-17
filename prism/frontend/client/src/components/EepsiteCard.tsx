import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { ChevronRight, ExternalLink, Globe } from "lucide-react"
import type { EepsiteTunnel } from "@/hooks/useI2pdApi"

interface EepsiteCardProps {
  tunnels: EepsiteTunnel[]
}

export default function EepsiteCard({ tunnels }: EepsiteCardProps) {
  if (!tunnels.length) return null

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="flex items-center gap-2">
          <Globe className="h-5 w-5 text-cyan-500" />
          Eepsite
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {tunnels.map((t) => (
          <div key={t.name} className="rounded-lg border border-border p-2">
            <div className="flex items-center gap-1.5 text-sm font-medium">
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              {t.name}
              <span className="text-[10px] text-muted-foreground ml-auto">
                {t.host}:{t.port}
              </span>
            </div>
            <Collapsible>
              <CollapsibleTrigger className="mt-0.5 flex items-center gap-1 text-[10px] text-muted-foreground hover:text-foreground [&[data-state=open]>svg]:rotate-90">
                <ChevronRight className="h-3 w-3 transition-transform" />
                Show b32 address
              </CollapsibleTrigger>
              <CollapsibleContent className="mt-1">
                <code className="block truncate rounded bg-muted p-1 text-[10px] font-mono">
                  {t.b32_address}
                </code>
              </CollapsibleContent>
            </Collapsible>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}