import { useEffect, useState, useRef } from "react";
import axios from "axios";

const API_BASE_URL = import.meta.env.VITE_API_URL || "";
const API_KEY = import.meta.env.VITE_API_KEY || "your-secure-api-key-here";

const COMMON_TLDS = new Set([
  "com", "org", "net", "gov", "edu", "mil",
  "io", "co", "uk", "de", "fr", "ru", "jp", "cn", "br", "au", "ca", "us", "eu",
  "app", "dev", "tech", "info", "me", "tv", "cc", "biz", "pro", "name", "ai",
  "in", "to", "xyz", "online", "site", "top", "shop", "blog", "wiki",
]);

/** Normalize a user-typed URL: prepend http://, append .i2p unless it's a known real-world TLD */
export function normalizeUrl(input: string): string {
  let target = input.trim();
  if (!target) return "";
  if (!target.startsWith("http://") && !target.startsWith("https://")) {
    target = "http://" + target;
  }
  try {
    const parsed = new URL(target);
    const host = parsed.hostname;
    // Already has .i2p → leave it
    if (host.endsWith(".i2p")) return target;
    // Ends with a known real-world TLD → leave it
    const lastDot = host.lastIndexOf(".");
    if (lastDot !== -1) {
      const tld = host.slice(lastDot + 1).toLowerCase();
      if (COMMON_TLDS.has(tld)) return target;
    }
    // Otherwise append .i2p
    parsed.hostname = host + ".i2p";
    target = parsed.toString();
  } catch {
    // If URL parsing fails, return as-is
  }
  return target;
}

interface StatusData {
  uptime: number;
  active_peers: number;
  tunnel_count: number;
  tunnels_in: number;
  tunnels_out: number;
  status: string;
}

interface BandwidthData {
  inbound_rate: number;
  outbound_rate: number;
  total_inbound: number;
  total_outbound: number;
}

interface TunnelInfo {
  id: string;
  state: string;
  direction: string;
  peers: number;
  created: number;
}

interface TunnelEntry {
  id: string;
  state: string;
  direction: string;
  latency_ms: number;
  data_kib: number;
}

interface TunnelsData {
  tunnels: TunnelEntry[];
  total: number;
}

interface RouterInfoData {
  version: string;
  identity: string;
  uptime: number;
  net_id: number;
}

interface RouterDetailsData {
  identity: string;
  caps: string;
  version: string;
  external_address: string;
  routers: number;
  floodfills: number;
  leasesets: number;
  client_tunnels: number;
  transit_tunnels: number;
  network_status: string;
  tunnel_success_rate: number;
  uptime: string;
  received: string;
  sent: string;
  transit: string;
  services: Record<string, string>;
}

// Create axios instance with default headers
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "x-api-key": API_KEY,
    "Content-Type": "application/json",
  },
});

export function useI2pdStatus(pollInterval: number = 5000) {
  const [data, setData] = useState<StatusData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchStatus = async () => {
    try {
      const response = await apiClient.get<StatusData>("/api/status");
      setData(response.data);
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to fetch status";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    intervalRef.current = setInterval(fetchStatus, pollInterval);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [pollInterval]);

  return { data, loading, error, refetch: fetchStatus };
}

export function useI2pdBandwidth(pollInterval: number = 5000) {
  const [data, setData] = useState<BandwidthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchBandwidth = async () => {
    try {
      const response = await apiClient.get<BandwidthData>("/api/bandwidth");
      setData(response.data);
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to fetch bandwidth";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBandwidth();
    intervalRef.current = setInterval(fetchBandwidth, pollInterval);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [pollInterval]);

  return { data, loading, error, refetch: fetchBandwidth };
}

export function useI2pdTunnels(pollInterval: number = 5000) {
  const [data, setData] = useState<TunnelsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetchTunnels = async () => {
    try {
      const response = await apiClient.get<TunnelsData>("/api/tunnels");
      setData(response.data);
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to fetch tunnels";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTunnels();
    intervalRef.current = setInterval(fetchTunnels, pollInterval);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [pollInterval]);

  return { data, loading, error, refetch: fetchTunnels };
}

export function useI2pdRouterInfo() {
  const [data, setData] = useState<RouterInfoData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchRouterInfo = async () => {
    try {
      const response = await apiClient.get<RouterInfoData>("/api/router-info");
      setData(response.data);
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to fetch router info";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchRouterInfo();
  }, []);

  return { data, loading, error, refetch: fetchRouterInfo };
}

export function useI2pdRouterDetails() {
  const [data, setData] = useState<RouterDetailsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetch = async () => {
    try {
      const response = await apiClient.get<RouterDetailsData>("/api/router-details");
      setData(response.data);
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to fetch router details";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetch();
  }, []);

  return { data, loading, error, refetch: fetch };
}

export interface RouterHealthData {
  status: string;
  health_score: number;
  uptime_seconds: number;
  active_peers: number;
  tunnels: { inbound: number; outbound: number; total: number };
  bandwidth: { inbound_kbps: number; outbound_kbps: number };
  network: {
    status: string;
    routers_known: number;
    floodfills: number;
    leasesets: number;
    tunnel_success_rate_pct: number;
  };
  flags: { floodfill: boolean; reachable: boolean };
}

export function useI2pdRouterHealth(pollInterval: number = 5000) {
  const [data, setData] = useState<RouterHealthData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const fetch = async () => {
    try {
      const response = await apiClient.get<RouterHealthData>("/api/router-health");
      setData(response.data);
      setError(null);
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to fetch router health";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetch();
    intervalRef.current = setInterval(fetch, pollInterval);
    return () => { if (intervalRef.current) clearInterval(intervalRef.current); };
  }, [pollInterval]);

  return { data, loading, error, refetch: fetch };
}

export async function runCommand(cmdId: string) {
  const response = await apiClient.post(`/api/command/${cmdId}`);
  return response.data;
}

export interface CommandInfo {
  id: string;
  label: string;
}

export function useCommands() {
  const [commands, setCommands] = useState<CommandInfo[]>([]);
  const [loading, setLoading] = useState(true);

  const fetch = async () => {
    try {
      const response = await apiClient.get<{ commands: CommandInfo[] }>("/api/commands");
      setCommands(response.data.commands);
    } catch {
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetch();
  }, []);

  return { commands, loading, refetch: fetch };
}

export interface TransportInfo {
  name: string;
  peers: number;
}

export function useTransports() {
  const [data, setData] = useState<TransportInfo[]>([]);
  const [loading, setLoading] = useState(true);

  const fetch = async () => {
    try {
      const r = await apiClient.get<{ transports: TransportInfo[] }>("/api/transports");
      setData(r.data.transports);
    } catch {
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetch();
  }, []);

  return { data, loading, refetch: fetch };
}

export function useLocalDestinations() {
  const [data, setData] = useState<{ name: string; b32: string }[]>([]);
  const [loading, setLoading] = useState(true);

  const fetch = async () => {
    try {
      const r = await apiClient.get<{ destinations: { name: string; b32: string }[] }>("/api/local-destinations");
      setData(r.data.destinations);
    } catch {
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetch();
  }, []);

  return { data, loading, refetch: fetch };
}

// ---------------------------------------------------------------------------
// Browser (proxy + bookmarks)
// ---------------------------------------------------------------------------

export interface Bookmark {
  name: string;
  url: string;
}

export function useBookmarks() {
  const [bookmarks, setBookmarks] = useState<Bookmark[]>([]);
  const [loading, setLoading] = useState(true);

  const fetch = async () => {
    try {
      const r = await apiClient.get<{ bookmarks: Bookmark[] }>("/api/browser/bookmarks");
      setBookmarks(r.data.bookmarks);
    } catch {
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetch();
  }, []);

  return { bookmarks, loading, refetch: fetch };
}

export async function saveBookmarks(bookmarks: Bookmark[]) {
  await apiClient.post("/api/browser/bookmarks", bookmarks);
}

export function proxyUrl(url: string): string {
  return `${API_BASE_URL}/api/browser/proxy?url=${encodeURIComponent(url)}&api_key=${encodeURIComponent(API_KEY)}`;
}

// ---------------------------------------------------------------------------
// Bandwidth control
// ---------------------------------------------------------------------------

export async function setBandwidth(inbound?: number, outbound?: number) {
  const r = await apiClient.post("/api/bandwidth/set", { inbound, outbound });
  return r.data;
}

// ---------------------------------------------------------------------------
// Addressbook
// ---------------------------------------------------------------------------

export interface AddressSubscription {
  url: string;
  name: string;
}

export async function getAddressSubscriptions() {
  const r = await apiClient.get<{ subscriptions: AddressSubscription[] }>("/api/addressbook/subscriptions");
  return r.data.subscriptions;
}

export async function addAddressSubscription(url: string) {
  await apiClient.post("/api/addressbook/subscriptions", { url });
}

export async function removeAddressSubscription(url: string) {
  await apiClient.delete("/api/addressbook/subscriptions", { params: { url } });
}


