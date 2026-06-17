import { useEffect, useState, useCallback } from "react";
import { useI2pdStatus, useI2pdBandwidth, useI2pdTunnels, useI2pdRouterInfo, useI2pdRouterDetails, useTransports, useLocalDestinations, useI2pdRouterHealth, setBandwidth, useEepsite } from "@/hooks/useI2pdApi";
import StatusCard from "@/components/StatusCard";
import BandwidthCard from "@/components/BandwidthCard";
import TunnelManager from "@/components/TunnelManager";
import RouterInfo from "@/components/RouterInfo";
import RouterIdentityCard from "@/components/RouterIdentityCard";
import ContributionCard from "@/components/ContributionCard";
import RouterHealthCard from "@/components/RouterHealthCard";
import TransportsCard from "@/components/TransportsCard";
import LocalDestinationsCard from "@/components/LocalDestinationsCard";
import ServicesCard from "@/components/ServicesCard";
import EepsiteCard from "@/components/EepsiteCard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import SettingsSheet from "@/components/SettingsSheet";
import { RefreshCw, Wifi, WifiOff } from "lucide-react";
import { toast } from "sonner";

const BW_LETTERS: { letter: string; kbps: number; label: string }[] = [
  { letter: "K", kbps: 16, label: "Minimal" },
  { letter: "L", kbps: 32, label: "Low" },
  { letter: "M", kbps: 64, label: "Medium" },
  { letter: "N", kbps: 128, label: "Normal" },
  { letter: "O", kbps: 256, label: "High" },
  { letter: "P", kbps: 512, label: "Paranoid" },
  { letter: "X", kbps: 1024, label: "Extreme" },
];

function kbpsToLetter(kbps: number): string {
  const entry = BW_LETTERS.reduce((prev, curr) =>
    Math.abs(curr.kbps - kbps) < Math.abs(prev.kbps - kbps) ? curr : prev
  );
  return entry.letter;
}

function letterToKbps(letter: string): number {
  return BW_LETTERS.find(l => l.letter === letter)?.kbps ?? 64;
}

/**
 * Prism Dashboard
 * 
 * Design Philosophy: Minimalist Dark Mode
 * - Clean, spacious layout with clear visual hierarchy
 * - Dark background with subtle card elevation
 * - Real-time data polling (5-second intervals)
 * - Smooth animations and transitions
 * - Responsive grid layout for all screen sizes
 */
export default function Home() {
  const POLL_INTERVAL = 1000; // 1 second

  // Fetch data from backend API
  const status = useI2pdStatus(POLL_INTERVAL);
  const bandwidth = useI2pdBandwidth(POLL_INTERVAL);
  const tunnels = useI2pdTunnels(POLL_INTERVAL);
  const routerInfo = useI2pdRouterInfo();
  const routerDetails = useI2pdRouterDetails();
  const transports = useTransports();
  const localDests = useLocalDestinations();
  const routerHealth = useI2pdRouterHealth(POLL_INTERVAL);
  const eepsite = useEepsite();

  const [bwLetter, setBwLetter] = useState(() => localStorage.getItem("bwLetter") || "M");
  const [autoBw, setAutoBw] = useState(() => localStorage.getItem("autoBw") === "true");
  const [isRefreshing, setIsRefreshing] = useState(false);

  const applyBandwidth = useCallback(async (letter: string) => {
    const kbps = letterToKbps(letter);
    try {
      await setBandwidth(kbps, kbps);
    } catch {
      toast.error("Failed to set bandwidth");
    }
  }, []);

  const getWifiBandwidthLetter = useCallback((): string => {
    if (typeof navigator === "undefined" || !("connection" in navigator)) return "M";
    const conn = (navigator as any).connection;
    if (!conn) return "M";
    const map: Record<string, string> = {
      "slow-2g": "K",
      "2g": "L",
      "3g": "N",
      "4g": "P",
    };
    return map[conn.effectiveType] || "M";
  }, []);

  const handleAutoToggle = useCallback(async () => {
    const next = !autoBw;
    setAutoBw(next);
    localStorage.setItem("autoBw", String(next));
    if (next) {
      const letter = getWifiBandwidthLetter();
      setBwLetter(letter);
      localStorage.setItem("bwLetter", letter);
      await applyBandwidth(letter);
    }
  }, [autoBw, getWifiBandwidthLetter, applyBandwidth]);

  useEffect(() => {
    if (!autoBw) return;
    const conn = typeof navigator !== "undefined" ? (navigator as any).connection : null;
    if (!conn) return;
    const handler = () => {
      const letter = getWifiBandwidthLetter();
      setBwLetter(letter);
      localStorage.setItem("bwLetter", letter);
      applyBandwidth(letter);
    };
    conn.addEventListener("change", handler);
    return () => conn.removeEventListener("change", handler);
  }, [autoBw, getWifiBandwidthLetter, applyBandwidth]);

  // Apply auto on mount if enabled
  useEffect(() => {
    if (autoBw) {
      const letter = getWifiBandwidthLetter();
      setBwLetter(letter);
      localStorage.setItem("bwLetter", letter);
    }
  }, []); // intentional: only on mount

  const handleManualRefresh = async () => {
    setIsRefreshing(true);
    try {
      await Promise.all([
        status.refetch(),
        bandwidth.refetch(),
        tunnels.refetch(),
        routerInfo.refetch(),
        routerDetails.refetch(),
        routerHealth.refetch(),
        eepsite.refetch(),
      ]);
      toast.success("Data refreshed successfully");
    } catch (err) {
      toast.error("Failed to refresh data");
    } finally {
      setIsRefreshing(false);
    }
  };

  // Check for connection errors
  useEffect(() => {
    if (status.error && !status.data) {
      toast.error("Unable to connect to backend API. Make sure it's running on http://localhost:8000");
    }
  }, [status.error, status.data]);

  return (
    <div className="min-h-screen bg-background text-foreground">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-border/40 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60">
        <div className="container mx-auto px-4 py-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold tracking-tight">Prism</h1>
              <p className="text-sm text-muted-foreground">I2P All-in-One</p>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={handleManualRefresh}
                disabled={isRefreshing}
                className="gap-2"
              >
                <RefreshCw className={`h-4 w-4 ${isRefreshing ? "animate-spin" : ""}`} />
                {isRefreshing ? "Refreshing..." : "Refresh"}
              </Button>
              <SettingsSheet />
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-8 sm:px-6 lg:px-8">
        <div className="space-y-6">
          {/* Status Overview */}
          <section>
            <div className="mb-4">
              <h2 className="text-lg font-semibold">Overview</h2>
              <p className="text-sm text-muted-foreground">Real-time router status and statistics</p>
            </div>
            {status.data ? (
              <StatusCard
                uptime={status.data.uptime}
                active_peers={status.data.active_peers}
                tunnel_count={status.data.tunnel_count}
                tunnels_in={status.data.tunnels_in}
                tunnels_out={status.data.tunnels_out}
                status={status.data.status}
                loading={status.loading}
                error={status.error}
              />
            ) : (
              <div className="rounded-lg border border-dashed border-muted-foreground/25 py-12 text-center">
                <p className="text-sm text-muted-foreground">Loading status...</p>
              </div>
            )}
          </section>

          {/* Network Activity */}
          <section>
            <div className="mb-4">
              <h2 className="text-lg font-semibold">Network Activity</h2>
              <p className="text-sm text-muted-foreground">Current bandwidth usage</p>
            </div>
            <div className="grid gap-6 lg:grid-cols-2">
              <div>
                {bandwidth.data ? (
                  <BandwidthCard
                    inbound_rate={bandwidth.data.inbound_rate}
                    outbound_rate={bandwidth.data.outbound_rate}
                    total_inbound={bandwidth.data.total_inbound}
                    total_outbound={bandwidth.data.total_outbound}
                    loading={bandwidth.loading}
                    error={bandwidth.error}
                  />
                ) : (
                  <div className="rounded-lg border border-dashed border-muted-foreground/25 py-12 text-center">
                    <p className="text-sm text-muted-foreground">Loading bandwidth data...</p>
                  </div>
                )}
              </div>

              <Card>
                <CardHeader className="pb-2">
                  <CardTitle className="flex items-center justify-between text-sm">
                    <span>Bandwidth Limits</span>
                    <Button
                      variant={autoBw ? "default" : "outline"}
                      size="sm"
                      className="h-7 gap-1 text-[10px]"
                      onClick={handleAutoToggle}
                    >
                      {autoBw ? <Wifi className="h-3 w-3" /> : <WifiOff className="h-3 w-3" />}
                      {autoBw ? "Auto" : "Manual"}
                    </Button>
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex flex-wrap gap-1.5 justify-center">
                    {BW_LETTERS.map(({ letter, kbps, label }) => (
                      <button
                        key={letter}
                        disabled={autoBw}
                        onClick={() => {
                          setBwLetter(letter);
                          localStorage.setItem("bwLetter", letter);
                          applyBandwidth(letter);
                        }}
                        className={`flex flex-col items-center rounded-lg border px-2.5 py-1.5 text-[10px] transition-colors min-w-[44px] ${
                          bwLetter === letter && !autoBw
                            ? "border-primary bg-primary/10 text-primary font-semibold"
                            : autoBw
                              ? "border-muted text-muted-foreground cursor-not-allowed opacity-50"
                              : "border-border text-muted-foreground hover:border-primary/50 hover:text-foreground"
                        }`}
                        title={`${label} — ${kbps} KB/s`}
                      >
                        <span className="text-sm font-bold">{letter}</span>
                        <span className="text-[8px]">{kbps}</span>
                      </button>
                    ))}
                  </div>
                  <div className="text-center text-[10px] text-muted-foreground">
                    Current: <span className="font-semibold text-foreground">{bwLetter}</span> ({letterToKbps(bwLetter)} KB/s)
                  </div>
                </CardContent>
              </Card>
            </div>
          </section>

          {/* Router Info */}
          <section>
            <div className="mb-4">
              <h2 className="text-lg font-semibold">Info</h2>
              <p className="text-sm text-muted-foreground">Router details</p>
            </div>
            {routerDetails.data ? (
              <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
                <RouterInfo
                  version={routerInfo.data?.version ?? ""}
                  identity={routerInfo.data?.identity ?? ""}
                  uptime={routerInfo.data?.uptime ?? 0}
                  net_id={routerInfo.data?.net_id ?? 2}
                  loading={routerInfo.loading}
                  error={routerInfo.error}
                />
                <RouterHealthCard
                  score={routerHealth.data?.health_score ?? 0}
                  status={routerHealth.data?.status ?? "unknown"}
                  active_peers={routerHealth.data?.active_peers ?? 0}
                  tunnels={routerHealth.data?.tunnels ?? { inbound: 0, outbound: 0, total: 0 }}
                  bandwidth={routerHealth.data?.bandwidth ?? { inbound_kbps: 0, outbound_kbps: 0 }}
                  network={routerHealth.data?.network ?? { status: "unknown", routers_known: 0, floodfills: 0, leasesets: 0, tunnel_success_rate_pct: 0 }}
                  flags={routerHealth.data?.flags ?? { floodfill: false, reachable: false }}
                  loading={routerHealth.loading}
                  error={routerHealth.error}
                />
                <ContributionCard
                  transit={routerDetails.data.transit}
                  received={routerDetails.data.received}
                  sent={routerDetails.data.sent}
                  uptime={routerDetails.data.uptime}
                  transit_tunnels={routerDetails.data.transit_tunnels}
                  routers={routerDetails.data.routers}
                  floodfills={routerDetails.data.floodfills}
                  tunnel_success_rate={routerDetails.data.tunnel_success_rate}
                  error={routerDetails.error}
                />
                {transports.data.length > 0 && (
                  <TransportsCard transports={transports.data} />
                )}
                {localDests.data.length > 0 && (
                  <LocalDestinationsCard destinations={localDests.data} />
                )}
                {eepsite.tunnels.length > 0 && (
                  <EepsiteCard tunnels={eepsite.tunnels} />
                )}
                <RouterIdentityCard
                  identity={routerDetails.data.identity}
                  caps={routerDetails.data.caps}
                  external_address={routerDetails.data.external_address}
                  routers={routerDetails.data.routers}
                  floodfills={routerDetails.data.floodfills}
                  leasesets={routerDetails.data.leasesets}
                  client_tunnels={routerDetails.data.client_tunnels}
                  transit_tunnels={routerDetails.data.transit_tunnels}
                  network_status={routerDetails.data.network_status}
                  loading={routerDetails.loading}
                  error={routerDetails.error}
                />
                <ServicesCard services={routerDetails.data.services} error={routerDetails.error} />
              </div>
            ) : (
              <>
                {routerInfo.data ? (
                  <RouterInfo
                    version={routerInfo.data.version}
                    identity={routerInfo.data.identity}
                    uptime={routerInfo.data.uptime}
                    net_id={routerInfo.data.net_id}
                    loading={routerInfo.loading}
                    error={routerInfo.error}
                  />
                ) : (
                  <div className="rounded-lg border border-dashed border-muted-foreground/25 py-12 text-center">
                    <p className="text-sm text-muted-foreground">Loading router info...</p>
                  </div>
                )}
              </>
            )}
          </section>

          {/* Tunnel Manager */}
          <section>
            <div className="mb-4">
              <h2 className="text-lg font-semibold">Tunnels</h2>
              <p className="text-sm text-muted-foreground">Manage active I2P tunnels</p>
            </div>
            {tunnels.data ? (
              <TunnelManager
                tunnels={tunnels.data.tunnels}
                loading={tunnels.loading}
                error={tunnels.error}
              />
            ) : (
              <div className="rounded-lg border border-dashed border-muted-foreground/25 py-12 text-center">
                <p className="text-sm text-muted-foreground">Loading tunnels...</p>
              </div>
            )}
          </section>
        </div>
      </main>

      {/* Footer */}
      <footer className="border-t border-border/40 bg-muted/30 py-6 text-center text-sm text-muted-foreground">
        <p>Prism • Auto-refresh every 1 second</p>
      </footer>
    </div>
  );
}
