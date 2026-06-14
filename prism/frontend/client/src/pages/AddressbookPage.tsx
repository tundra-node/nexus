import { useState, useEffect } from "react";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";
import {
  getAddressSubscriptions,
  addAddressSubscription,
  removeAddressSubscription,
  type AddressSubscription,
} from "@/hooks/useI2pdApi";
import { toast } from "sonner";
import { Plus, Trash2, RefreshCw, BookmarkIcon } from "lucide-react";

export default function AddressbookPage() {
  const [subs, setSubs] = useState<AddressSubscription[]>([]);
  const [loading, setLoading] = useState(true);
  const [newUrl, setNewUrl] = useState("");
  const [adding, setAdding] = useState(false);

  const fetch = async () => {
    setLoading(true);
    try {
      const data = await getAddressSubscriptions();
      setSubs(data);
    } catch {
      toast.error("Failed to load addressbook");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetch();
  }, []);

  const handleAdd = async () => {
    if (!newUrl.trim()) return;
    setAdding(true);
    try {
      await addAddressSubscription(newUrl.trim());
      toast.success("Subscription added");
      setNewUrl("");
      await fetch();
    } catch {
      toast.error("Failed to add subscription");
    } finally {
      setAdding(false);
    }
  };

  const handleRemove = async (url: string) => {
    try {
      await removeAddressSubscription(url);
      toast.success("Subscription removed");
      await fetch();
    } catch {
      toast.error("Failed to remove subscription");
    }
  };

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold tracking-tight">Addressbook</h1>
          <p className="text-sm text-muted-foreground">
            Manage i2pd addressbook subscriptions
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetch} disabled={loading} className="gap-2">
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Add subscription */}
      <Card>
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm">
            <Plus className="h-4 w-4 text-green-500" />
            Add Subscription
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <p className="mb-1 text-xs text-muted-foreground">Subscription URL</p>
              <Input
                value={newUrl}
                onChange={(e) => setNewUrl(e.target.value)}
                placeholder="http://stats.i2p/addressbook"
                className="h-8 font-mono text-xs"
                onKeyDown={(e) => e.key === "Enter" && handleAdd()}
              />
            </div>
            <Button onClick={handleAdd} disabled={adding || !newUrl.trim()} size="sm">
              {adding ? <Spinner className="mr-1 h-3 w-3" /> : null}
              Add
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Subscription list */}
      <Card className="flex-1">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-sm">
            <BookmarkIcon className="h-4 w-4 text-primary" />
            Subscriptions
            {loading && <Spinner className="h-3 w-3" />}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {subs.length === 0 && !loading && (
            <p className="py-4 text-center text-xs text-muted-foreground">
              No subscriptions yet. Add one above.
            </p>
          )}
          <div className="space-y-1">
            {subs.map((s, i) => (
              <div
                key={i}
                className="flex items-center gap-2 rounded-lg border border-border p-2"
              >
                <div className="min-w-0 flex-1">
                  <p className="truncate text-xs font-medium">{s.name}</p>
                  <code className="truncate text-[10px] text-muted-foreground">{s.url}</code>
                </div>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 flex-shrink-0"
                  onClick={() => handleRemove(s.url)}
                >
                  <Trash2 className="h-3 w-3 text-destructive" />
                </Button>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
