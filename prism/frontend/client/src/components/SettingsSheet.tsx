import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import { Settings, Moon, Terminal } from "lucide-react";
import { useTheme } from "@/contexts/ThemeContext";
import { useCommands, runCommand } from "@/hooks/useI2pdApi";
import { toast } from "sonner";
import { useState } from "react";

export default function SettingsSheet() {
  const { theme, toggleTheme } = useTheme();
  const { commands, loading } = useCommands();
  const [runningId, setRunningId] = useState<string | null>(null);

  const handleCommand = async (cmdId: string) => {
    setRunningId(cmdId);
    try {
      const result = await runCommand(cmdId);
      toast.success(result.message || "Command executed");
    } catch {
      toast.error("Command failed");
    } finally {
      setRunningId(null);
    }
  };

  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="ghost" size="icon">
          <Settings className="h-5 w-5" />
        </Button>
      </SheetTrigger>
      <SheetContent side="right">
        <SheetHeader>
          <SheetTitle>Settings</SheetTitle>
        </SheetHeader>
        <div className="mt-6 space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Moon className="h-4 w-4" />
              <Label htmlFor="dark-mode">Dark Mode</Label>
            </div>
            <Switch
              id="dark-mode"
              checked={theme === "dark"}
              onCheckedChange={() => toggleTheme?.()}
            />
          </div>

          <Separator />

          <div>
            <div className="mb-3 flex items-center gap-2">
              <Terminal className="h-4 w-4" />
              <h3 className="text-sm font-medium">Router Commands</h3>
            </div>
            {loading ? (
              <p className="text-xs text-muted-foreground">Loading commands...</p>
            ) : commands.length === 0 ? (
              <p className="text-xs text-muted-foreground">No commands available</p>
            ) : (
              <div className="space-y-2">
                {commands.map((cmd) => (
                  <Button
                    key={cmd.id}
                    variant="outline"
                    size="sm"
                    className="w-full justify-start text-xs"
                    onClick={() => handleCommand(cmd.id)}
                    disabled={runningId !== null}
                  >
                    {runningId === cmd.id ? "Running..." : cmd.label}
                  </Button>
                ))}
              </div>
            )}
          </div>
        </div>
      </SheetContent>
    </Sheet>
  );
}
